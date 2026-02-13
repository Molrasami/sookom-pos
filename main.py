from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import sqlite3
from fastapi.middleware.cors import CORSMiddleware



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
        cursor = self.execute_query("INSERT INTO orders (table_number) VALUES (?)", (table_number,))
        return cursor.lastrowid

    def add_item_to_order(self, order_id, item_id, quantity):
        self.execute_query(
            "INSERT INTO order_items (order_id, item_id, quantity) VALUES (?, ?, ?)",
            (order_id, item_id, quantity)
        )

    # --- ส่วนที่เพิ่มใหม่สำหรับห้องครัว ---
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
# 2. สร้างแอป FastAPI และอนุญาต CORS
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


# ==========================================
# 3. ฟังก์ชันเตรียมข้อมูลเริ่มต้น (เมนู)
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

    items = db.get_all_menu()
    if len(items) == 0:
        db.execute_query("INSERT INTO menu_items VALUES ('F01', 'ข้าวกะเพราหมูสับไข่ดาว', 70, 'อาหารตามสั่ง')")
        db.execute_query("INSERT INTO menu_items VALUES ('F02', 'ข้าวผัดหมูกรอบ', 80, 'อาหารตามสั่ง')")
        db.execute_query("INSERT INTO menu_items VALUES ('D01', 'อเมริกาโน่เย็น', 55, 'เครื่องดื่ม')")
        db.execute_query("INSERT INTO menu_items VALUES ('D02', 'ชาไทยเย็น', 50, 'เครื่องดื่ม')")
        print("✅ เตรียมฐานข้อมูล SOOKOM สำเร็จ!")


init_mock_data()


# ==========================================
# 4. โมเดลรับข้อมูล (Pydantic)
# ==========================================
class OrderItem(BaseModel):
    item_id: str
    quantity: int


class OrderRequest(BaseModel):
    table_number: int
    items: List[OrderItem]


# ==========================================
# 5. Endpoints (URL สำหรับเชื่อมต่อหน้าเว็บ)
# ==========================================
@app.get("/")
def read_root():
    return {"message": "Welcome to SOOKOM POS API. ระบบทำงานปกติ!"}


@app.get("/api/menu")
def get_menu():
    return {"status": "success", "data": db.get_all_menu()}


@app.post("/api/orders")
def place_order(order: OrderRequest):
    order_id = db.create_order(order.table_number)
    for item in order.items:
        db.add_item_to_order(order_id, item.item_id, item.quantity)
    return {"status": "success", "message": "รับออเดอร์สำเร็จ", "order_id": order_id}


# --- Endpoints ที่เพิ่มใหม่สำหรับห้องครัว ---
@app.get("/api/kitchen/orders")
def get_kitchen_orders():
    return {"status": "success", "data": db.get_pending_orders()}


@app.put("/api/kitchen/orders/{order_id}/complete")
def complete_order(order_id: int):
    db.update_order_status(order_id, 'Completed')
    return {"status": "success", "message": f"ออเดอร์ #{order_id} ทำเสร็จแล้ว"}