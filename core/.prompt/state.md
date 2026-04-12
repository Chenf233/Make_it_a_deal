# 文件：state.py
**职责**：系统全局状态总线。维护所有只能实例化一次的对象（CV引擎、摄像头）、内存级的高频业务缓存（人脸 1:N 特征矩阵），以及负责跨端实时通信（WebSocket）和硬件交互指令下发。
**接口**：
- **核心实例导出**：`app_state` (全局唯一管理器)。
- **硬件与通信接口**：
  - `app_state.ws_manager`: 访问 WebSocket 连接管理器。
  - `app_state.trigger_hardware_alert(action_type, payload)`: 触发前端弹窗（或串口硬件）报警。
- **人脸检索缓存接口**：
  - `app_state.build_face_cache(user_records)`: 启动时将 DB 数据构建为内存 Numpy 矩阵。
  - `app_state.add_single_face_to_cache(user_id, embedding)`: 管理端新增人脸后，热更新追加到内存矩阵。
  - `app_state.search_face(target_embedding, threshold) -> Optional[int]`: 传入单帧特征，在内存中执行极速 1:N 检索，返回命中的 user_id。
**外部调用示例**：
```python
from core.state import app_state

# 客户刷脸：从摄像头抓图并极速检索
success, frame = app_state.camera.get_frame()
emb = app_state.face_recognizer.extract_feature(frame)
matched_user_id = app_state.search_face(emb, threshold=0.5)

# 如果检测到出门漏取包裹，触发体验端报警弹窗 (并预留了真实的串口触发能力)
if has_forgotten_parcels:
    await app_state.trigger_hardware_alert(
        action_type="FORGET_ALERT", 
        payload={"msg": "您有包裹未取出", "parcels":["1234"]}
    )
```