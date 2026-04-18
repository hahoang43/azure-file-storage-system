import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 1. Tải thông tin từ file .env
load_dotenv()

def test_azure_connection():
    # Lấy URL từ biến môi trường
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("❌ Lỗi: Không tìm thấy DATABASE_URL trong file .env. Hãy kiểm tra lại tên biến.")
        return

    print(f"🔄 Đang thử kết nối tới Azure MySQL...")
    
    try:
        # 2. Tạo engine kết nối
        # Thêm cấu hình connect_timeout để tránh chờ quá lâu nếu bị chặn Firewall
        # Thêm "ssl": {} vào để bật kết nối bảo mật
        engine = create_engine(db_url, connect_args={"connect_timeout": 10, "ssl": {}})
        
        # 3. Thực hiện truy vấn đơn giản nhất để xác nhận kết nối
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            print("✅ Chúc mừng! Kết nối tới Database trên Azure thành công rực rỡ.")
            
    except Exception as e:
        print("❌ Kết nối thất bại.")
        print("-" * 30)
        print(f"Lỗi hệ thống: {e}")
        print("-" * 30)
        print("\n💡 GỢI Ý KHẮC PHỤC:")
        print("1. Kiểm tra lại Username/Password trong file .env.")
        print("2. QUAN TRỌNG: Vào Azure Portal -> Networking và bấm 'Add current client IP address' để cho phép máy tính của bạn truy cập.")
        print("3. Đảm bảo dịch vụ MySQL trên Azure của bạn đang ở trạng thái 'Started'.")

if __name__ == "__main__":
    test_azure_connection()