# server.py
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from typing import Union
import uuid

from typing import List, Dict, Any, Optional

class Order(BaseModel): 
    id: int 
    customer_id: int 
    quantity: int 
    total_price: float 
    status: str

class Cart(BaseModel):
    id: int
    orders: List[Order]

class Product(BaseModel):
    id: int
    name: str
    description: str
    price: float
    category: str

class Category(BaseModel):
    id: int
    name: str
    description: str

class Customer(BaseModel):
    id: int
    name: str
    adress: str

# Create an MCP server
mcp = FastMCP("Demo")


# Add a multiply tool
@mcp.tool()
def multiply(first: int, second: int) -> int:
    """Multiply two numbers"""
    return first * second


# Add a dynamic greeting resource
@mcp.resource("echo://{message}")
def get_greeting(message: str) -> str:
    """Echo out the message"""
    return f"Resource echo, {message}!"

@mcp.tool(name="get-orders")
def get_orders(customer_id: Optional[int] = 0):
    """Return a list of orders"""
    return [
        Order(id=1, customer_id=101, quantity=2, total_price=49.99, status="shipped"), 
        Order(id=2, customer_id=102, quantity=1, total_price=19.99, status="processing"), 
        Order(id=3, customer_id=103, quantity=5, total_price=149.95, status="delivered"),
    ]

@mcp.tool(name="get-order")
def get_order(order_id: int):
    """Return a specific order"""
    return [
        Order(id=1, customer_id=101, quantity=2, total_price=49.99, status="shipped"), 
    ]
@mcp.tool(name="place-order")
def plcae_order(customer_id: int, cart_id: int):
    """Place a specific order"""
    return "Order placed"

@mcp.tool(name="get-cart")
def get_cart(cart_id: int):
    """Return a specific cart"""
    return Cart(id =cart_id, orders = [Order(id=1, customer_id=101, quantity=2, total_price=49.99, status="shipped"),  Order(id=2, customer_id=102, quantity=1, total_price=19.99, status="processing"),])
    
@mcp.tool(name="get-cart")
def get_cart(cart_id: int):
    """Return a specific cart"""
    return Cart(id =cart_id, orders = [Order(id=1, customer_id=101, quantity=2, total_price=49.99, status="shipped"),  Order(id=2, customer_id=102, quantity=1, total_price=19.99, status="processing"),])


@mcp.tool(name="get-cart-items")
def get_cart_items(cart_id: int):
    """Return a specific cart items"""
    return [Order(id=1, customer_id=101, quantity=2, total_price=49.99, status="shipped"),  Order(id=2, customer_id=102, quantity=1, total_price=19.99, status="processing"),]
    

@mcp.tool(name="add-to-cart")
def add_to_cart(cart_id: int, prod_id:int, quantity:int):
    """Add products to cart"""
    return "Products added"

@mcp.tool(name="products")
def list_products():
    """List all products"""
    return [
        Product(id=1, name="Wireless Mouse", description="Ergonomic 2.4G wireless mouse", price=19.99, category="Accessories"),
        Product(id=2, name="Mechanical Keyboard", description="Compact mechanical keyboard with blue switches", price=79.99, category="Accessories"),
        Product(id=3, name="USB-C Hub", description="6-in-1 USB-C hub with HDMI and USB-A ports", price=29.99, category="Adapters"),
    ]

@mcp.tool(name="product")
def get_product(prod_id:int):
    """List all products"""
    return  Product(id=3, name="USB-C Hub", description="6-in-1 USB-C hub with HDMI and USB-A ports", price=29.99, category="Adapters")

@mcp.tool(name="categories")
def get_categories():
    """List all categories"""
    return [
        Category(id=1, name="Accessories", description="Peripherals and add-ons for your setup"),
        Category(id=2, name="Adapters", description="Hubs, dongles, and connectivity accessories"),
        Category(id=3, name="Storage", description="Drives and storage-related products"),
    ]

@mcp.tool(name="get-customers")
def get_customers():
    """List all customers"""
    return [
        Customer(id=1, name="Ass lick", adress="Sofia"),
        Customer(id=2, name="Ass lick", adress="Sofia"),
        Customer(id=3, name="Ass lick", adress="Sofia"),
    ]


@mcp.resource("catalog://products/{category}")
def products_catalog_by_category(category: str) -> list[Product]:
    all_products = [
        Product(id=1, name="Wireless Mouse", description="Ergonomic 2.4G wireless mouse", price=19.99, category="Accessories"),
        Product(id=2, name="Mechanical Keyboard", description="Compact mechanical keyboard with blue switches", price=79.99, category="Accessories"),
        Product(id=3, name="USB-C Hub", description="6-in-1 USB-C hub with HDMI and USB-A ports", price=29.99, category="Adapters"),
    ]
    return [p for p in all_products if p.category.lower() == category.lower()]