# SmartStation — Intelligent Unmanned Parcel Locker System

SmartStation is a **single-machine, web-based intelligent unmanned parcel locker system** that combines **facial recognition (1:N matching)** and **computer vision-based barcode scanning** to fully automate the parcel pickup workflow. Designed for rural and community postal stations, it eliminates the need for manual verification and enables 24/7 self-service operation.

- **Backend Management Terminal** — Admin dashboard for user registration, parcel board, and access logs
- **Station Worker Terminal** — Courier interface for scanning parcels into lockers with motor/buzzer hardware controls
- **Client Experience Terminal** — Customer-facing kiosk with face authentication for entry, exit, and parcel pickup

---

## Tech Stack

| Category           | Technology                                                       |
| ------------------ | ---------------------------------------------------------------- |
| Backend            | Python 3.9+, FastAPI, Uvicorn, Jinja2                            |
| Database           | SQLite (via aiosqlite, SQLAlchemy), WAL journal mode             |
| Face Recognition   | InsightFace (buffalo_s model), 512-dim embeddings, ONNX Runtime  |
| Computer Vision    | OpenCV (camera capture, MJPEG streaming, QR overlay blending)    |
| Barcode / QR       | pyzbar, qrcode                                                   |
| Hardware Control   | Hobot.GPIO, pySerial (RDK X5 GPIO — stepper motors, buzzers, LEDs) |
| Frontend           | Vanilla HTML/CSS/JS, WebSocket real-time updates                 |
| ML / AI            | PyTorch, Ultralytics YOLO (archived experimental modules)        |
| Validation         | Pydantic, Pydantic-Settings                                      |

---

## Features

- **1:N Face Recognition** — InsightFace-based 512-dim feature extraction with in-memory matrix for ultra-fast cosine similarity search. Hot-update caching without restart. Configurable threshold (default 0.45).
- **QR/Barcode Parcel Scanning** — Real-world decoding via pyzbar; demo mode with mock data when no camera is available; built-in QR generator for test labels.
- **Automated Parcel Workflow** — Courier scans a parcel QR → auto-registered into DB → automatic cabinet assignment (A01–D20 format). Status tracking: In Storage, Picked Up, Exception.
- **Entry/Exit State Machine** — Tracks IN / OUT / PICKUP per user. On entry, shows all active parcels. On exit, warns about forgotten parcels.
- **Real-time WebSocket Communication** — Three independent channels (admin, station, client) for live updates; auto-reconnect on disconnect.
- **Live MJPEG Video Streaming** — Two independent camera streams for station (parcel camera) and client (face camera); dummy camera fallback for development.
- **Admin Dashboard** — CRUD for users and parcels, photo upload, status filters, paginated access logs.
- **Hardware Integration (RDK X5)** — 3 motors (vertical lift, horizontal rotation, DC gear motor), 2 buzzers with LED indicators, GPIO control via Hobot.GPIO. Demo mode simulates hardware via WebSocket popups.

---

## Project Structure

```
├── main.py                 # FastAPI entry point + lifespan management
├── requirements.txt
├── core/                   # App config (Pydantic Settings) & global state
│   ├── config.py
│   └── state.py            # GlobalStateManager, ConnectionManager, face cache, hardware control
├── database/               # Data access layer (Repository pattern)
│   ├── models.py           # UserRepository, ParcelRepository, AccessLogRepository
│   ├── schemas.py          # Pydantic request/response models
│   ├── db_manager.py       # SQLite connection manager (WAL, foreign keys)
│   └── constants.py        # DB path, cabinet config, dummy data
├── routers/                # API route handlers
│   ├── backend_api.py      # /api/backend/* — User & Parcel CRUD, Logs
│   ├── station_api.py      # /api/station/* — Scan-in, motor/buzzer, video feed
│   └── client_api.py       # /api/client/* — Face auth, exit confirm, pickup
├── services/               # Independent service modules
│   ├── camera_manager/     # RealCamera / DummyCamera via factory pattern
│   ├── face_recognition/   # FaceRecognizer (InsightFace wrapper)
│   ├── scanner/            # QRScanner, QR generator
│   ├── pickup/             # Pickup confirmation logic
│   ├── motor/              # Stepper motor GPIO control (RDK X5)
│   └── BuzzerLight/        # Buzzer & LED GPIO control (RDK X5)
├── templates/              # Frontend HTML/CSS/JS
│   ├── backend.html        # Admin dashboard
│   ├── station.html        # Station worker page
│   ├── client.html         # Client kiosk page
│   ├── css/                # Stylesheets
│   └── js/                 # Client-side scripts
├── scripts/                # Utility scripts (start, export, project tree)
├── archive_services/       # Experimental modules (YOLO label detect, serial demo, etc.)
├── wendang/                # Chinese documentation (architecture doc, proposal, diagrams)
└── qr_codes/               # Generated QR code samples
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- Camera device
- RDK X5 board 

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/smartstation.git
cd smartstation

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

The system is configured through environment variables and per-module `constants.py` files:

| File                                       | Key Settings                                    |
| ------------------------------------------ | ----------------------------------------------- |
| `core/config.py`                           | `HOST`, `PORT`, `CORS_ORIGINS`, `DEBUG_MODE`    |
| `services/camera_manager/constants.py`     | `CAMERA_TYPE` (real/dummy), resolution          |
| `services/face_recognition/constants.py`   | `SIMILARITY_THRESHOLD`, inference providers     |
| `services/scanner/constants.py`            | `DEMO_MODE_ENABLED`                             |
| `database/constants.py`                    | Cabinet prefix ranges, dummy test data          |

### Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Access Points

| Page                  | URL                              |
| --------------------- | -------------------------------- |
| Client Kiosk          | `http://localhost:8000/client`   |
| Station Worker        | `http://localhost:8000/station`  |
| Backend Management    | `http://localhost:8000/backend`  |
| API Docs (Swagger)    | `http://localhost:8000/docs`     |

---

## API Overview

### Backend Management (`/api/backend`)
- `POST /users` — Register user with face photo
- `GET /users` — List users (paginated)
- `PUT /users/{id}/status` — Enable/disable user
- `DELETE /users/{id}` — Delete user (cascade)
- `GET /parcels` — List parcels (filterable by status)
- `POST /parcels` — Create parcel (manual check-in)
- `GET /logs` — Access logs with filtering

### Station Worker (`/api/station`)
- `POST /scan_in` — Scan parcel QR → auto check-in
- `POST /motor/{1,2}/{left,right}/{start,stop}` — Continuous motor control
- `POST /buzzer/{1,2}/{start,stop}` — Buzzer on/off
- `GET /video_feed` — MJPEG camera stream

### Client Kiosk (`/api/client`)
- `POST /access/auth` — Face authentication (entry/exit)
- `POST /access/exit_confirm` — Confirm exit after pickup
- `POST /confirm_pickup` — Face + QR verification for pickup
- `GET /video_feed` — MJPEG camera stream

### WebSocket
- `ws://localhost:8000/ws/{admin|station|client}` — Real-time channel

---

## Hardware Support (RDK X5)

| Component  | GPIO Pins           | Function              |
| ---------- | ------------------- | --------------------- |
| Motor 1    | PUL=13, DIR=11      | Vertical lift         |
| Motor 2    | PUL=16, DIR=15      | Horizontal rotation   |
| Motor 3    | CW=37, CCW=35       | DC gear motor         |
| Buzzer 1   | SIG=8, LED-G=22, LED-B=24 | Buzzer + green/blue LED |
| Buzzer 2   | SIG=10, LED-G=19, LED-B=21 | Buzzer + green/blue LED |

On non-RDK platforms, hardware modules automatically fall back to **demo simulation mode**, sending WebSocket notifications instead of physical GPIO signals.

---

## Architecture & Design Patterns

- **Repository Pattern** — `database/models.py`: stateless data access classes
- **Factory Pattern** — `camera_manager`: `get_camera()` returns `RealCamera` or `DummyCamera`
- **Singleton** — `core/state.py`: `GlobalStateManager` as single global service container
- **Lifespan Management** — FastAPI lifespan context manager for graceful startup/shutdown of hardware resources

