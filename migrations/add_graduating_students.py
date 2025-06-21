from flask import Flask
import os
import sys
import sqlite3
import logging

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app factory
from app import create_app

def add_graduating_students_table():
    """
    Add graduating_student table to the database for MÜDEK filtering.
    This script creates the table if it doesn't exist and is safe to run multiple times.
    """
    app = create_app()
    
    # Get database path
    with app.app_context():
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    
    print(f"Adding graduating_student table to database at {db_path}")
    
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='graduating_student'
        """)
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            print("graduating_student table already exists, skipping creation")
            return True
        
        # Create the graduating_student table
        cursor.execute("""
            CREATE TABLE graduating_student (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id VARCHAR(20) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Created graduating_student table")
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX idx_graduating_student_student_id 
            ON graduating_student(student_id)
        """)
        print("Created index on graduating_student.student_id")
        
        # Commit the changes
        conn.commit()
        print("graduating_student table and indexes created successfully!")
        
        # Log the migration
        try:
            cursor.execute("""
                INSERT INTO log (action, description, timestamp) 
                VALUES ('MIGRATION_ADD_GRADUATING_STUDENTS', 
                       'Added graduating_student table for MÜDEK filtering', 
                       CURRENT_TIMESTAMP)
            """)
            conn.commit()
            print("Migration logged successfully")
        except Exception as e:
            print(f"Warning: Could not log migration (log table may not exist yet): {e}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"Error creating graduating_student table: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_graduating_students_table_exists():
    """
    Check if the graduating_student table exists.
    Returns True if table exists, False otherwise.
    """
    try:
        app = create_app()
        
        with app.app_context():
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='graduating_student'
        """)
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
        
    except Exception as e:
        logging.error(f"Error checking graduating_student table existence: {e}")
        return False

if __name__ == "__main__":
    success = add_graduating_students_table()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
        sys.exit(1) 