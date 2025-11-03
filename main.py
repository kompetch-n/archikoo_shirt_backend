# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
from pymongo import MongoClient
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import random
import string


# ===== MongoDB Atlas Connection =====
MONGO_URI = "mongodb+srv://kompetchn:1234@cluster0.3fttexy.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client["shirt_orders"]
collection = db["customers"]

collection.create_index("orderId", unique=True)
collection.create_index("tracking_number")

# ===== ฟังก์ชันช่วยสร้าง Order ID =====
def generate_order_id():
    prefix = "ORD"
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"{prefix}{random_part}"

# ===== Pydantic Models =====
class ShirtItem(BaseModel):
    size: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)

    @validator("size")
    def uppercase_size(cls, v):
        return v.upper()

class CustomerIn(BaseModel):
    full_name: str = Field(..., alias="fullName")
    phone: str
    address: str
    items: List[ShirtItem]
    tracking_number: Optional[str] = None  # 🆕 เลขพัสดุ

    @validator("items")
    def at_least_one_item(cls, v):
        if not v:
            raise ValueError("ต้องระบุอย่างน้อย 1 รายการ")
        return v

class TrackingUpdate(BaseModel):
    tracking_number: str

# ===== FastAPI App =====
app = FastAPI(title="ลงทะเบียนสั่งซื้อเสื้อ (หลาย Size)")

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. ลงทะเบียนสั่งซื้อ
@app.post("/register")
async def register(customer: CustomerIn):
    data = customer.dict(by_alias=True)

    # 🆕 สร้าง Order ID อัตโนมัติ
    order_id = generate_order_id()
    while collection.find_one({"orderId": order_id}):
        order_id = generate_order_id()  # กันซ้ำ

    data["orderId"] = order_id
    data["order_date"] = datetime.utcnow()
    data["status"] = "pending" if not data.get("tracking_number") else "shipped"

    result = collection.insert_one(data)
    created = collection.find_one({"_id": result.inserted_id})
    created["id"] = str(created["_id"])
    created.pop("_id", None)
    return created

# 2. ค้นหาด้วยเลขพัสดุ
@app.get("/track/{tracking}")
async def track(tracking: str):
    customer = collection.find_one({"tracking_number": tracking})
    if not customer:
        raise HTTPException(404, "ไม่พบเลขพัสดุนี้")
    customer["id"] = str(customer["_id"])
    customer.pop("_id", None)
    return customer

# 3. ค้นหาด้วย Order ID
@app.get("/order/{order_id}")
async def get_order(order_id: str):
    customer = collection.find_one({"orderId": order_id})
    if not customer:
        raise HTTPException(404, "ไม่พบ Order ID")
    customer["id"] = str(customer["_id"])
    customer.pop("_id", None)
    return customer

# 4. อัปเดตเลขพัสดุ
@app.put("/order/{order_id}/track")
async def update_tracking(order_id: str, body: TrackingUpdate):
    result = collection.update_one(
        {"orderId": order_id},
        {"$set": {"tracking_number": body.tracking_number, "status": "shipped"}}
    )
    if result.modified_count == 0:
        raise HTTPException(404, "ไม่พบ Order หรืออัปเดตไม่สำเร็จ")
    
    updated = collection.find_one({"orderId": order_id})
    updated["id"] = str(updated["_id"])
    updated.pop("_id", None)
    return updated

# 5. ดูข้อมูลทั้งหมด
@app.get("/all")
async def get_all():
    customers = list(collection.find())
    for c in customers:
        c["id"] = str(c["_id"])
        c.pop("_id", None)
    return customers

# 6. ค้นหา Order(s) ด้วยชื่อ
@app.get("/search-by-name")
async def search_by_name(name: str):
    # ใช้ regex เพื่อค้นหา case-insensitive
    customers = list(collection.find({"full_name": {"$regex": name, "$options": "i"}}))
    if not customers:
        raise HTTPException(404, "ไม่พบชื่อที่ค้นหา")
    
    for c in customers:
        c["id"] = str(c["_id"])
        c.pop("_id", None)
    return customers


# ===== รันเซิร์ฟเวอร์ =====
# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
