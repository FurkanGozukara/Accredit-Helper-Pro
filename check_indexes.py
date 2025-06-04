import sqlite3
import os

db_path = os.path.join("instance", "accredit_data.db")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
    indexes = cursor.fetchall()
    
    print(f"Found {len(indexes)} custom indexes:")
    for name, in indexes:
        print(f"  - {name}")
        
    conn.close()
else:
    print("Database not found!") 