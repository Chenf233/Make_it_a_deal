# SmartStation Agent Entry

本文件是所有开发 Agent 的起点。开始分析或修改代码前，先阅读
[`.prompt/README.md`](.prompt/README.md)，再根据任务类型按需加载上下文。

## 基本原则

1. 不要默认读取整个仓库或全部 `.prompt` 文档。
2. 先判断任务属于“功能模块开发”还是“FastAPI 增量开发”。
3. 修改前先确认实际代码；旧 `.prompt` 和根 README 可能落后于实现。
4. 当前分层是增量目标，不代表旧代码已经完成重构。
5. 不要为了符合目标架构而主动重构与当前需求无关的旧代码。
6. 新功能必须遵守目标依赖方向；修改旧复杂流程时再评估是否顺手迁移。
7. 本地验证不能代替 RDK、真实 GPIO、摄像头、原生库或华为云验证。
8. 不得覆盖、回滚或整理与当前任务无关的工作区改动。

## 两类开发任务

- 修改摄像头、识别、扫码、电机、柜体、GPIO、Python-C IPC 或华为云传输：
  阅读 [功能模块开发流程](.prompt/workflows/module-development.md)。
- 修改页面、HTTP API、数据库业务、跨模块调用、后台业务任务或用户可观察流程：
  阅读 [FastAPI 增量开发流程](.prompt/workflows/fastapi-development.md)。
- 如果 FastAPI 需求发现模块能力不足，先进入功能模块流程完善接口，再返回
  FastAPI 流程完成业务编排。

## 全局运行约束

- FastAPI/Uvicorn 使用单 worker。摄像头、GPIO、进程内状态和华为设备连接均为
  独占或进程内资源。
- RDK GPIO 使用 `Hobot.GPIO` 的 `GPIO.BOARD` 物理引脚编号。
- SQLite 是业务数据和持久化计数的本地真源。
- 华为 C SDK 连接由常驻 `station_iotd` 子进程持有，Python 通过 NDJSON 通信。
- `services/huaweicloud-iot-device-sdk-c-master-mine` 大部分是第三方 SDK；除非任务
  明确涉及原生适配器或构建，否则不要展开或修改 Vendor 源码。
- 包含设备密钥的真实配置不得写入文档、测试输出或 Git 跟踪文件。

## 修改完成标准

- 说明完成了哪一级验证：本地、RDK 组件或 RDK 端到端。
- 无法访问 RDK 时，准备确定的设备验证命令、前置条件、成功标准和失败诊断。
- 公开接口、状态所有权、生命周期或跨模块流程改变时，同步相关上下文文档。
