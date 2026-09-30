from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    """Fetch all users for dynamic member and contact selection."""
    users = db.query(models.User).order_by(models.User.name.asc()).all()
    return users

@router.post("/", response_model=schemas.UserResponse)
def create_or_get_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create a new contact user or return existing one by phone/name."""
    name = payload.name.strip()
    phone = payload.phone.strip() if payload.phone else None
    email = payload.email.strip() if payload.email else None
    
    # Check if existing user exists with same phone or email or name
    existing_user = None
    if phone:
        existing_user = db.query(models.User).filter(models.User.phone == phone).first()
    if not existing_user and email:
        existing_user = db.query(models.User).filter(models.User.email == email).first()
    if not existing_user:
        existing_user = db.query(models.User).filter(models.User.name.ilike(name)).first()

    if existing_user:
        if payload.upi_id and not existing_user.upi_id:
            existing_user.upi_id = payload.upi_id.strip()
        if phone and not existing_user.phone:
            existing_user.phone = phone
        db.commit()
        db.refresh(existing_user)
        return existing_user

    dummy_email = email or f"{uuid.uuid4().hex[:8]}@contacts.local"
    new_user = models.User(
        name=name,
        email=dummy_email,
        phone=phone,
        upi_id=payload.upi_id.strip() if payload.upi_id else None
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/contacts/import", response_model=List[schemas.UserResponse])
def import_contacts(payload: schemas.ContactImportRequest, db: Session = Depends(get_db)):
    """Import contacts picked from phone Contact Picker API."""
    imported_users = []
    for item in payload.contacts:
        name = item.name.strip()
        if not name:
            continue
        phone = item.phone.strip() if item.phone else None
        email = item.email.strip() if item.email else None
        upi_id = item.upi_id.strip() if item.upi_id else None

        existing_user = None
        if phone:
            existing_user = db.query(models.User).filter(models.User.phone == phone).first()
        if not existing_user and email:
            existing_user = db.query(models.User).filter(models.User.email == email).first()
        if not existing_user:
            existing_user = db.query(models.User).filter(models.User.name.ilike(name)).first()

        if existing_user:
            if phone and not existing_user.phone:
                existing_user.phone = phone
            if upi_id and not existing_user.upi_id:
                existing_user.upi_id = upi_id
            imported_users.append(existing_user)
        else:
            dummy_email = email or f"{uuid.uuid4().hex[:8]}@contacts.local"
            new_user = models.User(
                name=name,
                email=dummy_email,
                phone=phone,
                upi_id=upi_id
            )
            db.add(new_user)
            imported_users.append(new_user)

    db.commit()
    for u in imported_users:
        db.refresh(u)
    return imported_users

@router.post("/bulk", response_model=List[schemas.UserResponse])
def create_users_bulk(payload: schemas.UserBulkCreate, db: Session = Depends(get_db)):
    """Dynamically create users from comma-separated names."""
    created_users = []
    for name in payload.names:
        clean_name = name.strip()
        if not clean_name:
            continue
        existing = db.query(models.User).filter(models.User.name.ilike(clean_name)).first()
        if existing:
            created_users.append(existing)
        else:
            dummy_email = f"{uuid.uuid4().hex[:8]}@temp.com"
            db_user = models.User(name=clean_name, email=dummy_email)
            db.add(db_user)
            created_users.append(db_user)
    db.commit()
    for user in created_users:
        db.refresh(user)
    return created_users

