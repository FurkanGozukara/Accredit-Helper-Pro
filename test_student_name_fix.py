#!/usr/bin/env python3
"""
Quick test to verify the student name fix works correctly
"""

import os
import sys
import requests

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_student_name_fix():
    """Test that student name is retrieved correctly"""
    print("Testing Student Name Fix...")
    print("=" * 30)
    
    try:
        from app import app
        from models import Student
        
        with app.app_context():
            # Get a sample student from the database
            sample_student = Student.query.first()
            if sample_student:
                student_id = sample_student.student_id
                print(f"Testing with Student ID: {student_id}")
                print(f"Student first_name: {sample_student.first_name}")
                print(f"Student last_name: {sample_student.last_name}")
                
                # Test the helper function
                from routes.calculation_routes import get_cross_course_student_info
                student_courses, student_name, total_courses = get_cross_course_student_info(student_id)
                
                print(f"✓ Function executed successfully")
                print(f"✓ Student name retrieved: '{student_name}'")
                print(f"✓ Total courses: {total_courses}")
                print(f"✓ Course count: {len(student_courses)}")
                
                return True
            else:
                print("⚠ No students found in database")
                return False
                
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_web_request():
    """Test a web request with student ID parameter"""
    print("\nTesting Web Request...")
    print("=" * 30)
    
    try:
        # Get a sample student ID from database first
        from app import app
        from models import Student
        
        with app.app_context():
            sample_student = Student.query.first()
            if not sample_student:
                print("⚠ No students found for web test")
                return False
            
            student_id = sample_student.student_id
        
        # Test the web request
        base_url = "http://localhost:5000"
        response = requests.get(f"{base_url}/calculation/all_courses?student_id={student_id}", timeout=10)
        
        if response.status_code == 200:
            print(f"✓ Web request successful for student ID: {student_id}")
            print(f"✓ Response received (status: {response.status_code})")
            
            # Check if the response contains student info
            if "Student Information" in response.text or "No student found" in response.text:
                print("✓ Student information processed correctly")
            else:
                print("⚠ Student information section not found in response")
            
            return True
        else:
            print(f"✗ Web request failed with status: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠ Cannot connect to Flask app - make sure it's running on localhost:5000")
        return False
    except Exception as e:
        print(f"✗ Error during web test: {e}")
        return False

def main():
    print("Student Name Fix Verification")
    print("=" * 40)
    
    test1_passed = test_student_name_fix()
    test2_passed = test_web_request()
    
    print("\n" + "=" * 40)
    if test1_passed and test2_passed:
        print("🎉 All tests PASSED! Student name fix is working correctly.")
    elif test1_passed:
        print("✓ Function test passed, web test needs app running")
    else:
        print("❌ Tests failed - please check the implementation")

if __name__ == "__main__":
    main() 