from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

Role = Literal["admin", "librarian", "reader"]

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    username: str
    reader_id: Optional[int] = None

class LoginIn(BaseModel):
    username: str
    password: str
    user_type: Literal["reader", "staff"]

class RegisterReaderIn(BaseModel):
    username: str
    password: str
    reader_no: str
    name: str
    category_id: int

class ReaderCategoryOut(BaseModel):
    category_id: int
    category_name: str
    max_borrow_count: int
    max_borrow_days: int
    fine_per_day: float

    class Config:
        from_attributes = True

class ReaderOut(BaseModel):
    reader_id: int
    category_id: int
    reader_no: str
    name: str
    gender: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    status: str
    borrowed_count: int
    fine_balance: float
    fine_total_history: float

    class Config:
        from_attributes = True

class ReaderUpdateIn(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None

class PublisherIn(BaseModel):
    name: str
    contact: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class PublisherOut(PublisherIn):
    publisher_id: int
    class Config:
        from_attributes = True

class BookIn(BaseModel):
    isbn: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    publisher_id: Optional[int] = None
    publish_date: Optional[date] = None
    category: Optional[str] = None
    language: Optional[str] = None
    price: Optional[float] = None
    summary: Optional[str] = None

class BookOut(BookIn):
    book_id: int
    total_copies: int
    available_copies: int
    publisher_name: str | None = None  # ✅ 新增
    class Config:
        from_attributes = True

class CopyIn(BaseModel):
    book_id: int
    barcode: str
    location: Optional[str] = None
    status: str = "available"

class CopyOut(CopyIn):
    copy_id: int
    class Config:
        from_attributes = True

class BorrowIn(BaseModel):
    copy_id: int
    # reader_id：读者端不传（从 token 拿）；管理员端可传为他人办理
    reader_id: Optional[int] = None

class ReturnIn(BaseModel):
    borrow_id: int
    is_damaged: bool = False
    damage_desc: Optional[str] = None
    # 丢失可做扩展：mark_lost: bool

class BorrowOut(BaseModel):
    borrow_id: int
    reader_id: int
    copy_id: int
    book_id: int
    borrow_time: datetime
    due_time: datetime
    return_time: Optional[datetime]
    status: str
    overdue_days: int
    is_damaged: bool
    damage_desc: Optional[str]
    fine_amount: float
    fine_status: str

    class Config:
        from_attributes = True

class FineOut(BaseModel):
    fine_id: int
    reader_id: int
    borrow_id: Optional[int]
    reason: str
    amount: float
    status: str
    created_at: datetime
    paid_at: Optional[datetime]
    class Config:
        from_attributes = True

class PayIn(BaseModel):
    method: str = Field(default="cash")
