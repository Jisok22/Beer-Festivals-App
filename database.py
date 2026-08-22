import sqlite3
from datetime import datetime

DB_FILE = "festivals.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS festivals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            opening_time TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_festival(name, location, start_date, end_date, opening_time):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO festivals (name, location, start_date, end_date, opening_time)
           VALUES (?, ?, ?, ?, ?)""",
        (name, location, start_date.isoformat(), end_date.isoformat(), opening_time),
    )
    conn.commit()
    conn.close()


def get_all_festivals():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, location, start_date, end_date, opening_time FROM festivals ORDER BY start_date"
    )
    rows = cursor.fetchall()
    conn.close()

    festivals = []
    for name, location, start_text, end_text, opening_time in rows:
        festivals.append({
            "name": name,
            "location": location,
            "start_date": datetime.strptime(start_text, "%Y-%m-%d").date(),
            "end_date": datetime.strptime(end_text, "%Y-%m-%d").date(),
            "opening_time": opening_time,
        })
    return festivals