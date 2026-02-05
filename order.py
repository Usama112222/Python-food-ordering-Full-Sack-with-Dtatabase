from database import get_connection

class Menu:
    def __init__(self):
        self.menu_items = {}

    def add_item(self, name, price):
        self.menu_items[name] = price

    def get_price(self, name):
        return self.menu_items.get(name, 0)


class Order:
    def __init__(self, menu):
        self.menu = menu

    # -------- ADD ORDER --------
    def add_order_web(self, items, user_id):
        total = sum(self.menu.get_price(i) * q for i, q in items.items())
        conn = get_connection()
        if not conn:
            print("Cannot connect to database")
            return
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO orders (user_id, total) VALUES (%s, %s) RETURNING order_id;",
                (int(user_id), total)
            )
            order_id = cur.fetchone()[0]

            for item, qty in items.items():
                cur.execute(
                    """
                    INSERT INTO order_items (order_id, item_name, quantity, price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (order_id, item, qty, self.menu.get_price(item))
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("Error adding order:", e)
        finally:
            cur.close()
            conn.close()

    # -------- DELETE ORDER --------
    def delete_order_web(self, order_id, user_id=None):
        conn = get_connection()
        if not conn:
            return
        cur = conn.cursor()
        try:
            if user_id:
                cur.execute(
                    "DELETE FROM orders WHERE order_id=%s AND user_id=%s;",
                    (int(order_id), int(user_id))
                )
            else:
                cur.execute(
                    "DELETE FROM orders WHERE order_id=%s;",
                    (int(order_id),)
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("Error deleting order:", e)
        finally:
            cur.close()
            conn.close()

    # -------- UPDATE ORDER --------
    def update_order_web(self, order_id, items, user_id=None):
        total = sum(self.menu.get_price(i) * q for i, q in items.items())
        conn = get_connection()
        if not conn:
            return
        cur = conn.cursor()
        try:
            if user_id:
                cur.execute("SELECT user_id FROM orders WHERE order_id=%s;", (int(order_id),))
                owner = cur.fetchone()
                if not owner or owner[0] != int(user_id):
                    print("Cannot update order: not authorized")
                    return

            cur.execute("DELETE FROM order_items WHERE order_id=%s;", (int(order_id),))

            for item, qty in items.items():
                cur.execute(
                    "INSERT INTO order_items (order_id, item_name, quantity, price) VALUES (%s,%s,%s,%s);",
                    (int(order_id), item, qty, self.menu.get_price(item))
                )

            cur.execute("UPDATE orders SET total=%s WHERE order_id=%s;", (total, int(order_id)))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("Error updating order:", e)
        finally:
            cur.close()
            conn.close()

    # -------- GET SINGLE ORDER --------
    def get_order_web(self, order_id, user_id=None):
        conn = get_connection()
        if not conn:
            return []
        cur = conn.cursor()
        try:
            if user_id is not None:
                cur.execute(
                    """
                    SELECT item_name, quantity, price
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.order_id
                    WHERE oi.order_id=%s AND o.user_id=%s
                    """,
                    (int(order_id), int(user_id))
                )
            else:
                cur.execute(
                    "SELECT item_name, quantity, price FROM order_items WHERE order_id=%s;",
                    (int(order_id),)
                )
            return [{"name": item, "quantity": qty, "price": price} for item, qty, price in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    # -------- GET ALL ORDERS (with username & items) --------
    def get_all_orders_web(self, user_id=None):
        """
        Returns a list of orders:
        [
            {
                "order_id": 1,
                "username": "admin",
                "total": 200,
                "items": [{"name":"burger","quantity":2,"price":100}, ...]
            },
            ...
        ]
        """
        conn = get_connection()
        if not conn:
            return []
        cur = conn.cursor()
        try:
            if user_id is not None:
                cur.execute("""
                    SELECT o.order_id, o.total, u.username
                    FROM orders o
                    JOIN users u ON o.user_id = u.id
                    WHERE o.user_id=%s
                    ORDER BY o.created_at DESC
                """, (int(user_id),))
            else:
                cur.execute("""
                    SELECT o.order_id, o.total, u.username
                    FROM orders o
                    JOIN users u ON o.user_id = u.id
                    ORDER BY o.created_at DESC
                """)

            orders_data = []
            for order_id, total, username in cur.fetchall():
                # Fetch items for each order
                cur.execute("SELECT item_name, quantity, price FROM order_items WHERE order_id=%s;", (int(order_id),))
                items = [{"name": name, "quantity": qty, "price": price} for name, qty, price in cur.fetchall()]
                orders_data.append({
                    "order_id": order_id,
                    "username": username,
                    "total": total,
                    "items": items
                })

            return orders_data
        finally:
            cur.close()
            conn.close()
