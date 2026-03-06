from schema import Product, Order, Customer, Category
import uuid

products = [
    Product(id=1, name="Wireless Mouse", price=29.99, description="Ergonomic wireless mouse with USB receiver"),
    Product(id=2, name="Mechanical Keyboard", price=89.99, description="Compact mechanical keyboard with RGB backlight"),
    Product(id=3, name="USB-C Hub", price=49.99, description="7-in-1 USB-C hub with HDMI and card reader"),
    Product(id=4, name="Monitor Stand", price=39.99, description="Adjustable aluminium monitor riser"),
    Product(id=5, name="Webcam HD", price=69.99, description="1080p webcam with built-in microphone"),
]

customers = [
    Customer(id=101, name="Alice Johnson", email="alice.johnson@example.com"),
    Customer(id=102, name="Bob Smith", email="bob.smith@example.com"),
    Customer(id=103, name="Carol White", email="carol.white@example.com"),
]

orders = [
    Order(id=uuid.uuid4(), customer_id=101, description="Wireless Mouse x1"),
    Order(id=uuid.uuid4(), customer_id=101, description="Mechanical Keyboard x1, USB-C Hub x2"),
    Order(id=uuid.uuid4(), customer_id=102, description="Monitor Stand x1"),
    Order(id=uuid.uuid4(), customer_id=102, description="Webcam HD x1, Wireless Mouse x1"),
    Order(id=uuid.uuid4(), customer_id=103, description="USB-C Hub x1"),
]

categories = [
    Category(id=uuid.uuid4(), name="Category 1", description="Description of Category 1"),
    Category(id=uuid.uuid4(), name="Category 2", description="Description of Category 2"),
    Category(id=uuid.uuid4(), name="Category 3", description="Description of Category 3"),
]

carts = []
cart_items = []
