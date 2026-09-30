from pydantic import BaseModel
from typing import List, Optional

class UserCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    upi_id: Optional[str] = None

class UserBulkCreate(BaseModel):
    names: List[str]

class ContactImportItem(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    upi_id: Optional[str] = None

class ContactImportRequest(BaseModel):
    contacts: List[ContactImportItem]

class UserResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    upi_id: Optional[str] = None
    default_currency: Optional[str] = "INR"
    class Config:
        from_attributes = True

class UserUpiUpdate(BaseModel):
    upi_id: str

class UserCurrencyUpdate(BaseModel):
    default_currency: str

class ItemCreate(BaseModel):
    item_name: str
    price: float

class ItemUpdate(BaseModel):
    item_name: Optional[str] = None
    price: Optional[float] = None

class ItemResponse(BaseModel):
    id: int
    item_name: str
    price: float
    class Config:
        from_attributes = True

class TaxTipUpdate(BaseModel):
    tax_amount: float = 0.0
    tip_amount: float = 0.0
    tax_split_method: str = "proportional"  # 'proportional' or 'equal'

class ManualReceiptCreate(BaseModel):
    uploader_id: int
    store_name: str
    currency: Optional[str] = "INR"
    tax_amount: Optional[float] = 0.0
    tip_amount: Optional[float] = 0.0
    tax_split_method: Optional[str] = "proportional"
    group_id: Optional[int] = None
    items: List[ItemCreate] = []

class ReceiptPayerEntry(BaseModel):
    user_id: int
    user_name: Optional[str] = None
    upi_id: Optional[str] = None
    amount_paid: float

class SetReceiptPayersRequest(BaseModel):
    receipt_id: int
    payers: List[ReceiptPayerEntry]

class ReceiptResponse(BaseModel):
    id: int
    join_code: Optional[str] = None
    store_name: Optional[str] = None
    total_amount: float
    tax_amount: float = 0.0
    tip_amount: float = 0.0
    tax_split_method: str = "proportional"
    currency: str = "INR"
    currency_symbol: str = "₹"
    uploader_id: Optional[int] = None
    uploader_name: Optional[str] = None
    uploader_upi_id: Optional[str] = None
    group_id: Optional[int] = None
    items: List[ItemResponse] = []
    payers: List[ReceiptPayerEntry] = []
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

class DebtTransfer(BaseModel):
    from_user_id: int
    from_user_name: str
    to_user_id: int
    to_user_name: str
    to_user_upi: Optional[str] = None
    amount: float
    is_paid: bool = False
    settled_at: Optional[str] = None
    transaction_ref: Optional[str] = None

class UserTotalOwed(BaseModel):
    user_id: int
    user_name: str
    upi_id: Optional[str] = None
    amount_paid: float = 0.0
    items_cost: float = 0.0
    tax_tip_share: float = 0.0
    consumed_cost: float = 0.0
    net_balance: float = 0.0
    total_owed: float = 0.0
    is_paid: bool = False
    settled_at: Optional[str] = None
    transaction_ref: Optional[str] = None
    items: List[ItemBreakdown] = []

class ReceiptSummaryResponse(BaseModel):
    receipt_id: int
    join_code: Optional[str] = None
    store_name: Optional[str] = None
    currency: str = "INR"
    currency_symbol: str = "₹"
    items_subtotal: float = 0.0
    tax_amount: float = 0.0
    tip_amount: float = 0.0
    tax_split_method: str = "proportional"
    total_amount: float
    users: List[UserTotalOwed]
    transfers: List[DebtTransfer]
    payers: List[ReceiptPayerEntry]

class SettlementRequest(BaseModel):
    receipt_id: int
    user_id: int
    payee_id: Optional[int] = None
    is_paid: bool = True
    amount: Optional[float] = None
    transaction_ref: Optional[str] = None

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
    default_currency: Optional[str] = "INR"

class UserLogin(BaseModel):
    username: str
    password: str

class UserAuthResponse(BaseModel):
    id: int
    name: str
    username: Optional[str] = None
    email: Optional[str] = None
    upi_id: Optional[str] = None
    default_currency: Optional[str] = "INR"
    token: str

class ReceiptHistoryItem(BaseModel):
    id: int
    join_code: Optional[str] = None
    store_name: str
    total_amount: float
    currency: str = "INR"
    currency_symbol: str = "₹"
    created_at: str
    is_uploader: bool
    uploader_name: str
    my_share_cost: float
    is_paid: bool = False
    items_count: int

# Group / Trip Schemas
class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    currency: Optional[str] = "INR"
    member_ids: Optional[List[int]] = []

class GroupMemberResponse(BaseModel):
    user_id: int
    user_name: str
    upi_id: Optional[str] = None
    joined_at: Optional[str] = None

class GroupReceiptItem(BaseModel):
    receipt_id: int
    join_code: Optional[str] = None
    store_name: str
    total_amount: float
    currency: str = "INR"
    currency_symbol: str = "₹"
    created_at: str
    items_count: int
    uploader_name: str

class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    currency: str = "INR"
    currency_symbol: str = "₹"
    created_by: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: str
    members: List[GroupMemberResponse] = []
    receipts: List[GroupReceiptItem] = []
    total_spend: float = 0.0

class AddGroupMemberRequest(BaseModel):
    user_id: int

class BulkAddGroupMembersRequest(BaseModel):
    user_ids: Optional[List[int]] = []
    contact_names: Optional[List[str]] = []


class GroupSummaryResponse(BaseModel):
    group_id: int
    group_name: str
    currency: str = "INR"
    currency_symbol: str = "₹"
    total_spend: float = 0.0
    receipts_count: int = 0
    users: List[UserTotalOwed] = []
    transfers: List[DebtTransfer] = []