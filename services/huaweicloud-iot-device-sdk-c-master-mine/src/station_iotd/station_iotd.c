#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <unistd.h>

#include "cJSON.h"
#include "iota_cfg.h"
#include "iota_datatrans.h"
#include "iota_init.h"
#include "iota_login.h"

#define MAX_LINE_LENGTH 4096
#define MAX_REQUEST_ID 96
#define MAX_PENDING_REPORTS 32

typedef struct {
    char *work_path;
    char *address;
    char *port;
    char *device_id;
    char *secret;
} StationConfig;

typedef struct ReportRequest {
    char id[MAX_REQUEST_ID + 1];
    char station;
    int value;
    struct ReportRequest *next;
} ReportRequest;

static StationConfig g_config;
static volatile sig_atomic_t g_stopping = 0;
static int g_connected = 0;
static int g_connecting = 0;
static int g_pending_count = 0;
static ReportRequest *g_queue_head = NULL;
static ReportRequest *g_queue_tail = NULL;
static ReportRequest *g_in_flight = NULL;
static pthread_mutex_t g_state_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t g_output_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_state_changed = PTHREAD_COND_INITIALIZER;

static void emit_json(cJSON *message)
{
    char *text = cJSON_PrintUnformatted(message);
    if (text == NULL) {
        return;
    }
    pthread_mutex_lock(&g_output_mutex);
    fprintf(stdout, "%s\n", text);
    fflush(stdout);
    pthread_mutex_unlock(&g_output_mutex);
    cJSON_free(text);
}

static void emit_connection(const char *state, const char *error)
{
    cJSON *message = cJSON_CreateObject();
    cJSON_AddStringToObject(message, "event", "connection");
    cJSON_AddStringToObject(message, "state", state);
    if (error != NULL) {
        cJSON_AddStringToObject(message, "error", error);
    }
    emit_json(message);
    cJSON_Delete(message);
}

static void emit_report_event(const char *event, const ReportRequest *request, const char *error)
{
    cJSON *message = cJSON_CreateObject();
    char station[2] = {request->station, '\0'};
    cJSON_AddStringToObject(message, "event", event);
    cJSON_AddStringToObject(message, "id", request->id);
    cJSON_AddStringToObject(message, "station", station);
    cJSON_AddNumberToObject(message, "value", request->value);
    if (error != NULL) {
        cJSON_AddStringToObject(message, "error", error);
    }
    emit_json(message);
    cJSON_Delete(message);
}

static void emit_response(const char *id, int ok, const char *result, const char *error)
{
    cJSON *message = cJSON_CreateObject();
    cJSON_AddStringToObject(message, "id", id);
    cJSON_AddBoolToObject(message, "ok", ok);
    if (result != NULL) {
        cJSON_AddStringToObject(message, "result", result);
    }
    if (error != NULL) {
        cJSON_AddStringToObject(message, "error", error);
    }
    emit_json(message);
    cJSON_Delete(message);
}

static void station_log(int level, char *format, va_list args)
{
    (void)level;
    vfprintf(stderr, format, args);
    fflush(stderr);
}

static void set_connection_state(int connected, int connecting)
{
    pthread_mutex_lock(&g_state_mutex);
    g_connected = connected;
    g_connecting = connecting;
    pthread_cond_broadcast(&g_state_changed);
    pthread_mutex_unlock(&g_state_mutex);
}

static void interruptible_sleep(unsigned int seconds)
{
    unsigned int ticks = seconds * 10;
    while (!g_stopping && ticks-- > 0) {
        usleep(100000);
    }
}

static void handle_connect_success(EN_IOTA_MQTT_PROTOCOL_RSP *response)
{
    (void)response;
    set_connection_state(1, 0);
    emit_connection("connected", NULL);
}

static void handle_connect_failure(EN_IOTA_MQTT_PROTOCOL_RSP *response)
{
    const char *message = response != NULL && response->message != NULL ? response->message : "connect_failed";
    set_connection_state(0, 0);
    emit_connection("disconnected", message);
}

static void handle_connection_lost(EN_IOTA_MQTT_PROTOCOL_RSP *response)
{
    const char *message = response != NULL && response->message != NULL ? response->message : "connection_lost";
    set_connection_state(0, 0);
    emit_connection("disconnected", message);
}

static void prepend_report_locked(ReportRequest *request)
{
    request->next = g_queue_head;
    g_queue_head = request;
    if (g_queue_tail == NULL) {
        g_queue_tail = request;
    }
    g_pending_count++;
}

static void handle_publish_success(EN_IOTA_MQTT_PROTOCOL_RSP *response)
{
    ReportRequest *request = response != NULL && response->mqtt_msg_info != NULL
        ? (ReportRequest *)response->mqtt_msg_info->context : NULL;
    if (request == NULL) {
        return;
    }

    pthread_mutex_lock(&g_state_mutex);
    if (g_in_flight == request) {
        g_in_flight = NULL;
    }
    pthread_cond_broadcast(&g_state_changed);
    pthread_mutex_unlock(&g_state_mutex);

    emit_report_event("published", request, NULL);
    free(request);
}

static void handle_publish_failure(EN_IOTA_MQTT_PROTOCOL_RSP *response)
{
    ReportRequest *request = response != NULL && response->mqtt_msg_info != NULL
        ? (ReportRequest *)response->mqtt_msg_info->context : NULL;
    const char *message = response != NULL && response->message != NULL ? response->message : "publish_failed";
    if (request == NULL) {
        return;
    }

    pthread_mutex_lock(&g_state_mutex);
    if (g_in_flight == request) {
        g_in_flight = NULL;
    }
    pthread_mutex_unlock(&g_state_mutex);

    emit_report_event("publish_failed", request, message);

    pthread_mutex_lock(&g_state_mutex);
    prepend_report_locked(request);
    pthread_cond_broadcast(&g_state_changed);
    pthread_mutex_unlock(&g_state_mutex);
}

static char *read_text_file(const char *path)
{
    FILE *file = fopen(path, "rb");
    long length;
    char *buffer;
    if (file == NULL) {
        return NULL;
    }
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 || fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return NULL;
    }
    buffer = (char *)malloc((size_t)length + 1);
    if (buffer == NULL) {
        fclose(file);
        return NULL;
    }
    if (fread(buffer, 1, (size_t)length, file) != (size_t)length) {
        free(buffer);
        fclose(file);
        return NULL;
    }
    buffer[length] = '\0';
    fclose(file);
    return buffer;
}

static char *duplicate_json_string(cJSON *root, const char *name)
{
    cJSON *item = cJSON_GetObjectItemCaseSensitive(root, name);
    return cJSON_IsString(item) && item->valuestring != NULL ? strdup(item->valuestring) : NULL;
}

static int load_config(const char *path)
{
    char *text = read_text_file(path);
    cJSON *root;
    if (text == NULL) {
        fprintf(stderr, "cannot read config %s: %s\n", path, strerror(errno));
        return -1;
    }
    root = cJSON_Parse(text);
    free(text);
    if (root == NULL) {
        fprintf(stderr, "invalid JSON config: %s\n", path);
        return -1;
    }

    g_config.work_path = duplicate_json_string(root, "work_path");
    g_config.address = duplicate_json_string(root, "address");
    g_config.port = duplicate_json_string(root, "port");
    g_config.device_id = duplicate_json_string(root, "device_id");
    g_config.secret = duplicate_json_string(root, "secret");
    cJSON_Delete(root);

    if (g_config.work_path == NULL || g_config.address == NULL || g_config.port == NULL ||
        g_config.device_id == NULL || g_config.secret == NULL) {
        fprintf(stderr, "config requires work_path, address, port, device_id and secret\n");
        return -1;
    }
    return 0;
}

static void free_config(void)
{
    free(g_config.work_path);
    free(g_config.address);
    free(g_config.port);
    free(g_config.device_id);
    free(g_config.secret);
    memset(&g_config, 0, sizeof(g_config));
}

static int valid_request_id(const char *id)
{
    size_t i;
    size_t length = id == NULL ? 0 : strlen(id);
    if (length == 0 || length > MAX_REQUEST_ID) {
        return 0;
    }
    for (i = 0; i < length; i++) {
        char ch = id[i];
        if (!((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
              (ch >= '0' && ch <= '9') || ch == '-' || ch == '_')) {
            return 0;
        }
    }
    return 1;
}

static int queue_report(const char *id, char station, int value)
{
    ReportRequest *request;
    pthread_mutex_lock(&g_state_mutex);
    for (request = g_queue_head; request != NULL; request = request->next) {
        if (strcmp(request->id, id) == 0) {
            pthread_mutex_unlock(&g_state_mutex);
            return 1;
        }
    }
    if (g_in_flight != NULL && strcmp(g_in_flight->id, id) == 0) {
        pthread_mutex_unlock(&g_state_mutex);
        return 1;
    }
    if (g_pending_count >= MAX_PENDING_REPORTS) {
        pthread_mutex_unlock(&g_state_mutex);
        return -1;
    }
    request = (ReportRequest *)calloc(1, sizeof(ReportRequest));
    if (request == NULL) {
        pthread_mutex_unlock(&g_state_mutex);
        return -1;
    }
    snprintf(request->id, sizeof(request->id), "%s", id);
    request->station = station;
    request->value = value;
    if (g_queue_tail == NULL) {
        g_queue_head = request;
    } else {
        g_queue_tail->next = request;
    }
    g_queue_tail = request;
    g_pending_count++;
    pthread_cond_broadcast(&g_state_changed);
    pthread_mutex_unlock(&g_state_mutex);
    return 0;
}

static void *connection_worker(void *unused)
{
    unsigned int backoff = 1;
    (void)unused;
    while (!g_stopping) {
        pthread_mutex_lock(&g_state_mutex);
        while (!g_stopping && (g_connected || g_connecting)) {
            pthread_cond_wait(&g_state_changed, &g_state_mutex);
        }
        if (g_stopping) {
            pthread_mutex_unlock(&g_state_mutex);
            break;
        }
        g_connecting = 1;
        pthread_mutex_unlock(&g_state_mutex);

        emit_connection("connecting", NULL);
        if (IOTA_Connect() != 0) {
            set_connection_state(0, 0);
        }

        pthread_mutex_lock(&g_state_mutex);
        while (!g_stopping && g_connecting) {
            pthread_cond_wait(&g_state_changed, &g_state_mutex);
        }
        if (g_connected) {
            backoff = 1;
        }
        pthread_mutex_unlock(&g_state_mutex);
        if (!g_connected && !g_stopping) {
            interruptible_sleep(backoff);
            backoff = backoff < 16 ? backoff * 2 : 30;
        }
    }
    return NULL;
}

static void *report_worker(void *unused)
{
    (void)unused;
    while (!g_stopping) {
        ReportRequest *request;
        ST_IOTA_SERVICE_DATA_INFO service;
        char properties[128];
        const char *service_id;
        const char *property_name;
        int result;

        pthread_mutex_lock(&g_state_mutex);
        while (!g_stopping && (!g_connected || g_queue_head == NULL || g_in_flight != NULL)) {
            pthread_cond_wait(&g_state_changed, &g_state_mutex);
        }
        if (g_stopping) {
            pthread_mutex_unlock(&g_state_mutex);
            break;
        }
        request = g_queue_head;
        g_queue_head = request->next;
        if (g_queue_head == NULL) {
            g_queue_tail = NULL;
        }
        request->next = NULL;
        g_pending_count--;
        g_in_flight = request;
        pthread_mutex_unlock(&g_state_mutex);

        service_id = request->station == 'A' ? "Station_1" : "Station_2";
        property_name = request->station == 'A' ? "A parcels per D" : "B parcels per D";
        snprintf(properties, sizeof(properties), "{\"%s\":%d}", property_name, request->value);
        service.service_id = (char *)service_id;
        service.event_time = NULL;
        service.properties = properties;
        result = IOTA_PropertiesReport(&service, 1, 0, request);
        if (result != 0) {
            pthread_mutex_lock(&g_state_mutex);
            if (g_in_flight == request) {
                g_in_flight = NULL;
            }
            pthread_mutex_unlock(&g_state_mutex);
            emit_report_event("publish_failed", request, "sdk_rejected_report");
            pthread_mutex_lock(&g_state_mutex);
            prepend_report_locked(request);
            pthread_cond_broadcast(&g_state_changed);
            pthread_mutex_unlock(&g_state_mutex);
            interruptible_sleep(1);
        }
    }
    return NULL;
}

static void handle_command(const char *line)
{
    cJSON *root = cJSON_Parse(line);
    cJSON *id;
    cJSON *operation;
    if (root == NULL) {
        emit_response("invalid", 0, NULL, "invalid_json");
        return;
    }
    id = cJSON_GetObjectItemCaseSensitive(root, "id");
    operation = cJSON_GetObjectItemCaseSensitive(root, "op");
    if (!cJSON_IsString(id) || !valid_request_id(id->valuestring) || !cJSON_IsString(operation)) {
        emit_response("invalid", 0, NULL, "invalid_request");
        cJSON_Delete(root);
        return;
    }

    if (strcmp(operation->valuestring, "shutdown") == 0) {
        emit_response(id->valuestring, 1, "stopping", NULL);
        g_stopping = 1;
        pthread_mutex_lock(&g_state_mutex);
        pthread_cond_broadcast(&g_state_changed);
        pthread_mutex_unlock(&g_state_mutex);
    } else if (strcmp(operation->valuestring, "status") == 0) {
        cJSON *response = cJSON_CreateObject();
        pthread_mutex_lock(&g_state_mutex);
        cJSON_AddStringToObject(response, "id", id->valuestring);
        cJSON_AddBoolToObject(response, "ok", 1);
        cJSON_AddStringToObject(response, "state", g_connected ? "connected" : g_connecting ? "connecting" : "disconnected");
        cJSON_AddNumberToObject(response, "pending_reports", g_pending_count + (g_in_flight != NULL));
        pthread_mutex_unlock(&g_state_mutex);
        emit_json(response);
        cJSON_Delete(response);
    } else if (strcmp(operation->valuestring, "report_station") == 0) {
        cJSON *station = cJSON_GetObjectItemCaseSensitive(root, "station");
        cJSON *value = cJSON_GetObjectItemCaseSensitive(root, "value");
        char station_value;
        if (!cJSON_IsString(station) || strlen(station->valuestring) != 1 || !cJSON_IsNumber(value)) {
            emit_response(id->valuestring, 0, NULL, "invalid_report");
            cJSON_Delete(root);
            return;
        }
        station_value = station->valuestring[0];
        if ((station_value != 'A' && station_value != 'B') || value->valuedouble < 0 || value->valuedouble != value->valueint) {
            emit_response(id->valuestring, 0, NULL, "invalid_report");
        } else {
            int queued = queue_report(id->valuestring, station_value, value->valueint);
            if (queued < 0) {
                emit_response(id->valuestring, 0, NULL, "queue_full");
            } else {
                emit_response(id->valuestring, 1, queued == 1 ? "already_queued" : "queued", NULL);
            }
        }
    } else {
        emit_response(id->valuestring, 0, NULL, "unknown_operation");
    }
    cJSON_Delete(root);
}

static void handle_signal(int signal_number)
{
    (void)signal_number;
    g_stopping = 1;
    close(STDIN_FILENO);
}

static void free_reports(void)
{
    ReportRequest *request;
    pthread_mutex_lock(&g_state_mutex);
    request = g_queue_head;
    while (request != NULL) {
        ReportRequest *next = request->next;
        free(request);
        request = next;
    }
    g_queue_head = NULL;
    g_queue_tail = NULL;
    g_pending_count = 0;
    if (g_in_flight != NULL) {
        /* The SDK owns this pointer as async callback context until process exit. */
        g_in_flight = NULL;
    }
    pthread_mutex_unlock(&g_state_mutex);
}

int main(int argc, char **argv)
{
    pid_t parent_pid;
    pthread_t connection_thread;
    pthread_t report_thread;
    char line[MAX_LINE_LENGTH];
    cJSON *ready;
    struct sigaction action;

    if (argc != 3 || strcmp(argv[1], "--config") != 0) {
        fprintf(stderr, "usage: %s --config <path>\n", argv[0]);
        return 2;
    }

    parent_pid = getppid();
    if (prctl(PR_SET_PDEATHSIG, SIGTERM) != 0 || getppid() != parent_pid) {
        fprintf(stderr, "failed to bind daemon lifetime to parent\n");
        return 3;
    }
    memset(&action, 0, sizeof(action));
    action.sa_handler = handle_signal;
    sigemptyset(&action.sa_mask);
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);
    setvbuf(stdout, NULL, _IOLBF, 0);

    if (load_config(argv[2]) != 0) {
        free_config();
        return 4;
    }
    if (IOTA_Init(g_config.work_path) != 0) {
        fprintf(stderr, "IOTA_Init failed\n");
        free_config();
        return 5;
    }
    IOTA_SetPrintLogCallback(station_log);
    IOTA_ConnectConfigSet(g_config.address, g_config.port, g_config.device_id, g_config.secret);
    if (IOTA_ConfigSetUint(EN_IOTA_CFG_AUTH_MODE, EN_IOTA_CFG_AUTH_MODE_SECRET) != 0) {
        fprintf(stderr, "failed to configure secret authentication\n");
        IOTA_Destroy();
        free_config();
        return 6;
    }

    IOTA_SetProtocolCallback(EN_IOTA_CALLBACK_CONNECT_SUCCESS, handle_connect_success);
    IOTA_SetProtocolCallback(EN_IOTA_CALLBACK_CONNECT_FAILURE, handle_connect_failure);
    IOTA_SetProtocolCallback(EN_IOTA_CALLBACK_CONNECTION_LOST, handle_connection_lost);
    IOTA_SetProtocolCallback(EN_IOTA_CALLBACK_PUBLISH_SUCCESS, handle_publish_success);
    IOTA_SetProtocolCallback(EN_IOTA_CALLBACK_PUBLISH_FAILURE, handle_publish_failure);

    if (pthread_create(&connection_thread, NULL, connection_worker, NULL) != 0) {
        fprintf(stderr, "failed to create worker threads\n");
        IOTA_Destroy();
        free_config();
        return 7;
    }
    if (pthread_create(&report_thread, NULL, report_worker, NULL) != 0) {
        fprintf(stderr, "failed to create worker threads\n");
        g_stopping = 1;
        pthread_mutex_lock(&g_state_mutex);
        pthread_cond_broadcast(&g_state_changed);
        pthread_mutex_unlock(&g_state_mutex);
        pthread_join(connection_thread, NULL);
        IOTA_Destroy();
        free_config();
        return 7;
    }

    ready = cJSON_CreateObject();
    cJSON_AddStringToObject(ready, "event", "ready");
    cJSON_AddStringToObject(ready, "state", "connecting");
    emit_json(ready);
    cJSON_Delete(ready);

    while (!g_stopping && fgets(line, sizeof(line), stdin) != NULL) {
        handle_command(line);
    }
    g_stopping = 1;
    pthread_mutex_lock(&g_state_mutex);
    pthread_cond_broadcast(&g_state_changed);
    pthread_mutex_unlock(&g_state_mutex);
    pthread_join(connection_thread, NULL);
    pthread_join(report_thread, NULL);
    IOTA_Destroy();
    free_reports();
    free_config();
    return 0;
}
