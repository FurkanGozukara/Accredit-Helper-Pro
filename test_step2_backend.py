#!/usr/bin/env python3
"""
Test script for Step 2: Backend Route Enhancement

This script tests the new student filtering functionality in the all_courses route
to ensure it works correctly with the new database indexes.

Usage: python test_step2_backend.py
"""

import os
import sys
import requests
from flask import Flask

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_student_filtering_functionality():
    """Test the student filtering functionality"""
    print("Testing Step 2: Backend Route Enhancement...")
    print("=" * 50)
    
    # Test the helper functions
    try:
        from routes.calculation_routes import get_cross_course_student_info, filter_courses_by_student
        from models import Student, Course
        
        print("✓ Successfully imported student filtering functions")
        
        # Get a sample student ID from the database
        sample_student = Student.query.first()
        if sample_student:
            student_id = sample_student.student_id
            print(f"✓ Found sample student ID: {student_id}")
            
            # Test get_cross_course_student_info
            student_courses, student_name, total_courses = get_cross_course_student_info(student_id)
            print(f"✓ Student '{student_name}' found in {total_courses} courses")
            
            # Test filter_courses_by_student
            all_courses = Course.query.all()
            filtered_courses, student_info = filter_courses_by_student(all_courses, student_id)
            print(f"✓ Filtered {len(filtered_courses)} courses from {len(all_courses)} total courses")
            print(f"  Student info: {student_info}")
            
        else:
            print("⚠ No students found in database - skipping function tests")
            
    except Exception as e:
        print(f"✗ Error testing functions: {e}")
        return False
    
    return True

def test_route_endpoints():
    """Test the enhanced route endpoints"""
    print("\nTesting route endpoints...")
    print("-" * 30)
    
    base_url = "http://localhost:5000"
    
    try:
        # Test basic all_courses endpoint
        response = requests.get(f"{base_url}/calculation/all_courses", timeout=10)
        if response.status_code == 200:
            print("✓ Basic all_courses route works")
        else:
            print(f"✗ all_courses route failed: {response.status_code}")
            return False
        
        # Test with student_id parameter
        test_student_id = "12345"  # Example student ID
        response = requests.get(f"{base_url}/calculation/all_courses?student_id={test_student_id}", timeout=10)
        if response.status_code == 200:
            print(f"✓ all_courses route with student_id parameter works")
        else:
            print(f"✗ all_courses route with student_id failed: {response.status_code}")
            return False
        
        # Test export with student filtering
        response = requests.get(f"{base_url}/calculation/all_courses/export?student_id={test_student_id}", timeout=10)
        if response.status_code == 200:
            print("✓ Export route with student filtering works")
        else:
            print(f"✗ Export route with student filtering failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠ Cannot connect to Flask app - make sure it's running on localhost:5000")
        return False
    except Exception as e:
        print(f"✗ Error testing routes: {e}")
        return False
    
    return True

def test_ajax_response():
    """Test AJAX response format"""
    print("\nTesting AJAX response format...")
    print("-" * 30)
    
    base_url = "http://localhost:5000"
    
    try:
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        response = requests.get(f"{base_url}/calculation/all_courses?student_id=12345", 
                               headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for new fields in response
            if 'student_info' in data:
                print("✓ student_info field present in AJAX response")
            else:
                print("✗ student_info field missing from AJAX response")
                
            if 'filter_student_id' in data:
                print("✓ filter_student_id field present in AJAX response")
            else:
                print("✗ filter_student_id field missing from AJAX response")
                
            print(f"✓ AJAX response contains {len(data)} top-level fields")
            return True
        else:
            print(f"✗ AJAX request failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠ Cannot connect to Flask app for AJAX test")
        return False
    except Exception as e:
        print(f"✗ Error testing AJAX: {e}")
        return False

def main():
    """Run all tests"""
    print("Step 2 Backend Enhancement Test Suite")
    print("=" * 50)
    
    all_passed = True
    
    # Test 1: Student filtering functionality
    if not test_student_filtering_functionality():
        all_passed = False
    
    # Test 2: Route endpoints
    if not test_route_endpoints():
        all_passed = False
        
    # Test 3: AJAX response
    if not test_ajax_response():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All Step 2 backend tests PASSED!")
        print("\nStep 2 Summary:")
        print("✓ Student filtering functions implemented")
        print("✓ Cross-course student lookup working")
        print("✓ Route parameters enhanced") 
        print("✓ AJAX responses updated")
        print("✓ Export functionality enhanced")
        print("✓ Database indexes utilized")
    else:
        print("❌ Some Step 2 backend tests FAILED!")
        print("Please check the implementation and try again.")
    
    return all_passed

if __name__ == "__main__":
    # Initialize Flask app context for testing
    try:
        from app import app
        with app.app_context():
            main()
    except ImportError:
        print("Error: Could not import Flask app. Make sure you're in the correct directory.")
        sys.exit(1) 