(function() {
    // ============ 常量 & 状态 ============
    const PAGES = {
        users: { skip: 0, limit: 20 },
        parcels: { skip: 0, limit: 20, status: '' },
        logs: { skip: 0, limit: 20, action: '' }
    };

    let currentView = 'users';

    // ============ 工具函数 ============
    function $(selector, parent = document) {
        return parent.querySelector(selector);
    }

    function $$(selector, parent = document) {
        return Array.from(parent.querySelectorAll(selector));
    }

    function showToast(msg, type = 'success') {
        const toast = $('#toast');
        toast.textContent = msg;
        toast.className = `toast ${type}`;
        setTimeout(() => toast.classList.add('hidden'), 2500);
    }

    function showLoading(tbody) {
        tbody.innerHTML = '<tr class="table-placeholder"><td colspan="10">加载中...</td></tr>';
    }

    // ============ 模态框通用 ============
    function openModal(id) {
        $(`#${id}`).classList.remove('hidden');
    }

    function closeModal(id) {
        $(`#${id}`).classList.add('hidden');
    }

    // ============ 视图切换 ============
    function switchView(view) {
        currentView = view;
        $$('.nav-item').forEach(el => el.classList.remove('active'));
        document.querySelector(`[data-view="${view}"]`).classList.add('active');
        $$('.view').forEach(v => v.classList.remove('active'));
        $(`#view-${view}`).classList.add('active');

        if (view === 'users') loadUsers();
        if (view === 'parcels') loadParcels();
        if (view === 'logs') loadLogs();
    }

    $$('.nav-item').forEach(item => {
        item.addEventListener('click', () => switchView(item.dataset.view));
    });

    // ============ 用户管理 ============
    async function loadUsers() {
        const tbody = $('#users-tbody');
        showLoading(tbody);
        const { skip, limit } = PAGES.users;
        try {
            const resp = await fetch(`/api/backend/users?skip=${skip}&limit=${limit}`);
            const json = await resp.json();
            if (!resp.ok) throw new Error(json.detail || '加载用户失败');
            renderUsers(json.data);
        } catch (e) {
            tbody.innerHTML = `<tr class="table-placeholder"><td colspan="6">加载出错：${e.message}</td></tr>`;
        }
    }

    function renderUsers(users) {
        const tbody = $('#users-tbody');
        if (!users || users.length === 0) {
            tbody.innerHTML = '<tr class="table-placeholder"><td colspan="6">暂无数据</td></tr>';
            return;
        }
        tbody.innerHTML = users.map(u => `
            <tr>
                <td>${u.id}</td>
                <td>${u.name || '-'}</td>
                <td>${u.phone}</td>
                <td><span class="status-badge ${u.is_active ? 'status-in' : 'status-out'}">${u.is_active ? '启用' : '禁用'}</span></td>
                <td>${u.created_at || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-primary btn-edit" data-id="${u.id}">编辑</button>
                    <button class="btn btn-sm ${u.is_active ? 'btn-secondary' : 'btn-primary'} btn-toggle-status" data-id="${u.id}" data-status="${u.is_active ? 0 : 1}">${u.is_active ? '禁用' : '启用'}</button>
                    <button class="btn btn-sm btn-danger btn-delete" data-id="${u.id}">删除</button>
                </td>
            </tr>
        `).join('');
        
        tbody.querySelectorAll('.btn-edit').forEach(btn => btn.addEventListener('click', () => editUser(btn.dataset.id)));
        tbody.querySelectorAll('.btn-toggle-status').forEach(btn => btn.addEventListener('click', () => toggleUserStatus(btn.dataset.id, btn.dataset.status)));
        tbody.querySelectorAll('.btn-delete').forEach(btn => btn.addEventListener('click', () => deleteUser(btn.dataset.id)));
        updatePaginationState('users', users.length);
    }

    $('#btn-add-user').addEventListener('click', () => {
        document.getElementById('form-user').reset();
        $('#user-id').value = '';
        $('#photo-group').style.display = 'block';
        $('#photo-preview').classList.add('hidden');
        $('#modal-user-title').textContent = '注册新用户';
        openModal('modal-user');
    });

    async function editUser(id) {
        try {
            const resp = await fetch(`/api/backend/users/${id}`);
            const json = await resp.json();
            if (!resp.ok) throw new Error(json.detail || '获取用户信息失败');
            const u = json.data;
            $('#user-id').value = u.id;
            $('#user-name').value = u.name || '';
            $('#user-phone').value = u.phone;
            $('#photo-group').style.display = 'none';
            $('#modal-user-title').textContent = '编辑用户';
            openModal('modal-user');
        } catch (e) {
            showToast(e.message, 'error');
        }
    }

    async function toggleUserStatus(id, newStatus) {
        try {
            const resp = await fetch(`/api/backend/users/${id}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: parseInt(newStatus) })
            });
            const json = await resp.json();
            if (!resp.ok) throw new Error(json.detail || '操作失败');
            showToast('状态更新成功');
            loadUsers();
        } catch (e) {
            showToast(e.message, 'error');
        }
    }

    function deleteUser(id) {
        openModal('modal-confirm');
        $('#confirm-message').textContent = '确定要删除该用户吗？此操作不可逆。';
        const handler = async () => {
            try {
                const resp = await fetch(`/api/backend/users/${id}`, { method: 'DELETE' });
                const json = await resp.json();
                if (!resp.ok) throw new Error(json.detail || '删除失败');
                showToast('用户已删除');
                loadUsers();
            } catch (e) {
                showToast(e.message, 'error');
            } finally {
                closeModal('modal-confirm');
                $('#confirm-ok').removeEventListener('click', handler);
            }
        };
        $('#confirm-ok').addEventListener('click', handler, { once: true });
    }

    // 用户表单提交
    $('#form-user').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = $('#user-id').value;
        const name = $('#user-name').value.trim();
        const phone = $('#user-phone').value.trim();
        const fileInput = $('#user-photo');
        const file = fileInput.files[0];

        if (!name || !phone) {
            showToast('姓名和手机号为必填', 'error');
            return;
        }
        if (!/^1[3-9]\d{9}$/.test(phone)) {
            showToast('手机号格式不正确', 'error');
            return;
        }

        if (!id) {
            if (!file) {
                showToast('请选择人脸照片', 'error');
                return;
            }
            const form = new FormData();
            form.append('name', name);
            form.append('phone', phone);
            form.append('file', file);
            try {
                const resp = await fetch('/api/backend/users', { method: 'POST', body: form });
                const json = await resp.json();
                if (!resp.ok) throw new Error(json.detail || '注册失败');
                showToast('用户注册成功');
                closeModal('modal-user');
                loadUsers();
            } catch (err) {
                showToast(err.message, 'error');
            }
        } else {
            try {
                const body = { name, phone };
                const resp = await fetch(`/api/backend/users/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                const json = await resp.json();
                if (!resp.ok) throw new Error(json.detail || '更新失败');
                showToast('用户信息已更新');
                closeModal('modal-user');
                loadUsers();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }
    });

    $('#user-photo').addEventListener('change', (e) => {
        const file = e.target.files[0];
        const preview = $('#photo-preview');
        if (file) {
            const reader = new FileReader();
            reader.onload = (ev) => {
                preview.src = ev.target.result;
                preview.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        } else {
            preview.classList.add('hidden');
        }
    });

    // ============ 包裹看板 ============
    async function loadParcels() {
        const tbody = $('#parcels-tbody');
        showLoading(tbody);
        const { skip, limit, status } = PAGES.parcels;
        let url = `/api/backend/parcels?skip=${skip}&limit=${limit}`;
        if (status) url += `&status=${status}`;
        try {
            const resp = await fetch(url);
            const json = await resp.json();
            if (!resp.ok) throw new Error(json.detail || '加载包裹失败');
            renderParcels(json.data);
        } catch (e) {
            tbody.innerHTML = `<tr class="table-placeholder"><td colspan="6">${e.message}</td></tr>`;
        }
    }

    function renderParcels(parcels) {
        const tbody = $('#parcels-tbody');
        if (!parcels || parcels.length === 0) {
            tbody.innerHTML = '<tr class="table-placeholder"><td colspan="7">暂无数据</td></tr>';
            updatePaginationState('parcels', 0);
            return;
        }
        const statusMap = { 1: '在库', 2: '已取件', 3: '异常' };
        tbody.innerHTML = parcels.map(p => `
            <tr>
                <td>${p.tracking_no || '-'}</td>
                <td>${p.company || '-'}</td>
                <td>${p.receiver_name || '-'}</td>
                <td>${p.receiver_phone || '-'}</td>
                <td>${p.cabinet_number || '-'}</td>
                <td>${statusMap[p.status] || '-'}</td>
                <td>${p.in_time || '-'}</td>
            </tr>
        `).join('');
        updatePaginationState('parcels', parcels.length);
    }

    $$('.filter-btn', $('#view-parcels')).forEach(btn => {
        btn.addEventListener('click', () => {
            btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            PAGES.parcels.status = btn.dataset.status;
            PAGES.parcels.skip = 0;
            loadParcels();
        });
    });

    // ============ 日志管理 ============
    async function loadLogs() {
        const tbody = $('#logs-tbody');
        showLoading(tbody);
        const { skip, limit, action } = PAGES.logs;
        let url = `/api/backend/logs?skip=${skip}&limit=${limit}`;
        if (action) url += `&action_type=${action}`;
        try {
            const resp = await fetch(url);
            const json = await resp.json();
            if (!resp.ok) throw new Error(json.detail || '加载日志失败');
            renderLogs(json.data);
        } catch (e) {
            tbody.innerHTML = `<tr class="table-placeholder"><td colspan="4">${e.message}</td></tr>`;
        }
    }

    function renderLogs(logs) {
        const tbody = $('#logs-tbody');
        if (!logs || logs.length === 0) {
            tbody.innerHTML = '<tr class="table-placeholder"><td colspan="4">暂无数据</td></tr>';
            return;
        }
        tbody.innerHTML = logs.map(l => `
            <tr>
                <td>${l.user_name || '-'}</td>
                <td><span class="status-badge ${l.action_type === 'IN' ? 'status-in' : 'status-out'}">${l.action_type}</span></td>
                <td>${l.created_at || '-'}</td>
                <td>${l.remark || ''}</td>
            </tr>
        `).join('');
        updatePaginationState('logs', logs.length);
    }

    $$('.filter-btn', $('#view-logs')).forEach(btn => {
        btn.addEventListener('click', () => {
            btn.parentElement.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            PAGES.logs.action = btn.dataset.action;
            PAGES.logs.skip = 0;
            loadLogs();
        });
    });

    // ============ 分页 ============
    function updatePaginationState(view, dataLength) {
        const prevBtn = $(`#${view}-prev`);
        const nextBtn = $(`#${view}-next`);
        const pageInfo = $(`#${view}-page-info`);
        const { skip, limit } = PAGES[view];

        prevBtn.disabled = (skip <= 0);
        nextBtn.disabled = (dataLength < limit);
        pageInfo.textContent = `第 ${Math.floor(skip / limit) + 1} 页`;
    }

    function setupPagination(view, loadFn) {
        const prevBtn = $(`#${view}-prev`);
        const nextBtn = $(`#${view}-next`);
        const pageInfo = $(`#${view}-page-info`);

        prevBtn.addEventListener('click', () => {
            if (PAGES[view].skip <= 0) return;
            PAGES[view].skip = Math.max(0, PAGES[view].skip - PAGES[view].limit);
            loadFn();
            pageInfo.textContent = `第 ${Math.floor(PAGES[view].skip / PAGES[view].limit) + 1} 页`;
        });

        nextBtn.addEventListener('click', () => {
            PAGES[view].skip += PAGES[view].limit;
            loadFn();
            pageInfo.textContent = `第 ${Math.floor(PAGES[view].skip / PAGES[view].limit) + 1} 页`;
        });
    }

    setupPagination('users', loadUsers);
    setupPagination('parcels', loadParcels);
    setupPagination('logs', loadLogs);

    // ============ 全局模态框关闭 ============
    document.querySelectorAll('.modal-close, .modal-cancel').forEach(btn => {
        btn.addEventListener('click', () => {
            btn.closest('.modal').classList.add('hidden');
        });
    });

    // ============ 初始加载 ============
    switchView('users');
})();