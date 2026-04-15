const API_URL = "http://127.0.0.1:8000";
let token = localStorage.getItem("mycloud_token");

// 1. KIỂM TRA ĐĂNG NHẬP
if (!token) {
    window.location.href = "auth.html";
}

let allFiles = []; // Dữ liệu thô từ server
let currentFolderId = null;
let currentPath = [{ id: null, name: "Home" }];
let viewMode = "grid";

// 2. LOAD DỮ LIỆU TỪ SERVER
async function loadFiles() {
    try {
        const response = await fetch(`${API_URL}/folders/contents${currentFolderId ? `?parent_id=${currentFolderId}` : ''}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (response.status === 401) logout();
        const data = await response.json();
        // Chuẩn hóa dữ liệu: gắn type cho từng item
        allFiles = [
            ...data.folders.map(f => ({
                id: f.id,
                name: f.name,
                type: "folder",
                updated_at: f.updated_at
            })),
            ...data.files.map(f => ({
                id: f.id,
                name: f.name,
                type: "file",
                updated_at: f.updated_at
            }))
        ];
        renderFiles(allFiles);
        renderBreadcrumb();
    } catch (error) {
        console.error("Không thể tải danh sách file và thư mục.");
    }
}

// 3. RENDER GIAO DIỆN
function renderFiles(list) {
    const container = document.getElementById("fileContainer");
    container.innerHTML = "";

    if (list.length === 0) {
        container.innerHTML = `<div class="text-center mt-5 text-muted"><i class="bi bi-folder2 fs-1"></i><p>Thư mục này trống</p></div>`;
        return;
    }

    list.forEach(f => {
        let iconClass = "bi-file-earmark-text text-secondary";
        if (f.type === "folder") iconClass = "bi-folder-fill text-warning";
        else if (f.type === "image") iconClass = "bi-file-earmark-image text-success";
        else if (f.name.endsWith(".pdf")) iconClass = "bi-file-earmark-pdf text-danger";

        const colClass = viewMode === "grid" ? "col-md-3 col-sm-6 mb-4" : "col-12 mb-2";

        if (viewMode === "grid") {
            container.innerHTML += `
                <div class="${colClass}">
                    <div class="card file-card p-3 text-center" onclick="openItem(${f.id}, '${f.name}', '${f.type}')">
                        <i class="bi ${iconClass} file-icon"></i>
                        <div class="text-truncate fw-medium">${f.name}</div>
                        <div class="d-flex justify-content-center mt-2 opacity-0-hover">
                            <button class="btn btn-sm btn-light me-1" onclick="event.stopPropagation(); renameItem(${f.id}, '${f.type}')"><i class="bi bi-pencil"></i></button>
                            <button class="btn btn-sm btn-light text-danger" onclick="event.stopPropagation(); deleteItem(${f.id}, '${f.type}')"><i class="bi bi-trash"></i></button>
                        </div>
                    </div>
                </div>`;
        } else {
            container.innerHTML += `
                <div class="${colClass}">
                    <div class="d-flex align-items-center p-3 bg-white rounded shadow-sm file-card" onclick="openItem(${f.id}, '${f.name}', '${f.type}')">
                        <i class="bi ${iconClass} fs-4 me-3"></i>
                        <div class="flex-grow-1 text-truncate">${f.name}</div>
                        <div class="text-muted small me-4">${f.type.toUpperCase()}</div>
                        <button class="btn btn-sm btn-link text-dark" onclick="event.stopPropagation(); deleteItem(${f.id}, '${f.type}')"><i class="bi bi-trash"></i></button>
                    </div>
                </div>`;
        }
    });
}

// 4. XỬ LÝ SỰ KIỆN MỞ ITEM
function openItem(id, name, type) {
    if (type === "folder") {
        currentFolderId = id;
        currentPath.push({ id: id, name: name });
        loadFiles();
    } else {
        // Nếu có hàm xem trước file thì gọi, nếu không thì có thể mở file trực tiếp
        if (typeof previewFile === 'function') previewFile(id, name);
        else alert('Xem file: ' + name);
    }
}
// 7. HIỂN THỊ BREADCRUMB
function renderBreadcrumb() {
    const breadcrumb = document.getElementById('breadcrumb');
    if (!breadcrumb) return;
    breadcrumb.innerHTML = currentPath.map((item, idx) => {
        if (idx === currentPath.length - 1) {
            return `<li class="breadcrumb-item active">${item.name}</li>`;
        } else {
            return `<li class="breadcrumb-item"><a href="#" onclick="goToFolder(${idx})">${item.name}</a></li>`;
        }
    }).join('');
}

function goToFolder(idx) {
    // Quay lại folder ở vị trí idx trong currentPath
    currentPath = currentPath.slice(0, idx + 1);
    currentFolderId = currentPath[idx].id;
    loadFiles();
}

// 5. UPLOAD FILE THẬT
async function handleFileUpload(input) {
    const file = input.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    if (currentFolderId) formData.append("folder_id", currentFolderId);

    try {
        const response = await fetch(`${API_URL}/files/upload`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` },
            body: formData
        });
        if (response.ok) { loadFiles(); alert("Tải lên thành công!"); }
    } catch (e) { alert("Lỗi kết nối server!"); }
}

// 6. ĐĂNG XUẤT
function logout() {
    localStorage.removeItem("mycloud_token");
    window.location.href = "auth.html";
}

// KHỞI TẠO
document.addEventListener("DOMContentLoaded", () => {
    loadFiles();
    // Chuyển chế độ xem
    document.getElementById("gridBtn").onclick = () => { viewMode = "grid"; renderFiles(allFiles); };
    document.getElementById("listBtn").onclick = () => { viewMode = "list"; renderFiles(allFiles); };
});