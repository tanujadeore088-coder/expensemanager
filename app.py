import os
import sqlite3
import tempfile
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
# Secret key for session messages and flash alerts
app.secret_key = "expense_tracker_secret_key_super_secure"

# Path to SQLite database file
# On Vercel serverless environments, the root directory is read-only. We write to /tmp.
if os.environ.get("VERCEL"):
    DATABASE = os.path.join(tempfile.gettempdir(), "database.db")
else:
    DATABASE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "database.db")


def get_db_connection():
    """
    Creates and returns a connection to the SQLite database.
    row_factory is set to sqlite3.Row so columns can be accessed by name (like dictionaries).
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    # Enable foreign key support in SQLite
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Initializes the database schema and seeds default categories and sample records
    if they do not already exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Categories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT NOT NULL UNIQUE
        )
    """)

    # Create Expenses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            category_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE RESTRICT
        )
    """)

    # Check and insert default categories
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ("Food",),
            ("Travel",),
            ("Shopping",),
            ("Education",),
            ("Bills",),
            ("Entertainment",)
        ]
        cursor.executemany("INSERT INTO categories (category_name) VALUES (?)", default_categories)
        conn.commit()

    # Clean up any previously seeded sample/dummy expenses
    cursor.execute("""
        DELETE FROM expenses WHERE title IN (
            'Weekly Grocery Restock',
            'Monthly Metro Card',
            'Electricity & Internet Bill',
            'Programming Books & Course',
            'Weekend Cinema & Dinner',
            'Casual Sneakers',
            'Flight Booking for Holiday'
        )
    """)
    conn.commit()

    conn.close()


# Ensure database and tables exist at application launch
init_db()


# ==============================================================================
# ROUTE 1: DASHBOARD
# ==============================================================================
@app.route("/")
def index():
    """
    Renders the modern Dashboard with summary metric cards,
    recent transactions list, and category breakdown.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Total expenses across all time
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM expenses")
    total_expenses = cursor.fetchone()["total"]

    # 2. Total expenses in the current month (YYYY-MM)
    current_month_prefix = datetime.now().strftime("%Y-%m")
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as total 
        FROM expenses 
        WHERE strftime('%Y-%m', date) = ?
    """, (current_month_prefix,))
    current_month_expenses = cursor.fetchone()["total"]

    # 3. Total number of transactions
    cursor.execute("SELECT COUNT(*) as count FROM expenses")
    total_transactions = cursor.fetchone()["count"]

    # 4. Top spending category
    cursor.execute("""
        SELECT c.category_name, SUM(e.amount) as total_cat
        FROM expenses e
        JOIN categories c ON e.category_id = c.category_id
        GROUP BY c.category_id
        ORDER BY total_cat DESC
        LIMIT 1
    """)
    top_cat_row = cursor.fetchone()
    top_category = top_cat_row["category_name"] if top_cat_row else "None"

    # 5. Recent 6 transactions
    cursor.execute("""
        SELECT e.expense_id, e.title, e.amount, e.date, e.description, c.category_name
        FROM expenses e
        JOIN categories c ON e.category_id = c.category_id
        ORDER BY e.date DESC, e.expense_id DESC
        LIMIT 6
    """)
    recent_expenses = cursor.fetchall()

    # 6. Category breakdown list for table view
    cursor.execute("""
        SELECT c.category_name, COALESCE(SUM(e.amount), 0) as total_spent, COUNT(e.expense_id) as txn_count
        FROM categories c
        LEFT JOIN expenses e ON c.category_id = e.category_id
        GROUP BY c.category_id
        ORDER BY total_spent DESC
    """)
    category_summary = cursor.fetchall()

    conn.close()

    return render_template(
        "index.html",
        total_expenses=total_expenses,
        current_month_expenses=current_month_expenses,
        total_transactions=total_transactions,
        top_category=top_category,
        recent_expenses=recent_expenses,
        category_summary=category_summary,
        current_month_name=datetime.now().strftime("%B %Y")
    )


# ==============================================================================
# ROUTE 2: API FOR CHART.JS (DYNAMIC DATA)
# ==============================================================================
@app.route("/api/chart-data")
def chart_data():
    """
    Returns JSON formatted data for Chart.js:
    - category_labels & category_amounts for Pie/Doughnut Chart
    - monthly_labels & monthly_amounts for Bar Chart (last 6 months)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Category data (only categories with expenses > 0)
    cursor.execute("""
        SELECT c.category_name, ROUND(SUM(e.amount), 2) as total_amount
        FROM expenses e
        JOIN categories c ON e.category_id = c.category_id
        GROUP BY c.category_id
        ORDER BY total_amount DESC
    """)
    category_rows = cursor.fetchall()
    cat_labels = [row["category_name"] for row in category_rows]
    cat_amounts = [row["total_amount"] for row in category_rows]

    # 2. Monthly expense trends (last 6 months ordered chronologically)
    cursor.execute("""
        SELECT strftime('%Y-%m', date) as month_key, ROUND(SUM(amount), 2) as total_amount
        FROM expenses
        GROUP BY month_key
        ORDER BY month_key DESC
        LIMIT 6
    """)
    monthly_rows = cursor.fetchall()
    # Reverse so earliest month is on the left and latest month on the right
    monthly_rows = list(reversed(monthly_rows))

    month_labels = []
    month_amounts = []
    for row in monthly_rows:
        try:
            # Format "2026-11" into "Nov 2026"
            dt = datetime.strptime(row["month_key"], "%Y-%m")
            month_labels.append(dt.strftime("%b %Y"))
        except Exception:
            month_labels.append(row["month_key"])
        month_amounts.append(row["total_amount"])

    conn.close()

    return jsonify({
        "categories": {
            "labels": cat_labels,
            "amounts": cat_amounts
        },
        "monthly": {
            "labels": month_labels,
            "amounts": month_amounts
        }
    })


# ==============================================================================
# ROUTE 3: VIEW & FILTER EXPENSES (READ)
# ==============================================================================
@app.route("/expenses")
def view_expenses():
    """
    Lists all expenses with support for:
    - Search by keyword in title/description
    - Filter by category
    - Filter by date range (from_date to to_date)
    - Sorting by date or amount
    """
    search_query = request.args.get("search", "").strip()
    category_id = request.args.get("category_id", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    sort_by = request.args.get("sort_by", "date_desc").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch all categories for filter dropdown
    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    categories = cursor.fetchall()

    # Build dynamic SQL query based on filters
    sql = """
        SELECT e.expense_id, e.title, e.amount, e.date, e.description, c.category_name, e.category_id
        FROM expenses e
        JOIN categories c ON e.category_id = c.category_id
        WHERE 1=1
    """
    params = []

    if search_query:
        sql += " AND (e.title LIKE ? OR e.description LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    if category_id:
        sql += " AND e.category_id = ?"
        params.append(category_id)

    if start_date:
        sql += " AND e.date >= ?"
        params.append(start_date)

    if end_date:
        sql += " AND e.date <= ?"
        params.append(end_date)

    # Sorting
    if sort_by == "date_asc":
        sql += " ORDER BY e.date ASC, e.expense_id ASC"
    elif sort_by == "amount_desc":
        sql += " ORDER BY e.amount DESC"
    elif sort_by == "amount_asc":
        sql += " ORDER BY e.amount ASC"
    else:
        # Default: date descending
        sql += " ORDER BY e.date DESC, e.expense_id DESC"

    cursor.execute(sql, params)
    expenses = cursor.fetchall()

    # Calculate filtered total sum
    filtered_total = sum(exp["amount"] for exp in expenses)

    conn.close()

    return render_template(
        "view_expense.html",
        expenses=expenses,
        categories=categories,
        search_query=search_query,
        selected_category=category_id,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        filtered_total=filtered_total,
        count=len(expenses)
    )


# ==============================================================================
# ROUTE 4: ADD EXPENSE (CREATE)
# ==============================================================================
@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    """
    GET: Displays the add expense form with category choices.
    POST: Validates inputs and inserts a new expense record into SQLite.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        category_id = request.form.get("category_id", "").strip()
        date_val = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        # Validation
        if not title:
            flash("Please enter an expense title.", "danger")
        elif not amount_raw:
            flash("Please enter a valid amount.", "danger")
        elif not category_id:
            flash("Please select a category.", "danger")
        elif not date_val:
            flash("Please choose a valid date.", "danger")
        else:
            try:
                amount = float(amount_raw)
                if amount <= 0:
                    flash("Amount must be greater than zero.", "danger")
                    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
                    categories = cursor.fetchall()
                    conn.close()
                    return render_template("add_expense.html", categories=categories, form=request.form)

                cursor.execute("""
                    INSERT INTO expenses (title, amount, category_id, date, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (title, amount, category_id, date_val, description))
                conn.commit()
                conn.close()

                flash("Expense successfully recorded!", "success")
                return redirect(url_for("view_expenses"))

            except ValueError:
                flash("Invalid number format for amount.", "danger")

    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    categories = cursor.fetchall()
    conn.close()

    # Default today's date for convenient input
    today_date = datetime.now().strftime("%Y-%m-%d")
    return render_template("add_expense.html", categories=categories, today_date=today_date, form={})


# ==============================================================================
# ROUTE 5: EDIT EXPENSE (UPDATE)
# ==============================================================================
@app.route("/expenses/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    """
    GET: Loads the selected expense for editing in a pre-populated form.
    POST: Validates and updates the expense record in SQLite.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM expenses WHERE expense_id = ?", (expense_id,))
    expense = cursor.fetchone()

    if not expense:
        conn.close()
        flash("Expense record not found.", "warning")
        return redirect(url_for("view_expenses"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount_raw = request.form.get("amount", "").strip()
        category_id = request.form.get("category_id", "").strip()
        date_val = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        if not title or not amount_raw or not category_id or not date_val:
            flash("All required fields must be filled.", "danger")
        else:
            try:
                amount = float(amount_raw)
                if amount <= 0:
                    flash("Amount must be greater than zero.", "danger")
                else:
                    cursor.execute("""
                        UPDATE expenses
                        SET title = ?, amount = ?, category_id = ?, date = ?, description = ?
                        WHERE expense_id = ?
                    """, (title, amount, category_id, date_val, description, expense_id))
                    conn.commit()
                    conn.close()

                    flash("Expense updated successfully!", "success")
                    return redirect(url_for("view_expenses"))
            except ValueError:
                flash("Invalid number format for amount.", "danger")

    cursor.execute("SELECT * FROM categories ORDER BY category_name ASC")
    categories = cursor.fetchall()
    conn.close()

    return render_template("edit_expense.html", expense=expense, categories=categories)


# ==============================================================================
# ROUTE 6: DELETE EXPENSE (DELETE)
# ==============================================================================
@app.route("/expenses/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    """
    Deletes the expense record from the database.
    Requires a POST request to prevent accidental deletion via URL.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE expense_id = ?", (expense_id,))
    conn.commit()
    conn.close()

    flash("Expense deleted successfully.", "info")
    return redirect(url_for("view_expenses"))


# ==============================================================================
# ROUTE 7: CATEGORY MANAGEMENT (CRUD)
# ==============================================================================
@app.route("/categories", methods=["GET"])
def manage_categories():
    """
    Displays the list of all categories along with count and sum of expenses
    associated with each category, plus the form to create new categories.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.category_id, c.category_name, 
               COUNT(e.expense_id) as expense_count,
               COALESCE(SUM(e.amount), 0) as total_spent
        FROM categories c
        LEFT JOIN expenses e ON c.category_id = e.category_id
        GROUP BY c.category_id
        ORDER BY c.category_name ASC
    """)
    categories = cursor.fetchall()
    conn.close()

    return render_template("categories.html", categories=categories)


@app.route("/categories/add", methods=["POST"])
def add_category():
    """
    Adds a new category to the database. Checks for duplicate category names.
    """
    name = request.form.get("category_name", "").strip()

    if not name:
        flash("Category name cannot be empty.", "danger")
        return redirect(url_for("manage_categories"))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO categories (category_name) VALUES (?)", (name,))
        conn.commit()
        flash(f"Category '{name}' added successfully!", "success")
    except sqlite3.IntegrityError:
        flash(f"A category named '{name}' already exists.", "warning")
    finally:
        conn.close()

    return redirect(url_for("manage_categories"))


@app.route("/categories/edit/<int:category_id>", methods=["POST"])
def edit_category(category_id):
    """
    Edits an existing category's name.
    """
    new_name = request.form.get("category_name", "").strip()

    if not new_name:
        flash("Category name cannot be empty.", "danger")
        return redirect(url_for("manage_categories"))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE categories SET category_name = ? WHERE category_id = ?", (new_name, category_id))
        conn.commit()
        flash("Category renamed successfully!", "success")
    except sqlite3.IntegrityError:
        flash(f"A category named '{new_name}' already exists.", "warning")
    finally:
        conn.close()

    return redirect(url_for("manage_categories"))


@app.route("/categories/delete/<int:category_id>", methods=["POST"])
def delete_category(category_id):
    """
    Deletes a category. Prevents deletion if there are still active expenses linked
    to maintain relational integrity, or informs the user.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if any expenses are currently using this category
    cursor.execute("SELECT COUNT(*) FROM expenses WHERE category_id = ?", (category_id,))
    count = cursor.fetchone()[0]

    if count > 0:
        flash(f"Cannot delete category: {count} expense record(s) are linked to it. Please reassign or delete those expenses first.", "danger")
    else:
        cursor.execute("DELETE FROM categories WHERE category_id = ?", (category_id,))
        conn.commit()
        flash("Category deleted successfully.", "info")

    conn.close()
    return redirect(url_for("manage_categories"))


# ==============================================================================
# MAIN APPLICATION ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    # Runs the Flask local development server
    # debug=True allows auto-reloading when code is edited
    print("Expense Manager Tracker running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
