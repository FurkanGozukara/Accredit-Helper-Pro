"""
Migration script to add the StudentExamAttendance table and set default attendance values

This script adds a new table to track whether a student attended an exam.
By default, all students are marked as having attended all exams.
"""

import sqlite3
import os
import sys
from datetime import datetime

def run_migration(db_path):
    """Execute the migration on the specified database"""
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        print("Starting migration: Adding StudentExamAttendance table")
        
        # Create the new table
        c.execute('''
        CREATE TABLE IF NOT EXISTS student_exam_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            attended BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES student (id) ON DELETE CASCADE,
            FOREIGN KEY (exam_id) REFERENCES exam (id) ON DELETE CASCADE,
            UNIQUE (student_id, exam_id)
        )
        ''')
        
        # Create indexes
        c.execute('CREATE INDEX IF NOT EXISTS idx_attendance_student ON student_exam_attendance (student_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_attendance_exam ON student_exam_attendance (exam_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_attendance_student_exam ON student_exam_attendance (student_id, exam_id)')
        
        # Add trigger to update the updated_at column when a row is updated
        c.execute('''
        CREATE TRIGGER IF NOT EXISTS update_student_exam_attendance_trigger
        AFTER UPDATE ON student_exam_attendance
        BEGIN
            UPDATE student_exam_attendance SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        ''')
        
        # Populate the table with default values (all students attended all exams)
        c.execute('''
        INSERT OR IGNORE INTO student_exam_attendance (student_id, exam_id, attended)
        SELECT s.id, e.id, 1
        FROM student s, exam e
        WHERE s.course_id = e.course_id
        ''')
        
        # Commit the changes
        conn.commit()
        print(f"Migration completed successfully. Added StudentExamAttendance table and populated with default values.")
        
        # Get count of records added
        c.execute('SELECT COUNT(*) FROM student_exam_attendance')
        count = c.fetchone()[0]
        print(f"Added {count} attendance records.")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    # Get database path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default path assuming script is run from project root
        db_path = os.path.join(os.getcwd(), "instance", "accredit_data.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        sys.exit(1)
    
    success = run_migration(db_path)
    sys.exit(0 if success else 1) 