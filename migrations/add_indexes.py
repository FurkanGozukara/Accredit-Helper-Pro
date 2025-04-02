from flask import Flask
import os
import sys
import sqlite3

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app factory
from app import create_app

def add_indexes():
    """
    Add indexes to the database to improve query performance.
    This script should be run after the database is already initialized.
    """
    app = create_app()
    
    # Get database path
    with app.app_context():
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    
    print(f"Adding indexes to database at {db_path}")
    
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Define indexes to add - we'll use raw SQL for more control
    indexes = [
        # Course table indexes
        "CREATE INDEX IF NOT EXISTS idx_course_code ON course(code)",
        "CREATE INDEX IF NOT EXISTS idx_course_semester ON course(semester)",
        
        # Exam table indexes
        "CREATE INDEX IF NOT EXISTS idx_exam_course_id ON exam(course_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_is_makeup ON exam(is_makeup)",
        "CREATE INDEX IF NOT EXISTS idx_exam_makeup_for ON exam(makeup_for)",
        "CREATE INDEX IF NOT EXISTS idx_exam_is_mandatory ON exam(is_mandatory)",
        "CREATE INDEX IF NOT EXISTS idx_exam_course_makeup ON exam(course_id, is_makeup)",
        "CREATE INDEX IF NOT EXISTS idx_exam_name ON exam(name)",
        "CREATE INDEX IF NOT EXISTS idx_exam_course_mandatory ON exam(course_id, is_mandatory)",
        "CREATE INDEX IF NOT EXISTS idx_exam_course_name ON exam(course_id, name)",
        
        # ExamWeight table indexes
        "CREATE INDEX IF NOT EXISTS idx_exam_weight_exam_id ON exam_weight(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_weight_course_id ON exam_weight(course_id)",
        "CREATE INDEX IF NOT EXISTS idx_exam_weight_exam_course ON exam_weight(exam_id, course_id)",
        
        # CourseOutcome table indexes
        "CREATE INDEX IF NOT EXISTS idx_course_outcome_code ON course_outcome(code)",
        "CREATE INDEX IF NOT EXISTS idx_course_outcome_course_id ON course_outcome(course_id)",
        "CREATE INDEX IF NOT EXISTS idx_course_outcome_code_course ON course_outcome(code, course_id)",
        "CREATE INDEX IF NOT EXISTS idx_course_outcome_course_created ON course_outcome(course_id, created_at)",
        
        # ProgramOutcome table indexes
        "CREATE INDEX IF NOT EXISTS idx_program_outcome_code ON program_outcome(code)",
        
        # Question table indexes
        "CREATE INDEX IF NOT EXISTS idx_question_number ON question(number)",
        "CREATE INDEX IF NOT EXISTS idx_question_exam_id ON question(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_question_exam_number ON question(exam_id, number)",
        
        # Student table indexes
        "CREATE INDEX IF NOT EXISTS idx_student_student_id ON student(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_student_course_id ON student(course_id)",
        "CREATE INDEX IF NOT EXISTS idx_student_course_student_id ON student(course_id, student_id)",
        
        # Score table indexes
        "CREATE INDEX IF NOT EXISTS idx_score_student_id ON score(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_score_question_id ON score(question_id)",
        "CREATE INDEX IF NOT EXISTS idx_score_exam_id ON score(exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_score_student_exam ON score(student_id, exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_score_student_question_exam ON score(student_id, question_id, exam_id)",
        "CREATE INDEX IF NOT EXISTS idx_score_exam_question ON score(exam_id, question_id)",
        "CREATE INDEX IF NOT EXISTS idx_score_student_question ON score(student_id, question_id)",
        
        # Log table indexes
        "CREATE INDEX IF NOT EXISTS idx_log_action ON log(action)",
        "CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log(timestamp)",
        
        # CourseSettings table indexes
        "CREATE INDEX IF NOT EXISTS idx_course_settings_course_id ON course_settings(course_id)",

        # Association table indexes (these may already exist as they are primary keys)
        "CREATE INDEX IF NOT EXISTS idx_co_po_course_outcome_id ON course_outcome_program_outcome(course_outcome_id)",
        "CREATE INDEX IF NOT EXISTS idx_co_po_program_outcome_id ON course_outcome_program_outcome(program_outcome_id)",
        "CREATE INDEX IF NOT EXISTS idx_co_po_combined ON course_outcome_program_outcome(course_outcome_id, program_outcome_id)",
        "CREATE INDEX IF NOT EXISTS idx_q_co_question_id ON question_course_outcome(question_id)",
        "CREATE INDEX IF NOT EXISTS idx_q_co_course_outcome_id ON question_course_outcome(course_outcome_id)",
        "CREATE INDEX IF NOT EXISTS idx_qco_combined ON question_course_outcome(question_id, course_outcome_id)"
    ]
    
    # Execute each index creation
    for index in indexes:
        try:
            cursor.execute(index)
            print(f"Created index: {index}")
        except sqlite3.OperationalError as e:
            print(f"Error creating index: {e}")
    
    # Commit the changes
    conn.commit()
    print("All indexes created successfully!")
    
    # Analyze the database to update statistics for the query planner
    cursor.execute("ANALYZE")
    print("Database analyzed for query optimization")
    
    # Close the connection
    conn.close()

if __name__ == "__main__":
    add_indexes() 