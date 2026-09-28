from pydantic import BaseModel
from typing import List, Optional

class UserCreate(BaseModel):
    name: str
    email: str

class UserResponse(UserCreate):
    id: int
    upi_id: Optional[str] = None
    class Config:
        from_attributes = True

class UserUpiUpdate(BaseModel):
    upi_id: str

class ItemResponse(BaseModel):
    id: int
    item_name: str
    price: float
    class Config:
        from_attributes = True

class ReceiptResponse(BaseModel):
    id: int
    store_name: Optional[str]
    total_amount: float
    uploader_id: Optional[int] = None
    uploader_name: Optional[str] = None
    uploader_upi_id: Optional[str] = None
    items: List[ItemResponse]
    class Config:
        from_attributes = True

class ShareAssignment(BaseModel):
    user_id: int
    fraction: float  # e.g., 0.5 for 1/2, 0.3333 for 1/3

class ItemShareRequest(BaseModel):
    item_id: int
    shares: List[ShareAssignment]

class ItemBreakdown(BaseModel):
    item_name: str
    cost: float
    share_fraction: Optional[float] = 1.0
    portion_label: Optional[str] = "Full"

class UserTotalOwed(BaseModel):
    user_id: int
    user_name: str
    upi_id: Optional[str] = None
    total_owed: float
    items: List[ItemBreakdown] = []

class UserBulkCreate(BaseModel):
    names: List[str]

class ItemAssignment(BaseModel):
    item_id: int
    user_ids: List[int]

class BulkAssignRequest(BaseModel):
    receipt_id: int
    assignments: List[ItemAssignment]

class UserItemShare(BaseModel):
    item_id: int
    fraction: float  # e.g., 1.0 (full), 0.5 (1/2), 0.3333 (1/3), 0.25 (1/4)
    portion_label: Optional[str] = None

class UserShareRequest(BaseModel):
    receipt_id: int
    user_id: int
    item_ids: Optional[List[int]] = None
    shares: Optional[List[UserItemShare]] = None

class UserRegister(BaseModel):
    name: str
    username: str
    password: str
    email: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserAuthResponse(BaseModel):
    id: int
    name: str
    username: Optional[str] = None
    email: Optional[str] = None
    upi_id: Optional[str] = None
    token: str

class ReceiptHistoryItem(BaseModel):
    id: int
    store_name: str
    total_amount: float
    created_at: str
    is_uploader: bool
    uploader_name: str
    my_share_cost: float
    items_count: int