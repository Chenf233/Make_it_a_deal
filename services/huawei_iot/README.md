# Huawei IoT Integration

SmartStation starts `station_iotd` as a long-running child process from the
FastAPI lifespan. The child process owns the Huawei C SDK connection. Python
and C communicate with newline-delimited JSON over stdin/stdout; SDK logs are
written to stderr.

## Native Protocol

`station_iotd` accepts one JSON object per stdin line. Property reports use a
generic service ID and retain the complete properties object, including string,
number, boolean, null, array, and nested object values:

```json
{"op":"report_properties","id":"report-42","service_id":"parcel_counters","properties":{"count":12,"active":true,"note":null}}
```

The daemon returns `queued` or `already_queued` when it accepts the request,
then emits `published` or `publish_failed` after the Huawei SDK callback. The
publish event contains the request `id` and `service_id`:

```json
{"id":"report-42","ok":true,"result":"queued"}
{"event":"published","id":"report-42","service_id":"parcel_counters"}
```

Reports are queued while disconnected and only one report is in flight at a
time. stdout is reserved for NDJSON protocol messages; SDK and daemon logs are
written to stderr.

## Build On RDK Linux

Prepare the SDK `lib/` directory as described in the Huawei SDK README, then
run from the SDK root:

```sh
make station_iotd
```

The executable contains the Huawei SDK object code and dynamically loads the
third-party libraries from `$ORIGIN/lib` through its ELF RUNPATH.

## Configure

Copy `station_iotd.example.json` to `station_iotd.json` in the SDK root and
fill in the device values. `station_iotd.json` is ignored by Git. `work_path`
may be `.` when the executable and configuration are in the SDK root.

`work_path` must be the absolute SDK root containing:

```text
conf/rootcert.pem
```

The FastAPI settings can be overridden through `.env`:

```text
HUAWEI_IOT_ENABLED=true
HUAWEI_IOT_EXECUTABLE=services/huaweicloud-iot-device-sdk-c-master-mine/station_iotd
HUAWEI_IOT_CONFIG=services/huaweicloud-iot-device-sdk-c-master-mine/station_iotd.json
```

Run Uvicorn with one worker because the application owns exclusive camera,
GPIO, in-memory wheel state, and one Huawei device connection.

## API

```text
GET /api/iot/daily-counters
GET /api/iot/daily-counters?business_date=2026-07-22
POST /api/iot/daily-sync  {"business_date":"2026-07-22","force":true}
GET /api/iot/status
```

Picked-up parcels are counted by `target_location` for each Asia/Shanghai
business date. After midnight, Python reports the previous day's values to
`Station_1` using `A_parcels_per_D` and `B_parcels_per_D`. Startup retries
unfinished historical reports. The manual sync endpoint is intended for
diagnostics and only accepts completed business dates.

## Tests

The process-manager unit tests do not start the C executable or connect to the
cloud:

```sh
python -m unittest services.huawei_iot.test_process_manager -v
```

The real integration test must be run on the RDK only after SmartStation and
any existing `station_iotd` process have been stopped. The test scans `/proc`
and fails before connecting if it finds SmartStation, Uvicorn `main:app`, or
another `station_iotd` process.

It reads the previous business day's A/B values from SQLite and reports those
exact values in one generic property report, so the test does not increment or
otherwise change the local counters:

```sh
RUN_HUAWEI_IOT_INTEGRATION_TEST=1 \
python -m unittest services.huawei_iot.test_real_connection -v
```

Optional overrides:

```text
HUAWEI_IOT_EXECUTABLE=/absolute/path/to/station_iotd
HUAWEI_IOT_CONFIG=/absolute/path/to/station_iotd.json
HUAWEI_IOT_CONNECT_TIMEOUT=45
HUAWEI_IOT_PUBLISH_TIMEOUT=20
```

The real test verifies dynamic dependencies, certificate/configuration,
authentication, property publish, status, and graceful shutdown. A
`published` event confirms MQTT publish completion; the IoTDA console should
still be checked once to confirm the product model displays both properties.
