#!/usr/bin/env python3
"""
Test script for the Database Index Manager

This script tests the index management functionality to ensure it works correctly
with both new and existing databases.

Usage: python test_index_manager.py
"""

import os
import sys
import sqlite3
import tempfile
import shutil
from flask import Flask

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_with_existing_database():
    """Test index manager with existing database"""
    print("Testing with existing database...")
    
    # Use the actual database if it exists
    db_path = os.path.join(os.getcwd(), "instance", "accredit_data.db")
    
    if os.path.exists(db_path):
        print(f"Found existing database at: {db_path}")
        
        # Import the index manager
        from db_index_manager import create_indexes_manually
        
        # Test manual index creation
        print("Testing manual index creation...")
        success = create_indexes_manually(db_path)
        
        if success:
            print("✓ Manual index creation succeeded")
        else:
            print("✗ Manual index creation failed")
            
        return success
    else:
        print("No existing database found, skipping existing database test")
        return True

def test_with_new_database():
    """Test index manager with a new temporary database"""
    print("\nTesting with new temporary database...")
    
    # Create a temporary database
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, "test_accredit.db")
    
    try:
        # Create a minimal Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{temp_db_path}'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Import and initialize database
        from models import db
        db.init_app(app)
        
        with app.app_context():
            # Create tables
            db.create_all()
            print(f"Created test database at: {temp_db_path}")
            
            # Test the index manager
            from db_index_manager import initialize_index_manager
            
            print("Testing index manager initialization...")
            success = initialize_index_manager(app, db)
            
            if success:
                print("✓ Index manager initialization succeeded")
                
                # Check the status
                if hasattr(app, 'index_manager'):
                    status = app.index_manager.get_index_status()
                    print(f"✓ Index status check succeeded:")
                    print(f"  - Total required: {status.get('total_required', 0)}")
                    print(f"  - Existing: {status.get('existing', 0)}")
                    print(f"  - Missing: {status.get('missing', 0)}")
                    
                    if status.get('missing', 0) == 0:
                        print("✓ All indexes created successfully")
                        return True
                    else:
                        print("✗ Some indexes are missing")
                        return False
                else:
                    print("✗ Index manager not found in app")
                    return False
            else:
                print("✗ Index manager initialization failed")
                return False
                
    except Exception as e:
        print(f"✗ Error in new database test: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temporary directory: {temp_dir}")

def test_index_existence():
    """Test if we can check index existence properly"""
    print("\nTesting index existence checking...")
    
    db_path = os.path.join(os.getcwd(), "instance", "accredit_data.db")
    
    if not os.path.exists(db_path):
        print("No database found for index existence test")
        return True
        
    try:
        # Connect to database and check for indexes
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = cursor.fetchall()
        
        print(f"Found {len(indexes)} indexes with 'idx_' prefix:")
        for (index_name,) in indexes:
            print(f"  - {index_name}")
            
        # Check for specific indexes we should have created
        expected_indexes = [
            'idx_student_student_id_global',
            'idx_student_student_id_course_lookup',
            'idx_course_code_name_search',
            'idx_score_course_student_lookup',
            'idx_course_settings_excluded_lookup',
            'idx_exam_course_lookup'
        ]
        
        found_indexes = [name for (name,) in indexes]
        missing_indexes = [idx for idx in expected_indexes if idx not in found_indexes]
        
        if missing_indexes:
            print(f"Missing expected indexes: {missing_indexes}")
        else:
            print("✓ All expected indexes found")
            
        conn.close()
        return len(missing_indexes) == 0
        
    except Exception as e:
        print(f"✗ Error checking index existence: {e}")
        return False

def main():
    """Run all tests"""
    print("Database Index Manager Test Suite")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Existing database
    total_tests += 1
    if test_with_existing_database():
        tests_passed += 1
    
    # Test 2: New database
    total_tests += 1
    if test_with_new_database():
        tests_passed += 1
    
    # Test 3: Index existence
    total_tests += 1
    if test_index_existence():
        tests_passed += 1
    
    # Results
    print("\n" + "=" * 50)
    print(f"Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✓ All tests passed! Index management system is working correctly.")
        return 0
    else:
        print("✗ Some tests failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 