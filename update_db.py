import sqlite3
from app import create_app

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

if __name__ == '__main__':
    add_missing_column() 