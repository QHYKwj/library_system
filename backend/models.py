from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, Date, Enum, Text, DECIMAL, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base

# role: admin / librarian / reader
class User(Base):
    __tablename__ = "user"
    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum("admin", "librarian", "reader"), nullable=False, default="reader")
    # 读者用户关联 reader_id（管理员/馆员可以为空）
    reader_id = Column(BigInteger, ForeignKey("reader.reader_id"), nullable=True)

    status = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    reader = relationship("Reader", back_populates="account", uselist=False)

class ReaderCategory(Base):
    __tablename__ = "reader_category"
    category_id = Column(BigInteger, primary_key=True, autoincrement=True)
    category_name = Column(String(50), unique=True, nullable=False)
    max_borrow_count = Column(Integer, nullable=False, default=5)
    max_borrow_days = Column(Integer, nullable=False, default=30)
    fine_per_day = Column(DECIMAL(10, 2), nullable=False, default=0.50)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

class Reader(Base):
    __tablename__ = "reader"
    reader_id = Column(BigInteger, primary_key=True, autoincrement=True)
    category_id = Column(BigInteger, ForeignKey("reader_category.category_id"), nullable=False)
    reader_no = Column(String(30), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    gender = Column(Enum("M", "F", "U"), nullable=False, default="U")
    phone = Column(String(30))
    email = Column(String(120))
    address = Column(String(255))
    status = Column(Enum("active", "blocked"), nullable=False, default="active")
    borrowed_count = Column(Integer, nullable=False, default=0)
    fine_balance = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    fine_total_history = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    category = relationship("ReaderCategory")
    borrows = relationship("BorrowRecord", back_populates="reader")
    account = relationship("User", back_populates="reader")

class Publisher(Base):
    __tablename__ = "publisher"
    publisher_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(120), unique=True, nullable=False)
    contact = Column(String(120))
    phone = Column(String(30))
    address = Column(String(255))
    created_at = Column(DateTime, nullable=False, server_default=func.now())

class Book(Base):
    __tablename__ = "book"
    book_id = Column(BigInteger, primary_key=True, autoincrement=True)
    isbn = Column(String(20), unique=True)
    title = Column(String(200), nullable=False)
    subtitle = Column(String(200))
    publisher_id = Column(BigInteger, ForeignKey("publisher.publisher_id"), nullable=True)
    publish_date = Column(Date, nullable=True)
    category = Column(String(80))
    language = Column(String(30))
    price = Column(DECIMAL(10, 2))
    summary = Column(Text)

    total_copies = Column(Integer, nullable=False, default=0)
    available_copies = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    publisher = relationship("Publisher")
    copies = relationship("BookCopy", back_populates="book")

class BookCopy(Base):
    __tablename__ = "book_copy"
    copy_id = Column(BigInteger, primary_key=True, autoincrement=True)
    book_id = Column(BigInteger, ForeignKey("book.book_id"), nullable=False)
    barcode = Column(String(50), unique=True, nullable=False)
    location = Column(String(80))
    status = Column(Enum("available", "borrowed", "lost", "repair"), nullable=False, default="available")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    book = relationship("Book", back_populates="copies")

class BorrowRecord(Base):
    __tablename__ = "borrow_record"
    borrow_id = Column(BigInteger, primary_key=True, autoincrement=True)
    reader_id = Column(BigInteger, ForeignKey("reader.reader_id"), nullable=False)
    copy_id = Column(BigInteger, ForeignKey("book_copy.copy_id"), nullable=False)
    book_id = Column(BigInteger, ForeignKey("book.book_id"), nullable=False)

    borrow_time = Column(DateTime, nullable=False, server_default=func.now())
    due_time = Column(DateTime, nullable=False)
    return_time = Column(DateTime, nullable=True)

    status = Column(Enum(
        "borrowed", "returned", "overdue_returned", "lost", "damaged_returned"
    ), nullable=False, default="borrowed")

    overdue_days = Column(Integer, nullable=False, default=0)
    is_damaged = Column(Boolean, nullable=False, default=False)
    damage_desc = Column(String(255))

    fine_amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    fine_status = Column(Enum("none", "unpaid", "paid"), nullable=False, default="none")

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    reader = relationship("Reader", back_populates="borrows")
    copy = relationship("BookCopy")
    book = relationship("Book")

class FineRecord(Base):
    __tablename__ = "fine_record"
    fine_id = Column(BigInteger, primary_key=True, autoincrement=True)
    reader_id = Column(BigInteger, ForeignKey("reader.reader_id"), nullable=False)
    borrow_id = Column(BigInteger, ForeignKey("borrow_record.borrow_id"), nullable=True)
    reason = Column(Enum("overdue", "damage", "lost", "other"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(Enum("unpaid", "paid"), nullable=False, default="unpaid")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    paid_at = Column(DateTime, nullable=True)

class PaymentRecord(Base):
    __tablename__ = "payment_record"
    pay_id = Column(BigInteger, primary_key=True, autoincrement=True)
    reader_id = Column(BigInteger, ForeignKey("reader.reader_id"), nullable=False)
    fine_id = Column(BigInteger, ForeignKey("fine_record.fine_id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    method = Column(Enum("cash", "wechat", "alipay", "card", "other"), nullable=False, default="cash")
    paid_at = Column(DateTime, nullable=False, server_default=func.now())
