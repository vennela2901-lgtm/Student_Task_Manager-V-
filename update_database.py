import sqlite3

connection = sqlite3.connect("tasks.db")
cursor = connection.cursor()

# Existing task columns
cursor.execute("PRAGMA table_info(tasks)")
task_columns = [column[1] for column in cursor.fetchall()]

if "due_date" not in task_columns:
    cursor.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
    print("✅ due_date added")

if "priority" not in task_columns:
    cursor.execute("ALTER TABLE tasks ADD COLUMN priority TEXT")
    print("✅ priority added")

if "category" not in task_columns:
    cursor.execute("ALTER TABLE tasks ADD COLUMN category TEXT")
    print("✅ category added")


# Activity history table
cursor.execute("""
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    task TEXT NOT NULL,
    activity_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

connection.commit()
connection.close()

print("🎉 Database update completed successfully!")