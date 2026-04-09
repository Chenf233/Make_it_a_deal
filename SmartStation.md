# 角色设定
你是一个资深的 Python 后端架构师和计算机视觉工程师，擅长使用 FastAPI 搭建高性能的异步 Web 服务，熟练掌握面向对象设计原则、依赖注入、以及 InsightFace/OpenCV 的工程化落地。

# 项目背景与核心业务流转
我们要使用 Python 实现一个基于计算机视觉的简易“智能无人驿站自取系统”（单机部署，提供 Web 端）。系统的核心目的是利用 CV 技术替代人工核验，实现包裹自动入库、客户刷脸通行、智能取件提醒的无缝闭环。

系统严格划分为三个端（MVP 核心流程如下）：
1. **后台管理端 (Backend)**：
   - 系统的超级大脑。负责调用摄像头录入客户的人脸特征与基础信息到数据库。
   - 提供数据看板，查看【人员进出日志表】和【包裹状态信息表】。
   - 录入人脸，所有的人脸数据都预先从这里录
2. **驿站工作端 (Station)**：
   - 快递员的作业界面。工作人员放置包裹后即离开，系统通过摄像头+条码识别模块（当前使用 Dummy 接口）自动抓取 4 位包裹码。
   - 识别成功后，系统自动将包裹信息与条码入库，包裹状态标记为“在库”。
   - （进阶保留）处理异常状态报错（如遮挡、无法识别）及视频留档监控。
3. **客户体验端 (Client)**：
   - 部署在驿站大门的交互终端。客户到达后进行刷脸比对（1:N）。
   - **进门动作**：识别成功后，Web 页面亮绿灯（模拟开门），数据库记录“进门日志”。同时，网页上高亮展示该客户当前在库的所有 4 位包裹码（模拟蜂鸣器与寻件指示灯）。
   - **出门动作**：客户拿取包裹后，再次刷脸，记录“出门日志”，界面恢复默认待机状态。
   - **查询快递信息**：客户可以在客户端查询自己的包裹
   - **申请遗漏**：发现遗漏物品用户可上报。

# 技术栈选型
* **后端框架**：FastAPI (负责异步 API、视频流分发、WebSocket/SSE 状态推送)
* **数据库**：SQLite (使用 sqlite3 或 SQLAlchemy 构建，处理并发读写)
* **人脸识别**：InsightFace (要求支持 ONNXRuntime-GPU 侧重准确率和稳定性)
* **图像捕获**：OpenCV (cv2)
* **前端展示**：原生 HTML/JS/CSS (Ajax 轮询 或 WebSocket)

# 核心架构与约束要求
本项目高度重视代码的工程化和模块化，具体要求如下：
1. **服务模块化**：`services` 目录下的每个功能（人脸、扫码、摄像头）必须是独立的文件夹。
2. **配置隔离**：每个服务文件夹内必须包含 `constants.py`，用于存放所有的阈值、路径、模拟数据等，方便集中修改。
3. **接口与Mock机制**：
   * **包裹扫码 (`barcode_scanner`)**：由其他同事开发，当前仅提供 Dummy 接口（预留入参和出参），返回模拟的4位包裹码。
   * **摄像头管理 (`camera_manager`)**：必须提供基类抽象，实现 `RealCamera`（调用物理设备）和 `DummyCamera`（播放本地测试视频或生成占位图像），方便无摄像头的设备进行本地调试。
4. **高内聚低耦合**：路由层 (`routers`) 只负责接收请求和返回响应，所有的业务逻辑与CV计算必须交由 `services` 层处理。
5. **Vibe Coding 微型文档（Micro-Documentation）机制**：为了建立高密度的上下文索引，所有模块文件夹内部必须包含一个 `.prompt/` 目录。对于该模块下的每一个核心源码文件，都需要在 `.prompt/` 中提供一个同名的 `.md` 解释文件。文件内容需采用“职责+接口+示例”的三段式精简格式，极度节约 Token 并指明外部调用方式。该文件夹应当包含模块总描述和每个文件的单独描述。

# 项目目录结构设计
请理解以下项目目录结构，在我们后续的代码编写中严格遵循此结构：

```text
📦 SmartStation
 ┣ 📂 database/
 ┃ ┣ 📂 .prompt/
 ┃ ┃ ┣ 📜 database.md           # database 模块总说明
 ┃ ┃ ┣ 📜 db_manager.md         # db_manager.py 的说明
 ┃ ┃ ┗ 📜 models.md             # models.py 的说明
 ┃ ┣ 📜 db_manager.py
 ┃ ┗ 📜 models.py
 ┃
 ┣ 📂 services/
 ┃ ┣ 📂 face_recognition/
 ┃ ┃ ┣ 📂 .prompt/              # 存放 core.md, constants.md 等
 ┃ ┃ ┣ 📜 __init__.py
 ┃ ┃ ┣ 📜 benchmark.py
 ┃ ┃ ┣ 📜 core.py
 ┃ ┃ ┣ 📜 constants.py
 ┃ ┃ ┗ 📜 test_face.py
 ┃ ┃
 ┃ ┣ 📂 barcode_scanner/
 ┃ ┃ ┣ 📂 .prompt/              # 存放 dummy_core.md 等
 ┃ ┃ ┣ 📜 __init__.py
 ┃ ┃ ┣ 📜 dummy_core.py
 ┃ ┃ ┣ 📜 constants.py
 ┃ ┃ ┗ 📜 test_barcode.py
 ┃ ┃
 ┃ ┗ 📂 camera_manager/
 ┃   ┣ 📂 .prompt/              # 存放 camera_manager.md, base.md 等
 ┃   ┣ 📂 pics/                 #存放静态图片作为dummy camera的显示对象
 ┃   ┣ 📜 __init__.py
 ┃   ┣ 📜 base.py               
 ┃   ┣ 📜 real_camera.py
 ┃   ┣ 📜 dummy_camera.py
 ┃   ┣ 📜 constants.py
 ┃   ┗ 📜 test_camera.py
 ┃
 ┣ 📂 routers/                  
 ┃ ┣ 📂 .prompt/                # 存放 API 路由规范说明
 ┃ ┣ 📜 backend_api.py          
 ┃ ┣ 📜 station_api.py          
 ┃ ┗ 📜 client_api.py           
 ┃
 ┣ 📂 templates/
 ┃ ┣ 📜 backend.html
 ┃ ┣ 📜 station.html
 ┃ ┗ 📜 client.html
 ┃
 ┣ 📂 core/
 ┃ ┣ 📂 .prompt/
 ┃ ┃ ┗ 📜 config.md
 ┃ ┗ 📜 config.py
 ┃
 ┣ 📂 labeldetect/          #同事实现的模块，为方便git管理放在外面
 ┃
 ┣ 📜 main.py
 ┗ 📜 requirements.txt
```
# 样例markdown
```text
# 模块：camera_manager
**职责**：提供对物理摄像头和虚拟摄像头的统一抽象与管理，解决 OpenCV 阻塞主线程以及多端同时拉流时的帧同步问题。
**设计模式**：后台守护线程(Daemon Thread)循环读取 + 线程锁(Lock)提取最新帧。
**对外暴露的核心类**：
- `BaseCamera`: 抽象基类
- `RealCamera`: 真实摄像头
- `DummyCamera`: 测试用的虚拟摄像头
```

# 已经完成的模块
目前services中的camera和face recognition已经完成测试。

# 交互指令
如果你已经完全理解了项目背景、技术栈、架构约束和目录结构，请回复：
“我已经完全掌握了 SmartStation 的架构设计与约束。请发送您希望开始实现的第一步（例如：1. 编写 database 模块，或 2. 编写 camera_manager 抽象层），我将为您输出生产级别的优质代码。”
请不要在第一次回复中输出任何实现代码。
如果你对这个项目的描述有任何疑问或者建议，也可以提出
扫码那里是dummy实现是因为具体的识别实现我的同事正在实现，在外面的文件夹中，里面的内容与我们项目的组织不同，到时候我想方法改一改即可