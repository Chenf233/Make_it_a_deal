# SmartStation — 智能无人驿站自取系统

SmartStation 是一个**单机部署、基于 Web 的智能无人驿站自取系统**，集成了**人脸识别（1:N 比对）**与**视觉条码扫描**技术，实现包裹取件的全流程自动化。系统专为乡镇及社区邮政驿站设计，无需人工核验，支持 24 小时自助服务。

- **后台管理终端** — 管理员界面，支持用户注册、包裹看板、出入记录查询
- **驿站工作人员终端** — 快递员操作界面，支持扫描包裹入库及电机/蜂鸣器硬件控制
- **客户体验终端** — 面向用户的交互界面，通过人脸识别完成进出认证与包裹取件

---

## 技术栈

| 类别               | 技术                                                               |
| ------------------ | ------------------------------------------------------------------ |
| 后端框架           | Python 3.9+, FastAPI, Uvicorn, Jinja2                              |
| 数据库             | SQLite（基于 aiosqlite、SQLAlchemy），WAL 日志模式                 |
| 人脸识别           | InsightFace（buffalo_s 模型），512 维特征向量，ONNX Runtime        |
| 计算机视觉         | OpenCV（摄像头采集、MJPEG 推流、二维码叠加合成）                   |
| 条码/二维码        | pyzbar（解码），qrcode（生成）                                     |
| 硬件控制           | Hobot.GPIO、pySerial（RDK X5 开发板 GPIO — 步进电机、蜂鸣器、LED） |
| 前端               | 原生 HTML/CSS/JS，WebSocket 实时通信                                |
| 机器学习           | PyTorch、Ultralytics YOLO（已归档的实验模块）                      |
| 数据校验           | Pydantic, Pydantic-Settings                                        |

---

## 功能特性

- **1:N 人脸识别** — 基于 InsightFace 的 512 维特征提取，内存特征矩阵实现极速余弦相似度搜索。新增用户热更新无需重启。可配置相似度阈值（默认 0.45）。
- **二维码/条码包裹扫描** — 通过 pyzbar 进行实时解码；无摄像头时自动切换演示模式；内置二维码生成器用于制作测试面单。
- **自动化包裹流程** — 快递员扫描包裹二维码 → 自动录入数据库 → 自动分配柜号（A01–D20 格式）。状态追踪：已入库、已取件、异常。
- **进出状态机** — 记录每个用户的 IN / OUT / PICKUP 动作。进门时显示所有待取包裹；出门时检测并提醒遗忘包裹。
- **实时 WebSocket 通信** — 三个独立通道（admin / station / client）实时推送更新；断线自动重连。
- **实时 MJPEG 视频流** — 两路独立摄像头：工作站（包裹扫码摄像头）与客户终端（人脸识别摄像头）；开发模式下使用静态图像模拟。
- **后台管理看板** — 用户与包裹的增删改查、照片上传、状态筛选、分页出入记录。
- **硬件集成（RDK X5）** — 3 路电机（垂直升降、水平旋转、直流减速电机）、2 路蜂鸣器带 LED 指示灯，通过 Hobot.GPIO 控制。演示模式通过 WebSocket 弹窗模拟硬件动作。

---

## 项目结构

```
├── main.py                 # FastAPI 入口 + 生命周期管理
├── requirements.txt
├── core/                   # 应用配置（Pydantic Settings）& 全局状态
│   ├── config.py
│   └── state.py            # GlobalStateManager、ConnectionManager、人脸缓存、硬件控制
├── database/               # 数据访问层（Repository 模式）
│   ├── models.py           # UserRepository、ParcelRepository、AccessLogRepository
│   ├── schemas.py          # Pydantic 请求/响应模型
│   ├── db_manager.py       # SQLite 连接管理器（WAL、外键）
│   └── constants.py        # 数据库路径、柜号配置、测试数据
├── routers/                # API 路由处理
│   ├── backend_api.py      # /api/backend/* — 用户与包裹 CRUD、记录查询
│   ├── station_api.py      # /api/station/* — 扫码入库、电机/蜂鸣器控制、视频流
│   └── client_api.py       # /api/client/* — 人脸认证、出门确认、取件
├── services/               # 独立服务模块
│   ├── camera_manager/     # RealCamera / DummyCamera 工厂模式
│   ├── face_recognition/   # FaceRecognizer（InsightFace 封装）
│   ├── scanner/            # QRScanner、二维码生成器
│   ├── pickup/             # 取件确认逻辑
│   ├── motor/              # 步进电机 GPIO 控制（RDK X5）
│   └── BuzzerLight/        # 蜂鸣器 & LED GPIO 控制（RDK X5）
├── templates/              # 前端 HTML/CSS/JS
│   ├── backend.html        # 后台管理页面
│   ├── station.html        # 工作站页面
│   ├── client.html         # 客户终端页面
│   ├── css/                # 样式表
│   └── js/                 # 客户端脚本
├── scripts/                # 工具脚本（启动、导出依赖、项目树）
├── archive_services/       # 实验模块（YOLO 面单检测、串口演示等）
├── wendang/                # 项目文档（技术架构文档、方案书、架构图）
└── qr_codes/               # 生成的二维码样本
```

---

## 快速开始

### 环境要求

- Python 3.9+
- 摄像头
- RDK X5 开发板
### 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/smartstation.git
cd smartstation

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate          # Windows

# 安装依赖
pip install -r requirements.txt
```

### 配置

系统通过环境变量和各模块的 `constants.py` 文件进行配置：

| 文件                                           | 关键配置项                                     |
| ---------------------------------------------- | ---------------------------------------------- |
| `core/config.py`                               | `HOST`、`PORT`、`CORS_ORIGINS`、`DEBUG_MODE`   |
| `services/camera_manager/constants.py`         | `CAMERA_TYPE`（real/dummy）、分辨率             |
| `services/face_recognition/constants.py`       | `SIMILARITY_THRESHOLD`、推理引擎 providers     |
| `services/scanner/constants.py`                | `DEMO_MODE_ENABLED`                            |
| `database/constants.py`                        | 柜号前缀范围、测试数据                         |

### 启动

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 访问地址

| 页面                 | URL                              |
| -------------------- | -------------------------------- |
| 客户终端             | `http://localhost:8000/client`   |
| 工作站               | `http://localhost:8000/station`  |
| 后台管理             | `http://localhost:8000/backend`  |
| API 文档（Swagger）  | `http://localhost:8000/docs`     |

---

## API 概览

### 后台管理（`/api/backend`）
- `POST /users` — 注册用户（含人脸照片）
- `GET /users` — 用户列表（分页）
- `PUT /users/{id}/status` — 启用/禁用用户
- `DELETE /users/{id}` — 删除用户（级联）
- `GET /parcels` — 包裹列表（按状态筛选）
- `POST /parcels` — 创建包裹（手动入库）
- `GET /logs` — 出入记录（含筛选）

### 工作站（`/api/station`）
- `POST /scan_in` — 扫描包裹二维码 → 自动入库
- `POST /motor/{1,2}/{left,right}/{start,stop}` — 连续电机控制
- `POST /buzzer/{1,2}/{start,stop}` — 蜂鸣器开关
- `GET /video_feed` — MJPEG 摄像头视频流

### 客户终端（`/api/client`）
- `POST /access/auth` — 人脸认证（进门/出门）
- `POST /access/exit_confirm` — 取件后确认出门
- `POST /confirm_pickup` — 人脸+二维码双重验证取件
- `GET /video_feed` — MJPEG 摄像头视频流

### WebSocket
- `ws://localhost:8000/ws/{admin|station|client}` — 实时通信通道

---

## 硬件支持（RDK X5）

| 组件     | GPIO 引脚               | 功能                   |
| -------- | ----------------------- | ---------------------- |
| 电机 1   | PUL=13, DIR=11          | 垂直升降               |
| 电机 2   | PUL=16, DIR=15          | 水平旋转               |
| 电机 3   | CW=37, CCW=35           | 直流减速电机           |
| 蜂鸣器 1 | SIG=8, LED-G=22, LED-B=24 | 蜂鸣器 + 绿/蓝 LED   |
| 蜂鸣器 2 | SIG=10, LED-G=19, LED-B=21 | 蜂鸣器 + 绿/蓝 LED   |

在非 RDK 平台上，硬件模块自动降级为**演示模拟模式**，通过 WebSocket 发送通知代替物理 GPIO 信号。

---

## 架构设计模式

- **Repository 模式** — `database/models.py`：无状态数据访问类
- **工厂模式** — `camera_manager`：`get_camera()` 根据配置返回 `RealCamera` 或 `DummyCamera`
- **单例模式** — `core/state.py`：`GlobalStateManager` 作为全局服务容器
- **生命周期管理** — FastAPI lifespan 上下文管理器，优雅启停硬件资源

