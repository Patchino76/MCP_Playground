from pydantic import BaseModel, Field
import uuid

class Customer(BaseModel):
    id: int
    name: str
    email: str


class Category(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    description: str


class Product(BaseModel):
    id: int
    name: str
    price: float
    description: str


class CartItem(BaseModel):
    id: int
    cart_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: int
    quantity: int


class Cart(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    customer_id: int


class Order(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    customer_id: int
    description: str
