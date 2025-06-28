#!/usr/bin/env python3
"""
Debug script to analyze why course 155-6047 (YAPAY ZEKA) produces impossible scores >300%
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Course, ProgramOutcome, CourseOutcome, Question, Score, Student, ExamWeight, CourseSettings
from routes.calculation_routes import calculate_course_results_from_bulk_data_v2_optimized, bulk_load_course_data
from decimal import Decimal

# Create app instance
app = create_app()

def debug_course_155_6047():
    """Debug the specific problematic course"""
    with app.app_context():
        print("=== DEBUG: Course 155-6047 (YAPAY ZEKA) ===\n")
        
        # Get the course
        course = Course.query.filter_by(code='155-6047').first()
        if not course:
            print("Course 155-6047 not found!")
            return
        
        print(f"Course: {course.code} - {course.name}")
        print(f"Course ID: {course.id}")
        print(f"Course Weight: {course.course_weight}")
        
        # Get course settings
        settings = course.settings
        if settings:
            print(f"Settings: {settings.success_rate_method}, threshold: {settings.relative_success_threshold}")
            print(f"Excluded: {settings.excluded}")
        else:
            print("No course settings found")
        
        print()
        
        # Get course outcomes
        course_outcomes = CourseOutcome.query.filter_by(course_id=course.id).all()
        print(f"Course Outcomes ({len(course_outcomes)}):")
        for co in course_outcomes:
            print(f"  {co.code}: {co.description}")
            # Get associated program outcomes
            pos = [po.code for po in co.program_outcomes]
            print(f"    Associated POs: {', '.join(pos)}")
        print()
        
        # Get exams
        from models import Exam
        exams = Exam.query.filter_by(course_id=course.id).all()
        print(f"Exams ({len(exams)}):")
        for exam in exams:
            print(f"  {exam.name} (ID: {exam.id}) - Mandatory: {exam.is_mandatory}, Makeup: {exam.is_makeup}")
            questions = Question.query.filter_by(exam_id=exam.id).all()
            print(f"    Questions: {len(questions)}")
        print()
        
        # Get exam weights
        weights = ExamWeight.query.filter_by(course_id=course.id).all()
        print(f"Exam Weights ({len(weights)}):")
        total_weight = Decimal('0')
        for weight in weights:
            print(f"  Exam {weight.exam_id}: {weight.weight}")
            total_weight += weight.weight
        print(f"  Total Weight: {total_weight}")
        print()
        
        # Get students
        students = Student.query.filter_by(course_id=course.id).all()
        print(f"Students: {len(students)}")
        excluded_students = [s for s in students if getattr(s, 'excluded', False)]
        print(f"Excluded Students: {len(excluded_students)}")
        print()
        
        # Calculate using bulk data
        bulk_data = bulk_load_course_data([course.id], 'absolute')
        result = calculate_course_results_from_bulk_data_v2_optimized(course.id, bulk_data, 'absolute')
        
        print("=== CALCULATION RESULTS ===")
        print(f"Is valid for aggregation: {result['is_valid_for_aggregation']}")
        print(f"Student count used: {result['student_count_used']}")
        print(f"Contributing PO IDs: {len(result['contributing_po_ids'])}")
        print()
        
        print("Program Outcome Scores:")
        for po_id, score in result['program_outcome_scores'].items():
            po = ProgramOutcome.query.get(po_id)
            if po:
                print(f"  {po.code}: {score:.2f}%")
                if score > 100:
                    print(f"    ⚠️  PROBLEMATIC SCORE!")
        print()
        
        # Examine specific problematic PO (PÇ11.2)
        po_11_2 = ProgramOutcome.query.filter_by(code='PÇ11.2').first()
        if po_11_2 and po_11_2.id in result['program_outcome_scores']:
            score = result['program_outcome_scores'][po_11_2.id]
            print(f"=== DETAILED ANALYSIS: PÇ11.2 (Score: {score:.2f}%) ===")
            
            # Find course outcomes that contribute to this PO
            contributing_cos = []
            for co in course_outcomes:
                if po_11_2 in co.program_outcomes:
                    contributing_cos.append(co)
            
            print(f"Contributing Course Outcomes: {len(contributing_cos)}")
            for co in contributing_cos:
                print(f"  {co.code}: {co.description}")
                
                # Get questions for this CO
                questions = Question.query.filter_by(course_outcome_id=co.id).all()
                print(f"    Questions: {len(questions)}")
                
                # Get CO-PO weights
                from models import CourseOutcomeProgramOutcome
                co_po_link = CourseOutcomeProgramOutcome.query.filter_by(
                    course_outcome_id=co.id, 
                    program_outcome_id=po_11_2.id
                ).first()
                if co_po_link:
                    print(f"    CO-PO Weight: {co_po_link.relative_weight}")
                else:
                    print(f"    CO-PO Weight: Default (1.0)")
                
                # Examine some sample student scores
                sample_students = students[:5]  # First 5 students
                print(f"    Sample student scores:")
                for student in sample_students:
                    scores = Score.query.filter_by(student_id=student.id).all()
                    student_scores = []
                    for question in questions:
                        score_obj = next((s for s in scores if s.question_id == question.id), None)
                        if score_obj:
                            student_scores.append(f"Q{question.id}:{score_obj.score}/{question.max_score}")
                    print(f"      Student {student.id}: {', '.join(student_scores[:3])}...")
            print()

def debug_course_outcome_calculation():
    """Debug the course outcome calculation step by step"""
    with app.app_context():
        course = Course.query.filter_by(code='155-6047').first()
        if not course:
            return
        
        print("=== STEP-BY-STEP COURSE OUTCOME CALCULATION ===\n")
        
        # Get a specific student for detailed analysis
        students = Student.query.filter_by(course_id=course.id, excluded=False).limit(3).all()
        print(f"Analyzing first 3 students...")
        
        for student in students:
            print(f"\nStudent {student.id} ({student.first_name} {student.last_name}):")
            
            # Get all scores for this student
            scores = Score.query.filter_by(student_id=student.id).all()
            score_dict = {score.question_id: score.score for score in scores}
            
            # Get course outcomes
            course_outcomes = CourseOutcome.query.filter_by(course_id=course.id).all()
            
            for co in course_outcomes:
                print(f"  Course Outcome {co.code}:")
                
                # Get questions for this CO
                questions = Question.query.filter_by(course_outcome_id=co.id).all()
                
                if not questions:
                    print(f"    No questions linked to this CO")
                    continue
                
                # Group by exam
                from collections import defaultdict
                questions_by_exam = defaultdict(list)
                for q in questions:
                    questions_by_exam[q.exam_id].append(q)
                
                # Calculate score for each exam
                print(f"    Questions by exam:")
                total_co_score = Decimal('0')
                total_weight = Decimal('0')
                
                for exam_id, exam_questions in questions_by_exam.items():
                    exam = Exam.query.get(exam_id)
                    if not exam:
                        continue
                    
                    # Get exam weight
                    weight_obj = ExamWeight.query.filter_by(course_id=course.id, exam_id=exam_id).first()
                    exam_weight = weight_obj.weight if weight_obj else Decimal('0')
                    
                    # Calculate student's score on this exam for this CO
                    student_score = Decimal('0')
                    max_possible = Decimal('0')
                    
                    for q in exam_questions:
                        student_answer = score_dict.get(q.id, 0)
                        student_score += Decimal(str(student_answer))
                        max_possible += Decimal(str(q.max_score))
                    
                    # Calculate percentage for this exam's contribution to CO
                    if max_possible > 0:
                        exam_percentage = (student_score / max_possible) * Decimal('100')
                    else:
                        exam_percentage = Decimal('0')
                    
                    print(f"      Exam {exam.name}: {student_score}/{max_possible} = {exam_percentage:.2f}% (weight: {exam_weight})")
                    
                    # Add to weighted total
                    total_co_score += exam_percentage * exam_weight
                    total_weight += exam_weight
                
                # Calculate final CO score
                if total_weight > 0:
                    final_co_score = total_co_score / total_weight
                    print(f"    Final CO Score: {final_co_score:.2f}%")
                    
                    if final_co_score > 100:
                        print(f"    ⚠️  CO SCORE EXCEEDS 100%!")
                else:
                    print(f"    Final CO Score: 0.00% (no weight)")

if __name__ == "__main__":
    debug_course_155_6047()
    print("\n" + "="*60 + "\n")
    debug_course_outcome_calculation() 