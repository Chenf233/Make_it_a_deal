# SmartStation — 项目文档 (2026-06-20)

## 环境

| 项目 | 内容 |
|------|------|
| 远程主机 | RDK X5, `sunrise@192.168.137.58`, 密码 `sunrise` |
| 项目路径 | `~/SMStation/deal/` |
| Conda 环境 | `~/SMStation/env/` (Python 3.11.15) |
| 连接方式 | 本地 Win → Posh-SSH (PowerShell SSH.NET 模块) |

## 目录结构

```
~/SMStation/
├── env/                        # Conda 环境 (含手动复制的 Hobot.GPIO)
├── deal/                       # 项目主代码 (Git 仓库)
│   ├── main.py                 # FastAPI 入口
│   ├── core/
│   │   ├── config.py           # Settings (host 0.0.0.0, port 8000)
│   │   └── state.py            # 全局状态 (camera/face_recognizer/scanner)
│   ├── database/
│   │   ├── db_manager.py       # SQLite 连接管理 (WAL + foreign_keys ON)
│   │   ├── models.py           # User/Parcel/AccessLogRepository
│   │   ├── schemas.py          # Pydantic 模型
│   │   └── data/smart_station.db
│   ├── services/
│   │   ├── motor/              # 步进电机控制（双电机）
│   │   │   └── __init__.py     # half_turn(motor1) / half_turn2(motor2)
│   │   ├── camera_manager/     # 摄像头 (real/dummy)
│   │   ├── face_recognition/   # InsightFace (buffalo_s, CPU)
│   │   ├── pickup/             # 取件业务
│   │   └── scanner/            # 二维码扫描 (含 DEMO 模式)
│   ├── routers/
│   │   ├── backend_api.py      # 后台管理 API
│   │   ├── client_api.py       # 客户端 API
│   │   └── station_api.py      # 站点操作 API（含电机控制）
│   └── templates/
│       ├── backend.html/js     # 后台管理页面
│       ├── client.html/js      # 客户自助页面
│       └── station.html        # 站点操作页面（含双电机按钮）
└── scripts/
```

## 三个前端页面

| 页面 | URL | 用途 |
|------|-----|------|
| 客户自助 | `/client` | 刷脸进门、扫码取件、出口确认 |
| 后台管理 | `/backend` | 注册/删除用户、查询包裹和日志 |
| 站点操作 | `/station` | 快递员扫码入库、电机控制 |

## 核心业务流程

1. 管理员注册用户（含人脸照片）
2. 快递员在站点页面扫码入库包裹
3. 客户在 client 页面刷脸 → 进门（ENTRY）→ 展示待取包裹 → 扫码取件
4. 客户再刷脸 → 出门（EXIT）→ 弹窗确认 → 锁柜

## API 路由速查

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/station/scan_in` | 扫码入库包裹 |
| POST | `/api/station/motor/left` | 电机1 下降半圈 |
| POST | `/api/station/motor/right` | 电机1 上升半圈 |
| POST | `/api/station/motor/left/start` | 电机1 持续下降（长按） |
| POST | `/api/station/motor/left/stop` | 电机1 停止 |
| POST | `/api/station/motor/right/start` | 电机1 持续上升（长按） |
| POST | `/api/station/motor/right/stop` | 电机1 停止 |
| POST | `/api/station/motor2/left` | 电机2 左旋半圈 |
| POST | `/api/station/motor2/right` | 电机2 右旋半圈 |
| POST | `/api/station/motor2/left/start` | 电机2 持续左旋（长按） |
| POST | `/api/station/motor2/left/stop` | 电机2 停止 |
| POST | `/api/station/motor2/right/start` | 电机2 持续右旋（长按） |
| POST | `/api/station/motor2/right/stop` | 电机2 停止 |
| POST | `/api/station/buzzer/1/start` | 蜂鸣器1 循环响 |
| POST | `/api/station/buzzer/1/stop` | 蜂鸣器1 停止 |
| POST | `/api/station/buzzer/2/start` | 蜂鸣器2 循环响 |
| POST | `/api/station/buzzer/2/stop` | 蜂鸣器2 停止 |
| GET | `/api/station/video_feed` | 摄像头 MJPEG 视频流 |

## 电机硬件接线

| 电机 | 驱动器 | DIR | PUL | 细分 | 半圈脉冲 |
|------|--------|-----|-----|------|---------|
| 电机1 (17HS4401) | TB6600 | GPIO11 | GPIO13 | 1/4 (800脉冲/圈) | 400 |
| 电机2 (17HS4401) | TB6600 | GPIO15 | GPIO16 | 1/4 (800脉冲/圈) | 400 |

拨码开关：S1=ON S2=OFF S3=OFF (1/4细分)，S4=ON S5=ON S6=OFF (电流 ~1.5A)，电源 12V DC。

## 已修改文件

| 文件 | 改动内容 |
|------|----------|
| `database/models.py` | `AccessLogRepository` 新增 `delete_logs_by_user_id(user_id)` 静态方法 |
| `routers/backend_api.py` | `delete_user()` 先清理关联日志再硬删除，修复外键约束错误 |
| `routers/station_api.py` | 新增电机1(`/motor/left\|right`)和电机2(`/motor2/left\|right`)端点 |
| `services/motor/__init__.py` | **新建** 双电机控制模块，`half_turn()` / `half_turn2()` / `start_continuous()` / `stop_continuous()` |
| `services/BuzzerLight/__init__.py` | **新建** 双蜂鸣器 + LED 控制，`beep_twice()` / `start_loop()` / `stop_loop()` |
| `database/models.py` | `AccessLogRepository` 新增 `delete_logs_by_user_id()` 静态方法 |
| `templates/station.html` | 双组电机按钮 + 长按连续转动 + 蜂鸣器控制 + JS |
| `templates/js/backend.js` | `json.detail` → `json.message`，修复错误展示 |
| Conda 环境 | 将系统 `Hobot.GPIO` (Python 3.10) 复制到 conda env site-packages |

## 已修复 Bug

| Bug | 位置 | 状态 |
|-----|------|------|
| 删除用户报错"可能存在关联数据"（外键约束） | `routers/backend_api.py` `delete_user()` | ✅ |
| 前端错误弹窗只显示"删除失败" | `templates/js/backend.js` | ✅ |

## 启动与管理

```bash
# 启动（首次约 22 秒，不加 --reload）
screen -dmS smstation bash -c 'cd ~/SMStation/deal && exec ~/SMStation/env/bin/uvicorn main:app --host 0.0.0.0 --port 8000'

# 管理
screen -ls                                    # 查看会话
screen -r smstation                           # 进入日志（Ctrl+A D 脱离）
screen -S smstation -X quit                   # 停止
pkill -f 'uvicorn main:app'                   # 强制停止
```

## Posh-SSH 常用命令

```powershell
# 连接
$secPasswd = ConvertTo-SecureString 'sunrise' -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential('sunrise', $secPasswd)
Remove-SSHSession -SessionId 0 -ErrorAction SilentlyContinue
$null = New-SSHSession -ComputerName '192.168.137.58' -Credential $cred -AcceptKey -Force

# 执行命令（注意 PowerShell 会解析 {} 和 $，需转义）
$r = Invoke-SSHCommand -SessionId 0 -Command "ls ~/"
$r.Output -join "`n"
```

## 注意点

- `Hobot.GPIO` 是系统级包（Python 3.10），不在 conda 中，需手动复制到环境
- 首次启动约 22 秒，不要加 `--reload`
- 修改 HTML 后浏览器需硬刷新（Ctrl+F5）
- 重启服务需 `pkill` + 重新 `screen` 启动
- 每次 `Invoke-SSHCommand` 需在同一 PowerShell 进程中创建和使用 session，变量不会跨调用保持

## 未测试路径/待办

| # | 路径 | 涉及代码 | 风险 |
|---|------|----------|------|
| 1 | **出门流程** | `client_auth()` EXIT 分支 → `get_last_action()` → `check_exit_status()` → 前端 `showExitPopup()` | 高 |
| 2 | **出门确认** | `client_exit_confirm()` → `add_log(OUT)` → `CABINET_LOCK` WS 广播 | 高 |
| 3 | **后端注册用户** | `backend_api.py` `register_user` → `run_in_executor` | 高 |
| 4 | 出口弹窗"确认离开"按钮 | `handleExitConfirm()` → 返回 idle | 中 |
| 5 | 出口弹窗"我再看看"按钮 | `dismissPopup()` | 低 |
| 6 | 入口弹窗 8s 自动关闭 | `startPopupAutoDismiss()` | 低 |
| 7 | **station 电机1 控制** | `motorControl()` → `POST /motor/left\|right` → `half_turn()` | 中 |
| 8 | **station 电机2 控制** | `motorControl2()` → `POST /motor2/left\|right` → `half_turn2()` | 中 |
| 9 | **电机连续转动（长按）** | `pressStart()` → `POST /motor/left/start` → `start_continuous()` | 中 |
| 10 | **蜂鸣器启停** | `buzzerStart()` → `POST /buzzer/1/start` → `start_loop()` | 低 |

## 本次对话 (2026-06-23)

### 新增服务

| 文件 | 内容 |
|------|------|
| `services/BuzzerLight/__init__.py` | **新建** 双蜂鸣器 + LED GPIO 控制模块，引脚 8/10 (BOARD)，import 时自动 `init()` 置 LOW |

### 目录结构更新

```
services/
├── BuzzerLight/            # 双蜂鸣器 + LED 控制（新增）
│   └── __init__.py         # init(), beep_twice(), start_loop(), stop_loop()
├── motor/                  # 双电机控制（含连续转动）
│   └── __init__.py         # half_turn(), half_turn2(), start_continuous(), stop_continuous()
├── camera_manager/
├── face_recognition/
├── pickup/
└── scanner/
```

### 连接说明

| 项目 | 内容 |
|------|------|
| 蜂鸣器1 | 引脚 8 (BOARD) |
| 蜂鸣器2 | 引脚 10 (BOARD) |
| LED1_Green | 引脚 22 (BOARD) |
| LED1_Blue | 引脚 24 (BOARD) |
| LED2_Green | 引脚 19 (BOARD) |
| LED2_Blue | 引脚 21 (BOARD) |
| 初始化行为 | import 时自动置 LOW，蜂鸣器静默，LED 默认蓝灯 |

---

## 本次对话 (2026-06-28) — 程序中断恢复 + 新增功能

### 恢复说明

程序运行中意外中断（SSH 会话断开），RDK 端文件已保存但未同步到本地。本次通过 SSH 读取 RDK 端所有变动文件，将新增功能完整记录至此文档。

### 新增功能

#### Motor 模块升级

| 项 | 说明 |
|---|------|
| 函数 | `start_continuous(motor_id, direction)` / `stop_continuous(motor_id)` — 连续转动 |
| 函数 | `rotate_turns(motor_id, direction, turns)` — 按圈数旋转 |
| 机制 | 基于 `threading.Event` 的守护线程 |
| 脉冲 | 800µs 延迟，1 圈 = 800 脉冲（1/4 细分） |
| 前端配合 | 长按 500ms 后连续转，松手停止 |

#### BuzzerLight 模块升级

| 项 | 说明 |
|---|------|
| 新增引脚 | LED1_Green=22, LED1_Blue=24, LED2_Green=19, LED2_Blue=21 |
| 新增函数 | `beep_twice(pin)`, `start_loop(pin)`, `stop_loop(pin)` |
| LED 逻辑 | 蜂鸣响亮绿灯，蜂鸣停亮蓝灯 |
| 循环蜂鸣 | threading 守护线程，1s 响 + 0.5s 停 + 0.5s 响 + 1s 停 |

#### Station API — 新增端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/station/motor/left/start` | 电机1 持续下降 |
| POST | `/api/station/motor/left/stop` | 电机1 停止 |
| POST | `/api/station/motor/right/start` | 电机1 持续上升 |
| POST | `/api/station/motor/right/stop` | 电机1 停止 |
| POST | `/api/station/motor2/left/start` | 电机2 持续左旋 |
| POST | `/api/station/motor2/left/stop` | 电机2 停止 |
| POST | `/api/station/motor2/right/start` | 电机2 持续右旋 |
| POST | `/api/station/motor2/right/stop` | 电机2 停止 |
| POST | `/api/station/buzzer/1/start` | 蜂鸣器1 循环响 |
| POST | `/api/station/buzzer/1/stop` | 蜂鸣器1 停止 |
| POST | `/api/station/buzzer/2/start` | 蜂鸣器2 循环响 |
| POST | `/api/station/buzzer/2/stop` | 蜂鸣器2 停止 |
| POST | `/api/station/move_to_a02` | 电机2 左旋 20 圈 → 入库 DEMO_DATA_LIST[0]，取件码=A02 |

#### Database

| 文件 | 改动 |
|------|------|
| `database/models.py` | `AccessLogRepository` 新增 `delete_logs_by_user_id(user_id)` |

#### Station 模板

| 文件 | 改动 |
|------|------|
| `templates/station.html` | 长按连续转动 JS + 蜂鸣器控制 + "A01→A02" 移库入库按钮 |

### 修复 Bug

| Bug | 原因 | 修复 |
|-----|------|------|
| 入库时间与现实时间差 8 小时 | SQLite `CURRENT_TIMESTAMP` 返回 UTC | `add_parcel()` / `update_parcel_status()` / `update_parcel()` / `add_log()` 改用 `datetime.now()` 传入本地 CST |

### 已修改文件总表

| 文件 | 改动内容 |
|------|----------|
| `services/motor/__init__.py` | 新增 `start_continuous()` / `stop_continuous()` / `rotate_turns()` + threading |
| `services/BuzzerLight/__init__.py` | 新增 LED + `beep_twice()` + `start_loop()` / `stop_loop()` |
| `routers/station_api.py` | 新增 8 个连续转动 + 4 个蜂鸣器 + `move_to_a02` 端点 |
| `database/models.py` | 新增 `delete_logs_by_user_id()`；修复时间用本地 CST |
| `routers/backend_api.py` | `delete_user()` 先清理日志再删除 |
| `templates/station.html` | 长按连续转动 UI + 蜂鸣器 UI + A01→A02 按钮 + JS |

---

## 本次对话 (2026-06-30) — 程序恢复 + 记录 RDK 遗漏改动

### 背景

本日连接 RDK 时发现程序因 `services/scanner/constants.py` 为空文件 (0 字节) 而崩溃。读取 RDK 全量文件并与本地仓库比对，发现此前若干改动未记录在 `re1.md` 中。

---

### 新增功能（此前遗漏记录）

#### 电机3 (Motor3) 控制

| 文件 | 内容 |
|------|------|
| `services/motor/__init__.py` | 新增 `motor3_cw(duration)` / `motor3_ccw(duration)` — 直连 GPIO 控制，引脚 35/37 (BOARD)，无细分无步进，纯高电平持续 |
| `routers/station_api.py` | 新增 `POST /api/station/motor3/cw`（顺时针5秒）、`POST /api/station/motor3/ccw`（逆时针5秒） |
| `templates/station.html` | 新增电机3按钮 + `motor3Control()` JS 函数 |

电机3接线：
| 功能 | GPIO BOARD 引脚 |
|------|---------------|
| 电机3 顺时针 | 37 |
| 电机3 逆时针 | 35 |

> 注意：电机3 与电机1/2 原理不同——电机1/2 使用步进驱动器 TB6600（DIR+PUL），电机3 直连 GPIO 高低电平控制，无细分，持续时长控制旋转角度。

#### 快捷操作 `move_to_a02` 升级

`routers/station_api.py` 中 `move_to_a02` 新增电机3 参与：
```
电机2 左旋 20 圈 → 电机3 顺时针 10 秒 → 电机2 右旋 20 圈
```

#### BuzzerLight 模块

`services/BuzzerLight/__init__.py` — 双蜂鸣器（引脚 8/10）+ 双色 LED（引脚 22/24 绿蓝、19/21 绿蓝），import 时自动 init()，蜂鸣响绿灯，蜂鸣停蓝灯。

---

### 配置变更（此前遗漏记录）

| 文件 | 改动 |
|------|------|
| `services/camera_manager/constants.py` | `DEMO_OVERLAY_ENABLED = True` → `False` |
| `services/scanner/constants.py` | `DEMO_MODE_ENABLED = True` → `False` |

---

### 本次会话操作 (2026-06-30)

#### 修复程序崩溃

RDK 端 `services/scanner/constants.py` 为空文件 (0 字节)，导致启动时 `ImportError: cannot import name 'BBOX_COLOR'`。将本地完整文件通过 SCP 上传修复。

#### 变更内容

| 文件 | 改动 |
|------|------|
| `services/camera_manager/constants.py` | `CAMERA_TYPE = "dummy"` → `"real"` |
| `services/scanner/constants.py` | `DEMO_DATA_LIST[0]`：`receiver_name` → `"我不想上学"`，`receiver_phone` → `"13800000000"` |

#### 启动命令

```bash
screen -dmS smstation bash -c 'cd ~/SMStation/deal && exec ~/SMStation/env/bin/uvicorn main:app --host 0.0.0.0 --port 8000'
```

#### 验证状态

| 项目 | 状态 |
|------|------|
| Screen 会话 `smstation` | ✅ 已分离运行 |
| Uvicorn 进程 | ✅ 运行中，端口 8000 |
| InsightFace 模型 | ✅ `buffalo_s` 全模型加载 (CPU) |
| 导入错误 `BBOX_COLOR` | ✅ 已修复 |
| 摄像头模式 | ✅ 已切换为 `real` |
| 快捷入库默认值 | ✅ `"我不想上学"` / `"13800000000"` |

#### 已修改文件总表（含本次 + 补充遗漏）

| 文件 | 改动 |
|------|------|
| `services/scanner/constants.py` | `ImportError` 修复；`DEMO_MODE_ENABLED = False`；`DEMO_DATA_LIST[0]` receiver 改为 `"我不想上学"` / `"13800000000"` |
| `services/camera_manager/constants.py` | `CAMERA_TYPE = "real"`；`DEMO_OVERLAY_ENABLED = False` |
| `services/motor/__init__.py` | 新增 `motor3_cw()` / `motor3_ccw()` + 引脚 37/35 |
| `services/BuzzerLight/__init__.py` | 新建双蜂鸣器 + LED 模块（RDK 端独有，本地未同步） |
| `routers/station_api.py` | 新增 `/motor3/cw`、`/motor3/ccw` 端点；`move_to_a02` 集成电机3 |
| `templates/station.html` | 新增电机3 按钮 + JS |

---

## 本次对话 (2026-06-30 续) — 客户端复原 + 杂项修复

### 变更内容

| 文件 | 改动 |
|------|------|
| `templates/client.html` | 按钮 "刷脸认证" → `"刷脸进门"`；新增 "刷脸查询包裹" 按钮 (`handleAuth()`)；后来复原独立 "扫码取件" 按钮 |
| `templates/js/client.js` | 添加 `$btnAuthQuery`；弹窗 (ENTRY/EXIT) 内临时加入 "扫码取件" 按钮后复原；恢复原始 `startPickup()/doPickup()/cancelPickup()` 取件流程（30次重试，人脸→二维码）；恢复原始入口弹窗（仅自动关闭提示）、出口弹窗（确认离开+我再看看） |
| `routers/station_api.py` | 交换蜂鸣器1/2 逻辑：`BUZZER1_PIN=8` → `buzzer2` 循环响，`BUZZER2_PIN=10` → `buzzer1` 循环响；`move_to_a02` 执行前增加 `asyncio.sleep(5)` |
| `services/motor/__init__.py` | 模块级别增加 `init()` 调用 (第29行)，确保 import 时 motor3 引脚 (35/37) 置 LOW |

### 关键要点

- 客户端取件流程最终恢复为原始设计：idle 面板独立 "扫码取件" 按钮，点击后 30 次重试（先人脸验证，再二维码扫描），而非在弹窗内操作
- 蜂鸣器引脚交换：之前接反，`/api/station/buzzer/1/start` 实际控制的是引脚 10，现更正为引脚 8
- `move_to_a02` 加 5 秒延迟：防止电机动作冲突
- motor3 增加模块级初始化：确保引脚在导入时即输出 LOW，避免复位后高电平导致意外转动
