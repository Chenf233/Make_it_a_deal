# Huawei IoT Integration

SmartStation starts `station_iotd` as a long-running child process from the
FastAPI lifespan. The child process owns the Huawei C SDK connection. Python
and C communicate with newline-delimited JSON over stdin/stdout; SDK logs are
written to stderr.

## Product Model

The native process reports integer values with these fixed mappings:

| Station | Huawei service ID | Property |
| --- | --- | --- |
| A | `Station_1` | `A parcels per D` |
| B | `Station_2` | `B parcels per D` |

Successful automatic arrival increments the corresponding SQLite value by one
and queues the new absolute value for reporting. Values are not reset by date.

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
fill in the device values. `station_iotd.json` is ignored by Git.

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
GET /api/wheels/counters
PUT /api/wheels/counters/a  {"value": 10}
PUT /api/wheels/counters/b  {"value": 20}
GET /api/wheels/iot-status
```

Setting a value persists it and queues that absolute value for cloud reporting.

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

It reads the current A/B values from SQLite and reports those exact values, so
the test does not increment or otherwise change the local counters:

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
authentication, A publish, B publish, status, and graceful shutdown. A
`published` event confirms MQTT publish completion; the IoTDA console should
still be checked once to confirm the product model displays both properties.
