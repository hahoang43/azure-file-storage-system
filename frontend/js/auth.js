const API_URL = "http://127.0.0.1:8000";


// 1. XỬ LÝ SỰ KIỆN ĐĂNG KÝ

document.getElementById('registerForm').addEventListener('submit', async function (e) {
    e.preventDefault(); // Ngăn trình duyệt tải lại trang
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const confirm = document.getElementById('register-confirm').value;
    const errorDiv = document.getElementById('register-error');

    // Kiểm tra mật khẩu
    if (password !== confirm) {
        errorDiv.textContent = 'Mật khẩu xác nhận không khớp!';
        return;
    }
    errorDiv.textContent = ''; // Xóa lỗi cũ

    try {
        const response = await fetch(`${API_URL}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: username,
                email: email,
                password: password,
                // display_name: display_name
            })
        });

        let data = {};
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
            data = await response.json();
        } else {
            const text = await response.text();
            data = { detail: text || "Đăng ký thất bại!" };
        }

        if (response.ok) {
            alert("Đăng ký thành công! Vui lòng đăng nhập.");
            // Chuyển sang tab Đăng nhập
            showTab(true);
            // Tự động điền sẵn tên đăng nhập cho tiện
            const loginUsernameInput = document.getElementById('login-username');
            if (loginUsernameInput) {
                loginUsernameInput.value = username;
            }
            document.getElementById('registerForm').reset();
        } else {
            errorDiv.textContent = data.detail || "Đăng ký thất bại!";
        }
    } catch (error) {
        errorDiv.textContent = "Không thể kết nối tới máy chủ!";
        console.error("Lỗi:", error);
    }
});

// 2. XỬ LÝ SỰ KIỆN ĐĂNG NHẬP

document.getElementById('loginForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const errorDiv = document.getElementById('login-error');

    errorDiv.textContent = '';

    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });

        let data = {};
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
            data = await response.json();
        } else {
            const text = await response.text();
            data = { detail: text || "Đăng nhập thất bại!" };
        }

        if (response.ok) {
            // LƯU THẺ THÔNG HÀNH (TOKEN) VÀO BỘ NHỚ TRÌNH DUYỆT
            localStorage.setItem("mycloud_token", data.access_token);

            alert("Đăng nhập thành công!");

            // Chuyển hướng người dùng vào trang trong của hệ thống
            window.location.href = "index.html";
        } else {
            // Sai mật khẩu hoặc tài khoản
            errorDiv.textContent = data.detail || "Sai thông tin đăng nhập!";
        }
    } catch (error) {
        errorDiv.textContent = "Không thể kết nối tới máy chủ!";
        console.error("Lỗi:", error);
    }
});
document.addEventListener("DOMContentLoaded", function () {
    const token = localStorage.getItem("mycloud_token");
    const currentPath = window.location.pathname;

    // Nếu người dùng ĐÃ có thẻ Token (đã đăng nhập) mà cố tình vào trang auth.html
    // -> Lập tức đẩy họ về trang chủ (index.html)
    if (token && (currentPath.includes("auth.html") || currentPath.endsWith("/"))) {
        // Tạm thời đẩy về index.html. Sau này bạn code xong trang quản lý file thì đổi thành dashboard.html nhé!
        if (currentPath.includes("auth.html")) {
            window.location.href = "index.html";
        }
    }
});