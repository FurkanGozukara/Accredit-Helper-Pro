import logging
import sqlite3
from flask import Flask
from sqlalchemy import inspect, MetaData, Table, Column, Numeric, text
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, OperationalError
from sqlalchemy.orm import declarative_base

def check_and_update_database(app):
    """
    Check and update the database schema if necessary.
    This function runs at app startup to handle migrations for new columns.
    """
    logging.info("Checking database schema for required columns...")
    
    try:
        with app.app_context():
            # Get database engine
            try:
                engine = app.extensions['sqlalchemy'].db.engine
            except (KeyError, AttributeError) as e:
                # Check if db is directly available on app
                try:
                    from models import db
                    engine = db.engine
                    logging.info("Using db.engine directly instead of app.extensions")
                except Exception as inner_e:
                    raise Exception(f"Failed to access database engine: {str(e)}, inner error: {str(inner_e)}")
                
            inspector = inspect(engine)
            
            # Check if course_outcome_program_outcome table exists
            if 'course_outcome_program_outcome' in inspector.get_table_names():
                logging.info("Found course_outcome_program_outcome table, checking for relative_weight column")
                
                # Check if relative_weight column exists
                columns = [c['name'] for c in inspector.get_columns('course_outcome_program_outcome')]
                
                if 'relative_weight' not in columns:
                    logging.info("Adding relative_weight column to course_outcome_program_outcome table")
                    
                    # Add the column using raw SQL to ensure it works with SQLite
                    if engine.dialect.name == 'sqlite':
                        # SQLite doesn't support ALTER TABLE ADD COLUMN with DEFAULT
                        # We need to use raw SQL with a specific approach for SQLite
                        with engine.connect() as connection:
                            connection.execute(text(
                                "ALTER TABLE course_outcome_program_outcome ADD COLUMN relative_weight NUMERIC(10,2) DEFAULT 1.0"
                            ))
                            connection.commit()
                    else:
                        # For other databases like PostgreSQL, we can use MetaData approach
                        metadata = MetaData()
                        metadata.reflect(bind=engine)
                        table = Table('course_outcome_program_outcome', metadata)
                        
                        with engine.begin() as connection:
                            connection.execute(
                                text(
                                    "ALTER TABLE course_outcome_program_outcome ADD COLUMN relative_weight NUMERIC(10,2) DEFAULT 1.0"
                                )
                            )
                    
                    logging.info("Successfully added relative_weight column to course_outcome_program_outcome table")
                else:
                    logging.info("relative_weight column already exists in course_outcome_program_outcome table")
            else:
                logging.warning("course_outcome_program_outcome table not found. It will be created when the app runs.")
        
            # --- START: Add Check for Question-CO Relative Weight ---
            if 'question_course_outcome' in inspector.get_table_names():
                logging.info("Found question_course_outcome table, checking for relative_weight column")
                
                # Check if relative_weight column exists
                qco_columns = [c['name'] for c in inspector.get_columns('question_course_outcome')]
                
                if 'relative_weight' not in qco_columns:
                    logging.info("Adding relative_weight column to question_course_outcome table")
                    
                    # Add the column using raw SQL
                    # Use specific ALTER TABLE syntax compatible with SQLite and default value
                    with engine.connect() as connection:
                        connection.execute(text(
                            "ALTER TABLE question_course_outcome ADD COLUMN relative_weight NUMERIC(10,2) DEFAULT 1.0 NOT NULL"
                        ))
                        # No need for separate UPDATE as default is set during ADD COLUMN in SQLite
                        connection.commit()
                    
                    logging.info("Successfully added relative_weight column to question_course_outcome table")
                else:
                    logging.info("relative_weight column already exists in question_course_outcome table")
            else:
                logging.warning("question_course_outcome table not found. It will be created when the app runs.")
            # --- END: Add Check for Question-CO Relative Weight ---
        
            # --- START: Add Check for Graduating Students Table ---
            if 'graduating_student' not in inspector.get_table_names():
                logging.info("graduating_student table not found, creating it...")
                
                try:
                    # Create the graduating_student table using raw SQL
                    with engine.connect() as connection:
                        connection.execute(text("""
                            CREATE TABLE graduating_student (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                student_id VARCHAR(20) NOT NULL UNIQUE,
                                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                            )
                        """))
                        
                        # Create index for performance
                        connection.execute(text("""
                            CREATE INDEX idx_graduating_student_student_id 
                            ON graduating_student(student_id)
                        """))
                        
                        connection.commit()
                    
                    logging.info("Successfully created graduating_student table and index")
                    
                    # Log the migration
                    try:
                        with engine.connect() as connection:
                            connection.execute(text("""
                                INSERT INTO log (action, description, timestamp) 
                                VALUES ('MIGRATION_ADD_GRADUATING_STUDENTS', 
                                       'Auto-created graduating_student table for MÜDEK filtering', 
                                       CURRENT_TIMESTAMP)
                            """))
                            connection.commit()
                        logging.info("Migration logged successfully")
                    except Exception as log_e:
                        logging.warning(f"Could not log migration: {log_e}")
                        
                except Exception as table_e:
                    logging.error(f"Failed to create graduating_student table: {table_e}")
                    # Don't fail the entire migration for this optional feature
            else:
                logging.info("graduating_student table already exists")
            # --- END: Add Check for Graduating Students Table ---
        
        return True
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logging.error(f"Error checking or updating database schema: {str(e)}\n{error_traceback}")
        return False 
        
def graduating_students_table_exists():
    """
    Check if the graduating_student table exists in the database.
    This function is safe to call from anywhere in the application.
    Returns True if table exists, False otherwise.
    """
    try:
        # Import here to avoid circular imports
        from flask import current_app
        from models import db
        
        # Get the engine from the current app context
        if current_app:
            engine = db.engine
        else:
            # If no app context, try to create one
            from app import create_app
            app = create_app()
            with app.app_context():
                engine = db.engine
        
        inspector = inspect(engine)
        return 'graduating_student' in inspector.get_table_names()
        
    except Exception as e:
        logging.error(f"Error checking graduating_student table existence: {e}")
        return False

def ensure_graduating_students_table():
    """
    Ensure the graduating_student table exists, create it if it doesn't.
    This function can be called from routes to auto-create the table when needed.
    Returns True if table exists or was created successfully, False otherwise.
    """
    try:
        if graduating_students_table_exists():
            return True
        
        logging.info("graduating_student table doesn't exist, attempting to create it...")
        
        # Import here to avoid circular imports
        from flask import current_app
        from models import db
        
        engine = db.engine
        
        # Create the table
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE graduating_student (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id VARCHAR(20) NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create index
            connection.execute(text("""
                CREATE INDEX idx_graduating_student_student_id 
                ON graduating_student(student_id)
            """))
            
            connection.commit()
        
        logging.info("Successfully created graduating_student table")
        
        # Log the creation
        try:
            from models import Log
            log = Log(
                action="AUTO_CREATE_GRADUATING_STUDENTS", 
                description="Auto-created graduating_student table when accessed"
            )
            db.session.add(log)
            db.session.commit()
        except Exception as log_e:
            logging.warning(f"Could not log table creation: {log_e}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error ensuring graduating_student table exists: {e}")
        return False

def safe_graduating_students_query(query_func):
    """
    Decorator to safely execute graduating students queries.
    If table doesn't exist, it will try to create it first.
    If creation fails, it returns empty results.
    
    Usage:
        @safe_graduating_students_query
        def get_graduating_students():
            return GraduatingStudent.query.all()
    """
    def wrapper(*args, **kwargs):
        try:
            # Check if table exists, create if needed
            if not ensure_graduating_students_table():
                logging.warning("graduating_student table not available, returning empty result")
                return []
            
            # Execute the query
            return query_func(*args, **kwargs)
            
        except Exception as e:
            logging.error(f"Error in graduating students query: {e}")
            return []
    
    return wrapper 