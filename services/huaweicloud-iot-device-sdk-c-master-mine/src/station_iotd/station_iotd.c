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
#define MAX_SERVICE_ID 128
#define MAX_PROPERTIES_LENGTH 4096
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
    char service_id[MAX_SERVICE_ID + 1];
    char *properties;
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

static void emit_report_event(const char *event, const char *id, const char *service_id, const char *error)
{
    cJSON *message = cJSON_CreateObject();
    cJSON_AddStringToObject(message, "event", event);
    cJSON_AddStringToObject(message, "id", id);
    cJSON_AddStringToObject(message, "service_id", service_id);
    if (error != NULL) {
        cJSON_AddStringToObject(message, "error", error);
    }
    emit_json(message);
    cJSON_Delete(message);
}

static void free_report(ReportRequest *request)
{
    if (request == NULL) {
        return;
    }
    cJSON_free(request->properties);
    free(request);
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

    emit_report_event("published", request->id, request->service_id, NULL);
    free_report(request);
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
    prepend_report_locked(request);
    pthread_cond_broadcast(&g_state_changed);
    pthread_mutex_unlock(&g_state_mutex);
    emit_report_event("publish_failed", request->id, request->service_id, message);
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

static int valid_bounded_string(const cJSON *item, size_t max_length)
{
    size_t length;
    if (!cJSON_IsString(item) || item->valuestring == NULL) {
        return 0;
    }
    length = strlen(item->valuestring);
    return length > 0 && length <= max_length;
}

static int queue_report(const char *id, const char *service_id, char *properties, char *queued_service_id)
{
    ReportRequest *request;
    pthread_mutex_lock(&g_state_mutex);
    for (request = g_queue_head; request != NULL; request = request->next) {
        if (strcmp(request->id, id) == 0) {
            snprintf(queued_service_id, MAX_SERVICE_ID + 1, "%s", request->service_id);
            pthread_mutex_unlock(&g_state_mutex);
            return 1;
        }
    }
    if (g_in_flight != NULL && strcmp(g_in_flight->id, id) == 0) {
        snprintf(queued_service_id, MAX_SERVICE_ID + 1, "%s", g_in_flight->service_id);
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
        return -2;
    }
    snprintf(request->id, sizeof(request->id), "%s", id);
    snprintf(request->service_id, sizeof(request->service_id), "%s", service_id);
    snprintf(queued_service_id, MAX_SERVICE_ID + 1, "%s", request->service_id);
    request->properties = properties;
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

        service.service_id = request->service_id;
        service.event_time = NULL;
        service.properties = request->properties;
        result = IOTA_PropertiesReport(&service, 1, 0, request);
        if (result < 0) {
            pthread_mutex_lock(&g_state_mutex);
            if (g_in_flight == request) {
                g_in_flight = NULL;
            }
            prepend_report_locked(request);
            pthread_cond_broadcast(&g_state_changed);
            pthread_mutex_unlock(&g_state_mutex);
            emit_report_event("publish_failed", request->id, request->service_id, "sdk_rejected_report");
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
    if (!cJSON_IsObject(root)) {
        emit_response("invalid", 0, NULL, "invalid_request");
        cJSON_Delete(root);
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
    } else if (strcmp(operation->valuestring, "report_properties") == 0) {
        cJSON *service_id = cJSON_GetObjectItemCaseSensitive(root, "service_id");
        cJSON *properties = cJSON_GetObjectItemCaseSensitive(root, "properties");
        char *serialized_properties;
        size_t properties_length;
        char queued_service_id[MAX_SERVICE_ID + 1];
        int queued;
        if (!valid_bounded_string(service_id, MAX_SERVICE_ID) || !cJSON_IsObject(properties)) {
            emit_response(id->valuestring, 0, NULL, "invalid_report");
            cJSON_Delete(root);
            return;
        }
        serialized_properties = cJSON_PrintUnformatted(properties);
        if (serialized_properties == NULL) {
            emit_response(id->valuestring, 0, NULL, "out_of_memory");
            cJSON_Delete(root);
            return;
        }
        properties_length = strlen(serialized_properties);
        if (properties_length > MAX_PROPERTIES_LENGTH) {
            cJSON_free(serialized_properties);
            emit_response(id->valuestring, 0, NULL, "properties_too_large");
            cJSON_Delete(root);
            return;
        }
        queued = queue_report(id->valuestring, service_id->valuestring, serialized_properties, queued_service_id);
        if (queued == -2) {
            cJSON_free(serialized_properties);
            emit_response(id->valuestring, 0, NULL, "out_of_memory");
        } else if (queued < 0) {
            cJSON_free(serialized_properties);
            emit_response(id->valuestring, 0, NULL, "queue_full");
        } else {
            if (queued == 1) {
                cJSON_free(serialized_properties);
            }
            emit_response(id->valuestring, 1, queued == 1 ? "already_queued" : "queued", NULL);
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
        free_report(request);
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
