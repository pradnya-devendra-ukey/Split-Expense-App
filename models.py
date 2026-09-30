from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Boolean, Text
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
    default_currency = Column(String(10), default="INR")
    created_at = Column(DateTime, default=datetime.utcnow)

    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete")

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    currency = Column(String(10), default="INR")
    currency_symbol = Column(String(5), default="₹")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", foreign_keys=[created_by])
    members = relationship("GroupMember", back_populates="group", cascade="all, delete")
    receipts = relationship("Receipt", back_populates="group")

class GroupMember(Base):
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="group_memberships")

class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, index=True)
    join_code = Column(String(10), unique=True, nullable=True, index=True)
    uploader_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)
    store_name = Column(String(150))
    total_amount = Column(Numeric(10, 2), nullable=False)
    tax_amount = Column(Numeric(10, 2), default=0.0)
    tip_amount = Column(Numeric(10, 2), default=0.0)
    tax_split_method = Column(String(20), default="proportional")  # 'proportional' or 'equal'
    currency = Column(String(10), default="INR")
    currency_symbol = Column(String(5), default="₹")
    created_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="receipts")
    items = relationship("Item", back_populates="receipt", cascade="all, delete")
    payers = relationship("ReceiptPayer", back_populates="receipt", cascade="all, delete")

class ReceiptPayer(Base):
    __tablename__ = "receipt_payers"
    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False)

    receipt = relationship("Receipt", back_populates="payers")
    user = relationship("User")

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
    payee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    is_paid = Column(Boolean, default=True)
    amount = Column(Numeric(10, 2), nullable=True)
    transaction_ref = Column(String(100), nullable=True)
    settled_at = Column(DateTime, default=datetime.utcnow)