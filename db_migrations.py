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
        
        return True
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logging.error(f"Error checking or updating database schema: {str(e)}\n{error_traceback}")
        return False 