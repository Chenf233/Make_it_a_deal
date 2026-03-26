# 创建主目录结构
mkdir -p database/.prompt services/face_recognition/.prompt services/barcode_scanner/.prompt services/camera_manager/.prompt routers/.prompt templates core/.prompt

# 创建 database 文件
touch database/db_manager.py database/models.py
touch database/.prompt/database.md database/.prompt/db_manager.md database/.prompt/models.md

# 创建 face_recognition 文件
touch services/face_recognition/__init__.py services/face_recognition/core.py services/face_recognition/constants.py services/face_recognition/test_face.py
touch services/face_recognition/.prompt/face_recognition.md services/face_recognition/.prompt/core.md services/face_recognition/.prompt/constants.md

# 创建 barcode_scanner 文件
touch services/barcode_scanner/__init__.py services/barcode_scanner/dummy_core.py services/barcode_scanner/constants.py services/barcode_scanner/test_barcode.py
touch services/barcode_scanner/.prompt/barcode_scanner.md services/barcode_scanner/.prompt/dummy_core.md

# 创建 camera_manager 文件
touch services/camera_manager/__init__.py services/camera_manager/base.py services/camera_manager/real_camera.py services/camera_manager/dummy_camera.py services/camera_manager/constants.py services/camera_manager/test_camera.py
touch services/camera_manager/.prompt/camera_manager.md services/camera_manager/.prompt/base.md services/camera_manager/.prompt/real_camera.md services/camera_manager/.prompt/dummy_camera.md

# 创建 routers 文件
touch routers/backend_api.py routers/station_api.py routers/client_api.py
touch routers/.prompt/routers.md

# 创建 templates 和 core 文件
touch templates/backend.html templates/station.html templates/client.html
touch core/config.py core/.prompt/config.md

# 创建根目录文件
touch main.py requirements.txt

echo "✅ 目录树创建成功！"