from flask import Flask
import os
import sys
import sqlite3

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app factory and db
from app import create_app
from models import db

def update_schema():
    """
    Update the database schema to include index definitions.
    This script will recreate tables with the new indexes.
    Note: This will only work if there's no data, or you've backed up your data.
    """
    app = create_app()
    
    with app.app_context():
        print("Dropping all tables and recreating with indexes...")
        db.drop_all()
        db.create_all()
        print("Schema updated successfully with indexes!")

if __name__ == "__main__":
    update_schema() 