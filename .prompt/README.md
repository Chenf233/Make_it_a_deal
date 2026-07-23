# SmartStation 渐进式上下文入口

本目录为 AI 优先、兼顾开发者阅读的工程上下文索引。它不替代源码、测试、
OpenAPI 或运行手册，而是帮助开发者用最少上下文找到正确的资产和工作流程。

## 首次进入项目

无项目上下文时按以下顺序阅读：

1. 根目录 [`AGENTS.md`](../AGENTS.md)。
2. 本文件。
3. [`project-design.md`](project-design.md) 中与当前任务相关的职责和依赖规则。
4. 根据任务类型选择一份开发流程。
5. 只读取目标模块、直接调用者、相关测试和必要的旧 `.prompt` 文件。

不要默认读取全部源码或所有历史 `.prompt`。渐进式披露的目标是先建立正确的
工程边界，再按任务加载实现细节。

## 任务路由

| 任务 | 必读文档 | 继续读取 |
| --- | --- | --- |
| 新增或修改独立能力模块 | [`workflows/module-development.md`](workflows/module-development.md) | 目标模块源码、入口、测试和直接调用者 |
| 修改页面、API 或简单 CRUD | [`workflows/fastapi-development.md`](workflows/fastapi-development.md) | 对应 Router、Schema、Template/JS、Repository |
| 数据库与硬件或云端协作 | [`project-design.md`](project-design.md)、FastAPI 流程 | 相关 Application/Router、Repository、Service 接口 |
| 修改后台任务、取消或跨请求状态 | 项目设计章程、FastAPI 流程 | 生命周期所有者、关闭逻辑和相关测试 |
| 修改 GPIO 或机械行为 | 功能模块流程 | 目标硬件模块、引脚映射、Fake/设备测试 |
| 修改 Python-C IPC | 功能模块流程 | Python 管理器、`station_iotd.c`、协议测试和 Makefile |
| 修改 Huawei IoT 业务规则 | 两份流程都读 | FastAPI 编排、计数 Repository、IoT 公开接口 |
| 修改启动或关闭顺序 | 项目设计章程 | `main.py`、资源模块生命周期、后台控制器 |

## 当前设计状态

项目采用以下增量目标结构：

```text
main.py       应用组装和生命周期
core/         配置与通用应用基础设施
routers/      HTTP、WebSocket 和流媒体传输适配
application/  复杂业务用例与跨模块编排
database/     SQLite、Repository 和持久化约束
services/     可独立调用和验证的功能能力
templates/    浏览器页面、样式和交互
```

`application/` 是目标层次，当前旧代码可能仍在 Router 或部分 `services` 中承担业务
编排。后续采用“增量遵守，触碰迁移”：

- 不主动进行全项目重构。
- 新功能遵守目标边界。
- 修改旧复杂流程时，只有在边界已经阻碍需求、验证或正确性时才顺手迁移。
- 首次迁移默认保持 HTTP API、数据库 Schema、GPIO、硬件时序和 C 协议不变。

## 当前认知分类

### 功能能力

- `services/camera_manager`
- `services/face_recognition`
- `services/scanner`
- `services/motor`
- `services/BuzzerLight`
- `services/electromagnet`
- Huawei IoT 的进程、IPC 和传输部分
- `station_iotd` 原生适配器

### FastAPI 业务编排

- 包裹入库预览与确认
- 客户进出认证
- 取件流程
- 自动到站、计数和上报
- 用户注册与人脸缓存同步
- 用户与已打开柜体的业务关联

这些职责目前不一定已经位于 `application/`，分类用于指导新增和修改，不代表要求
立即移动文件。

## 信息权威顺序

发生冲突时按以下顺序判断：

1. 实际源码和自动生成的 OpenAPI。
2. 可执行测试及真实设备验证结果。
3. 当前项目设计章程和开发流程。
4. 模块旁的 `.prompt` 文件。
5. 根 README 和历史设计稿。
6. 第三方 SDK 文档，仅用于解释第三方行为。

旧 `.prompt` 中的接口、路由和方法签名可能已经过期。使用前必须和源码核对。

## 文档索引

- [`project-design.md`](project-design.md)：目标架构、职责、依赖与增量兼容政策。
- [`workflows/module-development.md`](workflows/module-development.md)：独立功能模块开发流程。
- [`workflows/fastapi-development.md`](workflows/fastapi-development.md)：FastAPI 业务增量开发流程。

部署、硬件接线和故障排查等长文档暂不在本阶段建立。后续需要时放入 `docs/`，
本目录只保留导航、设计约束和高密度开发上下文。
