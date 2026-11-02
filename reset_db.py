import os
import sqlite3

DATABASE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "database.db")

def reset_database():
    """
    Clears all expense data and resets categories to the default 6 categories.
    """
    if os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Clear expenses
        cursor.execute("DELETE FROM expenses")
        
        # Reset categories table
        cursor.execute("DELETE FROM categories")
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
        conn.close()
        print("Database cleaned successfully! All dummy expenses removed.")
        print("Standard categories ready: Food, Travel, Shopping, Education, Bills, Entertainment.")
    else:
        print("database.db not found yet. Run 'python app.py' to initialize.")

if __name__ == "__main__":
    reset_database()
