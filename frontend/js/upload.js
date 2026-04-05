const dropZone = document.getElementById('drop-zone');
const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('file-input');
const progressContainer = document.getElementById('upload-progress-container');

const emptyState = document.getElementById('empty-state');
const fileTable = document.getElementById('file-table');
const fileList = document.getElementById('file-list');

// 1. Mở cửa sổ chọn file
uploadBtn.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('click', (e) => {
    // Tránh click đúp nếu click thẳng vào nút
    if(e.target !== uploadBtn) fileInput.click();
});

fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

// 2. Kéo thả file
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});

// Xử lý danh sách file truyền vào
function handleFiles(files) {
    for (let i = 0; i < files.length; i++) {
        uploadFileMockup(files[i]);
    }
}

// 3. Giả lập Upload & Cập nhật UI
function uploadFileMockup(file) {
    // --- BƯỚC 1: TẠO THANH TIẾN TRÌNH UI ---
    const progressId = 'prog-' + Math.random().toString(36).substr(2, 9);
    
    // HTML cho 1 item đang tải
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

    const progressBar = document.getElementById(`bar-${progressId}`);
    const progressText = document.getElementById(`txt-${progressId}`);
    const progressItemDiv = document.getElementById(progressId);

    // --- BƯỚC 2: CHẠY % GIẢ LẬP ---
    let percent = 0;
    let interval = setInterval(() => {
        percent += Math.floor(Math.random() * 20) + 10; // Tăng ngẫu nhiên 10-30%
        if (percent >= 100) percent = 100;

        progressBar.style.width = `${percent}%`;
        progressText.textContent = `${percent}%`;

        if (percent === 100) {
            clearInterval(interval);
            progressText.textContent = "Completed";
            progressText.style.color = "var(--success-color)";
            progressBar.style.backgroundColor = "var(--success-color)";
            
            // Đợi 1 giây rồi xóa thanh tiến trình, đưa file vào bảng
            setTimeout(() => {
                progressItemDiv.remove();
                addFileToTable(file);
            }, 1000);
        }
    }, 300); // 0.3s cập nhật 1 lần
}

// --- BƯỚC 3: ĐƯA FILE VÀO BẢNG FILE LIST ---
function addFileToTable(file) {
    // Ẩn Empty state, Hiện bảng
    emptyState.classList.add('hidden');
    fileTable.classList.remove('hidden');

    // Chuyển đổi size file cho đẹp (KB, MB)
    let fileSize = (file.size / 1024).toFixed(2) + ' KB';
    if (file.size > 1024 * 1024) {
        fileSize = (file.size / (1024 * 1024)).toFixed(2) + ' MB';
    }

    // Lấy ngày hiện tại
    const dateStr = new Date().toLocaleDateString('vi-VN');

    // Thêm dòng mới vào bảng
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td class="file-name-cell">
            <i class="fa-solid fa-file-pdf"></i> ${file.name}
        </td>
        <td>${fileSize}</td>
        <td>${dateStr}</td>
        <td class="action-btns">
            <i class="fa-solid fa-download" title="Download"></i>
            <i class="fa-solid fa-share-nodes" title="Share"></i>
            <i class="fa-solid fa-trash" title="Delete"></i>
        </td>
    `;
    
    // Thêm lên đầu danh sách
    fileList.prepend(tr);
}