# SmartStation 增量项目设计章程

## 1. 适用范围

本章程约束后续增量开发，不要求现有代码立即完成分层重构。

基本政策：

- 新代码遵守目标设计。
- 旧代码保持可运行。
- 修改旧复杂流程时，按需求范围评估迁移。
- 不为了目录整洁执行无业务收益的大规模重构。
- 结构调整与硬件行为、数据库 Schema、HTTP API 等高风险变化应尽量分开。

## 2. 总体结构

```text
templates
    ↓ HTTP / WebSocket
routers
    ↓
application
    ├──→ database
    └──→ services

main.py 负责构造、连接和管理以上组件的生命周期。
```

### `main.py`

应用组装根，负责：

- 创建 FastAPI 应用并注册 Router。
- 构造 Repository、功能模块和 Application 控制器。
- 启动摄像头、GPIO、后台控制器和原生子进程。
- 按安全顺序取消业务任务、停止硬件并释放资源。
- 挂载模板、静态文件并维持单 worker 约束。

`main.py` 不实现具体业务流程。

### `core/`

存放与具体业务无关的应用基础设施：

- 配置和日志。
- 通用异常基础类型。
- 资源注册或依赖组装辅助。
- WebSocket Hub、通知器等公共机制。

`core` 不是无法分类代码的收容目录，不应加入包裹、取件、轮子等具体业务规则。

### `routers/`

FastAPI 传输适配层，负责：

- HTTP 方法、路径和请求解析。
- Pydantic 校验和 FastAPI 依赖。
- 调用 Application、简单 Repository 或简单 Service。
- 将业务结果和错误映射为 HTTP 响应。
- WebSocket、MJPEG 和 StreamingResponse 等协议行为。

Router 不拥有复杂业务顺序、长期后台任务、跨请求业务状态或数据库与硬件之间的
一致性策略。

### `application/`

业务用例和跨模块编排层，负责：

- 组织 Repository 和功能模块的调用顺序。
- 定义业务成功点和失败语义。
- 管理业务级后台任务、锁、取消、重试和跨请求状态。
- 决定数据库、硬件和云端副作用的先后与补偿。
- 返回与 HTTP 无关的结果，抛出与 HTTP 无关的业务错误。

Application 不读取 FastAPI `Request`，不返回 `Response`，不写 SQL，也不实现 GPIO、
CV 或 C SDK 细节。

### `database/`

FastAPI 应用的数据持久化边界，负责：

- SQLite 连接、表结构和 SQL。
- Repository、事务和原子读写。
- 数据库约束和持久化数据转换。

Application 决定何时保存什么，Database 决定怎样可靠地保存。

### `services/`

可独立调用和验证的能力模块，负责：

- 摄像头、人脸识别、扫码和二维码生成。
- 电机、蜂鸣器、灯、电磁锁和柜体设备能力。
- Python-C 子进程通信及华为云传输。

Service 可以是 SmartStation 专用能力，但原则上：

- 不依赖 FastAPI、Router 或 Application。
- 不访问 SmartStation 业务数据库。
- 不决定跨模块业务流程。
- 自己管理能力内部的线程、锁、子进程和设备状态。
- 提供明确的构造、启动、调用、状态和停止接口。

### `templates/`

负责浏览器显示和交互：

- HTML、CSS、JavaScript。
- 页面级临时状态和请求反馈。
- HTTP/WebSocket 调用。

浏览器不认定数据库或硬件最终事实，不复制后端核心业务规则。

## 3. 依赖规则

允许的主要方向：

```text
main → core / database / services / application / routers
routers → application
routers → database    仅简单 CRUD
routers → services    仅单能力调用或诊断接口
application → database / services / core 基础设施
database → SQLite 及数据库依赖
services → 各自底层技术依赖
```

未来不得新增的反向依赖：

```text
services → routers / application / FastAPI / database
database → services / application / routers
application → routers / FastAPI Request / FastAPI Response
```

现有反向依赖可以暂时保留，但不能作为新增功能的范例。

## 4. Application 抽取门槛

以下全部成立时，逻辑可以留在 Router：

- 只有一个主要依赖。
- 没有跨模块业务顺序。
- 没有数据库与外部副作用组合。
- 没有后台任务、跨请求状态、补偿或复杂恢复。
- 不需要被其他入口复用。

命中以下任一条件时，必须进入 Application：

1. 同时涉及数据库和硬件。
2. 同时涉及数据库和云端。
3. 数据库与进程、文件等不可事务化副作用组合。
4. 多个功能模块的调用顺序表达业务规则。
5. 存在后台任务、超时、取消或重试。
6. 存在跨请求状态、幂等或重复请求问题。
7. 存在部分成功、补偿或重启恢复问题。
8. 同一流程会被多个入口调用。
9. 需要脱离 HTTP 单独测试业务行为。

简单 CRUD、状态读取、视频流和单个硬件诊断接口不需要形式化地包装成 Use Case。

## 5. 状态所有权

重要状态必须只有一个权威拥有者：

| 状态 | 权威拥有者 |
| --- | --- |
| 用户、包裹和访问日志 | SQLite / Application |
| A/B 持久化累计值 | SQLite / Application |
| 当前电机动作和估算位置 | Motor Service |
| 自动到站业务任务 | Application |
| 柜体物理动作状态 | Cabinet/Hardware Service |
| 用户当前打开的柜体 | Application |
| Huawei 连接和进程状态 | Huawei IoT Service |
| 入库预览 token 和预留状态 | Application |
| 浏览器临时交互状态 | Template/JavaScript |

镜像、缓存和传输队列不得反向覆盖真源，除非流程明确允许。

## 6. 生命周期

- Service 定义自己的 `start/init`、`status`、`stop/close` 能力。
- Application 控制器若拥有后台任务，必须提供取消或 `shutdown`。
- `main.py` 的 FastAPI lifespan 决定整体启动和关闭顺序。
- 导入模块原则上不应触碰真实硬件或启动线程、子进程。
- 当前存在的导入副作用暂不要求立即重构，但不得在新模块中复制。

## 7. 增量迁移政策

“触碰迁移”不等于修改旧文件的一行代码就重构整个流程。以下情况才评估迁移：

- 新需求显著改变调用顺序或状态所有权。
- 新增硬件、云端、进程等外部副作用。
- 新增后台任务、取消、重试或恢复。
- 当前结构阻碍本地测试或造成逻辑重复。
- 旧边界已经无法安全表达新行为。

首次迁移默认保持：

- HTTP API 和页面行为不变。
- 数据库 Schema 不变。
- GPIO 映射和硬件时序不变。
- Python-C 协议和华为产品模型不变。

先固定原行为并调整责任所有权，再单独处理行为变化。

## 8. Application 组织方式

首次需要时再创建目录，不预建空架构：

```text
application/
├── __init__.py
├── parcel_inbound.py
├── customer_access.py
├── pickup.py
└── wheel_arrival.py
```

- 无状态、一次性流程可以使用函数。
- 拥有后台任务、锁、队列或跨请求状态的流程使用类。
- 不强制为每个依赖建立抽象基类。
- 需要 Fake、多实现或隔离平台依赖时，再引入最小 `Protocol`。

## 9. 当前已知责任归类

以下是开发认知，不要求立即移动文件：

- `services/pickup` 当前实质属于 Application 业务编排。
- Wheel Router 中的自动任务、计数和上报属于 Application。
- Station Router 中的入库预览、确认和机械编排属于 Application。
- Client Router 中的进出、取件和开柜顺序属于 Application。
- Huawei Manager 的进程和传输属于 Service，SQLite 计数规则属于 Application。
- Hardware Manager 的柜体动作属于 Service，用户到已开柜体的关联属于 Application。
