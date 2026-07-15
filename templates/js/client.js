(function() {
    /* ============ 工具函数 ============ */
    function $(selector, parent) {
        return (parent || document).querySelector(selector);
    }

    function $$(selector, parent) {
        return Array.from((parent || document).querySelectorAll(selector));
    }

    /* ============ DOM 引用 ============ */
    const $idlePanel   = $('#state-idle');
    const $authPopup   = $('#auth-popup');
    const $popupTitle  = $('#popup-title');
    const $popupBody   = $('#popup-body');
    const $popupFooter = $('#popup-footer');
    const $notification = $('#notification');
    const $btnAuth     = $('#btn-auth');
    const $btnExit     = $('#btn-exit');

    /* ============ 常量 ============ */
    let notifTimer = null;
    const NOTIF_DURATION = 3500;
    let popupDismissTimer = null;
    const POPUP_AUTO_DISMISS = 8000;
    var pickupRetryTimer = null;
    var MAX_PICKUP_RETRIES = 30;
    var exitScanCancelFlag = false;
    var currentExitData = null;

    /* ============ 通知系统 ============ */
    function showNotification(msg, type) {
        if (notifTimer) clearTimeout(notifTimer);
        $notification.textContent = msg;
        $notification.className = 'notification ' + type + ' show';
        notifTimer = setTimeout(function() {
            $notification.className = 'notification';
        }, NOTIF_DURATION);
    }

    /* ============ 按钮加载态 ============ */
    function setBtnLoading(btn, loading) {
        if (loading) {
            btn.disabled = true;
            btn.classList.add('btn-loading');
            btn.dataset.originalText = btn.textContent;
        } else {
            btn.disabled = false;
            btn.classList.remove('btn-loading');
            if (btn.dataset.originalText) {
                btn.textContent = btn.dataset.originalText;
                delete btn.dataset.originalText;
            }
        }
    }

    /* ============ 弹窗控制 ============ */
    function showPopup() {
        $idlePanel.style.display = 'none';
        $authPopup.style.display = 'flex';
    }

    function dismissPopup() {
        if (popupDismissTimer) clearTimeout(popupDismissTimer);
        if (pickupRetryTimer) clearTimeout(pickupRetryTimer);
        popupDismissTimer = null;
        pickupRetryTimer = null;
        exitScanCancelFlag = true;
        currentExitData = null;
        $authPopup.style.display = 'none';
        $idlePanel.style.display = 'flex';
    }

    function startPopupAutoDismiss() {
        if (popupDismissTimer) clearTimeout(popupDismissTimer);
        popupDismissTimer = setTimeout(dismissPopup, POPUP_AUTO_DISMISS);
    }

    /* ============ 渲染 ============ */
    function renderParcelList(parcels) {
        if (!parcels || parcels.length === 0) {
            return '<p class="popup-empty">暂无在库包裹</p>';
        }
        return '<div class="popup-parcels">' + parcels.map(function(p) {
            return '<div class="pp-item">' +
                '<div class="pp-meta">' +
                    '<span class="pp-company">' + (p.company || '--') + '</span>' +
                    '<span class="pp-tracking">' + (p.tracking_no || '--') + '</span>' +
                '</div>' +
                '<div class="pp-cabinet">' +
                    '<span class="pp-cabinet-label">柜号</span>' +
                    '<span class="pp-cabinet-code">' + (p.cabinet_number || '--') + '</span>' +
                '</div>' +
            '</div>';
        }).join('') + '</div>';
    }

    /* ============ 刷脸认证 ============ */
    async function handleAuth(intent, btn) {
        setBtnLoading(btn, true);
        try {
            var resp = await fetch('/api/client/access/auth?intent=' + encodeURIComponent(intent), { method: 'POST' });
            var json = await resp.json();

            if (!resp.ok || json.code !== 200 || !json.data) {
                showNotification(json.message || '认证失败', 'error');
                return;
            }

            var data = json.data;
            if (data.action === 'ENTRY') {
                showEntryPopup(data);
            } else if (data.action === 'EXIT') {
                showExitPopup(data);
            }
        } catch (e) {
            showNotification('网络异常：' + e.message, 'error');
        } finally {
            setBtnLoading(btn, false);
        }
    }

    function showEntryPopup(data) {
        var user = data.user;
        var parcels = data.active_parcels || [];

        $popupTitle.textContent = '欢迎 ' + user.name;
        $popupBody.innerHTML = renderParcelList(parcels);
        $popupFooter.innerHTML = '<span class="popup-hint">点击任意位置关闭 · ' + (POPUP_AUTO_DISMISS / 1000) + 's 后自动关闭</span>';

        showPopup();
        startPopupAutoDismiss();
    }

    function showExitPopup(data) {
        currentExitData = data;
        renderExitPopup();
        showPopup();
    }

    function renderExitPopup() {
        var data = currentExitData;
        if (!data) return;

        var user = data.user;
        var expected = data.exit_expected_total || 0;
        var picked = data.exit_picked_count || 0;
        var missing = data.active_parcels || [];
        var missingCount = missing.length;

        $popupTitle.textContent = user.name + ' 请确认取件';

        var bodyHtml = '<div class="exit-stats">' +
            '<div class="exit-stat"><span class="es-label">应取</span><span class="es-value">' + expected + '</span></div>' +
            '<div class="exit-stat"><span class="es-label">已取</span><span class="es-value" style="color:var(--success)">' + picked + '</span></div>' +
            '<div class="exit-stat"><span class="es-label">未取</span><span class="es-value" style="color:' + (missingCount > 0 ? 'var(--warning)' : 'var(--success)') + '">' + missingCount + '</span></div>' +
            '</div>';

        if (missingCount > 0) {
            bodyHtml += '<p class="exit-warning">您还有 ' + missingCount + ' 个包裹未取走</p>';
            bodyHtml += renderParcelList(missing);
        } else {
            bodyHtml += '<p class="exit-ok">全部包裹已取走 ✓</p>';
        }

        $popupBody.innerHTML = bodyHtml;
        $popupFooter.innerHTML = '<div class="popup-actions">' +
            '<button id="btn-exit-scan" class="btn btn-primary">扫码出库</button>' +
            '<button id="btn-exit-confirm" class="btn btn-outline">确认离开</button>' +
            '<button id="btn-exit-back" class="btn btn-outline">我再看看</button>' +
            '</div>';

        $('#btn-exit-scan').addEventListener('click', handleExitScan);
        $('#btn-exit-confirm').addEventListener('click', handleExitConfirm);
        $('#btn-exit-back').addEventListener('click', dismissPopup);
    }

    function handleExitScan() {
        var btn = $('#btn-exit-scan');
        if (!btn) return;
        if (btn.classList.contains('cancelling')) {
            cancelExitScan(true);
            return;
        }

        if (pickupRetryTimer) clearTimeout(pickupRetryTimer);
        pickupRetryTimer = null;
        exitScanCancelFlag = false;
        btn.textContent = '取消出库';
        btn.classList.add('cancelling');
        showNotification('正在人脸验证并扫描包裹二维码...', 'warning');
        doExitScan(0, btn);
    }

    function resetExitScanButton(btn) {
        btn = btn || $('#btn-exit-scan');
        if (!btn) return;
        btn.disabled = false;
        btn.classList.remove('btn-loading');
        btn.classList.remove('cancelling');
        btn.textContent = '扫码出库';
        if (btn.dataset.originalText) delete btn.dataset.originalText;
    }

    function cancelExitScan(showMsg) {
        exitScanCancelFlag = true;
        if (pickupRetryTimer) clearTimeout(pickupRetryTimer);
        pickupRetryTimer = null;
        resetExitScanButton();
        if (showMsg) {
            showNotification('已取消扫码出库', 'warning');
        }
    }

    function applyPickupToExitData(parcel) {
        if (!currentExitData || !parcel || !parcel.tracking_no) return;

        var removed = false;
        var active = currentExitData.active_parcels || [];
        currentExitData.active_parcels = active.filter(function(p) {
            if (p.tracking_no === parcel.tracking_no) {
                removed = true;
                return false;
            }
            return true;
        });

        if (removed) {
            currentExitData.exit_picked_count = (currentExitData.exit_picked_count || 0) + 1;
        }
    }

    async function doExitScan(retryCount, btn) {
        if (exitScanCancelFlag) return;

        try {
            var resp = await fetch('/api/client/confirm_pickup', { method: 'POST' });
            var json = await resp.json();

            if (exitScanCancelFlag) return;

            if (!resp.ok || json.code !== 200 || !json.data) {
                var msg = json.message || '';

                if (msg.indexOf('未检测到人脸') !== -1) {
                    if (retryCount < MAX_PICKUP_RETRIES) {
                        showNotification('未检测到人脸，请正对摄像头... (' + (retryCount + 1) + '/' + MAX_PICKUP_RETRIES + ')', 'warning');
                        pickupRetryTimer = setTimeout(function() { doExitScan(retryCount + 1, btn); }, 1500);
                        return;
                    }
                    showNotification('身份验证超时，请正对摄像头后重试', 'error');
                    resetExitScanButton(btn);
                    return;
                }

                if (msg.indexOf('未检测到包裹') !== -1 || msg.indexOf('二维码') !== -1) {
                    if (retryCount < MAX_PICKUP_RETRIES) {
                        if (retryCount === 0) {
                            showNotification('人脸验证通过，即将扫描二维码', 'warning');
                        } else {
                            showNotification('请将包裹二维码对准摄像头... (' + (retryCount + 1) + '/' + MAX_PICKUP_RETRIES + ')', 'warning');
                        }
                        pickupRetryTimer = setTimeout(function() { doExitScan(retryCount + 1, btn); }, 1500);
                        return;
                    }
                    showNotification('扫描超时，请确认二维码在画面中后重试', 'error');
                    resetExitScanButton(btn);
                    return;
                }

                showNotification(msg || '扫码出库失败', 'error');
                resetExitScanButton(btn);
                return;
            }

            var parcel = json.data;
            pickupRetryTimer = null;
            exitScanCancelFlag = false;
            applyPickupToExitData(parcel);
            renderExitPopup();
            showNotification('出库成功：' + parcel.tracking_no + '  柜号：' + parcel.cabinet_number, 'success');
        } catch (e) {
            if (exitScanCancelFlag) return;
            showNotification('网络异常：' + e.message, 'error');
            resetExitScanButton(btn);
        }
    }

    async function handleExitConfirm() {
        var btn = $('#btn-exit-confirm');
        if (!btn) return;
        setBtnLoading(btn, true);
        try {
            var resp = await fetch('/api/client/access/exit_confirm', { method: 'POST' });
            var json = await resp.json();

            if (!resp.ok || json.code !== 200) {
                showNotification(json.message || '出门失败', 'error');
                return;
            }

            showNotification('再见，欢迎下次光临', 'success');
            dismissPopup();
        } catch (e) {
            showNotification('网络异常：' + e.message, 'error');
        } finally {
            setBtnLoading(btn, false);
        }
    }

    /* ============ WebSocket ============ */
    var ws = null;
    var wsReconnectTimer = null;

    function connectWebSocket() {
        if (ws && ws.readyState === WebSocket.OPEN) return;

        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(protocol + '//' + window.location.host + '/ws/client');

        ws.onopen = function() {
            if (wsReconnectTimer) {
                clearTimeout(wsReconnectTimer);
                wsReconnectTimer = null;
            }
        };

        ws.onmessage = function(event) {
            try {
                var payload = JSON.parse(event.data);
                if (payload.type === 'HARDWARE_ACTION') {
                    var msg = (payload.data && payload.data.msg) || '';
                    var action = payload.action;

                    if (action === 'CABINET_UNLOCK') {
                        showNotification(msg || '柜门已解锁', 'success');
                    } else if (action === 'CABINET_LOCK') {
                        showNotification(msg || '柜门已锁闭', 'success');
                    } else if (action === 'FORGET_ALERT') {
                        showNotification(msg || '请注意：您有包裹未取', 'warning');
                    } else {
                        showNotification(msg || '硬件触发: ' + action, 'success');
                    }
                }
            } catch (e) {
                // ignore parse errors
            }
        };

        ws.onclose = function() {
            scheduleReconnect();
        };

        ws.onerror = function() {};
    }

    function scheduleReconnect() {
        if (wsReconnectTimer) return;
        wsReconnectTimer = setTimeout(function() {
            wsReconnectTimer = null;
            connectWebSocket();
        }, 3000);
    }

    /* ============ 事件绑定 ============ */
    $btnExit.addEventListener('click', function() { handleAuth('exit', $btnExit); });
    $btnAuth.addEventListener('click', function() { handleAuth('entry', $btnAuth); });

    $authPopup.addEventListener('click', function(e) {
        if (e.target === $authPopup) dismissPopup();
    });

    /* ============ 初始化 ============ */
    connectWebSocket();
})();
