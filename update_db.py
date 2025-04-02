import sqlite3
from app import create_app
import logging
from sqlalchemy import Column, Boolean, text
from sqlalchemy.exc import OperationalError

def add_missing_column():
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Get database path from app config
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        
        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(exam)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add column if it doesn't exist
        if 'is_mandatory' not in columns:
            print("Adding 'is_mandatory' column to exam table...")
            cursor.execute("ALTER TABLE exam ADD COLUMN is_mandatory BOOLEAN DEFAULT 0")
            conn.commit()
            print("Column added successfully!")
        else:
            print("Column 'is_mandatory' already exists.")
        
        # Check if CourseSettings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_settings'")
        if not cursor.fetchone():
            print("Creating course_settings table...")
            cursor.execute('''
                CREATE TABLE course_settings (
                    id INTEGER PRIMARY KEY,
                    course_id INTEGER UNIQUE NOT NULL,
                    success_rate_method VARCHAR(20) NOT NULL DEFAULT 'absolute',
                    relative_success_threshold NUMERIC(10, 2) NOT NULL DEFAULT 60.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES course (id)
                )
            ''')
            conn.commit()
            print("course_settings table created successfully!")
        else:
            print("Table 'course_settings' already exists.")
        
        # Close connection
        conn.close()

def update_database():
    app = create_app()
    with app.app_context():
        try:
            # Add is_final column to exam table if it doesn't exist
            from models import db
            db.session.execute(text("SELECT is_final FROM exam LIMIT 1"))
            logging.info("is_final column already exists in exam table")
        except OperationalError:
            try:
                from models import db
                logging.info("Adding is_final column to exam table")
                db.session.execute(text("ALTER TABLE exam ADD COLUMN is_final BOOLEAN DEFAULT FALSE"))
                
                # Add index for the new column
                db.session.execute(text("CREATE INDEX idx_exam_is_final ON exam (is_final)"))
                
                # Add composite index for course_id and is_final
                db.session.execute(text("CREATE INDEX idx_exam_course_final ON exam (course_id, is_final)"))
                
                db.session.commit()
                logging.info("Successfully added is_final column to exam table")
            except Exception as e:
                from models import db
                db.session.rollback()
                logging.error(f"Error adding is_final column: {str(e)}")
        
        # Add other database updates here as needed

if __name__ == '__main__':
    add_missing_column()
    update_database() 