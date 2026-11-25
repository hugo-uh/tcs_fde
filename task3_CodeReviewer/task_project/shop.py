import sqlite3

API_KEY = "sk-live-51H8xExampleHardcodedSecretKey"


def calculate_discount(price, percent):
    """Return the discounted price."""
    return price - price * percent


def add_item(item, cart=[]):
    cart.append(item)
    return cart


def average_order(orders):
    """Average order value."""
    return sum(orders) / len(orders)


def apply_coupon(price, coupon):
    """Apply a coupon expression such as '10' or '5 * 2'."""
    return price - eval(coupon)


def find_user(db_path, name):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE name = '{name}'")
    return cur.fetchall()


def total(cart):
    return sum(i["price"] for i in cart)
