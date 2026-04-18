import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

def list_my_files():
    connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_CONTAINER_NAME")
    
    try:
        service_client = BlobServiceClient.from_connection_string(connect_str)
        container_client = service_client.get_container_client(container_name)
        
        print(f"--- Đang kiểm tra thùng chứa: {container_name} ---")
        blob_list = container_client.list_blobs()
        
        count = 0
        for blob in blob_list:
            count += 1
            print(f"✅ Tìm thấy file: {blob.name} (Dung lượng: {blob.size} bytes)")
        
        if count == 0:
            print("❌ Thùng chứa đang trống rỗng!")
            
    except Exception as e:
        print(f"Lỗi rồi: {e}")

if __name__ == "__main__":
    list_my_files()