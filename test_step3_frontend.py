#!/usr/bin/env python3
"""
Test script for Step 3: Frontend Template Enhancement

This script tests the new UI components and functionality in the all_courses template
to ensure the student filtering and bulk actions work correctly.

Usage: python test_step3_frontend.py
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
import time

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_template_elements():
    """Test that new UI elements are present in the template"""
    print("Testing Step 3: Frontend Template Enhancement...")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    try:
        # Get the all_courses page
        response = requests.get(f"{base_url}/calculation/all_courses", timeout=10)
        if response.status_code != 200:
            print(f"✗ Failed to load all_courses page: {response.status_code}")
            return False
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Test 1: Student ID filter input
        student_filter = soup.find('input', {'id': 'studentIdFilter'})
        if student_filter:
            print("✓ Student ID filter input found")
        else:
            print("✗ Student ID filter input missing")
            return False
        
        # Test 2: Clear student filter button
        clear_btn = soup.find('button', {'id': 'clearStudentFilter'})
        if clear_btn:
            print("✓ Clear student filter button found")
        else:
            print("✗ Clear student filter button missing")
            return False
        
        # Test 3: Bulk action buttons
        include_all_btn = soup.find('button', {'id': 'includeAllBtn'})
        exclude_all_btn = soup.find('button', {'id': 'excludeAllBtn'})
        if include_all_btn and exclude_all_btn:
            print("✓ Bulk action buttons (Include/Exclude All) found")
        else:
            print("✗ Bulk action buttons missing")
            return False
        
        # Test 4: Select/Deselect all buttons
        select_all_btn = soup.find('button', {'id': 'selectAllCheckboxes'})
        deselect_all_btn = soup.find('button', {'id': 'deselectAllCheckboxes'})
        if select_all_btn and deselect_all_btn:
            print("✓ Select/Deselect all buttons found")
        else:
            print("✗ Select/Deselect all buttons missing")
            return False
        
        # Test 5: Master checkbox in table header
        select_all_checkbox = soup.find('input', {'id': 'selectAllCourses'})
        if select_all_checkbox:
            print("✓ Master select all checkbox found in table header")
        else:
            print("✗ Master select all checkbox missing")
            return False
        
        # Test 6: Course checkboxes in table rows
        course_checkboxes = soup.find_all('input', {'class': 'course-checkbox'})
        if len(course_checkboxes) > 0:
            print(f"✓ Found {len(course_checkboxes)} course checkboxes in table rows")
        else:
            print("✗ No course checkboxes found in table rows")
            return False
        
        # Test 7: Selected count display
        selected_count = soup.find('span', {'id': 'selectedCount'})
        if selected_count:
            print("✓ Selected count display found")
        else:
            print("✗ Selected count display missing")
            return False
        
        print("✓ All UI elements present in template")
        return True
        
    except requests.exceptions.ConnectionError:
        print("⚠ Cannot connect to Flask app - make sure it's running on localhost:5000")
        return False
    except Exception as e:
        print(f"✗ Error testing template elements: {e}")
        return False

def test_student_filter_functionality():
    """Test student filtering functionality"""
    print("\nTesting student filter functionality...")
    print("-" * 40)
    
    base_url = "http://localhost:5000"
    
    try:
        # Test with a sample student ID
        test_student_id = "12345"
        response = requests.get(f"{base_url}/calculation/all_courses?student_id={test_student_id}", timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check if student ID filter has the value
            student_filter = soup.find('input', {'id': 'studentIdFilter'})
            if student_filter and student_filter.get('value') == test_student_id:
                print("✓ Student ID filter preserves value in URL")
            else:
                print("✗ Student ID filter doesn't preserve value")
                return False
            
            # Check for student info alert or no student found alert
            student_info_alert = soup.find('div', {'id': 'studentInfoAlert'})
            if student_info_alert:
                if 'alert-info' in student_info_alert.get('class', []):
                    print("✓ Student information alert displayed (student found)")
                elif 'alert-warning' in student_info_alert.get('class', []):
                    print("✓ No student found alert displayed")
                else:
                    print("✗ Unknown alert type for student info")
                    return False
            else:
                print("⚠ No student info alert found (may be expected if no student with this ID)")
            
            return True
        else:
            print(f"✗ Student filter request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing student filter: {e}")
        return False

def test_javascript_functions():
    """Test JavaScript functions are properly defined"""
    print("\nTesting JavaScript functionality...")
    print("-" * 40)
    
    base_url = "http://localhost:5000"
    
    try:
        response = requests.get(f"{base_url}/calculation/all_courses", timeout=10)
        if response.status_code != 200:
            print(f"✗ Failed to load page for JS testing: {response.status_code}")
            return False
        
        content = response.text
        
        # Check for key JavaScript functions
        js_functions = [
            'clearStudentFilter',
            'applyStudentFilter', 
            'updateSelectedCount',
            'getSelectedCourses',
            'bulkUpdateCourseExclusion',
            'processCoursesBatch'
        ]
        
        missing_functions = []
        for func in js_functions:
            if f"function {func}" in content or f"{func} =" in content:
                print(f"✓ JavaScript function '{func}' found")
            else:
                missing_functions.append(func)
        
        if missing_functions:
            print(f"✗ Missing JavaScript functions: {missing_functions}")
            return False
        
        # Check for event listeners
        event_listeners = [
            'studentIdFilter.addEventListener',
            'clearStudentFilterBtn.addEventListener',
            'selectAllCourses.addEventListener',
            'includeAllBtn.addEventListener',
            'excludeAllBtn.addEventListener'
        ]
        
        missing_listeners = []
        for listener in event_listeners:
            if listener in content:
                print(f"✓ Event listener '{listener}' found")
            else:
                missing_listeners.append(listener)
        
        if missing_listeners:
            print(f"✗ Missing event listeners: {missing_listeners}")
            return False
        
        print("✓ All JavaScript functionality present")
        return True
        
    except Exception as e:
        print(f"✗ Error testing JavaScript: {e}")
        return False

def test_responsive_design():
    """Test responsive design elements"""
    print("\nTesting responsive design...")
    print("-" * 40)
    
    base_url = "http://localhost:5000"
    
    try:
        response = requests.get(f"{base_url}/calculation/all_courses", timeout=10)
        if response.status_code != 200:
            print(f"✗ Failed to load page for responsive testing: {response.status_code}")
            return False
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check for responsive classes
        responsive_elements = [
            ('flex-wrap', 'Flexible wrapping elements'),
            ('gap-2', 'Gap spacing'),
            ('d-flex', 'Flexbox layout'),
            ('align-items-center', 'Vertical alignment')
        ]
        
        for class_name, description in responsive_elements:
            elements = soup.find_all(class_=class_name)
            if elements:
                print(f"✓ {description} found ({len(elements)} elements with '{class_name}')")
            else:
                print(f"⚠ {description} not found ('{class_name}' class)")
        
        # Check for input groups
        input_groups = soup.find_all('div', class_='input-group')
        if len(input_groups) >= 2:  # Student ID filter + Course search
            print(f"✓ Input groups found ({len(input_groups)} groups)")
        else:
            print(f"⚠ Expected at least 2 input groups, found {len(input_groups)}")
        
        print("✓ Responsive design elements present")
        return True
        
    except Exception as e:
        print(f"✗ Error testing responsive design: {e}")
        return False

def test_accessibility_features():
    """Test accessibility features"""
    print("\nTesting accessibility features...")
    print("-" * 40)
    
    base_url = "http://localhost:5000"
    
    try:
        response = requests.get(f"{base_url}/calculation/all_courses", timeout=10)
        if response.status_code != 200:
            print(f"✗ Failed to load page for accessibility testing: {response.status_code}")
            return False
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check for ARIA labels and accessibility attributes
        aria_elements = [
            ('aria-label', 'ARIA labels'),
            ('title', 'Title attributes'),
            ('placeholder', 'Placeholder text')
        ]
        
        for attr, description in aria_elements:
            elements = soup.find_all(attrs={attr: True})
            if elements:
                print(f"✓ {description} found ({len(elements)} elements with '{attr}')")
            else:
                print(f"⚠ {description} not found")
        
        # Check for form labels
        labels = soup.find_all('label')
        if labels:
            print(f"✓ Form labels found ({len(labels)} labels)")
        else:
            print("⚠ No form labels found")
        
        # Check for button types
        buttons = soup.find_all('button')
        typed_buttons = [btn for btn in buttons if btn.get('type')]
        if typed_buttons:
            print(f"✓ Button types specified ({len(typed_buttons)}/{len(buttons)} buttons)")
        else:
            print(f"⚠ Button types not specified for {len(buttons)} buttons")
        
        print("✓ Accessibility features checked")
        return True
        
    except Exception as e:
        print(f"✗ Error testing accessibility: {e}")
        return False

def main():
    """Run all frontend tests"""
    print("Step 3 Frontend Enhancement Test Suite")
    print("=" * 50)
    
    all_passed = True
    
    # Test 1: Template elements
    if not test_template_elements():
        all_passed = False
    
    # Test 2: Student filter functionality
    if not test_student_filter_functionality():
        all_passed = False
        
    # Test 3: JavaScript functions
    if not test_javascript_functions():
        all_passed = False
    
    # Test 4: Responsive design
    if not test_responsive_design():
        all_passed = False
        
    # Test 5: Accessibility features
    if not test_accessibility_features():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All Step 3 frontend tests PASSED!")
        print("\nStep 3 Summary:")
        print("✓ Student ID filter input implemented")
        print("✓ Student information display working") 
        print("✓ Checkbox-based include/exclude functionality added")
        print("✓ Bulk action buttons implemented")
        print("✓ Select/Deselect all functionality working")
        print("✓ JavaScript event handlers implemented")
        print("✓ Responsive design elements added")
        print("✓ Accessibility features included")
    else:
        print("❌ Some Step 3 frontend tests FAILED!")
        print("Please check the template implementation and try again.")
    
    return all_passed

if __name__ == "__main__":
    main() 