import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/auth", tags=["Authentication"])

def hash_password(password: str) -> str:
    """Simple salted SHA256 hash for secure password storage."""
    salt = "split_expense_salt_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

@router.post("/register", response_model=schemas.UserAuthResponse)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    name = payload.name.strip()
    
    if not username or not payload.password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    # Check if username or email already exists
    existing = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == f"{username}@local.app")
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Username is already taken. Please login or choose another.")

    pwd_hash = hash_password(payload.password)
    user_email = payload.email.strip() if payload.email else f"{username}@split.app"
    
    # Check if email taken
    if db.query(models.User).filter(models.User.email == user_email).first():
        user_email = f"{username}_{secrets.token_hex(3)}@split.app"

    new_user = models.User(
        name=name,
        username=username,
        email=user_email,
        password_hash=pwd_hash
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = f"token_{new_user.id}_{secrets.token_hex(8)}"
    return schemas.UserAuthResponse(
        id=new_user.id,
        name=new_user.name,
        username=new_user.username,
        email=new_user.email,
        token=token
    )

@router.post("/login", response_model=schemas.UserAuthResponse)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    pwd_hash = hash_password(payload.password)

    user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == username)
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")

    if user.password_hash and user.password_hash != pwd_hash:
        raise HTTPException(status_code=400, detail="Invalid username or password")

    # If user had no password set previously, set it now
    if not user.password_hash:
        user.password_hash = pwd_hash
        user.username = username
        db.commit()
        db.refresh(user)

    token = f"token_{user.id}_{secrets.token_hex(8)}"
    return schemas.UserAuthResponse(
        id=user.id,
        name=user.name,
        username=user.username or username,
        email=user.email,
        token=token
    )

@router.get("/user/{user_id}", response_model=schemas.UserResponse)
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
