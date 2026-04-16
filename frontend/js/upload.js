const API_URL = "http://127.0.0.1:8000";


const dropZone = document.getElementById('drop-zone');
const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('file-input');
const progressContainer = document.getElementById('upload-progress-container');
const emptyState = document.getElementById('empty-state');
const fileTable = document.getElementById('file-table');
const fileList = document.getElementById('file-list');

// Chỉ thực thi event nếu đúng trang upload
if (dropZone && uploadBtn && fileInput) {
    dropZone.addEventListener('click', (e) => {
        if (e.target === dropZone) fileInput.click();
    });
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });
}

function getAuthToken() {
    return localStorage.getItem("mycloud_token");
}

function authHeaders() {
    const token = getAuthToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
}

function showEmptyState(show) {
    if (!emptyState || !fileTable) return;
    emptyState.classList.toggle('hidden', !show);
    fileTable.classList.toggle('hidden', show);
}

function clearFileTable() {
    if (!fileList) return;
    fileList.innerHTML = '';
}

function renderFilesFromBackend(items) {
    clearFileTable();

    if (!items.length) {
        showEmptyState(true);
        return;
    }

    showEmptyState(false);
    items.forEach((file) => addFileToTable(normalizeBackendFileItem(file), { prepend: false }));
}

function normalizeBackendFileItem(file) {
    return {
        file_name: file.file_name || file.name || 'Untitled',
        size_bytes: file.size_bytes ?? file.size ?? 0,
        file_url: file.file_url || file.blob_url || '',
        azure_name: file.azure_name || file.name || '',
        created_at: file.created_at || new Date().toISOString(),
    };
}

async function loadUploadedFiles() {
    const token = getAuthToken();
    if (!token) {
        logout();
        return;
    }

    try {
        const response = await fetch(`${API_URL}/files/list`, {
            headers: authHeaders(),
        });

        if (response.status === 401) {
            logout();
            return;
        }

        if (!response.ok) {
            throw new Error(`Không tải được danh sách file (${response.status})`);
        }

        const payload = await response.json();
        const items = Array.isArray(payload?.items) ? payload.items : [];
        renderFilesFromBackend(items);
    } catch (error) {
        console.error('Load uploaded files error:', error);
        showEmptyState(true);
    }
}

function humanFileSize(bytes) {
    const size = Number(bytes || 0);
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`;
    if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(2)} MB`;
    return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function addFileToTable(fileMeta, options = {}) {
    if (!fileList) return;
    const { prepend = true } = options;
    showEmptyState(false);

    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td class="file-name-cell">
            <i class="fa-solid fa-file-pdf"></i> ${fileMeta.file_name}
        </td>
        <td>${humanFileSize(fileMeta.size_bytes)}</td>
        <td>${new Date(fileMeta.created_at).toLocaleDateString('vi-VN')}</td>
        <td class="action-btns">
            <i class="fa-solid fa-download" data-action="download" title="Download"></i>
            <i class="fa-solid fa-share-nodes" data-action="share" title="Share"></i>
            <i class="fa-solid fa-trash" data-action="delete" title="Delete"></i>
        </td>
    `;

    tr.querySelector('[data-action="download"]').addEventListener('click', () => {
        if (fileMeta.file_url) {
            window.open(fileMeta.file_url, '_blank', 'noreferrer');
        } else {
            alert('Chưa có link tải xuống cho file này.');
        }
    });

    tr.querySelector('[data-action="share"]').addEventListener('click', async () => {
        const shareValue = fileMeta.file_url || fileMeta.azure_name;
        try {
            await navigator.clipboard.writeText(shareValue);
            alert('Đã sao chép link share vào clipboard.');
        } catch {
            prompt('Copy link share:', shareValue);
        }
    });

    tr.querySelector('[data-action="delete"]').addEventListener('click', () => {
        tr.remove();
        if (fileList.children.length === 0) {
            showEmptyState(true);
        }
    });

    if (prepend) {
        fileList.prepend(tr);
    } else {
        fileList.appendChild(tr);
    }
}

function createProgressItem(file) {
    if (!progressContainer) {
        return {
            progressId: '',
            progressBar: { style: {} },
            progressText: { textContent: '', style: {} },
            progressItemDiv: { remove: () => {} },
        };
    }

    const progressId = 'prog-' + Math.random().toString(36).slice(2, 11);
    const progressHTML = `
        <div class="progress-item" id="${progressId}">
            <i class="fa-solid fa-file-lines" style="color: var(--azure-blue); font-size: 24px;"></i>
            <div class="file-details">
                <div style="display: flex; justify-content: space-between;">
                    <span style="font-weight: 500;">${file.name}</span>
                    <span id="txt-${progressId}" style="color: var(--text-muted); font-size: 12px;">0%</span>
                </div>
                <div class="pb-wrapper">
                    <div id="bar-${progressId}" class="pb-fill"></div>
                </div>
            </div>
        </div>
    `;
    progressContainer.insertAdjacentHTML('beforeend', progressHTML);
    return {
        progressId,
        progressBar: document.getElementById(`bar-${progressId}`),
        progressText: document.getElementById(`txt-${progressId}`),
        progressItemDiv: document.getElementById(progressId),
    };
}

function uploadFileReal(file) {
    return new Promise((resolve, reject) => {
        const { progressBar, progressText, progressItemDiv } = createProgressItem(file);
        const xhr = new XMLHttpRequest();
        const formData = new FormData();

        formData.append('file', file);
        const activeFolderId = globalThis.currentFolderId ?? null;
        if (activeFolderId) {
            formData.append('folder_id', activeFolderId);
        }
        if (file.webkitRelativePath) {
            formData.append('relative_path', file.webkitRelativePath);
        }
        xhr.open('POST', `${API_URL}/files/upload`);

        const token = getAuthToken();
        if (token) {
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        }

        xhr.upload.onprogress = (event) => {
            if (!event.lengthComputable) return;
            const percent = Math.round((event.loaded / event.total) * 100);
            progressBar.style.width = `${percent}%`;
            progressText.textContent = `${percent}%`;
        };

        xhr.onload = () => {
            progressBar.style.width = '100%';
            if (xhr.status >= 200 && xhr.status < 300) {
                progressText.textContent = 'Completed';
                progressText.style.color = 'var(--success-color)';
                progressBar.style.backgroundColor = 'var(--success-color)';

                setTimeout(() => {
                    progressItemDiv.remove();
                    resolve();
                }, 500);
                return;
            }

            progressText.textContent = 'Failed';
            progressText.style.color = 'var(--danger-color, #dc3545)';
            setTimeout(() => progressItemDiv.remove(), 1500);

            let message = 'Upload thất bại';
            try {
                const errorData = JSON.parse(xhr.responseText || '{}');
                message = errorData.detail || message;
            } catch {
                message = xhr.responseText || message;
            }
            alert(message);
            reject(new Error(message));
        };

        xhr.onerror = () => {
            progressText.textContent = 'Failed';
            setTimeout(() => progressItemDiv.remove(), 1500);
            alert('Không thể kết nối tới máy chủ!');
            reject(new Error('Không thể kết nối tới máy chủ!'));
        };

        xhr.send(formData);
    });
}

async function handleFiles(files) {
    if (!files?.length) return;
    try {
        await Promise.all(Array.from(files).map(uploadFileReal));
        if (typeof globalThis.loadFiles === 'function') {
            await globalThis.loadFiles(globalThis.currentFolderId ?? null);
            if (typeof globalThis.renderBreadcrumb === 'function') {
                globalThis.renderBreadcrumb();
            }
        } else {
            await loadUploadedFiles();
        }
    } catch {
        // Lỗi đã được báo riêng theo từng file.
    }
}

function openCreateModal() {
    fileInput.click();
}

function logout() {
    localStorage.removeItem("mycloud_token");
    localStorage.removeItem("mycloud_username");
    globalThis.location.href = "auth.html";
}

function searchFile() {
    const keyword = (document.getElementById('searchInput')?.value || '').trim().toLowerCase();
    Array.from(fileList.querySelectorAll('tr')).forEach((row) => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(keyword) ? '' : 'none';
    });
}

if (uploadBtn) {
    uploadBtn.addEventListener('click', () => fileInput?.click());
}

globalThis.addEventListener('DOMContentLoaded', () => {
    if (!emptyState || !fileTable || !fileList) return;
    showEmptyState(true);
    loadUploadedFiles();
});