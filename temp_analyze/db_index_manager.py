"""
Database Index Management System

This module provides functionality to check and create database indexes
on application startup. It ensures optimal performance for the all_courses
page filtering features, especially student ID cross-course lookups.

The system:
1. Checks for required indexes on app startup
2. Creates missing indexes automatically
3. Logs all index operations
4. Is compatible with new and existing databases
"""

import logging
import sqlite3
from flask import current_app
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError, OperationalError


class IndexManager:
    """Manages database indexes for optimal performance"""
    
    def __init__(self, app=None, db=None):
        self.app = app
        self.db = db
        self.required_indexes = self._define_required_indexes()
        
    def _define_required_indexes(self):
        """Define all required indexes for optimal performance"""
        return {
            # Student table indexes for cross-course student lookups
            'idx_student_student_id_global': {
                'table': 'student',
                'columns': ['student_id'],
                'description': 'Global student ID lookup across all courses'
            },
            'idx_student_student_id_course_lookup': {
                'table': 'student', 
                'columns': ['student_id', 'course_id'],
                'description': 'Optimized student ID to course lookup'
            },
            
            # Course table indexes for all_courses page filtering
            'idx_course_code_name_search': {
                'table': 'course',
                'columns': ['code', 'name'],
                'description': 'Course search optimization'
            },
            
            # Score table indexes for calculation performance
            'idx_score_course_student_lookup': {
                'table': 'score',
                'columns': ['exam_id', 'student_id'],
                'description': 'Score lookup optimization for calculations'
            },
            
            # Course settings for exclusion filtering
            'idx_course_settings_excluded_lookup': {
                'table': 'course_settings',
                'columns': ['excluded', 'course_id'],
                'description': 'Course exclusion filtering optimization'
            },
            
            # Cross-table performance indexes
            'idx_exam_course_lookup': {
                'table': 'exam',
                'columns': ['course_id', 'is_makeup', 'is_mandatory'],
                'description': 'Exam filtering for course calculations'
            }
        }
    
    def check_and_create_indexes(self):
        """
        Check for required indexes and create missing ones
        Called on app startup
        """
        if not self.app or not self.db:
            logging.error("IndexManager not properly initialized")
            return False
            
        try:
            with self.app.app_context():
                logging.info("Starting database index check and creation...")
                
                # Get database engine and inspector
                engine = self.db.engine
                inspector = inspect(engine)
                
                # Check each required index
                created_count = 0
                for index_name, index_info in self.required_indexes.items():
                    if self._index_exists(inspector, index_name, index_info):
                        logging.debug(f"Index {index_name} already exists")
                    else:
                        if self._create_index(engine, index_name, index_info):
                            created_count += 1
                            logging.info(f"Created index: {index_name}")
                        else:
                            logging.error(f"Failed to create index: {index_name}")
                
                if created_count > 0:
                    logging.info(f"Successfully created {created_count} new database indexes")
                else:
                    logging.info("All required database indexes already exist")
                    
                return True
                
        except Exception as e:
            logging.error(f"Error during index check and creation: {str(e)}")
            return False
    
    def _index_exists(self, inspector, index_name, index_info):
        """Check if an index exists in the database"""
        try:
            table_name = index_info['table']
            
            # Get existing indexes for the table
            existing_indexes = inspector.get_indexes(table_name)
            
            # Check if index with this name exists
            for index in existing_indexes:
                if index['name'] == index_name:
                    return True
                    
            # Also check by column combination (in case index exists with different name)
            required_columns = set(index_info['columns'])
            for index in existing_indexes:
                existing_columns = set(index['column_names'])
                if existing_columns == required_columns:
                    logging.debug(f"Index with equivalent columns exists for {index_name}")
                    return True
                    
            return False
            
        except Exception as e:
            logging.warning(f"Error checking index existence for {index_name}: {str(e)}")
            return False
    
    def _create_index(self, engine, index_name, index_info):
        """Create a database index"""
        try:
            table_name = index_info['table']
            columns = index_info['columns']
            description = index_info['description']
            
            # Build CREATE INDEX SQL
            columns_sql = ', '.join(columns)
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_sql})"
            
            # Execute the SQL
            with engine.connect() as connection:
                connection.execute(text(sql))
                connection.commit()
                
            logging.info(f"Created index {index_name}: {description}")
            return True
            
        except OperationalError as e:
            if "already exists" in str(e).lower():
                logging.debug(f"Index {index_name} already exists (caught in creation)")
                return True
            else:
                logging.error(f"Operational error creating index {index_name}: {str(e)}")
                return False
        except Exception as e:
            logging.error(f"Unexpected error creating index {index_name}: {str(e)}")
            return False
    
    def get_index_status(self):
        """
        Get status of all required indexes
        Returns dict with index status information
        """
        if not self.app or not self.db:
            return {"error": "IndexManager not properly initialized"}
            
        try:
            with self.app.app_context():
                engine = self.db.engine
                inspector = inspect(engine)
                
                status = {
                    "total_required": len(self.required_indexes),
                    "existing": 0,
                    "missing": 0,
                    "indexes": {}
                }
                
                for index_name, index_info in self.required_indexes.items():
                    exists = self._index_exists(inspector, index_name, index_info)
                    status["indexes"][index_name] = {
                        "exists": exists,
                        "table": index_info["table"],
                        "columns": index_info["columns"],
                        "description": index_info["description"]
                    }
                    
                    if exists:
                        status["existing"] += 1
                    else:
                        status["missing"] += 1
                
                return status
                
        except Exception as e:
            logging.error(f"Error getting index status: {str(e)}")
            return {"error": str(e)}
    
    def create_missing_indexes_only(self):
        """
        Create only the missing indexes (useful for existing databases)
        Returns number of indexes created
        """
        if not self.app or not self.db:
            logging.error("IndexManager not properly initialized")
            return 0
            
        try:
            with self.app.app_context():
                engine = self.db.engine
                inspector = inspect(engine)
                
                created_count = 0
                for index_name, index_info in self.required_indexes.items():
                    if not self._index_exists(inspector, index_name, index_info):
                        if self._create_index(engine, index_name, index_info):
                            created_count += 1
                
                return created_count
                
        except Exception as e:
            logging.error(f"Error creating missing indexes: {str(e)}")
            return 0


def initialize_index_manager(app, db):
    """
    Initialize the index manager and check/create indexes
    Called from app startup
    """
    try:
        index_manager = IndexManager(app, db)
        success = index_manager.check_and_create_indexes()
        
        # Store index manager in app for later use if needed
        app.index_manager = index_manager
        
        return success
        
    except Exception as e:
        logging.error(f"Failed to initialize index manager: {str(e)}")
        return False


def get_index_status_for_debug():
    """
    Get index status for debugging/admin purposes
    Can be called from routes to show index status
    """
    try:
        if hasattr(current_app, 'index_manager'):
            return current_app.index_manager.get_index_status()
        else:
            return {"error": "Index manager not initialized"}
    except Exception as e:
        return {"error": str(e)}


# Utility function to manually create indexes (for migration scripts)
def create_indexes_manually(db_path):
    """
    Manually create indexes using direct SQLite connection
    Useful for migration scripts or standalone execution
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Define the same indexes as in the IndexManager
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_student_student_id_global ON student (student_id)",
            "CREATE INDEX IF NOT EXISTS idx_student_student_id_course_lookup ON student (student_id, course_id)",
            "CREATE INDEX IF NOT EXISTS idx_course_code_name_search ON course (code, name)",
            "CREATE INDEX IF NOT EXISTS idx_score_course_student_lookup ON score (exam_id, student_id)",
            "CREATE INDEX IF NOT EXISTS idx_course_settings_excluded_lookup ON course_settings (excluded, course_id)",
            "CREATE INDEX IF NOT EXISTS idx_exam_course_lookup ON exam (course_id, is_makeup, is_mandatory)",
        ]
        
        created_count = 0
        for sql in indexes:
            try:
                cursor.execute(sql)
                created_count += 1
                print(f"Executed: {sql}")
            except sqlite3.Error as e:
                print(f"Error executing {sql}: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"Successfully processed {created_count} index creation statements")
        return True
        
    except Exception as e:
        print(f"Error in manual index creation: {e}")
        return False


if __name__ == "__main__":
    """
    Standalone execution for manual index creation
    Usage: python db_index_manager.py [database_path]
    """
    import sys
    import os
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default path
        db_path = os.path.join(os.getcwd(), "instance", "accredit_data.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        sys.exit(1)
    
    print(f"Creating indexes for database at: {db_path}")
    success = create_indexes_manually(db_path)
    sys.exit(0 if success else 1) 