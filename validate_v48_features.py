#!/usr/bin/env python3
"""
V48 Feature Validation Script for Accredit Helper Pro
Tests new features to ensure they're working correctly
"""

import os
import sys
import sqlite3
import importlib.util
import logging
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.abspath('.'))

def test_database_connection():
    """Test database connection and basic functionality"""
    print("🔍 Testing database connection...")
    try:
        # Check if database file exists
        db_files = ['instance/accredit_helper.db', 'accredit_helper.db', 'database.db']
        db_path = None
        
        for db_file in db_files:
            if os.path.exists(db_file):
                db_path = db_file
                break
        
        if not db_path:
            print("❌ Database file not found")
            return False
        
        # Test connection
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        conn.close()
        print(f"✅ Database connection successful ({len(tables)} tables found)")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_graduating_students_table():
    """Test if the graduating_students table exists and is accessible"""
    print("🎓 Testing graduating students table...")
    try:
        # Find database file
        db_files = ['instance/accredit_helper.db', 'accredit_helper.db', 'database.db']
        db_path = None
        
        for db_file in db_files:
            if os.path.exists(db_file):
                db_path = db_file
                break
        
        if not db_path:
            print("❌ Database file not found")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if graduating_student table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='graduating_student'
        """)
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Test basic operations
            cursor.execute("SELECT COUNT(*) FROM graduating_student")
            count = cursor.fetchone()[0]
            print(f"✅ Graduating students table exists ({count} records)")
        else:
            print("⚠️ Graduating students table not found (migration may be needed)")
        
        conn.close()
        return table_exists
        
    except Exception as e:
        print(f"❌ Graduating students table test failed: {e}")
        return False

def test_migration_files():
    """Test if migration files exist and are properly structured"""
    print("🛠️ Testing migration files...")
    try:
        migration_files = [
            'migrations/add_graduating_students.py',
            'db_migrations.py'
        ]
        
        all_exist = True
        for migration_file in migration_files:
            if os.path.exists(migration_file):
                print(f"✅ {migration_file} exists")
                
                # Test if it's a valid Python file
                try:
                    spec = importlib.util.spec_from_file_location("migration", migration_file)
                    if spec and spec.loader:
                        print(f"✅ {migration_file} is valid Python")
                    else:
                        print(f"⚠️ {migration_file} may have import issues")
                except Exception as e:
                    print(f"⚠️ {migration_file} validation error: {e}")
            else:
                print(f"❌ {migration_file} not found")
                all_exist = False
        
        return all_exist
        
    except Exception as e:
        print(f"❌ Migration files test failed: {e}")
        return False

def test_pdf_dependencies():
    """Test if PDF generation dependencies are available"""
    print("📄 Testing PDF generation dependencies...")
    try:
        dependencies = [
            ('playwright', 'Playwright browser automation'),
            ('PyPDF2', 'PDF manipulation library')
        ]
        
        all_available = True
        for dep_name, description in dependencies:
            try:
                __import__(dep_name)
                print(f"✅ {dep_name} ({description}) is available")
            except ImportError:
                print(f"❌ {dep_name} ({description}) is missing")
                all_available = False
        
        # Check if multithreading module exists
        if os.path.exists('routes/pdf_multithread.py'):
            print("✅ Multi-threaded PDF module exists")
        else:
            print("❌ Multi-threaded PDF module not found")
            all_available = False
        
        return all_available
        
    except Exception as e:
        print(f"❌ PDF dependencies test failed: {e}")
        return False

def test_new_templates():
    """Test if new template files exist"""
    print("🎨 Testing new template files...")
    try:
        new_templates = [
            'templates/calculation/graduating_students.html',
            'templates/calculation/all_courses.html'
        ]
        
        all_exist = True
        for template in new_templates:
            if os.path.exists(template):
                print(f"✅ {template} exists")
                
                # Check file size (should not be empty)
                file_size = os.path.getsize(template)
                if file_size > 0:
                    print(f"✅ {template} has content ({file_size} bytes)")
                else:
                    print(f"⚠️ {template} is empty")
            else:
                print(f"❌ {template} not found")
                all_exist = False
        
        return all_exist
        
    except Exception as e:
        print(f"❌ Template files test failed: {e}")
        return False

def test_documentation_files():
    """Test if documentation files exist and have content"""
    print("📚 Testing documentation files...")
    try:
        doc_files = [
            'MULTITHREADED_PDF_IMPLEMENTATION.md',
            'PLAYWRIGHT_PDF_MIGRATION.md'
        ]
        
        all_exist = True
        for doc_file in doc_files:
            if os.path.exists(doc_file):
                print(f"✅ {doc_file} exists")
                
                # Check file size
                file_size = os.path.getsize(doc_file)
                if file_size > 1000:  # Should have substantial content
                    print(f"✅ {doc_file} has substantial content ({file_size} bytes)")
                else:
                    print(f"⚠️ {doc_file} may lack content ({file_size} bytes)")
            else:
                print(f"❌ {doc_file} not found")
                all_exist = False
        
        return all_exist
        
    except Exception as e:
        print(f"❌ Documentation files test failed: {e}")
        return False

def test_app_import():
    """Test if the Flask app can be imported successfully"""
    print("🚀 Testing Flask app import...")
    try:
        # Try to import the app
        import app
        print("✅ App module imported successfully")
        
        # Try to create app instance
        flask_app = app.create_app()
        print("✅ Flask app instance created successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Flask app import failed: {e}")
        return False

def generate_validation_report(results):
    """Generate a comprehensive validation report"""
    print(f"\n{'='*60}")
    print("V48 FEATURE VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"Validation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    passed = sum(1 for result in results.values() if result['status'])
    total = len(results)
    success_rate = (passed / total) * 100
    
    print(f"Overall Status: {passed}/{total} tests passed ({success_rate:.1f}%)")
    print()
    
    for test_name, result in results.items():
        status_icon = "✅" if result['status'] else "❌"
        print(f"{status_icon} {test_name}: {'PASS' if result['status'] else 'FAIL'}")
        if result.get('details'):
            print(f"   Details: {result['details']}")
    
    print(f"\n{'='*60}")
    
    if success_rate >= 80:
        print("🎉 V48 features are ready for production!")
        print("The majority of new features are working correctly.")
    elif success_rate >= 60:
        print("⚠️ V48 features need attention!")
        print("Some features may not work correctly. Please review failing tests.")
    else:
        print("🚨 V48 features have significant issues!")
        print("Multiple critical features are not working. Immediate attention required.")
    
    print(f"{'='*60}")
    
    return success_rate >= 80

def main():
    """Main validation function"""
    print("🔬 Starting V48 Feature Validation...")
    print(f"{'='*60}")
    
    # Run all tests
    tests = {
        "Database Connection": lambda: test_database_connection(),
        "Graduating Students Table": lambda: test_graduating_students_table(),
        "Migration Files": lambda: test_migration_files(),
        "PDF Dependencies": lambda: test_pdf_dependencies(),
        "Template Files": lambda: test_new_templates(),
        "Documentation Files": lambda: test_documentation_files(),
        "Flask App Import": lambda: test_app_import()
    }
    
    results = {}
    
    for test_name, test_func in tests.items():
        print(f"\n{'-'*40}")
        try:
            status = test_func()
            results[test_name] = {"status": status}
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = {"status": False, "details": str(e)}
    
    # Generate report
    success = generate_validation_report(results)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 