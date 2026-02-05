from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
from order import Order, Menu
from functools import wraps
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "supersecret"

# -------- FLASK-LOGIN SETUP --------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# -------- USER MODEL --------
class User(UserMixin):
    def __init__(self, id, username, email, password_hash, role):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, email, password_hash, role FROM users WHERE id=%s", (user_id,))
        user_data = cur.fetchone()
        if user_data:
            return User(*user_data)
    finally:
        cur.close()
        conn.close()
    return None

# -------- ADMIN CHECK DECORATOR --------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# -------- MENU & RESTAURANT --------
menu = Menu()
menu.add_item("pizza", 1500)
menu.add_item("burger", 500)
menu.add_item("pasta", 1000)
menu.add_item("fries", 300)
restaurant = Order(menu)

# -------- HOME --------
@app.route("/")
def home():
    return render_template("index.html")

# -------- SIGN UP --------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_pw = generate_password_hash(password)

        conn = get_connection()
        if not conn:
            flash("Database connection error", "danger")
            return redirect(url_for("signup"))

        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                (username, email, hashed_pw, "user")
            )
            conn.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            conn.rollback()
            flash("Username or Email already exists!", "danger")
            print(e)
            return redirect(url_for("signup"))
        finally:
            cur.close()
            conn.close()
    return render_template("signup.html")

# -------- LOGIN --------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_connection()
        if not conn:
            flash("Database connection error", "danger")
            return redirect(url_for("login"))

        try:
            cur = conn.cursor()
            cur.execute("SELECT id, username, email, password_hash, role FROM users WHERE email=%s", (email,))
            user_data = cur.fetchone()
            if user_data and check_password_hash(user_data[3], password):
                user = User(*user_data)
                login_user(user)
                flash(f"Welcome back, {user.username}!", "success")
                return redirect(url_for("home"))
            else:
                flash("Invalid email or password.", "danger")
                return redirect(url_for("login"))
        finally:
            cur.close()
            conn.close()
    return render_template("login.html")

# -------- LOGOUT --------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

# -------- BOOK ORDER --------
@app.route("/order", methods=["GET", "POST"])
@login_required
def order():
    message = ""
    if request.method == "POST":
        items = {item: int(qty) for item, qty in request.form.items() if qty.isdigit() and int(qty) > 0}
        if items:
            restaurant.add_order_web(items, user_id=current_user.id)
            message = "Order placed successfully!"
    return render_template("order.html", menu_items=menu.menu_items, message=message)

# -------- SEE ALL ORDERS WITH PAGINATION --------
@app.route("/orders")
@login_required
def orders():
    page = request.args.get('page', 1, type=int)
    per_page = 10

    if current_user.role == "admin":
        all_orders = restaurant.get_all_orders_web()
    else:
        all_orders = restaurant.get_all_orders_web(user_id=current_user.id)

    total_orders = len(all_orders)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_orders = all_orders[start:end]
    total_pages = (total_orders + per_page - 1) // per_page

    item_totals = defaultdict(int)
    for order in all_orders:
        for item in order['items']:
            item_totals[item['name']] += item['quantity']

    return render_template(
        "all_order.html",
        orders=paginated_orders,
        page=page,
        total_pages=total_pages,
        item_totals=dict(item_totals),
        current_user=current_user
    )

# -------- DELETE ORDER --------
@app.route("/delete_order/<int:order_id>", methods=["POST"])
@login_required
@admin_required
def delete_order(order_id):
    restaurant.delete_order_web(order_id)
    flash(f"Order #{order_id} deleted successfully!")
    return redirect(url_for("orders"))

# -------- SEARCH ORDER --------
@app.route("/search_order", methods=["GET"])
@login_required
def search_order():
    order_id = request.args.get("order_id")
    if not order_id or not order_id.isdigit():
        flash("Please enter a valid order ID.")
        return redirect(url_for("orders"))

    order_id = int(order_id)

    # Permission check
    if current_user.role == "admin":
        order_items = restaurant.get_order_web(order_id)
    else:
        order_items = restaurant.get_order_web(order_id, user_id=current_user.id)
        if not order_items:
            flash("Order not found or you do not have access to it.")
            return redirect(url_for("orders"))

    return redirect(url_for("update_order_page", order_id=order_id))

# -------- UPDATE ORDER --------
@app.route("/update_order/<int:order_id>", methods=["GET", "POST"])
@login_required
def update_order_page(order_id):
    if current_user.role == "admin":
        order_items = restaurant.get_order_web(order_id)
    else:
        order_items = restaurant.get_order_web(order_id, user_id=current_user.id)
        if not order_items:
            abort(403)

    all_menu = menu.menu_items

    if request.method == "POST":
        updated_items = {item: int(qty) for item, qty in request.form.items() if qty.isdigit() and int(qty) > 0}
        if updated_items:
            if current_user.role == "admin":
                restaurant.update_order_web(order_id, updated_items)
            else:
                restaurant.update_order_web(order_id, updated_items, user_id=current_user.id)
            flash(f"Order {order_id} updated successfully!")
            return redirect(url_for("orders"))

    return render_template("update_order.html", order_id=order_id, order_items=order_items, menu_items=all_menu)


# -------- RUN APP --------
if __name__ == "__main__":
    app.run(debug=True)
