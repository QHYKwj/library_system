from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timedelta

from db import Base, engine, get_db
import models as M
import schemas as S
from security import hash_password, verify_password, create_access_token, decode_token
from algolia_sync import upsert_book, delete_book

app = FastAPI(title="Library System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 大作业先放开
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- init tables ---
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# --- auth deps ---
def get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
        return payload
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(*roles):
    def _dep(user=Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Permission denied")
        return user
    return _dep

# --- auth routes ---
@app.post("/api/auth/login", response_model=S.TokenOut)
def login(data: S.LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(M.User).where(M.User.username == data.username))
    if not u or u.status != 1:
        raise HTTPException(status_code=400, detail="用户名不存在或账号被禁用")

    # 关键：身份选择要生效
    if data.user_type == "staff" and u.role == "reader":
        raise HTTPException(status_code=400, detail="该账号是读者账号，请选择“读者”身份登录")
    if data.user_type == "reader" and u.role in ("admin", "librarian"):
        raise HTTPException(status_code=400, detail="该账号是管理员/馆员账号，请选择“管理员/馆员”身份登录")

    if not verify_password(data.password, u.password_hash):
        raise HTTPException(status_code=400, detail="密码错误")

    # 读者账号必须有 reader_id（否则后续借还查不到）
    if u.role == "reader" and not u.reader_id:
        raise HTTPException(status_code=400, detail="读者账号未绑定 reader_id，请联系管理员")

    token = create_access_token({
        "sub": u.username,
        "role": u.role,
        "user_id": u.user_id,
        "reader_id": u.reader_id,
        "user_type": data.user_type,  # 可选：写进 token 便于调试
    })

    return S.TokenOut(
        access_token=token,
        role=u.role,
        username=u.username,
        reader_id=u.reader_id
    )

@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    return user

@app.post("/api/auth/register-reader", response_model=S.TokenOut)
def register_reader(data: S.RegisterReaderIn, db: Session = Depends(get_db)):
    # username unique
    if db.scalar(select(M.User).where(M.User.username == data.username)):
        raise HTTPException(status_code=400, detail="用户名已存在")

    cat = db.get(M.ReaderCategory, data.category_id)
    if not cat:
        raise HTTPException(status_code=400, detail="读者类别不存在")

    # reader_no unique
    if db.scalar(select(M.Reader).where(M.Reader.reader_no == data.reader_no)):
        raise HTTPException(status_code=400, detail="读者证号已存在")

    r = M.Reader(
        category_id=data.category_id,
        reader_no=data.reader_no,
        name=data.name,
        gender="U",
        status="active",
    )
    db.add(r)
    db.flush()  # get reader_id

    u = M.User(
        username=data.username,
        password_hash=hash_password(data.password),
        role="reader",
        reader_id=r.reader_id,
        status=1,
    )
    db.add(u)
    db.commit()

    token = create_access_token({"sub": u.username, "role": u.role, "user_id": u.user_id, "reader_id": u.reader_id})
    return S.TokenOut(access_token=token, role=u.role, username=u.username, reader_id=u.reader_id)

# --- reader categories ---
@app.get("/api/reader-categories", response_model=list[S.ReaderCategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(select(M.ReaderCategory)).all()

# --- readers CRUD (admin/librarian) ---
@app.get("/api/readers", response_model=list[S.ReaderOut])
def list_readers(db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    return db.scalars(select(M.Reader)).all()

@app.post("/api/readers", response_model=S.ReaderOut)
def create_reader(payload: S.ReaderUpdateIn, db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    # 为简化：读者创建请走注册-reader；这里留空或你可自行扩展
    raise HTTPException(status_code=400, detail="请使用注册读者接口 /api/auth/register-reader")

@app.put("/api/readers/{reader_id}", response_model=S.ReaderOut)
def update_reader(reader_id: int, data: S.ReaderUpdateIn, db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    r = db.get(M.Reader, reader_id)
    if not r:
        raise HTTPException(status_code=404, detail="读者不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r

@app.delete("/api/readers/{reader_id}")
def delete_reader(reader_id: int, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    r = db.get(M.Reader, reader_id)
    if not r:
        raise HTTPException(status_code=404, detail="读者不存在")
    # 删除前检查是否有未归还借阅
    open_borrow = db.scalar(select(M.BorrowRecord).where(M.BorrowRecord.reader_id == reader_id, M.BorrowRecord.status == "borrowed"))
    if open_borrow:
        raise HTTPException(status_code=400, detail="该读者仍有未归还图书，不能删除")
    # 先删账号
    acc = db.scalar(select(M.User).where(M.User.reader_id == reader_id))
    if acc:
        db.delete(acc)
    db.delete(r)
    db.commit()
    return {"ok": True}

# --- publishers CRUD (admin/librarian) ---
@app.get("/api/publishers", response_model=list[S.PublisherOut])
def list_publishers(db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    return db.scalars(select(M.Publisher)).all()

@app.post("/api/publishers", response_model=S.PublisherOut)
def create_publisher(data: S.PublisherIn, db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    if db.scalar(select(M.Publisher).where(M.Publisher.name == data.name)):
        raise HTTPException(status_code=400, detail="出版社已存在")
    p = M.Publisher(**data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@app.put("/api/publishers/{pid}", response_model=S.PublisherOut)
def update_publisher(pid: int, data: S.PublisherIn, db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    p = db.get(M.Publisher, pid)
    if not p:
        raise HTTPException(status_code=404, detail="出版社不存在")
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p

@app.delete("/api/publishers/{pid}")
def delete_publisher(pid: int, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    p = db.get(M.Publisher, pid)
    if not p:
        raise HTTPException(status_code=404, detail="出版社不存在")
    db.delete(p)
    db.commit()
    return {"ok": True}

# --- books CRUD ---
@app.get("/api/books", response_model=list[S.BookOut])
def list_books(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(
        select(M.Book, M.Publisher.name)
        .join(M.Publisher, M.Book.publisher_id == M.Publisher.publisher_id, isouter=True)
        .order_by(M.Book.book_id.desc())
    ).all()

    out: list[S.BookOut] = []
    for book, pub_name in rows:
        item = S.BookOut.model_validate(book)
        item.publisher_name = pub_name
        out.append(item)
    return out

@app.post("/api/books", response_model=S.BookOut)
def create_book(data: S.BookIn, db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    b = M.Book(**data.model_dump())
    db.add(b)
    db.commit()
    db.refresh(b)

    pub_name = None
    if b.publisher_id:
        pub = db.get(M.Publisher, b.publisher_id)
        pub_name = pub.name if pub else None
    upsert_book(b, pub_name)
    return b

@app.put("/api/books/{bid}", response_model=S.BookOut)
def update_book(bid: int, data: S.BookIn, db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    b = db.get(M.Book, bid)
    if not b:
        raise HTTPException(status_code=404, detail="图书不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    db.commit()
    db.refresh(b)

    pub_name = None
    if b.publisher_id:
        pub = db.get(M.Publisher, b.publisher_id)
        pub_name = pub.name if pub else None
    upsert_book(b, pub_name)
    return b

@app.delete("/api/books/{bid}")
def delete_book_api(bid: int, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    b = db.get(M.Book, bid)
    if not b:
        raise HTTPException(status_code=404, detail="图书不存在")
    # 若仍有馆藏或借阅，按需限制（这里简单限制：有馆藏不删）
    any_copy = db.scalar(select(M.BookCopy).where(M.BookCopy.book_id == bid))
    if any_copy:
        raise HTTPException(status_code=400, detail="该图书仍有关联馆藏，不能删除")
    db.delete(b)
    db.commit()
    delete_book(bid)
    return {"ok": True}

# --- copies CRUD ---
@app.get("/api/copies", response_model=list[S.CopyOut])
def list_copies(book_id: int | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = select(M.BookCopy)
    if book_id:
        q = q.where(M.BookCopy.book_id == book_id)
    return db.scalars(q).all()

@app.post("/api/copies", response_model=S.CopyOut)
def create_copy(data: S.CopyIn, db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    b = db.get(M.Book, data.book_id)
    if not b:
        raise HTTPException(status_code=400, detail="图书不存在")
    if db.scalar(select(M.BookCopy).where(M.BookCopy.barcode == data.barcode)):
        raise HTTPException(status_code=400, detail="条码已存在")

    c = M.BookCopy(**data.model_dump())
    db.add(c)

    # 更新 book.total/available
    b.total_copies += 1
    if c.status == "available":
        b.available_copies += 1

    db.commit()
    db.refresh(c)

    pub_name = b.publisher.name if b.publisher else None
    upsert_book(b, pub_name)
    return c

@app.put("/api/copies/{cid}", response_model=S.CopyOut)
def update_copy(cid: int, data: S.CopyIn, db: Session = Depends(get_db), user=Depends(require_role("admin", "librarian"))):
    c = db.get(M.BookCopy, cid)
    if not c:
        raise HTTPException(status_code=404, detail="馆藏不存在")
    # status变化要同步 book.available
    b = db.get(M.Book, c.book_id)
    old_status = c.status

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)

    if b:
        if old_status != c.status:
            if old_status == "available":
                b.available_copies -= 1
            if c.status == "available":
                b.available_copies += 1

    db.commit()
    db.refresh(c)
    if b:
        pub_name = b.publisher.name if b.publisher else None
        upsert_book(b, pub_name)
    return c

@app.delete("/api/copies/{cid}")
def delete_copy(cid: int, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    c = db.get(M.BookCopy, cid)
    if not c:
        raise HTTPException(status_code=404, detail="馆藏不存在")
    if c.status == "borrowed":
        raise HTTPException(status_code=400, detail="该馆藏正在借出，不能删除")
    b = db.get(M.Book, c.book_id)
    if b:
        b.total_copies -= 1
        if c.status == "available":
            b.available_copies -= 1
    db.delete(c)
    db.commit()
    if b:
        pub_name = b.publisher.name if b.publisher else None
        upsert_book(b, pub_name)
    return {"ok": True}

# --- borrow / return / fine / pay ---
@app.post("/api/borrow", response_model=S.BorrowOut)
def borrow(data: S.BorrowIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # reader端：reader_id从token拿；管理员端可代办
    reader_id = data.reader_id
    if user["role"] == "reader":
        if not user.get("reader_id"):
            raise HTTPException(status_code=400, detail="读者账号未绑定读者信息")
        reader_id = user["reader_id"]
    if not reader_id:
        raise HTTPException(status_code=400, detail="缺少 reader_id")

    r = db.get(M.Reader, reader_id)
    if not r or r.status != "active":
        raise HTTPException(status_code=400, detail="读者不存在或被禁用")

    cat = r.category
    if r.borrowed_count >= cat.max_borrow_count:
        raise HTTPException(status_code=400, detail="已达最大借阅数量")
    if float(r.fine_balance) > 0:
        # 你也可以允许借书，这里简单限制一下更“像系统”
        raise HTTPException(status_code=400, detail="存在未缴罚款，暂不能借书")

    c = db.get(M.BookCopy, data.copy_id)
    if not c or c.status != "available":
        raise HTTPException(status_code=400, detail="馆藏不存在或不可借")

    b = db.get(M.Book, c.book_id)
    if not b or b.available_copies <= 0:
        raise HTTPException(status_code=400, detail="该书无可借库存")

    # 事务：这里用同一session提交即可（发生异常会rollback）
    try:
        due = datetime.utcnow() + timedelta(days=cat.max_borrow_days)
        br = M.BorrowRecord(
            reader_id=r.reader_id,
            copy_id=c.copy_id,
            book_id=b.book_id,
            due_time=due,
            status="borrowed",
        )
        db.add(br)

        c.status = "borrowed"
        b.available_copies -= 1
        r.borrowed_count += 1

        db.commit()
        db.refresh(br)
        return br
    except Exception:
        db.rollback()
        raise

@app.post("/api/return", response_model=S.BorrowOut)
def return_book(data: S.ReturnIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    br = db.get(M.BorrowRecord, data.borrow_id)
    if not br or br.status != "borrowed":
        raise HTTPException(status_code=400, detail="借阅记录不存在或已归还")

    # 读者只能归还自己的
    if user["role"] == "reader" and user.get("reader_id") != br.reader_id:
        raise HTTPException(status_code=403, detail="不能归还他人的借阅记录")

    r = db.get(M.Reader, br.reader_id)
    c = db.get(M.BookCopy, br.copy_id)
    b = db.get(M.Book, br.book_id)
    if not r or not c or not b:
        raise HTTPException(status_code=400, detail="数据不一致")

    cat = r.category
    now = datetime.utcnow()

    try:
        br.return_time = now

        overdue_days = 0
        fine = 0.0
        status = "returned"

        if now > br.due_time:
            overdue_days = max(0, (now - br.due_time).days)
            if overdue_days > 0:
                fine += overdue_days * float(cat.fine_per_day)
                status = "overdue_returned"

        if data.is_damaged:
            br.is_damaged = True
            br.damage_desc = data.damage_desc or "damaged"
            # 简化：损坏固定罚款 10 元（你也可以按 price 比例）
            fine += 10.0
            status = "damaged_returned"

        br.overdue_days = overdue_days
        br.status = status

        # 还书：馆藏与库存与读者已借数
        if c.status == "borrowed":
            c.status = "available"
        b.available_copies += 1
        r.borrowed_count = max(0, r.borrowed_count - 1)

        if fine > 0:
            br.fine_amount = fine
            br.fine_status = "unpaid"
            fr = M.FineRecord(
                reader_id=r.reader_id,
                borrow_id=br.borrow_id,
                reason="overdue" if overdue_days > 0 else "damage",
                amount=fine,
                status="unpaid",
            )
            db.add(fr)
            r.fine_balance = float(r.fine_balance) + fine
            r.fine_total_history = float(r.fine_total_history) + fine
        else:
            br.fine_amount = 0.0
            br.fine_status = "none"

        db.commit()
        db.refresh(br)
        return br
    except Exception:
        db.rollback()
        raise

@app.get("/api/borrows", response_model=list[S.BorrowOut])
def list_borrows(db: Session = Depends(get_db), user=Depends(get_current_user), status: str | None = None):
    q = select(M.BorrowRecord)
    if user["role"] == "reader":
        q = q.where(M.BorrowRecord.reader_id == user.get("reader_id"))
    if status:
        q = q.where(M.BorrowRecord.status == status)
    return db.scalars(q.order_by(M.BorrowRecord.borrow_id.desc())).all()

@app.get("/api/fines", response_model=list[S.FineOut])
def list_fines(db: Session = Depends(get_db), user=Depends(get_current_user), status: str | None = None):
    q = select(M.FineRecord)
    if user["role"] == "reader":
        q = q.where(M.FineRecord.reader_id == user.get("reader_id"))
    if status:
        q = q.where(M.FineRecord.status == status)
    return db.scalars(q.order_by(M.FineRecord.fine_id.desc())).all()

@app.post("/api/fines/{fine_id}/pay")
def pay_fine(fine_id: int, data: S.PayIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    fr = db.get(M.FineRecord, fine_id)
    if not fr or fr.status != "unpaid":
        raise HTTPException(status_code=400, detail="罚款不存在或已缴")
    if user["role"] == "reader" and user.get("reader_id") != fr.reader_id:
        raise HTTPException(status_code=403, detail="不能缴纳他人的罚款")

    r = db.get(M.Reader, fr.reader_id)
    if not r:
        raise HTTPException(status_code=400, detail="读者不存在")

    try:
        pr = M.PaymentRecord(
            reader_id=fr.reader_id,
            fine_id=fr.fine_id,
            amount=fr.amount,
            method=data.method if data.method in ["cash","wechat","alipay","card","other"] else "other",
        )
        db.add(pr)
        fr.status = "paid"
        fr.paid_at = datetime.utcnow()
        r.fine_balance = max(0.0, float(r.fine_balance) - float(fr.amount))

        # 同步 borrow_record 里的 fine_status（如果有关联）
        if fr.borrow_id:
            br = db.get(M.BorrowRecord, fr.borrow_id)
            if br:
                br.fine_status = "paid"

        db.commit()
        return {"ok": True}
    except Exception:
        db.rollback()
        raise
