import sqlite3

connection = sqlite3.connect("tasks.db")

cursor = connection.cursor()

# Users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")

# Tasks table
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    task TEXT,
    status TEXT,
    due_date TEXT,
    priority TEXT
)
""")

connection.commit()

connection.close()

print("Database setup completed successfully!")