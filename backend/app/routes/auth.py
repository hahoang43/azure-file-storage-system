from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Import các file nội bộ của dự án
from app import models, schemas, utils
from app.database import get_db

router = APIRouter(
    prefix="/auth",
    tags=["Xac thuc nguoi dung"]
)

# ==========================================
# 1. API ĐĂNG KÝ TÀI KHOẢN (REGISTER)
# ==========================================
@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    print("👉 BƯỚC 1: Đã nhận được dữ liệu từ Web!")
    
    # 1. Kiểm tra xem username hoặc email đã tồn tại chưa
    print("👉 BƯỚC 2: Đang vào Database kiểm tra trùng lặp...")
    existing_user = db.query(models.User).filter(
        (models.User.username == user.username) | (models.User.email == user.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Tên đăng nhập hoặc Email đã được sử dụng!"
        )
    
    # 2. Băm mật khẩu
    print("👉 BƯỚC 3: Bắt đầu băm mật khẩu...")
    hash_pwd = utils.get_password_hash(user.password)
    
    # 3. Tạo người dùng mới
    print("👉 BƯỚC 4: Đang lưu tài khoản mới vào Database...")
    new_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=hash_pwd,  # Đúng tên cột trong models.py
        used_storage=0,
        max_storage=536870912    # 512MB hoặc sửa lại đúng với models.py
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    print("👉 BƯỚC 5: LƯU THÀNH CÔNG! Đang gửi trả về Web...")
    return new_user

# ==========================================
# 2. API ĐĂNG NHẬP (LOGIN)
# ==========================================
@router.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    # 1. Đi tìm user trong Database dựa vào username
    user = db.query(models.User).filter(models.User.username == user_credentials.username).first()

    # 2. Nếu không tìm thấy User HOẶC sai mật khẩu -> Đuổi ra
    if not user or not utils.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không chính xác!",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Nếu đúng hết -> In Thẻ thông hành (JWT) có chứa tên người dùng
    access_token = utils.create_access_token(data={"sub": user.username})

    # 4. Trả Thẻ về cho người dùng
    return {"access_token": access_token, "token_type": "bearer"}