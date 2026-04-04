function logout() {
    localStorage.removeItem("mycloud_token");
    window.location.href = "landing.html";
}
