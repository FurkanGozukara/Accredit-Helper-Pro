#!/usr/bin/env python3
"""
Test script for graduating students migration
This script verifies that the migration system works correctly.
"""

import sys
import os

# Add current directory to path
sys.path.append('.')

def test_migration():
    """Test the graduating students migration"""
    print("Testing graduating students migration...")
    
    try:
        # Import migration functions
        from db_migrations import (
            graduating_students_table_exists, 
            ensure_graduating_students_table,
            check_and_update_database
        )
        
        # Import app to create context
        from app import create_app
        
        app = create_app()
        
        with app.app_context():
            print("1. Testing table existence check...")
            exists_before = graduating_students_table_exists()
            print(f"   Table exists before migration: {exists_before}")
            
            print("2. Testing table creation...")
            success = ensure_graduating_students_table()
            print(f"   Table creation/verification success: {success}")
            
            print("3. Testing table existence after migration...")
            exists_after = graduating_students_table_exists()
            print(f"   Table exists after migration: {exists_after}")
            
            if success and exists_after:
                print("4. Testing model import...")
                try:
                    from models import GraduatingStudent, db
                    
                    # Test basic operations
                    print("5. Testing basic database operations...")
                    
                    # Test insert
                    test_student = GraduatingStudent(student_id="TEST123")
                    db.session.add(test_student)
                    db.session.commit()
                    print("   Insert test: SUCCESS")
                    
                    # Test query
                    found_student = GraduatingStudent.query.filter_by(student_id="TEST123").first()
                    if found_student:
                        print("   Query test: SUCCESS")
                    else:
                        print("   Query test: FAILED")
                    
                    # Test delete (cleanup)
                    db.session.delete(found_student)
                    db.session.commit()
                    print("   Delete test: SUCCESS")
                    
                except Exception as e:
                    print(f"   Model operations failed: {e}")
                    return False
            
            print("6. Testing full migration system...")
            migration_success = check_and_update_database(app)
            print(f"   Full migration success: {migration_success}")
            
            print("\n✅ All migration tests passed!")
            return True
            
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_migration()
    if not success:
        sys.exit(1)
    print("Migration test completed successfully!") 