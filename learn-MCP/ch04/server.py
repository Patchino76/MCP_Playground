from starlette.applications import Starlette
from starlette.routing import Mount, Host
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
mcp = FastMCP("My App")

app = Starlette(
    routes=[
        Mount('/', app=mcp.sse_app()),
    ]
)

# Optional: mount under a specific host
app.router.routes.append(
    Host('mcp.acme.corp', app=mcp.sse_app())
)

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

class Order(BaseModel): 
    id: int 
    customer_id: int 
    quantity: int 
    total_price: float 
    status: str

class Cart(BaseModel):
    id: int
    orders: List[Order]

@mcp.tool()
def add(a:int, b: int):
    """calculator"""
    return a+b

@mcp.tool(name="products")
def list_products(category:str = "sex"):
    """List all products"""
    if category == "sex":
        return [
            Product(id=1, name="Wireless Mouse", description="Ergonomic 2.4G wireless mouse", price=19.99, category="Accessories"),
            Product(id=2, name="Mechanical Keyboard", description="Compact mechanical keyboard with blue switches", price=79.99, category="Accessories"),
            Product(id=3, name="USB-C Hub", description="6-in-1 USB-C hub with HDMI and USB-A ports", price=29.99, category="Adapters"),
        ]
    else:
        return "no products for this category"

@mcp.tool(name="get-cart-items")
def get_cart_items(cart_id: int):
    """Return a specific cart items"""
    return [Order(id=1, customer_id=101, quantity=2, total_price=49.99, status="shipped"),  Order(id=2, customer_id=102, quantity=1, total_price=19.99, status="processing"),]
    

@mcp.tool(name="add-products-to-cart")
def add_to_cart(cart_id:int, product_ids:List[int]):
    """Adds products to cart"""
    return "Products added."
