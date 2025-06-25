#!/usr/bin/env python3
"""
Debug script to investigate calculation bug where program outcomes show percentages above 100%
"""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Course, Student, Exam, Question, Score, CourseOutcome, ProgramOutcome, ExamWeight
from routes.calculation_routes import calculate_single_course_results
from decimal import Decimal
import logging

def debug_calculation_issue():
    """Debug the calculation issue that's causing percentages above 100%"""
    
    app = create_app()
    
    with app.app_context():
        print("=== DEBUGGING CALCULATION ISSUE ===")
        print()
        
        # Get all courses to find problematic ones
        courses = Course.query.all()
        print(f"Found {len(courses)} courses total")
        
        problematic_courses = []
        
        for course in courses:
            print(f"\nAnalyzing Course: {course.code} - {course.name}")
            
            # Calculate results for this course
            try:
                result = calculate_single_course_results(course.id, 'absolute')
                
                if result['is_valid_for_aggregation']:
                    # Check for program outcome scores above 100%
                    for po_id, score in result['program_outcome_scores'].items():
                        if score > 100:
                            print(f"  ⚠️  ISSUE FOUND: PO ID {po_id} has score {score}% (above 100%)")
                            problematic_courses.append((course, po_id, score))
                            
                            # Get the program outcome details
                            po = ProgramOutcome.query.get(po_id)
                            if po:
                                print(f"      Program Outcome: {po.code} - {po.description}")
                            
                            # Let's investigate this specific course in detail
                            debug_course_calculation(course.id, po_id)
                        else:
                            # Normal score
                            po = ProgramOutcome.query.get(po_id)
                            if po:
                                print(f"  ✓ PO {po.code}: {score:.2f}%")
                else:
                    print(f"  (Course not valid for aggregation)")
                    
            except Exception as e:
                print(f"  ERROR calculating course {course.code}: {str(e)}")
                import traceback
                traceback.print_exc()
                
        print(f"\n=== SUMMARY ===")
        print(f"Found {len(problematic_courses)} issues with scores above 100%")
        
        for course, po_id, score in problematic_courses:
            po = ProgramOutcome.query.get(po_id)
            print(f"- {course.code}: PO {po.code if po else po_id} = {score:.2f}%")

def debug_course_calculation(course_id, problematic_po_id):
    """Debug a specific course calculation in detail"""
    print(f"\n    === DETAILED DEBUG FOR COURSE {course_id}, PO {problematic_po_id} ===")
    
    course = Course.query.get(course_id)
    
    # Get all exams
    exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()
    makeup_exams = Exam.query.filter_by(course_id=course_id, is_makeup=True).all()
    
    print(f"    Regular exams: {len(exams)}")
    print(f"    Makeup exams: {len(makeup_exams)}")
    
    # Get exam weights
    total_weight = Decimal('0')
    for exam in exams:
        weight = ExamWeight.query.filter_by(exam_id=exam.id).first()
        if weight:
            print(f"    Exam {exam.name}: weight = {weight.weight}")
            total_weight += weight.weight
        else:
            print(f"    Exam {exam.name}: NO WEIGHT DEFINED")
    
    print(f"    Total weight: {total_weight}")
    
    # Get course outcomes
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    print(f"    Course outcomes: {len(course_outcomes)}")
    
    # Find which course outcomes link to our problematic PO
    problematic_po = ProgramOutcome.query.get(problematic_po_id)
    linking_cos = []
    
    for co in course_outcomes:
        if problematic_po in co.program_outcomes:
            linking_cos.append(co)
            print(f"    CO {co.code} links to PO {problematic_po.code}")
            
            # Check questions for this CO
            questions = co.questions
            print(f"      Questions in CO {co.code}: {len(questions)}")
            
            for question in questions:
                print(f"        Q{question.number} (Exam: {question.exam.name}, Max: {question.max_score})")
    
    # Get students and their scores
    students = Student.query.filter_by(course_id=course_id).all()
    print(f"    Students: {len(students)}")
    
    # Sample a few student calculations
    if students:
        print(f"    Sampling student calculations...")
        for student in students[:3]:  # Check first 3 students
            print(f"      Student {student.student_id}:")
            
            # Calculate individual scores for this student and PO
            for co in linking_cos:
                questions = co.questions
                
                total_score = Decimal('0')
                total_possible = Decimal('0')
                
                for question in questions:
                    score_record = Score.query.filter_by(
                        student_id=student.id,
                        question_id=question.id,
                        exam_id=question.exam_id
                    ).first()
                    
                    if score_record:
                        total_score += Decimal(str(score_record.score))
                        print(f"        Q{question.number}: {score_record.score}/{question.max_score}")
                    else:
                        print(f"        Q{question.number}: NO_SCORE/{question.max_score}")
                    
                    total_possible += question.max_score
                
                if total_possible > 0:
                    percentage = (total_score / total_possible) * 100
                    print(f"        CO {co.code} total: {total_score}/{total_possible} = {percentage:.2f}%")
                else:
                    print(f"        CO {co.code} total: {total_score}/0 = N/A")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the debug
    debug_calculation_issue() 