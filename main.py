# main.py
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field, validator
from typing import List
from datetime import datetime
from pymongo import MongoClient
import uvicorn

# ===== MongoDB Atlas Connection =====
MONGO_URI = "mongodb+srv://kompetchn:1234@cluster0.3fttexy.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client["shirt_orders"]
collection = db["customers"]

collection.create_index("orderId", unique=True)
collection.create_index("tracking_number")

# ===== Pydantic Models =====
class ShirtItem(BaseModel):
    size: str = Field(..., pattern="^(S|M|L|XL|XXL|XXXL)$")
    quantity: int = Field(..., gt=0)

    @validator("size")
    def uppercase_size(cls, v):
        return v.upper()

class CustomerIn(BaseModel):
    order_id: str = Field(..., alias="orderId")
    full_name: str = Field(..., alias="fullName")  # แก้ตรงนี้
    phone: str
    address: str
    items: List[ShirtItem]

    @validator("items")
    def at_least_one_item(cls, v):
        if not v:
            raise ValueError("ต้องระบุอย่างน้อย 1 รายการ")
        return v

class TrackingUpdate(BaseModel):
    tracking_number: str

# ===== FastAPI App =====
app = FastAPI(title="ลงทะเบียนสั่งซื้อเสื้อ (หลาย Size)")

@app.post("/register")
async def register(customer: CustomerIn):
    data = customer.dict(by_alias=True)
    data["order_date"] = datetime.utcnow()
    data["status"] = "pending"

    if collection.find_one({"orderId": data["orderId"]}):
        raise HTTPException(400, "Order ID นี้มีอยู่แล้ว")

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

# ===== รันเซิร์ฟเวอร์ =====
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)