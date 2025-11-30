import logging
from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Load environment variables
load_dotenv(".env.local")
logger = logging.getLogger("agent")

# --- Data Models ---
@dataclass
class Product:
    id: str
    name: str
    description: str
    price: int
    currency: str
    category: str
    color: str
    sizes: List[str]

@dataclass
class Order:
    id: str
    items: List[dict]
    total: int
    currency: str
    created_at: str

# --- Product Catalog ---
PRODUCTS = [
    Product(
        id="hoodie-001",
        name="Jacferdi Hoodie",
        description="Unisex minimalist hoodie by Jacferdi Studios",
        price=1800,
        currency="INR",
        category="hoodie",
        color="black",
        sizes=["S", "M", "L", "XL"],
    ),
    Product(
        id="tshirt-001",
        name=" T-Shirt",
        description="Unisex classic t-shirt by Jacferdi Studios",
        price=1200,
        currency="INR",
        category="tshirt",
        color="white",
        sizes=["S", "M", "L", "XL"],
    ),
    Product(
        id="jeans-001",
        name="Straight Fit Jeans",
        description="Slim fit jeans by Jacferdi Studios",
        price=2200,
        currency="INR",
        category="jeans",
        color="indigo",
        sizes=["S", "M", "L", "XL"],
    ),
    Product(
        id="shoes-001",
        name="Converse Sneakers",
        description="Casual sneakers by Jacferdi Studios",
        price=3000,
        currency="INR",
        category="shoes",
        color="gray",
        sizes=[ "S", "M", "L"],
    ),
]

# --- Cart and Order Storage ---
CART_FILE = "cart.json"
ORDERS_FILE = "orders.json"
CART = []
ORDERS = []

# Load existing cart and orders if the files exist
if os.path.exists(CART_FILE):
    with open(CART_FILE, "r") as f:
        try:
            CART = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            CART = []

if os.path.exists(ORDERS_FILE):
    with open(ORDERS_FILE, "r") as f:
        try:
            ORDERS = [Order(**order) for order in json.load(f)]
        except (json.JSONDecodeError, FileNotFoundError):
            ORDERS = []

# --- Backend Functions ---
def save_cart():
    """Save the cart to the JSON file."""
    with open(CART_FILE, "w") as f:
        json.dump(CART, f, indent=2)

def save_orders():
    """Save all orders to the JSON file."""
    with open(ORDERS_FILE, "w") as f:
        json.dump([asdict(order) for order in ORDERS], f, indent=2)

def list_products(filters: Optional[dict] = None) -> List[dict]:
    """Filter and return products based on criteria."""
    if not filters:
        return [asdict(p) for p in PRODUCTS]

    filtered = PRODUCTS
    if filters.get("category"):
        category = filters["category"].lower()
        filtered = [p for p in filtered if category in p.category.lower()]
    if filters.get("name"):
        name = filters["name"].lower()
        filtered = [p for p in filtered if name in p.name.lower()]
    if filters.get("max_price"):
        filtered = [p for p in filtered if p.price <= filters["max_price"]]
    if filters.get("color"):
        filtered = [p for p in filtered if p.color.lower() == filters["color"].lower()]
    return [asdict(p) for p in filtered]

def add_to_cart(product_id: str, size: str, quantity: int = 1):
    """Add a product to the cart."""
    product = next((p for p in PRODUCTS if p.id == product_id), None)
    if product:
        item = {
            "product_id": product.id,
            "name": product.name,
            "size": size,
            "quantity": quantity,
            "price": product.price,
        }
        CART.append(item)
        save_cart()
        return item
    else:
        raise ValueError(f"Product {product_id} not found")

def create_order_from_cart():
    """Create an order from the cart."""
    if not CART:
        raise ValueError("Cart is empty")

    order_id = f"order-{len(ORDERS) + 1}"
    total = sum(item["price"] * item["quantity"] for item in CART)
    order = Order(
        id=order_id,
        items=CART.copy(),
        total=total,
        currency="INR",
        created_at=datetime.now().isoformat(),
    )
    ORDERS.append(order)
    CART.clear()
    save_cart()
    save_orders()
    return asdict(order)

def get_last_order() -> Optional[dict]:
    """Retrieve the most recent order."""
    return asdict(ORDERS[-1]) if ORDERS else None

# --- LiveKit Agent ---
class ECommerceAssistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
            You are a helpful voice shopping assistant for 'Jacferdi Studios'.
            - Use the provided tools to help users browse products and place orders.
            - Always confirm the order details and total price before finalizing.
            - If a user asks for "clothes" or "dress", respond with: "We offer hoodies, t-shirts, jeans, and sneakers. Which category are you interested in?"
            - If a user asks for a specific category, list the available products and ask for the size and color (if applicable).
            - Example: "We have the 'Jacferdi Hoodie' in black for 1800 INR. It's a unisex minimalist hoodie available in sizes S, M, L, and XL. Which size would you like?"
            - After the user specifies the size and color, add the item to the cart and say: "Item added to your cart. Would you like to buy anything else or checkout?"
            - If the user says "checkout", create an order from the cart and say: "Your order (ID) for (items) has been placed. The total is (total) INR. Thank you for shopping with Jacferdi Studios!"
            - Ask if the user wants anything else or needs changes before finalizing.
            """,
        )

    @function_tool
    async def list_products(self, context: RunContext, filters: dict = None):
        """Search the product catalog based on filters."""
        return list_products(filters)

    @function_tool
    async def add_to_cart(self, context: RunContext, product_id: str, size: str, quantity: int = 1):
        """Add a product to the cart."""
        item = add_to_cart(product_id, size, quantity)
        return {
            "message": f"Item '{item['name']}' (Size: {item['size']}) added to your cart. Would you like to buy anything else or checkout?"
        }

    @function_tool
    async def create_order_from_cart(self, context: RunContext):
        """Create an order from the cart."""
        order = create_order_from_cart()
        return {
            "order_id": order["id"],
            "items": order["items"],
            "total": order["total"],
            "currency": order["currency"],
            "message": f"Your order {order['id']} for {len(order['items'])} items has been placed. The total is {order['total']} {order['currency']}. Thank you for shopping with Jacferdi Studios!"
        }

    @function_tool
    async def get_last_order(self, context: RunContext):
        """Get the most recent order placed by the user."""
        return get_last_order()

# --- Agent Session Setup ---
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-daisy",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)
    await session.start(
        agent=ECommerceAssistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
