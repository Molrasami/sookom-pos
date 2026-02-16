from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sqlite3


# ==========================================
# 1. คลาสจัดการฐานข้อมูล SOOKOM
# ==========================================
class POSDatabase:
    def __init__(self, db_name='sookom_pos.db'):
        self.db_name = db_name

    def execute_query(self, query, params=()):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor

    def get_all_menu(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT item_id, name, price, category FROM menu_items")
            return [{"item_id": row[0], "name": row[1], "price": row[2], "category": row[3]} for row in
                    cursor.fetchall()]

    def create_order(self, table_number):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO orders (table_number) VALUES (?)", (table_number,))
            conn.commit()
            return cursor.lastrowid

    def add_item_to_order(self, order_id, item_id, quantity):
        self.execute_query(
            "INSERT INTO order_items (order_id, item_id, quantity) VALUES (?, ?, ?)",
            (order_id, item_id, quantity)
        )

    def get_pending_orders(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT order_id, table_number, timestamp FROM orders WHERE status = 'Pending'")
            orders = cursor.fetchall()

            result = []
            for order in orders:
                o_id, t_num, ts = order
                cursor.execute('''
                    SELECT m.name, oi.quantity
                    FROM order_items oi
                    JOIN menu_items m ON oi.item_id = m.item_id
                    WHERE oi.order_id = ?
                ''', (o_id,))
                items = [{"name": row[0], "quantity": row[1]} for row in cursor.fetchall()]

                result.append({
                    "order_id": o_id,
                    "table_number": t_num,
                    "timestamp": ts,
                    "items": items
                })
            return result

    def update_order_status(self, order_id, status):
        self.execute_query("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))


# ==========================================
# 2. สร้างแอป FastAPI และตัวแปรล็อกโต๊ะ
# ==========================================
app = FastAPI(title="SOOKOM POS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = POSDatabase()

# 🔥 ตัวแปรเก็บรายชื่อโต๊ะที่ถูกล็อก (เก็บในแรม)
LOCKED_TABLES = set()


# ==========================================
# 3. เตรียมข้อมูล
# ==========================================
def init_mock_data():
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS menu_items (
            item_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT
        )
    ''')
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_number INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            item_id TEXT,
            quantity INTEGER
        )
    ''')
    try:
        if len(db.get_all_menu()) == 0:
            db.execute_query("INSERT INTO menu_items VALUES ('F01', 'ข้าวกะเพราหมูสับไข่ดาว', 70, 'อาหารตามสั่ง')")
            db.execute_query("INSERT INTO menu_items VALUES ('F02', 'ข้าวผัดหมูกรอบ', 80, 'อาหารตามสั่ง')")
            db.execute_query("INSERT INTO menu_items VALUES ('D01', 'อเมริกาโน่เย็น', 55, 'เครื่องดื่ม')")
            db.execute_query("INSERT INTO menu_items VALUES ('D02', 'ชาไทยเย็น', 50, 'เครื่องดื่ม')")
    except:
        pass


init_mock_data()


# ==========================================
# 4. Endpoints
# ==========================================
class OrderItem(BaseModel):
    item_id: str
    quantity: int


class OrderRequest(BaseModel):
    table_number: int
    items: List[OrderItem]


@app.get("/")
def read_root():
    return {"message": "SOOKOM POS Ready"}


@app.get("/api/menu")
def get_menu():
    return {"status": "success", "data": db.get_all_menu()}


@app.post("/api/orders")
def place_order(order: OrderRequest):
    # 🔥 เช็คก่อนว่าโต๊ะล็อกอยู่ไหม
    if order.table_number in LOCKED_TABLES:
        return {"status": "error", "message": "โต๊ะนี้ถูกปิดรับออเดอร์แล้ว กรุณาติดต่อพนักงาน"}

    order_id = db.create_order(order.table_number)
    for item in order.items:
        db.add_item_to_order(order_id, item.item_id, item.quantity)
    return {"status": "success", "message": "รับออเดอร์สำเร็จ", "order_id": order_id}


@app.get("/api/kitchen/orders")
def get_kitchen_orders():
    return {"status": "success", "data": db.get_pending_orders()}


@app.put("/api/kitchen/orders/{order_id}/complete")
def complete_order(order_id: int):
    db.update_order_status(order_id, 'Completed')
    return {"status": "success", "message": "Done"}


@app.get("/api/bill/{table_number}")
def get_bill(table_number: int):
    with sqlite3.connect(db.db_name) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT order_id FROM orders WHERE table_number = ? AND status != 'Paid'", (table_number,))
        orders = cursor.fetchall()

        is_locked = table_number in LOCKED_TABLES  # เช็คสถานะล็อกส่งไปด้วย

        if not orders:
            return {"status": "empty", "message": "ไม่พบรายการ", "total": 0, "items": [], "is_locked": is_locked}

        total_price = 0
        items_summary = []

        for (order_id,) in orders:
            cursor.execute('''
                SELECT m.name, m.price, oi.quantity 
                FROM order_items oi
                JOIN menu_items m ON oi.item_id = m.item_id
                WHERE oi.order_id = ?
            ''', (order_id,))

            items = cursor.fetchall()
            for name, price, qty in items:
                subtotal = price * qty
                total_price += subtotal
                existing = next((x for x in items_summary if x['name'] == name), None)
                if existing:
                    existing['quantity'] += qty
                    existing['subtotal'] += subtotal
                else:
                    items_summary.append({"name": name, "price": price, "quantity": qty, "subtotal": subtotal})

    return {
        "status": "success",
        "table_number": table_number,
        "items": items_summary,
        "total": total_price,
        "is_locked": is_locked
    }


@app.post("/api/bill/{table_number}/pay")
def pay_bill(table_number: int):
    db.execute_query("UPDATE orders SET status = 'Paid' WHERE table_number = ? AND status != 'Paid'", (table_number,))
    # 🔥 จ่ายเงินเสร็จ ล็อกโต๊ะทันทีอัตโนมัติ!
    LOCKED_TABLES.add(table_number)
    return {"status": "success", "message": f"โต๊ะ {table_number} ชำระเงินแล้ว (ล็อกโต๊ะอัตโนมัติ)"}


# 🔥 API สำหรับเปิด/ปิดโต๊ะ (ใช้โดยแคชเชียร์)
@app.post("/api/tables/{table_number}/lock")
def lock_table(table_number: int):
    LOCKED_TABLES.add(table_number)
    return {"status": "success", "message": f"ล็อกโต๊ะ {table_number} แล้ว"}


@app.post("/api/tables/{table_number}/unlock")
def unlock_table(table_number: int):
    if table_number in LOCKED_TABLES:
        LOCKED_TABLES.remove(table_number)
    return {"status": "success", "message": f"เปิดโต๊ะ {table_number} แล้ว"}