import psycopg2
from psycopg2 import sql
from werkzeug.security import generate_password_hash

DB_CONFIG = {
    "host": "localhost",
    "database": "resturent",
    "user": "postgres",
    "password": "usama1122",
    "port": 5432
}

def get_connection():
    """
    Returns a new connection to the PostgreSQL database.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as error:
        print(f"Error connecting to PostgreSQL: {error}")
        return None

def create_tables():
    """
    Creates the users, orders, and order_items tables if they don't exist.
    Also creates a default admin if not exists.
    """
    conn = get_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()

        # -------- USERS TABLE --------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) DEFAULT 'user'  -- 'admin' or 'user'
        );
        """)

        # -------- ORDERS TABLE --------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            total NUMERIC(10, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # -------- ORDER ITEMS TABLE --------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            item_id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
            item_name VARCHAR(100),
            quantity INTEGER,
            price NUMERIC(10, 2)
        );
        """)

        conn.commit()
        print("Tables created successfully!")

        # -------- CREATE DEFAULT ADMIN --------
        cursor.execute("SELECT * FROM users WHERE role='admin';")
        admin_exists = cursor.fetchone()
        if not admin_exists:
            admin_username = "admin"
            admin_email = "admin@gmail.com"
            admin_password = generate_password_hash("admin123")  # Default admin password
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s);",
                (admin_username, admin_email, admin_password, "admin")
            )
            conn.commit()
            print("Default admin created: admin@gmail.com / admin123")

    except Exception as error:
        conn.rollback()
        print("Error creating tables or admin:", error)

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_tables()
