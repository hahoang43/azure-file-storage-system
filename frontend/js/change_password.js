document.getElementById('changePasswordForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const oldPassword = document.getElementById('oldPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const messageDiv = document.getElementById('message');

    if (newPassword !== confirmPassword) {
        messageDiv.textContent = 'Mật khẩu mới và xác nhận không khớp!';
        messageDiv.style.color = 'red';
        return;
    }

    try {
        // Thay đổi URL API cho phù hợp với backend của bạn
        const response = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + localStorage.getItem('access_token')
            },
            body: JSON.stringify({
                old_password: oldPassword,
                new_password: newPassword
            })
        });
        const data = await response.json();
        if (response.ok) {
            messageDiv.textContent = 'Đổi mật khẩu thành công!';
            messageDiv.style.color = 'green';
            document.getElementById('changePasswordForm').reset();
        } else {
            messageDiv.textContent = data.detail || 'Đổi mật khẩu thất bại!';
            messageDiv.style.color = 'red';
        }
    } catch (error) {
        messageDiv.textContent = 'Lỗi kết nối đến máy chủ!';
        messageDiv.style.color = 'red';
    }
});
