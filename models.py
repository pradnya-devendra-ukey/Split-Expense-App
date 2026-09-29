from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    username = Column(String(100), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    upi_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, index=True)
    uploader_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    store_name = Column(String(150))
    total_amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("Item", back_populates="receipt", cascade="all, delete")

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id", ondelete="CASCADE"))
    item_name = Column(String(255), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)

    receipt = relationship("Receipt", back_populates="items")
    shares = relationship("ItemShare", back_populates="item", cascade="all, delete")

class ItemShare(Base):
    __tablename__ = "item_shares"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    share_fraction = Column(Numeric(5, 4), nullable=False)

    item = relationship("Item", back_populates="shares")

class ReceiptSettlement(Base):
    __tablename__ = "receipt_settlements"
    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_paid = Column(Boolean, default=True)
    amount = Column(Numeric(10, 2), nullable=True)
    transaction_ref = Column(String(100), nullable=True)
    settled_at = Column(DateTime, default=datetime.utcnow)