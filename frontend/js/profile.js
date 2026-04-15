// profile.js: Đảm bảo các hàm popup hồ sơ và đổi mật khẩu luôn global
window.openUpdateProfileModal = function () {
    const modal = new bootstrap.Modal(document.getElementById('changeUsernameModal'));
    document.getElementById('changeUsernameForm').reset();
    document.getElementById('changeUsernameMessage').textContent = '';
    modal.show();
};

window.openChangePasswordModal = function () {
    const modal = new bootstrap.Modal(document.getElementById('changePasswordModal'));
    document.getElementById('changePasswordForm').reset();
    document.getElementById('changePasswordMessage').textContent = '';
    modal.show();
};
