from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from app import db
from models import (
    Course, Student, Exam, CourseOutcome, Question, Score, 
    ProgramOutcome, ExamWeight, StudentExamAttendance, CourseSettings,
    AchievementLevel, Log, GlobalAchievementLevel, GraduatingStudent
)
from datetime import datetime
import logging
import csv
import io
import os
from sqlalchemy import func
from routes.utility_routes import export_to_excel_csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import session
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import base64
import json
from flask import current_app

calculation_bp = Blueprint('calculation', __name__, url_prefix='/calculation')

# Helper function for achievement levels
def get_achievement_level(score, achievement_levels):
    """
    Get the achievement level for a given score using precise Decimal comparisons.
    Ensures boundaries are handled correctly (e.g., 60.00 falls into 60.00-69.99).
    """
    try:
        # Ensure score is a Decimal for precision. Handle potential non-numeric input.
        if not isinstance(score, Decimal):
            score_decimal = Decimal(str(score))
        else:
            score_decimal = score

        # Round the score to 2 decimal places using standard rounding (half up)
        # This standardizes the value being compared against boundaries.
        # Example: 59.995 -> 60.00, 59.994 -> 59.99
        rounded_score = score_decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    except (InvalidOperation, TypeError, ValueError):
         # Handle cases where score might be None, NaN, infinity, or unconvertible string
        return {'name': 'Invalid Score', 'color': 'secondary'}

    # Ensure achievement_levels is a list and contains valid level objects
    if not isinstance(achievement_levels, list):
         return {'name': 'Config Error', 'color': 'danger'} # Should not happen if called correctly

    # Sort levels by min_score descending to find the highest applicable level first.
    # Use Decimal for sorting to ensure correct order (e.g., 90.00 > 89.99)
    try:
        sorted_levels = sorted(achievement_levels, key=lambda x: Decimal(str(x.min_score)), reverse=True)
    except (InvalidOperation, TypeError, ValueError):
         return {'name': 'Config Error', 'color': 'danger'} # Error in level data

    for level in sorted_levels:
        try:
            # Convert level boundaries to Decimal for precise comparison
            min_score_decimal = Decimal(str(level.min_score))
            max_score_decimal = Decimal(str(level.max_score))

            # *** CRITICAL COMPARISON LOGIC ***
            # Check if the rounded score is WITHIN the level's range (inclusive)
            # rounded_score >= min_score AND rounded_score <= max_score
            if rounded_score >= min_score_decimal and rounded_score <= max_score_decimal:
                return {
                    'name': level.name,
                    'color': level.color
                }
        except (InvalidOperation, TypeError, ValueError):
             # Skip level if its boundaries are invalid
             print(f"Warning: Skipping achievement level '{level.name}' due to invalid boundary values.")
             continue # Move to the next level

    # If no category matches (e.g., score is 0.00 and lowest level starts at 0.01)
    # Or if all levels had errors
    return {'name': 'Not Categorized', 'color': 'secondary'}

@calculation_bp.route('/course/<int:course_id>')
def course_calculations(course_id):
    """Show calculation results for a course"""
    course = Course.query.get_or_404(course_id)
    
    # Get achievement levels for this course
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    # Check if the course has achievement levels, if not, add default ones
    if not achievement_levels:
        # Add default achievement levels
        default_levels = [
            {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
            {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
            {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
            {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
            {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
        ]
        
        for level_data in default_levels:
            level = AchievementLevel(
                course_id=course_id,
                name=level_data["name"],
                min_score=level_data["min_score"],
                max_score=level_data["max_score"],
                color=level_data["color"]
            )
            db.session.add(level)
        
        # Log action
        log = Log(action="ADD_DEFAULT_ACHIEVEMENT_LEVELS", 
                 description=f"Added default achievement levels to course: {course.code}")
        db.session.add(log)
        db.session.commit()
        
        # Refresh achievement levels
        achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    # Get the course settings or create default
    settings = CourseSettings.query.filter_by(course_id=course_id).first()
    if not settings:
        settings = CourseSettings(
            course_id=course_id,
            success_rate_method='absolute',
            relative_success_threshold=60.0
        )
        db.session.add(settings)
        db.session.commit()
    
    # Check if course is excluded
    if settings.excluded:
        flash(f'This course ({course.code}) is currently excluded from calculations. You can include it by using the button below.', 'warning')
        
        # Prepare empty data structure for template
        student_results = {}
        course_outcome_results = {}
        program_outcomes = set()
        for co in course.course_outcomes:
            for po in co.program_outcomes:
                program_outcomes.add(po)
        
        # Sort program outcomes numerically by extracting the number from the code
        program_outcomes = sorted(list(program_outcomes), key=lambda po: int(''.join(filter(str.isdigit, po.code))) if any(c.isdigit() for c in po.code) else po.code)
        
        program_outcome_results = {po.code: {'description': po.description, 'percentage': 0, 'level': get_achievement_level(0, achievement_levels)} for po in program_outcomes}
        
        # Get students from exam scores for display
        students = Student.query.filter_by(course_id=course_id).all()
        students_dict = {student.id: student for student in students}
        
        # Get regular and makeup exams separately for display purposes
        regular_exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).order_by(Exam.created_at).all()
        makeup_exams = Exam.query.filter_by(course_id=course_id, is_makeup=True).order_by(Exam.created_at).all()
        
        # Create a map from original exam to makeup exam for display
        makeup_map = {}
        for makeup in makeup_exams:
            if makeup.makeup_for:
                makeup_map[makeup.makeup_for] = makeup
        
        # Get exam weights for display
        weights = ExamWeight.query.filter_by(course_id=course_id).all()
        exam_weights = {}
        total_weight_percent = Decimal('0')
        for weight in weights:
            exam_weights[weight.exam_id] = weight.weight
            total_weight_percent += weight.weight * 100
        
        # Get course outcomes for display
        course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()
        
        return render_template('calculation/results.html',
                              course=course,
                              exams=regular_exams,
                              makeup_exams=makeup_map,
                              course_outcomes=course_outcomes,
                              program_outcomes=program_outcomes,
                              students=students_dict,
                              student_results=student_results,
                              course_outcome_results=course_outcome_results,
                              program_outcome_results=program_outcome_results,
                              achievement_levels=achievement_levels,
                              has_course_outcomes=len(course_outcomes) > 0,
                              has_exam_questions=True,
                              has_student_scores=True,
                              has_valid_weights=True,
                              is_excluded=True,
                              total_weight_percent=total_weight_percent,
                              exam_weights=exam_weights,
                              get_achievement_level=get_achievement_level,
                              active_page='courses')
    
    # Determine which calculation method to use (from session, like all_courses)
    calculation_method = session.get('display_method', 'absolute')
    
    # Get regular and makeup exams separately for display purposes
    regular_exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).order_by(Exam.created_at).all()
    makeup_exams = Exam.query.filter_by(course_id=course_id, is_makeup=True).order_by(Exam.created_at).all()
    
    # Create a map from original exam to makeup exam for display
    makeup_map = {}
    for makeup in makeup_exams:
        if makeup.makeup_for:
            makeup_map[makeup.makeup_for] = makeup
    
    # Get exam weights for display
    weights = ExamWeight.query.filter_by(course_id=course_id).all()
    exam_weights = {}
    for weight in weights:
        exam_weights[weight.exam_id] = weight.weight
    
    # Calculate the total weight percentage for display
    total_weight = Decimal('0')
    for exam in regular_exams:
        if exam.id in exam_weights:
            total_weight += exam_weights[exam.id]
    total_weight_percent = total_weight * Decimal('100')
    
    # Get course outcomes for display
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()
    
    # Get program outcomes for display
    program_outcomes = set()
    for co in course_outcomes:
        for po in co.program_outcomes:
            program_outcomes.add(po)
    # Sort program outcomes numerically by extracting the number from the code
    program_outcomes = sorted(list(program_outcomes), key=lambda po: int(''.join(filter(str.isdigit, po.code))) if any(c.isdigit() for c in po.code) else po.code)
    
    # Use the calculate_single_course_results function to get all data
    results = calculate_single_course_results(course_id, calculation_method)
    
    # Process results for template display
    if not results['is_valid_for_aggregation']:
        # Not enough data to calculate results
        flash('Insufficient data to calculate results. Please check that you have course outcomes, exam questions, and student scores.', 'warning')
        
        # Prepare empty data structure for template
        student_results = {}
        course_outcome_results = {}
        program_outcome_results = {po.code: {'description': po.description, 'percentage': 0, 'level': get_achievement_level(0, achievement_levels)} for po in program_outcomes}
        
        # Get students from exam scores for display
        students = Student.query.filter_by(course_id=course_id).all()
        students_dict = {student.id: student for student in students}
        
        return render_template('calculation/results.html',
                              course=course,
                              exams=regular_exams,
                              makeup_exams=makeup_map,
                              course_outcomes=course_outcomes,
                              program_outcomes=program_outcomes,
                              students=students_dict,
                              student_results=student_results,
                              course_outcome_results=course_outcome_results,
                              program_outcome_results=program_outcome_results,
                              achievement_levels=achievement_levels,
                              has_course_outcomes=len(course_outcomes) > 0,
                              has_exam_questions=False,
                              has_student_scores=False,
                              has_valid_weights=True,
                              is_excluded=False,
                              total_weight_percent=total_weight_percent,
                              exam_weights=exam_weights,
                              get_achievement_level=get_achievement_level,
                              active_page='courses')
    
    # Data is available for calculation
    # Get all students for display
    students = Student.query.filter_by(course_id=course_id).all()
    students_dict = {student.id: student for student in students}
    
    # Get scores for all students for each regular exam
    exam_scores_dict = {}
    exam_max_scores = {}  # Store max scores for each exam
    
    for exam in regular_exams:
        # Calculate max possible score for this exam
        questions = Question.query.filter_by(exam_id=exam.id).all()
        exam_max_scores[exam.id] = sum(float(q.max_score) for q in questions) if questions else 0
        
        # Get all scores for this exam
        exam_scores = Score.query.filter_by(exam_id=exam.id).all()
        
        # Initialize dictionary for this exam
        student_total_scores = {}
        
        # Sum up scores for each student across all questions
        for score in exam_scores:
            if score.student_id not in student_total_scores:
                student_total_scores[score.student_id] = 0
            student_total_scores[score.student_id] += float(score.score)
        
        # Store the summed scores
        exam_scores_dict[exam.id] = student_total_scores
    
    # Get scores for all students for each makeup exam
    makeup_scores_dict = {}
    for exam in makeup_exams:
        # Calculate max possible score for this makeup exam
        questions = Question.query.filter_by(exam_id=exam.id).all()
        exam_max_scores[exam.id] = sum(float(q.max_score) for q in questions) if questions else 0
        
        # Get all scores for this makeup exam
        makeup_scores = Score.query.filter_by(exam_id=exam.id).all()
        
        # Initialize dictionary for this exam
        student_total_scores = {}
        
        # Sum up scores for each student across all questions
        for score in makeup_scores:
            if score.student_id not in student_total_scores:
                student_total_scores[score.student_id] = 0
            student_total_scores[score.student_id] += float(score.score)
        
        # Store the summed scores
        makeup_scores_dict[exam.id] = student_total_scores
    
    # Get attendance info
    attendance_dict = {}
    attendances = StudentExamAttendance.query.join(Exam).filter(Exam.course_id == course_id).all()
    for attendance in attendances:
        attendance_dict[(attendance.student_id, attendance.exam_id)] = attendance.attended
    
    # Format program outcome results for template
    program_outcome_results = {}
    for po in program_outcomes:
        po_score = results['program_outcome_scores'].get(po.id, Decimal('0'))
        
        # Get related course outcome codes for this program outcome
        related_course_outcomes = []
        for co in course_outcomes:
            if po in co.program_outcomes:
                related_course_outcomes.append(co.code)
        
        program_outcome_results[po.code] = {
            'description': po.description,
            'percentage': po_score,
            'course_outcomes': related_course_outcomes,
            'level': get_achievement_level(float(po_score), achievement_levels)
        }
    
    # Create course_outcome_results for the template with percentage and achievement level
    course_outcome_results = {}
    for co in course_outcomes:
        co_score = results['course_outcome_scores'].get(co.id, Decimal('0'))
        co_data = {
            'description': co.description,
            'percentage': co_score,
            'program_outcomes': [po.code for po in co.program_outcomes],
            'achievement_level': get_achievement_level(float(co_score), achievement_levels)
        }
        course_outcome_results[co.code] = co_data
    
    # Create student_results for the template
    student_results = {}
    for student in students:
        if student.excluded:
            # For excluded students, only add minimal info with excluded flag
            student_results[student.id] = {
                'student_id': student.student_id,
                'name': f"{student.first_name} {student.last_name}".strip(),
                'excluded': True,
                'overall_percentage': 0,
                'course_outcomes': {},
                'exam_scores': {}
            }
            continue
            
        # Create data for non-excluded students
        student_result = {
            'student_id': student.student_id,
            'name': f"{student.first_name} {student.last_name}".strip(),
            'overall_percentage': 0,
            'course_outcomes': {},
            'exam_scores': {},  # Add empty exam_scores dictionary
            'attended_makeup_exams': {},  # Add empty attended_makeup_exams dictionary
            'excluded': False
        }
        
        # Get the student data from calculation results
        student_data = results.get('student_results', {}).get(student.id, {})
        if student_data:
            # Set overall percentage from weighted score
            student_result['overall_percentage'] = float(student_data.get('weighted_score', 0))
            
            # Ensure 2 decimal places precision for display consistency
            student_result['overall_percentage'] = round(student_result['overall_percentage'], 2)
            
            # Add course outcome scores
            for co in course_outcomes:
                co_score = student_data.get('course_outcomes', {}).get(co.id)
                if co_score is not None:
                    student_result['course_outcomes'][co.code] = float(co_score)
                else:
                    student_result['course_outcomes'][co.code] = 0
        
        # Add exam scores for this student
        for exam in regular_exams:
            exam_score = 0
            used_makeup = False
            makeup_exam_id = None
            
            # Check if there's a makeup for this exam and if student attended it
            if exam.id in makeup_map:
                makeup_exam = makeup_map[exam.id]
                makeup_attended = attendance_dict.get((student.id, makeup_exam.id), True)
                
                # If student attended the makeup, use that score
                if makeup_attended:
                    used_makeup = True
                    makeup_exam_id = makeup_exam.id
                    
                    # Calculate makeup exam score
                    if makeup_exam.id in makeup_scores_dict and student.id in makeup_scores_dict[makeup_exam.id]:
                        raw_score = float(makeup_scores_dict[makeup_exam.id][student.id])
                        max_score = exam_max_scores[makeup_exam.id]
                        if max_score > 0:
                            exam_score = (raw_score / max_score) * 100
            
            # If not using makeup, use regular exam score
            if not used_makeup:
                if exam.id in exam_scores_dict and student.id in exam_scores_dict[exam.id]:
                    raw_score = float(exam_scores_dict[exam.id][student.id])
                    max_score = exam_max_scores[exam.id]
                    if max_score > 0:
                        exam_score = (raw_score / max_score) * 100
            
            # Add exam score with info about whether it's from makeup
            student_result['exam_scores'][exam.name] = {
                'score': exam_score,
                'from_makeup': used_makeup,
                'makeup_exam_id': makeup_exam_id
            }
        
        # Add missing_mandatory flag if present in student data
        if student_data.get('missing_mandatory', False):
            student_result['missing_mandatory'] = True
        
        # Add to the student_results dictionary
        student_results[student.id] = student_result
    
    # Log the successful calculation
    log = Log(action="COURSE_CALCULATIONS", 
             description=f"Calculated results for course: {course.code}")
    db.session.add(log)
    db.session.commit()
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'student_results': student_results,
            'course_outcome_results': course_outcome_results,
            'program_outcome_results': program_outcome_results
        })
    
    # Render the template with all the data
    return render_template('calculation/results.html',
                          course=course,
                          exams=regular_exams,
                          makeup_exams=makeup_map,
                          course_outcomes=course_outcomes,
                          program_outcomes=program_outcomes,
                          students=students_dict,
                          student_results=student_results,
                          program_outcome_results=program_outcome_results,
                          course_outcome_results=course_outcome_results,
                          achievement_levels=achievement_levels,
                          has_course_outcomes=len(course_outcomes) > 0,
                          has_exam_questions=True,
                          has_student_scores=True,
                          has_valid_weights=True,
                          is_excluded=False,
                          total_weight_percent=total_weight_percent,
                          exam_weights=exam_weights,
                          get_achievement_level=get_achievement_level,
                          active_page='courses')

@calculation_bp.route('/course/<int:course_id>/export')
def export_results(course_id):
    """Export calculation results to CSV in Excel-compatible format"""
    course = Course.query.get_or_404(course_id)
    
    # Get sorting parameters from query string
    sort_by = request.args.get('sort_by', '')
    sort_direction = request.args.get('sort_direction', 'asc')
    
    # Get regular and makeup exams separately
    regular_exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).order_by(Exam.created_at).all()
    makeup_exams = Exam.query.filter_by(course_id=course_id, is_makeup=True).order_by(Exam.created_at).all()
    
    # Create a map from original exam to makeup exam
    makeup_map = {}
    for makeup in makeup_exams:
        if makeup.makeup_for:
            makeup_map[makeup.makeup_for] = makeup
    
    # Combined list of all exams (for certain operations)
    all_exams = regular_exams + makeup_exams
    
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()
    
    # Define outcome_questions variable that maps each course outcome's ID to its list of questions
    outcome_questions = {co.id: co.questions for co in course_outcomes}
    
    # Get achievement levels
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    students = Student.query.filter_by(course_id=course_id)
    
    # Apply sorting based on parameters
    if sort_by == 'student_id':
        students = students.order_by(Student.student_id.asc() if sort_direction == 'asc' else Student.student_id.desc())
    elif sort_by == 'name':
        students = students.order_by(
            Student.first_name.asc() if sort_direction == 'asc' else Student.first_name.desc(),
            Student.last_name.asc() if sort_direction == 'asc' else Student.last_name.desc()
        )
    else:
        # Default sort by student_id
        students = students.order_by(Student.student_id)
        
    students = students.all()
    
    # Get exam weights
    weights = {}
    for exam in regular_exams:
        weight = ExamWeight.query.filter_by(exam_id=exam.id).first()
        if weight:
            weights[exam.id] = weight.weight
        else:
            weights[exam.id] = Decimal('0')
    
    # Create a map of exams to their questions
    questions_by_exam = {}
    for exam in all_exams:
        questions_by_exam[exam.id] = exam.questions
    
    # Preload all scores
    scores_dict = {}
    student_ids = [s.id for s in students]
    exam_ids = [e.id for e in all_exams]
    
    if student_ids and exam_ids:
        scores = Score.query.filter(
            Score.student_id.in_(student_ids),
            Score.exam_id.in_(exam_ids)
        ).all()
        
        for score in scores:
            key = (score.student_id, score.question_id, score.exam_id)
            scores_dict[key] = score.score
    
    # Preload attendance information
    attendance_dict = {}
    if student_ids and exam_ids:
        attendances = StudentExamAttendance.query.filter(
            StudentExamAttendance.student_id.in_(student_ids),
            StudentExamAttendance.exam_id.in_(exam_ids)
        ).all()
        
        for attendance in attendances:
            attendance_dict[(attendance.student_id, attendance.exam_id)] = attendance.attended
    
    # Define CSV headers
    headers = ['Student ID', 'Student Name']
    
    # Add exam score headers
    for exam in regular_exams:
        headers.append(f'{exam.name} Score (%)')
    
    # Add course outcome headers
    for co in course_outcomes:
        headers.append(f'{co.code} Achievement (%)')
    
    # Add overall percentage header
    headers.append('Overall Weighted Score (%)')
    headers.append('Achievement Level')
    
    # Get display method from course settings
    settings = CourseSettings.query.filter_by(course_id=course_id).first()
    display_method = settings.success_rate_method if settings else 'absolute'
    
    # Calculate normalized weights for use in outcome calculations
    total_weight = Decimal('0')
    for weight in weights.values():
        total_weight += weight
    
    normalized_weights = {}
    for exam_id, weight in weights.items():
        if total_weight > Decimal('0'):
            normalized_weights[exam_id] = weight / total_weight
        else:
            normalized_weights[exam_id] = weight
    
    # Add student data rows
    data = []
    for student in students:
        # Skip excluded students
        student_data = {}
        attendances_count = StudentExamAttendance.query.filter_by(student_id=student.id).count()
        
        # Check if student should be skipped (similar to course_calculations logic)
        should_skip = False
        if student.excluded:
            should_skip = True
        elif course.settings and course.settings.excluded:
            should_skip = True
        
        if should_skip:
            continue
            
        # Create a map to track which exams have scores for this student
        student_exam_scores = {}
        for exam in all_exams:
            has_scores = False
            for question in questions_by_exam[exam.id]:
                if (student.id, question.id, exam.id) in scores_dict:
                    has_scores = True
                    break
            if has_scores:
                student_exam_scores[exam.id] = True
        
        # Use the headers list to ensure we maintain the correct order
        student_row = [""] * len(headers)
        
        # Set the student info
        student_row[0] = student.student_id
        student_row[1] = f"{student.first_name} {student.last_name}".strip()
        
        # Calculate weighted score
        weighted_score = Decimal('0')
        total_weight_used = Decimal('0')
        
        # Add exam scores
        exam_index_map = {}
        for i, header in enumerate(headers):
            for exam in regular_exams:
                if header == f'{exam.name} Score (%)':
                    exam_index_map[exam.id] = i
        
        for exam in regular_exams:
            idx = exam_index_map.get(exam.id)
            if idx is None:
                continue  # Skip if the exam isn't in headers
                
            # Check if this exam has a makeup and if the student took the makeup
            use_makeup = False
            actual_exam_id = exam.id
            
            if exam.id in makeup_map:
                makeup_exam = makeup_map[exam.id]
                if makeup_exam.id in student_exam_scores:
                    use_makeup = True
                    actual_exam_id = makeup_exam.id
            
            # Use the proper exam score (original or makeup)
            if use_makeup:
                exam_score = calculate_student_exam_score_optimized(student.id, actual_exam_id, scores_dict, questions_by_exam[actual_exam_id], attendance_dict)
                if exam_score is not None:
                    # Ensure consistent Decimal conversion
                    exam_score = Decimal(str(exam_score))
                    student_row[idx] = round(float(exam_score), 2)
                    
                    # Add to weighted score if weight exists
                    if exam.id in weights:
                        weighted_score += exam_score * weights[exam.id]
                        total_weight_used += weights[exam.id]
                    continue
            
            # Otherwise use regular exam score
            exam_score = calculate_student_exam_score_optimized(
                student.id, exam.id, scores_dict,
                questions_by_exam[exam.id], attendance_dict
            )
            if exam_score is not None:
                # Ensure consistent Decimal conversion
                exam_score = Decimal(str(exam_score))
                student_row[idx] = round(float(exam_score), 2)
                
                # Add to weighted score if weight exists
                if exam.id in weights:
                    weighted_score += exam_score * weights[exam.id]
                    total_weight_used += weights[exam.id]
        
        # Calculate and add course outcome scores
        co_index_map = {}
        for i, header in enumerate(headers):
            for co in course_outcomes:
                if header == f'{co.code} Achievement (%)':
                    co_index_map[co.id] = i
        
        for co in course_outcomes:
            idx = co_index_map.get(co.id)
            if idx is None:
                continue  # Skip if the outcome isn't in headers
            
            # Calculate course outcome achievement
            co_score = calculate_course_outcome_score_optimized(
                student.id, co.id, scores_dict, outcome_questions, normalized_weights
            )
            
            if co_score is not None:
                # Add score and achievement level
                student_row[idx] = round(float(co_score), 2)
        
        # Calculate and add overall weighted score
        if total_weight_used > Decimal('0'):
            overall_percentage = weighted_score / total_weight_used
            # Set overall percentage in the last column with 2 decimal places precision
            student_row[-2] = round(float(overall_percentage), 2)
            
            # Get and add achievement level
            level = get_achievement_level(float(overall_percentage), achievement_levels)
            student_row[-1] = level['name']
            
            # Store for potential sorting
            student_data = {
                'student_id': student.student_id,
                'name': f"{student.first_name} {student.last_name}".strip(),
                'row': student_row,
                'overall_score': float(overall_percentage)
            }
            data.append(student_data)
    
    # Sort by overall_score if requested
    if sort_by == 'overall_score':
        data.sort(key=lambda x: x['overall_score'], reverse=(sort_direction == 'desc'))
    
    # Extract just the row data for CSV
    csv_data = [d['row'] for d in data]
    
    # Log action
    log = Log(action="EXPORT_COURSE_RESULTS", 
             description=f"Exported calculation results for course: {course.code}")
    db.session.add(log)
    db.session.commit()
    
    # Convert data to CSV
    return export_to_excel_csv(csv_data, f"results_{course.code}", headers)

@calculation_bp.route('/course/<int:course_id>/export_program_outcomes')
def export_program_outcomes_achievement(course_id):
    """Export program outcomes achievement data to CSV"""
    course = Course.query.get_or_404(course_id)
    
    # Get program outcomes
    program_outcomes = ProgramOutcome.query.order_by(ProgramOutcome.code).all()
    
    # Get course outcomes for associations
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()
    
    # Get achievement levels
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    # Calculate the results using the existing calculation function
    settings = CourseSettings.query.filter_by(course_id=course_id).first()
    display_method = settings.success_rate_method if settings else 'absolute'
    results = calculate_single_course_results(course_id, display_method)
    
    if not results['is_valid_for_aggregation']:
        flash('Cannot export: Insufficient data to calculate results.', 'warning')
        return redirect(url_for('calculation.course_calculations', course_id=course_id))
    
    # Format program outcome results
    program_outcome_results = {}
    for po in program_outcomes:
        po_score = results['program_outcome_scores'].get(po.id, Decimal('0'))
        
        # Get related course outcome codes for this program outcome
        related_course_outcomes = []
        for co in course_outcomes:
            if po in co.program_outcomes:
                related_course_outcomes.append(co.code)
        
        program_outcome_results[po.code] = {
            'description': po.description,
            'percentage': po_score,
            'course_outcomes': related_course_outcomes,
            'level': get_achievement_level(float(po_score), achievement_levels)
        }
    
    # Prepare data for export
    headers = ['Program Outcome Code', 'Description', 'Achievement Percentage', 'Achievement Level', 'Related Course Outcomes']
    csv_data = []
    
    for po_code, po_data in program_outcome_results.items():
        related_cos = ', '.join(po_data['course_outcomes']) if po_data['course_outcomes'] else 'None'
        achievement_level = po_data['level']['name']
        
        csv_data.append([
            po_code,
            po_data['description'],
            f"{float(po_data['percentage']):.2f}%",
            achievement_level,
            related_cos
        ])
    
    # Log action
    log = Log(action="EXPORT_PROGRAM_OUTCOMES_ACHIEVEMENT", 
             description=f"Exported program outcome achievement data for course: {course.code}")
    db.session.add(log)
    db.session.commit()
    
    # Convert data to CSV
    return export_to_excel_csv(csv_data, f"program_outcomes_achievement_{course.code}", headers)

@calculation_bp.route('/course/<int:course_id>/export_course_outcomes')
def export_course_outcomes_achievement(course_id):
    """Export course outcomes achievement data to CSV"""
    course = Course.query.get_or_404(course_id)
    
    # Get course outcomes
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()
    
    # Get achievement levels
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    # Calculate the results using the existing calculation function
    settings = CourseSettings.query.filter_by(course_id=course_id).first()
    display_method = settings.success_rate_method if settings else 'absolute'
    results = calculate_single_course_results(course_id, display_method)
    
    if not results['is_valid_for_aggregation']:
        flash('Cannot export: Insufficient data to calculate results.', 'warning')
        return redirect(url_for('calculation.course_calculations', course_id=course_id))
    
    # Format course outcome results for export
    course_outcome_results = {}
    
    for outcome in course_outcomes:
        # Get score from results
        co_score = results['course_outcome_scores'].get(outcome.id, Decimal('0'))
        
        # Get related program outcomes
        related_pos = [po.code for po in outcome.program_outcomes]
        
        # Store in results dictionary
        course_outcome_results[outcome.code] = {
            'description': outcome.description,
            'percentage': co_score,
            'program_outcomes': related_pos,
            'level': get_achievement_level(float(co_score), achievement_levels)
        }
    
    # Prepare data for export
    headers = ['Course Outcome Code', 'Description', 'Achievement Percentage', 'Achievement Level', 'Related Program Outcomes']
    csv_data = []
    
    for co_code, co_data in course_outcome_results.items():
        related_pos = ', '.join(co_data['program_outcomes']) if co_data['program_outcomes'] else 'None'
        achievement_level = co_data['level']['name']
        
        csv_data.append([
            co_code,
            co_data['description'],
            f"{float(co_data['percentage']):.2f}%",
            achievement_level,
            related_pos
        ])
    
    # Log action
    log = Log(action="EXPORT_COURSE_OUTCOMES_ACHIEVEMENT", 
             description=f"Exported course outcome achievement data for course: {course.code}")
    db.session.add(log)
    db.session.commit()
    
    # Convert data to CSV
    return export_to_excel_csv(csv_data, f"course_outcomes_achievement_{course.code}", headers)

def bulk_load_course_data(course_ids, display_method='absolute'):
    """
    Bulk load all data needed for multiple course calculations in a single set of queries.
    This eliminates the N+1 query problem by loading everything upfront.
    
    Args:
        course_ids: List of course IDs to load data for
        display_method: Calculation method ('absolute' or 'relative')
    
    Returns:
        Dictionary containing all bulk-loaded data organized by course_id
    """
    if not course_ids:
        return {}
    
    # ==== BULK LOAD ALL DATA IN SINGLE QUERIES ====
    
    # 1. Load all courses with their settings in one query
    courses_query = Course.query.filter(Course.id.in_(course_ids))
    courses = {c.id: c for c in courses_query.all()}
    
    # 2. Load all course settings
    settings_query = CourseSettings.query.filter(CourseSettings.course_id.in_(course_ids))
    settings_dict = {s.course_id: s for s in settings_query.all()}
    
    # 3. Load all exams for these courses
    exams_query = Exam.query.filter(Exam.course_id.in_(course_ids))
    all_exams = exams_query.all()
    exams_by_course = {}
    exam_ids = []
    for exam in all_exams:
        if exam.course_id not in exams_by_course:
            exams_by_course[exam.course_id] = {'regular': [], 'makeup': []}
        
        if exam.is_makeup:
            exams_by_course[exam.course_id]['makeup'].append(exam)
        else:
            exams_by_course[exam.course_id]['regular'].append(exam)
        exam_ids.append(exam.id)
    
    # 4. Load all course outcomes for these courses
    outcomes_query = CourseOutcome.query.filter(CourseOutcome.course_id.in_(course_ids))
    all_course_outcomes = outcomes_query.all()
    outcomes_by_course = {}
    outcome_ids = []
    for outcome in all_course_outcomes:
        if outcome.course_id not in outcomes_by_course:
            outcomes_by_course[outcome.course_id] = []
        outcomes_by_course[outcome.course_id].append(outcome)
        outcome_ids.append(outcome.id)
    
    # 5. Load all students for these courses
    students_query = Student.query.filter(Student.course_id.in_(course_ids))
    all_students = students_query.all()
    students_by_course = {}
    student_ids = []
    for student in all_students:
        if student.course_id not in students_by_course:
            students_by_course[student.course_id] = []
        students_by_course[student.course_id].append(student)
        student_ids.append(student.id)
    
    # 6. Load all exam weights for these courses
    weights_query = ExamWeight.query.filter(ExamWeight.course_id.in_(course_ids))
    all_weights = weights_query.all()
    weights_by_course = {}
    for weight in all_weights:
        if weight.course_id not in weights_by_course:
            weights_by_course[weight.course_id] = {}
        weights_by_course[weight.course_id][weight.exam_id] = weight.weight
    
    # 7. Load all questions for all exams
    questions_query = Question.query.filter(Question.exam_id.in_(exam_ids)) if exam_ids else []
    all_questions = questions_query.all() if exam_ids else []
    questions_by_exam = {}
    question_ids = []
    for question in all_questions:
        if question.exam_id not in questions_by_exam:
            questions_by_exam[question.exam_id] = []
        questions_by_exam[question.exam_id].append(question)
        question_ids.append(question.id)
    
    # 8. Load all scores for all students and questions
    scores_dict = {}
    if student_ids and exam_ids:
        scores_query = Score.query.filter(
            Score.student_id.in_(student_ids),
            Score.exam_id.in_(exam_ids)
        )
        all_scores = scores_query.all()
        for score in all_scores:
            scores_dict[(score.student_id, score.question_id, score.exam_id)] = score.score
    
    # 9. Load all attendance records
    attendance_dict = {}
    if student_ids and exam_ids:
        attendance_query = StudentExamAttendance.query.filter(
            StudentExamAttendance.student_id.in_(student_ids),
            StudentExamAttendance.exam_id.in_(exam_ids)
        )
        all_attendances = attendance_query.all()
        for attendance in all_attendances:
            attendance_dict[(attendance.student_id, attendance.exam_id)] = attendance.attended
    
    # 10. Load program outcomes and their relationships
    # Get all program outcomes related to these course outcomes
    if outcome_ids:
        from sqlalchemy import text
        # Query the association table to get program outcome relationships
        placeholders = ','.join(str(id) for id in outcome_ids)
        po_relationships = db.session.execute(
            text(f"SELECT course_outcome_id, program_outcome_id FROM course_outcome_program_outcome WHERE course_outcome_id IN ({placeholders})")
        ).fetchall()
        
        # Get unique program outcome IDs
        po_ids = list(set(rel[1] for rel in po_relationships))
        
        # Load program outcomes
        program_outcomes_query = ProgramOutcome.query.filter(ProgramOutcome.id.in_(po_ids)) if po_ids else []
        program_outcomes = program_outcomes_query.all() if po_ids else []
        program_outcomes_dict = {po.id: po for po in program_outcomes}
        
        # Build program outcome relationships by course
        po_relationships_by_course = {}
        for course_id in course_ids:
            course_outcomes = outcomes_by_course.get(course_id, [])
            course_po_ids = set()
            for co in course_outcomes:
                for rel in po_relationships:
                    if rel[0] == co.id:
                        course_po_ids.add(rel[1])
            po_relationships_by_course[course_id] = course_po_ids
    else:
        program_outcomes = []
        program_outcomes_dict = {}
        po_relationships_by_course = {}
    
    # 11. Load question-course outcome relationships
    question_outcome_map = {}
    if question_ids and outcome_ids:
        q_placeholders = ','.join(str(id) for id in question_ids)
        co_placeholders = ','.join(str(id) for id in outcome_ids)
        qco_relationships = db.session.execute(
            text(f"SELECT question_id, course_outcome_id FROM question_course_outcome WHERE question_id IN ({q_placeholders}) AND course_outcome_id IN ({co_placeholders})")
        ).fetchall()
        
        for rel in qco_relationships:
            question_id, outcome_id = rel
            if outcome_id not in question_outcome_map:
                question_outcome_map[outcome_id] = []
            question_outcome_map[outcome_id].append(question_id)
    
    # ==== ORGANIZE DATA BY COURSE ====
    
    bulk_data = {}
    for course_id in course_ids:
        course = courses.get(course_id)
        if not course:
            continue
            
        # Get or create settings
        settings = settings_dict.get(course_id)
        if not settings:
            settings = CourseSettings(
                course_id=course_id,
                success_rate_method=display_method,
                relative_success_threshold=60.0
            )
        
        # Organize exam data
        course_exams = exams_by_course.get(course_id, {'regular': [], 'makeup': []})
        regular_exams = course_exams['regular']
        makeup_exams = course_exams['makeup']
        
        # Organize questions by exam for this course
        course_questions_by_exam = {}
        for exam in regular_exams + makeup_exams:
            course_questions_by_exam[exam.id] = questions_by_exam.get(exam.id, [])
        
        # Organize outcome questions for this course
        course_outcomes = outcomes_by_course.get(course_id, [])
        outcome_questions = {}
        for outcome in course_outcomes:
            related_question_ids = question_outcome_map.get(outcome.id, [])
            related_questions = []
            for q_id in related_question_ids:
                for exam_questions in course_questions_by_exam.values():
                    for question in exam_questions:
                        if question.id == q_id:
                            related_questions.append(question)
                            break
            outcome_questions[outcome.id] = related_questions
        
        # Calculate normalized weights
        course_weights = weights_by_course.get(course_id, {})
        total_weight = sum(course_weights.values())
        normalized_weights = {}
        if total_weight > 0:
            for exam_id, weight in course_weights.items():
                normalized_weights[exam_id] = weight / total_weight
        else:
            # Equal weights if no weights defined
            if regular_exams:
                equal_weight = Decimal('1') / Decimal(str(len(regular_exams)))
                for exam in regular_exams:
                    normalized_weights[exam.id] = equal_weight
        
        # Get program outcomes for this course
        course_po_ids = po_relationships_by_course.get(course_id, set())
        course_program_outcomes = [program_outcomes_dict[po_id] for po_id in course_po_ids if po_id in program_outcomes_dict]
        
        # Build program outcome to course outcome mapping
        program_to_course_outcomes = {}
        for po in course_program_outcomes:
            related_cos = []
            for co in course_outcomes:
                # Check if this CO is related to this PO using the pre-loaded relationships
                for rel in po_relationships:
                    if rel[0] == co.id and rel[1] == po.id:
                        related_cos.append(co)
                        break
            program_to_course_outcomes[po.id] = related_cos
        
        # Create makeup mapping
        makeup_map = {}
        for makeup in makeup_exams:
            if makeup.makeup_for:
                makeup_map[makeup.makeup_for] = makeup
        
        bulk_data[course_id] = {
            'course': course,
            'settings': settings,
            'regular_exams': regular_exams,
            'makeup_exams': makeup_exams,
            'all_exams': regular_exams + makeup_exams,
            'course_outcomes': course_outcomes,
            'program_outcomes': course_program_outcomes,
            'students': students_by_course.get(course_id, []),
            'questions_by_exam': course_questions_by_exam,
            'outcome_questions': outcome_questions,
            'normalized_weights': normalized_weights,
            'program_to_course_outcomes': program_to_course_outcomes,
            'makeup_map': makeup_map,
            'contributing_po_ids': course_po_ids,
            # Pre-filtered data for this course
            'scores_dict': {k: v for k, v in scores_dict.items() if any(s.id == k[0] for s in students_by_course.get(course_id, []))},
            'attendance_dict': {k: v for k, v in attendance_dict.items() if any(s.id == k[0] for s in students_by_course.get(course_id, []))}
        }
    
    return bulk_data

def calculate_course_results_from_bulk_data_v2_optimized(course_id, bulk_data, calculation_method='absolute'):
    """
    STEP 2.2: ADVANCED ALGORITHM OPTIMIZATIONS
    
    Further optimizations beyond Step 2.1:
    1. Minimize function call overhead by inlining critical calculations
    2. Use more efficient data structures and access patterns
    3. Optimize hot loops with pre-calculated indices and reduced lookups
    4. Implement early exit strategies for better worst-case performance
    5. Cache frequently accessed values at the function level
    
    Expected additional 15-25% performance improvement over Step 2.1
    """
    course_data = bulk_data.get(course_id)
    if not course_data:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': None
        }
    
    course = course_data['course']
    settings = course_data['settings']
    
    # Early exit for excluded courses
    if settings.excluded:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Extract and cache frequently accessed data
    regular_exams = course_data['regular_exams']
    course_outcomes = course_data['course_outcomes']
    program_outcomes = course_data['program_outcomes']
    students = course_data['students']
    questions_by_exam = course_data['questions_by_exam']
    outcome_questions = course_data['outcome_questions']
    normalized_weights = course_data['normalized_weights']
    program_to_course_outcomes = course_data['program_to_course_outcomes']
    makeup_map = course_data['makeup_map']
    scores_dict = course_data['scores_dict']
    attendance_dict = course_data['attendance_dict']
    contributing_po_ids = course_data['contributing_po_ids']
    
    # Early validation with fast exits
    if not course_outcomes or not students:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Check exam questions availability (optimized)
    total_questions = sum(len(questions) for questions in questions_by_exam.values())
    if total_questions == 0:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # ===== ADVANCED PRE-COMPUTATION PHASE =====
    
    # Pre-compute all exam-related data in a single pass
    mandatory_exam_ids = set()
    exam_info_cache = {}
    
    for exam in regular_exams:
        exam_id = exam.id
        exam_info = {
            'is_mandatory': exam.is_mandatory,
            'weight': normalized_weights.get(exam_id, Decimal('0')),
            'questions': questions_by_exam.get(exam_id, []),
            'makeup_exam_id': makeup_map.get(exam_id, {}).id if makeup_map.get(exam_id) else None
        }
        
        if exam.is_mandatory:
            mandatory_exam_ids.add(exam_id)
            
        exam_info_cache[exam_id] = exam_info
    
    # Pre-compute question totals for efficiency (avoid repeated calculations)
    question_totals_cache = {}
    for exam_id, questions in questions_by_exam.items():
        total_possible = sum(q.max_score for q in questions)
        question_totals_cache[exam_id] = {
            'total_possible': total_possible,
            'question_ids': [q.id for q in questions]
        }
    
    # Pre-compute attendance lookups for all students and exams (batch operation)
    student_attendance_cache = {}
    for student in students:
        student_id = student.id
        student_attendance_cache[student_id] = {}
        
        for exam_id in exam_info_cache.keys():
            student_attendance_cache[student_id][exam_id] = attendance_dict.get((student_id, exam_id), True)
            
            # Also pre-compute makeup attendance if exists
            makeup_exam_id = exam_info_cache[exam_id].get('makeup_exam_id')
            if makeup_exam_id:
                student_attendance_cache[student_id][makeup_exam_id] = attendance_dict.get((student_id, makeup_exam_id), True)
    
    # Pre-compute threshold conversion
    threshold = Decimal(str(settings.relative_success_threshold))
    
    # ===== OPTIMIZED STUDENT FILTERING PHASE =====
    
    valid_students = []
    
    # Use list comprehension with early exits for maximum efficiency
    for student in students:
        student_id = student.id
        
        # Quick exclusion check
        if getattr(student, 'excluded', False):
            continue
        
        # Optimized mandatory exam check using pre-computed cache
        if mandatory_exam_ids:
            attendance_cache = student_attendance_cache[student_id]
            skip_student = False
            
            for exam_id in mandatory_exam_ids:
                regular_attended = attendance_cache[exam_id]
                makeup_exam_id = exam_info_cache[exam_id].get('makeup_exam_id')
                makeup_attended = attendance_cache.get(makeup_exam_id, False) if makeup_exam_id else False
                
                if not regular_attended and not makeup_attended:
                    skip_student = True
                    break
            
            if skip_student:
                continue
        
        valid_students.append(student)
    
    if not valid_students:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # ===== VECTORIZED SCORE CALCULATION PHASE =====
    
    # Pre-allocate result containers for better memory performance
    num_students = len(valid_students)
    num_outcomes = len(course_outcomes)
    num_pos = len(program_outcomes)
    
    # Use more efficient data structures
    student_weighted_scores = {}
    student_outcome_scores = {}
    student_po_scores = {}
    
    # Pre-create dictionaries to avoid repeated allocation
    for student in valid_students:
        student_id = student.id
        student_weighted_scores[student_id] = Decimal('0')
        student_outcome_scores[student_id] = {}
        student_po_scores[student_id] = {}
    
    # ===== OPTIMIZED EXAM SCORE CALCULATION =====
    
    # Calculate all exam scores in a single optimized loop
    for student in valid_students:
        student_id = student.id
        total_weighted_score = Decimal('0')
        attendance_cache = student_attendance_cache[student_id]
        
        # Process exams with minimal function call overhead
        for exam_id, info in exam_info_cache.items():
            weight = info['weight']
            questions = info['questions']
            makeup_exam_id = info.get('makeup_exam_id')
            
            # Inline score calculation to reduce function call overhead
            exam_score = None
            
            # Check makeup first (optimized path)
            if makeup_exam_id and attendance_cache.get(makeup_exam_id, False):
                # Use makeup exam
                makeup_questions = questions_by_exam.get(makeup_exam_id, [])
                if makeup_questions:
                    exam_score = calculate_inline_exam_score(
                        student_id, makeup_exam_id, scores_dict, makeup_questions, 
                        question_totals_cache.get(makeup_exam_id, {'total_possible': Decimal('0')})['total_possible']
                    )
            else:
                # Use regular exam
                if questions and attendance_cache.get(exam_id, True):
                    exam_score = calculate_inline_exam_score(
                        student_id, exam_id, scores_dict, questions,
                        question_totals_cache[exam_id]['total_possible']
                    )
                elif not info['is_mandatory']:
                    # Non-mandatory exam with no attendance = 0
                    exam_score = Decimal('0')
            
            # Add weighted score
            if exam_score is not None:
                total_weighted_score += exam_score * weight
        
        student_weighted_scores[student_id] = total_weighted_score
    
    # ===== OPTIMIZED OUTCOME SCORE CALCULATION =====
    
    # Calculate course outcome scores with reduced overhead
    for student in valid_students:
        student_id = student.id
        
        for outcome in course_outcomes:
            outcome_id = outcome.id
            
            # Use optimized course outcome calculation
            co_score = calculate_course_outcome_score_optimized(
                student_id, outcome_id, scores_dict, outcome_questions, 
                normalized_weights, attendance_dict
            )
            student_outcome_scores[student_id][outcome_id] = co_score
    
    # Calculate program outcome scores with reduced overhead
    for student in valid_students:
        student_id = student.id
        
        for po in program_outcomes:
            po_id = po.id
            
            # Use optimized program outcome calculation
            po_score = calculate_program_outcome_score_optimized(
                student_id, po_id, course_id, scores_dict,
                program_to_course_outcomes, outcome_questions, 
                normalized_weights, attendance_dict
            )
            student_po_scores[student_id][po_id] = po_score
    
    # ===== OPTIMIZED AGGREGATION PHASE =====
    
    total_valid_students = num_students
    program_outcome_scores = {}
    
    if calculation_method == 'relative':
        # Vectorized relative calculation
        for po in program_outcomes:
            po_id = po.id
            
            # Collect all valid scores in a single pass
            scores = []
            for student in valid_students:
                score = student_po_scores[student.id].get(po_id)
                if score is not None:
                    scores.append(score)
            
            if scores:
                # Vectorized threshold comparison
                meeting_threshold = sum(1 for score in scores if score >= threshold)
                program_outcome_scores[po_id] = (meeting_threshold / len(scores)) * 100
            else:
                program_outcome_scores[po_id] = 0
    else:
        # Vectorized absolute calculation
        for po in program_outcomes:
            po_id = po.id
            
            # Collect and sum scores in a single pass
            scores = []
            for student in valid_students:
                score = student_po_scores[student.id].get(po_id)
                if score is not None:
                    scores.append(Decimal(str(score)))
            
            if scores:
                # Use built-in sum for optimal performance
                avg_score = sum(scores) / len(scores)
                program_outcome_scores[po_id] = float(avg_score)
            else:
                program_outcome_scores[po_id] = 0
    
    # Final validation
    is_valid_for_aggregation = (
        total_valid_students > 0 and
        program_outcome_scores and
        any(score > 0 for score in program_outcome_scores.values())
    )
    
    return {
        'program_outcome_scores': program_outcome_scores,
        'contributing_po_ids': contributing_po_ids,
        'is_valid_for_aggregation': is_valid_for_aggregation,
        'student_count_used': total_valid_students,
        'course': course
    }

def calculate_course_results_with_graduating_filter(course_id, bulk_data, calculation_method='absolute', include_graduating_only=False):
    """
    Calculate course results with graduating students filter applied.
    This function modifies the student list to only include graduating students
    before performing the calculations, ensuring accurate results when filtering.
    
    Parameters:
    - course_id: The course ID to calculate
    - bulk_data: Pre-loaded bulk data
    - calculation_method: 'absolute' or 'relative'
    - include_graduating_only: If True, only include graduating students in calculations
    
    Returns:
    - Same format as calculate_course_results_from_bulk_data_v2_optimized
    """
    course_data = bulk_data.get(course_id)
    if not course_data:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': None
        }
    
    course = course_data['course']
    settings = course_data['settings']
    
    # Early exit for excluded courses
    if settings.excluded:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Extract and cache frequently accessed data
    regular_exams = course_data['regular_exams']
    course_outcomes = course_data['course_outcomes']
    program_outcomes = course_data['program_outcomes']
    all_students = course_data['students']  # Original student list
    questions_by_exam = course_data['questions_by_exam']
    outcome_questions = course_data['outcome_questions']
    normalized_weights = course_data['normalized_weights']
    program_to_course_outcomes = course_data['program_to_course_outcomes']
    makeup_map = course_data['makeup_map']
    scores_dict = course_data['scores_dict']
    attendance_dict = course_data['attendance_dict']
    contributing_po_ids = course_data['contributing_po_ids']
    
    # CRITICAL FIX: Filter students to only include graduating students
    if include_graduating_only:
        graduating_student_ids = get_graduating_student_ids()
        students = [student for student in all_students 
                   if student.student_id in graduating_student_ids]
        
        # If no graduating students in this course, return empty result
        if not students:
            return {
                'program_outcome_scores': {},
                'contributing_po_ids': contributing_po_ids,
                'is_valid_for_aggregation': False,
                'student_count_used': 0,
                'course': course
            }
    else:
        students = all_students
    
    # Early validation with fast exits
    if not course_outcomes or not students:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Check exam questions availability
    total_questions = sum(len(questions) for questions in questions_by_exam.values())
    if total_questions == 0:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Pre-compute mandatory exam IDs
    mandatory_exam_ids = set()
    for exam in regular_exams:
        if exam.is_mandatory:
            mandatory_exam_ids.add(exam.id)
    
    # Filter valid students (those who attended mandatory exams)
    valid_students = []
    for student in students:  # Use filtered student list
        student_id = student.id
        
        # Quick exclusion check
        if getattr(student, 'excluded', False):
            continue
        
        # Check mandatory exam attendance
        if mandatory_exam_ids:
            skip_student = False
            for exam_id in mandatory_exam_ids:
                regular_attended = attendance_dict.get((student_id, exam_id), True)
                
                # Check if there's a makeup exam for this exam
                makeup_exam = makeup_map.get(exam_id)
                makeup_attended = False
                if makeup_exam:
                    makeup_attended = attendance_dict.get((student_id, makeup_exam.id), False)
                
                if not regular_attended and not makeup_attended:
                    skip_student = True
                    break
            
            if skip_student:
                continue
        
        valid_students.append(student)
    
    if not valid_students:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Calculate program outcome scores for valid students
    program_outcome_scores = {}
    threshold = Decimal(str(settings.relative_success_threshold))
    
    for po in program_outcomes:
        po_id = po.id
        
        # Calculate scores for all valid students
        valid_scores = []
        for student in valid_students:
            po_score = calculate_program_outcome_score_optimized(
                student.id, po_id, course_id, scores_dict,
                program_to_course_outcomes, outcome_questions, 
                normalized_weights, attendance_dict
            )
            if po_score is not None:
                valid_scores.append(po_score)
        
        if valid_scores:
            if calculation_method == 'absolute':
                # For absolute method: average of all valid scores
                avg_score = sum(valid_scores) / len(valid_scores)
                program_outcome_scores[po_id] = avg_score
            else:  # 'relative'
                # For relative method: percentage meeting threshold
                success_count = sum(1 for score in valid_scores if score >= threshold)
                success_rate = (success_count / len(valid_scores) * 100) if valid_scores else 0
                program_outcome_scores[po_id] = Decimal(str(success_rate))
        else:
            program_outcome_scores[po_id] = Decimal('0')
    
    # Return the results
    return {
        'program_outcome_scores': program_outcome_scores,
        'course_outcome_scores': {},  # Not needed for aggregation
        'contributing_po_ids': contributing_po_ids,
        'is_valid_for_aggregation': True,
        'student_count_used': len(valid_students),
        'course': course,
        'student_results': {}  # Not needed for aggregation
    }

def calculate_inline_exam_score(student_id, exam_id, scores_dict, questions, total_possible):
    """
    Inline exam score calculation to reduce function call overhead.
    This is a performance-optimized version of calculate_student_exam_score_optimized.
    """
    if not questions or total_possible == Decimal('0'):
        return None
    
    total_score = Decimal('0')
    has_scores = False
    
    # Optimized score accumulation
    for question in questions:
        score_value = scores_dict.get((student_id, question.id, exam_id))
        if score_value is not None:
            has_scores = True
            total_score += Decimal(str(score_value))
    
    if not has_scores:
        return Decimal('0')
    
    return (total_score / total_possible) * Decimal('100')

def calculate_course_results_from_bulk_data_optimized(course_id, bulk_data, calculation_method='absolute'):
    """
    OPTIMIZED version: Pre-calculates static values and restructures calculation flow.
    
    Key optimizations:
    1. Pre-calculate all static values that don't change per student
    2. Restructure loops to minimize redundant calculations
    3. Use list comprehensions and built-in functions for better performance
    4. Minimize object creation and lookups in hot loops
    
    Args:
        course_id: The course ID to calculate
        bulk_data: Pre-loaded data from bulk_load_course_data()
        calculation_method: 'absolute' or 'relative'
    
    Returns:
        Same format as original but with optimized performance
    """
    course_data = bulk_data.get(course_id)
    if not course_data:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': None
        }
    
    course = course_data['course']
    settings = course_data['settings']
    
    # Check if course is excluded in settings
    if settings.excluded:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # ===== STEP 2.3: PRE-CALCULATE ALL STATIC VALUES =====
    
    # Extract pre-loaded data (avoid repeated dict lookups)
    regular_exams = course_data['regular_exams']
    makeup_exams = course_data['makeup_exams']
    course_outcomes = course_data['course_outcomes']
    program_outcomes = course_data['program_outcomes']
    students = course_data['students']
    questions_by_exam = course_data['questions_by_exam']
    outcome_questions = course_data['outcome_questions']
    normalized_weights = course_data['normalized_weights']
    program_to_course_outcomes = course_data['program_to_course_outcomes']
    makeup_map = course_data['makeup_map']
    scores_dict = course_data['scores_dict']
    attendance_dict = course_data['attendance_dict']
    contributing_po_ids = course_data['contributing_po_ids']
    
    # Early validation checks
    if not course_outcomes or not students:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Check if there are exam questions (pre-calculate once)
    has_exam_questions = any(len(questions) > 0 for questions in questions_by_exam.values())
    if not has_exam_questions:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Pre-calculate mandatory exam info (avoid repeated list comprehension)
    mandatory_exam_ids = {exam.id for exam in regular_exams if exam.is_mandatory}
    mandatory_exams_with_makeups = {}
    for exam_id in mandatory_exam_ids:
        mandatory_exams_with_makeups[exam_id] = makeup_map.get(exam_id)
    
    # Pre-calculate threshold for relative method (convert once)
    threshold = Decimal(str(settings.relative_success_threshold))
    
    # Pre-calculate exam processing order (avoid repeated logic)
    exam_processing_order = []
    for exam in regular_exams:
        makeup_exam = makeup_map.get(exam.id)
        exam_processing_order.append({
            'exam': exam,
            'exam_id': exam.id,
            'weight': normalized_weights.get(exam.id, Decimal('0')),
            'makeup_exam': makeup_exam,
            'makeup_exam_id': makeup_exam.id if makeup_exam else None,
            'questions': questions_by_exam.get(exam.id, []),
            'makeup_questions': questions_by_exam.get(makeup_exam.id, []) if makeup_exam else []
        })
    
    # Pre-calculate outcome processing info
    outcome_processing_info = []
    for outcome in course_outcomes:
        outcome_processing_info.append({
            'outcome': outcome,
            'outcome_id': outcome.id,
            'questions': outcome_questions.get(outcome.id, [])
        })
    
    # Pre-calculate program outcome processing info
    po_processing_info = []
    for po in program_outcomes:
        po_processing_info.append({
            'po': po,
            'po_id': po.id,
            'related_cos': program_to_course_outcomes.get(po.id, [])
        })
    
    # ===== STEP 2.1: RESTRUCTURED CALCULATION FLOW =====
    
    # Phase 1: Filter and process students efficiently
    valid_students = []
    excluded_students = []
    
    for student in students:
        student_id = student.id
        
        # Quick exclusion checks
        if getattr(student, 'excluded', False):
            excluded_students.append(student_id)
            continue
        
        # Mandatory exam attendance check (optimized)
        if mandatory_exam_ids:
            skip_student = False
            for exam_id, makeup_exam in mandatory_exams_with_makeups.items():
                regular_attended = attendance_dict.get((student_id, exam_id), True)
                makeup_attended = attendance_dict.get((student_id, makeup_exam.id), True) if makeup_exam else False
                
                if not regular_attended and not makeup_attended:
                    skip_student = True
                    break
            
            if skip_student:
                excluded_students.append(student_id)
                continue
        
        valid_students.append(student)
    
    if not valid_students:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Phase 2: Batch calculate all student scores (vectorized approach)
    student_weighted_scores = {}
    student_outcome_scores = {}
    student_po_scores = {}
    
    # Pre-allocate dictionaries for better performance
    for student in valid_students:
        student_id = student.id
        student_weighted_scores[student_id] = Decimal('0')
        student_outcome_scores[student_id] = {}
        student_po_scores[student_id] = {}
    
    # Calculate weighted exam scores in batch
    for student in valid_students:
        student_id = student.id
        total_weighted_score = Decimal('0')
        
        # Process exams using pre-calculated order
        for exam_info in exam_processing_order:
            exam_id = exam_info['exam_id']
            weight = exam_info['weight']
            makeup_exam_id = exam_info['makeup_exam_id']
            questions = exam_info['questions']
            makeup_questions = exam_info['makeup_questions']
            
            # Check makeup attendance first (more efficient)
            if makeup_exam_id:
                makeup_attended = attendance_dict.get((student_id, makeup_exam_id), True)
                if makeup_attended:
                    # Use makeup score
                    makeup_score = calculate_student_exam_score_optimized(
                        student_id, makeup_exam_id, scores_dict, makeup_questions, attendance_dict
                    )
                    score_to_use = makeup_score if makeup_score is not None else Decimal('0')
                    total_weighted_score += score_to_use * weight
                    continue
            
            # Use regular exam score
            exam_score = calculate_student_exam_score_optimized(
                student_id, exam_id, scores_dict, questions, attendance_dict
            )
            
            if exam_score is not None:
                total_weighted_score += exam_score * weight
            elif exam_id not in mandatory_exam_ids:
                # Non-mandatory exam with no score = 0
                total_weighted_score += Decimal('0') * weight
        
        student_weighted_scores[student_id] = total_weighted_score
    
    # Calculate course outcome scores in batch
    for student in valid_students:
        student_id = student.id
        
        for outcome_info in outcome_processing_info:
            outcome_id = outcome_info['outcome_id']
            questions = outcome_info['questions']
            
            co_score = calculate_course_outcome_score_optimized(
                student_id, outcome_id, scores_dict, outcome_questions, normalized_weights, attendance_dict
            )
            student_outcome_scores[student_id][outcome_id] = co_score
    
    # Calculate program outcome scores in batch
    for student in valid_students:
        student_id = student.id
        
        for po_info in po_processing_info:
            po_id = po_info['po_id']
            
            po_score = calculate_program_outcome_score_optimized(
                student_id, po_id, course_id, scores_dict, 
                program_to_course_outcomes, outcome_questions, normalized_weights, attendance_dict
            )
            student_po_scores[student_id][po_id] = po_score
    
    # Phase 3: Aggregate results efficiently using vectorized operations
    total_valid_students = len(valid_students)
    
    # Calculate final program outcome scores
    program_outcome_scores = {}
    
    if calculation_method == 'relative':
        # Relative method: percentage of students meeting threshold
        for po_info in po_processing_info:
            po_id = po_info['po_id']
            
            # Use list comprehension for efficient filtering and counting
            valid_scores = [student_po_scores[s.id][po_id] for s in valid_students 
                          if student_po_scores[s.id][po_id] is not None]
            
            if valid_scores:
                students_meeting_threshold = sum(1 for score in valid_scores if score >= threshold)
                program_outcome_scores[po_id] = (students_meeting_threshold / len(valid_scores)) * 100
            else:
                program_outcome_scores[po_id] = 0
    else:
        # Absolute method: average scores
        for po_info in po_processing_info:
            po_id = po_info['po_id']
            
            # Use list comprehension for efficient aggregation
            valid_scores = [student_po_scores[s.id][po_id] for s in valid_students 
                          if student_po_scores[s.id][po_id] is not None]
            
            if valid_scores:
                # Use built-in sum for better performance than manual accumulation
                avg_score = sum(Decimal(str(score)) for score in valid_scores) / len(valid_scores)
                program_outcome_scores[po_id] = float(avg_score)
            else:
                program_outcome_scores[po_id] = 0
    
    # Determine validity for aggregation
    is_valid_for_aggregation = (
        total_valid_students > 0 and
        program_outcome_scores and
        any(score > 0 for score in program_outcome_scores.values())
    )
    
    return {
        'program_outcome_scores': program_outcome_scores,
        'contributing_po_ids': contributing_po_ids,
        'is_valid_for_aggregation': is_valid_for_aggregation,
        'student_count_used': total_valid_students,
        'course': course
    }

def calculate_course_results_from_bulk_data(course_id, bulk_data, calculation_method='absolute'):
    """
    Calculate results for a single course using pre-loaded bulk data.
    This replaces calculate_single_course_results to eliminate per-course database queries.
    
    Args:
        course_id: The course ID to calculate
        bulk_data: Pre-loaded data from bulk_load_course_data()
        calculation_method: 'absolute' or 'relative'
    
    Returns:
        Same format as calculate_single_course_results()
    """
    course_data = bulk_data.get(course_id)
    if not course_data:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': None
        }
    
    course = course_data['course']
    settings = course_data['settings']
    
    # Check if course is excluded in settings
    if settings.excluded:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Get data from bulk load
    regular_exams = course_data['regular_exams']
    makeup_exams = course_data['makeup_exams']
    course_outcomes = course_data['course_outcomes']
    program_outcomes = course_data['program_outcomes']
    students = course_data['students']
    questions_by_exam = course_data['questions_by_exam']
    outcome_questions = course_data['outcome_questions']
    normalized_weights = course_data['normalized_weights']
    program_to_course_outcomes = course_data['program_to_course_outcomes']
    makeup_map = course_data['makeup_map']
    scores_dict = course_data['scores_dict']
    attendance_dict = course_data['attendance_dict']
    contributing_po_ids = course_data['contributing_po_ids']
    
    # Check for necessary data
    if not course_outcomes:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Check if there are exam questions
    has_exam_questions = False
    for exam_questions in questions_by_exam.values():
        if len(exam_questions) > 0:
            has_exam_questions = True
            break
    
    if not has_exam_questions:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    if not students:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Get list of mandatory exams
    mandatory_exams = [exam for exam in regular_exams if exam.is_mandatory]
    
    # Calculate student results using the same logic as calculate_single_course_results
    student_results = {}
    success_count = 0
    total_valid_students = 0
    
    for student in students:
        # Initialize student data
        student_data = {
            'student_id': student.student_id,
            'name': f"{student.first_name} {student.last_name}".strip(),
            'course_outcomes': {},
            'program_outcomes': {},
            'weighted_score': Decimal('0'),
            'skip': False,
            'excluded': getattr(student, 'excluded', False)
        }
        
        # Check if student should be excluded due to excluded flag
        if student_data['excluded']:
            student_data['skip'] = True
            student_results[student.id] = student_data
            continue
        
        # Check if student should be excluded due to mandatory exam policy
        if mandatory_exams:
            skip_student = False
            for exam in mandatory_exams:
                # Check if student attended the regular exam (default to True if no record)
                regular_attended = attendance_dict.get((student.id, exam.id), True)
                
                # Check if there's a makeup exam for this mandatory exam
                makeup_exam = makeup_map.get(exam.id)
                makeup_attended = False
                
                if makeup_exam:
                    # For makeup exams, default to attended (True) if no record
                    makeup_attended = attendance_dict.get((student.id, makeup_exam.id), True)
                
                # If student attended either the regular exam OR its makeup, they satisfy the attendance requirement
                # Only skip if they missed BOTH the regular exam AND its makeup
                if not regular_attended and (not makeup_exam or not makeup_attended):
                    skip_student = True
                    break
            
            if skip_student:
                student_data['skip'] = True
                student_data['missing_mandatory'] = True  # Add flag for UI to show
                student_results[student.id] = student_data
                continue
        
        # Calculate total weighted score
        total_weighted_score = Decimal('0')
        
        for exam in regular_exams:
            # Check if there's a makeup for this exam
            makeup_exam = makeup_map.get(exam.id)
            
            # If there's a makeup exam, check if student attended it
            if makeup_exam:
                # Check attendance without requiring valid scores
                makeup_attended = attendance_dict.get((student.id, makeup_exam.id), True)  # Default to True
                
                # If student attended the makeup, use that score exclusively
                if makeup_attended:
                    makeup_score = calculate_student_exam_score_optimized(
                        student.id, makeup_exam.id, scores_dict, 
                        questions_by_exam[makeup_exam.id], attendance_dict
                    )
                    # Use makeup score even if it's 0 (as long as it's not None)
                    if makeup_score is not None:
                        total_weighted_score += makeup_score * normalized_weights.get(exam.id, Decimal('0'))
                        continue  # Skip the original exam completely
                    else:
                        # Even if makeup score is None, still skip original exam if student attended makeup
                        makeup_score = Decimal('0')
                        total_weighted_score += makeup_score * normalized_weights.get(exam.id, Decimal('0'))
                        continue
            
            # If no makeup was attended or makeup score is None, use regular exam score
            exam_score = calculate_student_exam_score_optimized(
                student.id, exam.id, scores_dict,
                questions_by_exam[exam.id], attendance_dict
            )
            
            # For non-mandatory exams, ensure None is treated as 0
            if exam_score is None and not exam.is_mandatory:
                exam_score = Decimal('0')
                
            if exam_score is not None:
                total_weighted_score += exam_score * normalized_weights.get(exam.id, Decimal('0'))
        
        student_data['weighted_score'] = total_weighted_score
        
        # Calculate course outcome scores
        for outcome in course_outcomes:
            co_score = calculate_course_outcome_score_optimized(
                student.id, outcome.id, scores_dict, outcome_questions, normalized_weights, attendance_dict
            )
            student_data['course_outcomes'][outcome.id] = co_score
        
        # Calculate program outcome scores
        for outcome in program_outcomes:
            po_score = calculate_program_outcome_score_optimized(
                student.id, outcome.id, course_id, scores_dict, 
                program_to_course_outcomes, outcome_questions, normalized_weights, attendance_dict
            )
            student_data['program_outcomes'][outcome.id] = po_score
        
        # Store student results
        student_results[student.id] = student_data
        
        # Track student totals for relative method calculation
        total_valid_students += 1
        if total_weighted_score >= settings.relative_success_threshold:
            success_count += 1
    
    # Calculate program outcome scores based on method
    program_outcome_scores = {}
    
    if calculation_method == 'relative':
        # Relative method: percentage of students meeting threshold for each program outcome
        for po in program_outcomes:
            students_meeting_threshold = 0
            total_students_with_scores = 0
            
            for student_id, student_data in student_results.items():
                if student_data['skip']:
                    continue
                    
                po_score = student_data['program_outcomes'].get(po.id)
                if po_score is not None:
                    total_students_with_scores += 1
                    if po_score >= settings.relative_success_threshold:
                        students_meeting_threshold += 1
            
            if total_students_with_scores > 0:
                program_outcome_scores[po.id] = (students_meeting_threshold / total_students_with_scores) * 100
            else:
                program_outcome_scores[po.id] = 0
    else:
        # Absolute method: average scores for each program outcome
        for po in program_outcomes:
            total_score = Decimal('0')
            count = 0
            
            for student_id, student_data in student_results.items():
                if student_data['skip']:
                    continue
                    
                po_score = student_data['program_outcomes'].get(po.id)
                if po_score is not None:
                    total_score += Decimal(str(po_score))
                    count += 1
            
            if count > 0:
                program_outcome_scores[po.id] = float(total_score / count)
            else:
                program_outcome_scores[po.id] = 0
    
    # Determine if this course should be included in aggregation
    is_valid_for_aggregation = (
        total_valid_students > 0 and
        len(program_outcome_scores) > 0 and
        any(score > 0 for score in program_outcome_scores.values())
    )
    
    return {
        'program_outcome_scores': program_outcome_scores,
        'contributing_po_ids': contributing_po_ids,
        'is_valid_for_aggregation': is_valid_for_aggregation,
        'student_count_used': total_valid_students,
        'course': course
    }

@calculation_bp.route('/all_courses', endpoint='all_courses')
def all_courses_calculations():
    """Show program outcome scores for all courses with optional student ID and graduating students filtering"""
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Check if we need to set up default global achievement levels
    achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
    if not achievement_levels:
        # Add default achievement levels
        default_levels = [
            {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
            {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
            {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
            {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
            {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
        ]
        
        for level_data in default_levels:
            level = GlobalAchievementLevel(
                name=level_data["name"],
                min_score=level_data["min_score"],
                max_score=level_data["max_score"],
                color=level_data["color"],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.session.add(level)
        
        # Log action
        log = Log(action="ADD_DEFAULT_GLOBAL_ACHIEVEMENT_LEVELS", 
                 description="Added default global achievement levels from all_courses page")
        db.session.add(log)
        db.session.commit()
        
        # Refresh achievement levels
        achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
    
    # Get sort parameters from query string, default to course_code_asc
    sort_by = request.args.get('sort_by', 'course_code_asc')
    
    # Get filter parameters
    filter_year = request.args.get('year', '')
    search_query = request.args.get('search', '').lower()
    filter_student_id = request.args.get('student_id', '').strip()
    include_graduating_only = request.args.get('graduating_only', '').lower() == 'true'
    
    # Get the display method from session or default to absolute
    display_method = session.get('display_method', 'absolute')
    
    # Get all courses
    courses = Course.query.all()
    
    # Filter by year if provided
    if filter_year:
        courses = [c for c in courses if filter_year in c.semester]
    
    # Filter by search query if provided
    if search_query:
        courses = [c for c in courses if search_query in c.code.lower() or search_query in c.name.lower()]
    
    # Filter by student ID if provided
    student_info = {}
    if filter_student_id:
        courses, student_info = filter_courses_by_student(courses, filter_student_id)
    
    # Filter by graduating students if requested
    # Always get graduating filter info to enable/disable checkbox properly
    courses, graduating_filter_info = filter_courses_by_graduating_students(courses, include_graduating_only)
    
    # Preload all program outcomes in one query
    program_outcomes = ProgramOutcome.query.all()
    
    # Extract years from courses for year filter dropdown
    years = sorted(set(course.semester.split(' ')[1] for course in courses 
                      if ' ' in course.semester), reverse=True)
    
    # Initialize data structure to hold results for all courses
    all_results = {}
    
    # Prepare aggregation structures for program outcomes
    po_scores = {}    # Dict mapping po_id to list of scores from each course
    po_counts = {}    # Dict counting valid courses for each po_id
    
    # Track excluded courses separately
    excluded_courses = []
    
    # ==== BULK LOAD ALL DATA TO ELIMINATE N+1 QUERIES ====
    course_ids = [course.id for course in courses]
    
    # Load all necessary data at once
    bulk_data = bulk_load_course_data(course_ids, display_method)
    
    # Calculate results for each course
    for course in courses:
        # Check if course is excluded
        is_excluded = course.settings and course.settings.excluded
        if is_excluded:
            excluded_courses.append(course)
            # Add excluded course to all_results to make it visible in the UI
            all_results[f"{course.code}_{course.semester}"] = {
                'course': course,
                'program_outcome_results': {},
                'settings': course.settings,
                'avg_outcome_score': 0,
                'excluded': True
            }
            continue
            
        # Skip courses with no outcomes or exams
        if not hasattr(course, 'course_outcomes') or not course.course_outcomes:
            continue
        
        if not hasattr(course, 'exams') or not course.exams:
            continue
        
        # Calculate course results
        # FIXED: Pass graduating students filter to the calculation function
        if include_graduating_only:
            # When graduating students filter is active, we need to modify the calculation
            # to only include graduating students in the course calculations
            result = calculate_course_results_with_graduating_filter(course.id, bulk_data, display_method, include_graduating_only)
        else:
            result = calculate_course_results_from_bulk_data_v2_optimized(course.id, bulk_data, display_method)
        
        # Skip courses that don't have valid data for aggregation
        if not result['is_valid_for_aggregation']:
            continue
        
        # Format program outcome results for this course for display
        program_outcome_results = {}
        
        # If filtering by student ID, show individual student scores instead of course averages
        if filter_student_id:
            # Get the specific student in this course
            student_in_course = Student.query.filter_by(student_id=filter_student_id, course_id=course.id).first()
            if student_in_course:
                # Calculate individual student scores
                individual_result = calculate_individual_student_results(student_in_course.id, course.id, bulk_data, display_method)
                for po in program_outcomes:
                    po_score = individual_result.get(po.id)
                    contributes = po.id in result['contributing_po_ids']
                    
                    program_outcome_results[po.code] = {
                        'description': po.description,
                        'percentage': po_score if po_score is not None else 0,
                        'contributes': contributes,
                        'is_individual': True  # Flag to indicate this is individual score
                    }
                    
                    # Aggregate individual student scores for program outcomes averages
                    if contributes and po_score is not None:
                        if po.id not in po_scores:
                            po_scores[po.id] = []
                            po_counts[po.id] = 0
                        
                        # Store the original individual score and weight separately without pre-multiplying
                        po_scores[po.id].append((po_score, Decimal(str(course.course_weight))))
                        po_counts[po.id] += 1
            else:
                # Student not in this course, skip
                continue
        else:
            # Show course averages (original behavior)
            # FIXED: When graduating students filter is active, the result already contains
            # calculations based only on graduating students
            for po in program_outcomes:
                po_score = result['program_outcome_scores'].get(po.id)
                contributes = po.id in result['contributing_po_ids']
                
                program_outcome_results[po.code] = {
                    'description': po.description,
                    'percentage': po_score if po_score is not None else 0,
                    'contributes': contributes,
                    'is_individual': False  # Flag to indicate this is course average
                }
                
                # Aggregate scores for program outcomes
                if contributes and po_score is not None:
                    if po.id not in po_scores:
                        po_scores[po.id] = []
                        po_counts[po.id] = 0
                    
                    # Store the original score and weight separately without pre-multiplying
                    po_scores[po.id].append((po_score, Decimal(str(course.course_weight))))
                    po_counts[po.id] += 1
        
        # Calculate average outcome score for this course
        course_avg_outcome_score = calculate_avg_outcome_score(program_outcome_results)
        
        # Store results for this course
        all_results[f"{course.code}_{course.semester}"] = {
            'course': course,
            'program_outcome_results': program_outcome_results,
            'settings': course.settings,
            'avg_outcome_score': course_avg_outcome_score,
            'excluded': False
        }
    
    # Calculate average scores for each program outcome across all courses
    po_averages = {}
    for po in program_outcomes:
        if po.id in po_scores and po_counts[po.id] > 0:
            # Calculate weighted average: sum(weight * score) / sum(weights)
            weighted_scores = po_scores[po.id]
            sum_weighted_scores = sum(Decimal(str(score)) * weight for score, weight in weighted_scores)
            sum_weights = sum(weight for _, weight in weighted_scores)
            
            if sum_weights > 0:
                po_averages[po.code] = sum_weighted_scores / sum_weights
            else:
                po_averages[po.code] = None
        else:
            po_averages[po.code] = None
    
    # Sort the results according to the sort parameter
    sorted_results = {}
    
    if sort_by == 'course_code_asc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: (k.split('_')[0], k.split('_', 1)[1] if '_' in k else ''))
    elif sort_by == 'course_code_desc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: (k.split('_')[0], k.split('_', 1)[1] if '_' in k else ''), reverse=True)
    elif sort_by == 'course_name_asc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: all_results[k]['course'].name.lower())
    elif sort_by == 'course_name_desc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: all_results[k]['course'].name.lower(), reverse=True)
    elif sort_by == 'avg_score_asc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: all_results[k]['avg_outcome_score'])
    elif sort_by == 'avg_score_desc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: all_results[k]['avg_outcome_score'], reverse=True)
    else:
        # Default to course code ascending
        sorted_keys = sorted(all_results.keys(), key=lambda k: (k.split('_')[0], k.split('_', 1)[1] if '_' in k else ''))
    
    for key in sorted_keys:
        sorted_results[key] = all_results[key]
    
    # Log action
    log_description = f"Viewed program outcome scores for all courses"
    if filter_student_id:
        log_description += f" (filtered by student ID: {filter_student_id})"
    if include_graduating_only:
        log_description += f" (graduating students only)"
    log = Log(action="ALL_COURSES_CALCULATIONS", description=log_description)
    db.session.add(log)
    db.session.commit()
    
    # Check if this is an AJAX request
    if is_ajax:
        # Return JSON data for AJAX requests
        return jsonify({
            'all_results': {k: {
                'course': {
                    'id': v['course'].id,
                    'code': v['course'].code,
                    'name': v['course'].name,
                    'semester': v['course'].semester
                },
                'program_outcome_results': v['program_outcome_results'],
                'settings': {
                    'success_rate_method': v['settings'].success_rate_method if v['settings'] else display_method,
                    'relative_success_threshold': float(v['settings'].relative_success_threshold) if v['settings'] else 60.0,
                    'excluded': v['settings'].excluded if v['settings'] else False
                },
                'avg_outcome_score': float(v['avg_outcome_score']),
                'excluded': v['settings'].excluded if v['settings'] else False
            } for k, v in sorted_results.items()},
            'program_outcomes': [{'id': po.id, 'code': po.code, 'description': po.description} for po in program_outcomes],
            'po_averages': {k: float(v) if v is not None else None for k, v in po_averages.items()},
            'excluded_courses': [{'id': c.id, 'code': c.code, 'name': c.name, 'semester': c.semester} for c in excluded_courses],
            'global_achievement_levels': [{'id': l.id, 'name': l.name, 'min_score': float(l.min_score), 
                                        'max_score': float(l.max_score), 'color': l.color} 
                                       for l in GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()],
            'progress': 100,  # Always 100 when returning final results
            'current_sort': sort_by,
            'student_info': student_info,
            'filter_student_id': filter_student_id,
            'graduating_filter_info': graduating_filter_info,
            'include_graduating_only': include_graduating_only
        })
    
    # For regular requests, render the template
    return render_template('calculation/all_courses.html', 
                          all_results=sorted_results,
                          program_outcomes=program_outcomes,
                          po_averages=po_averages,
                          excluded_courses=excluded_courses,
                          years=years,
                          active_page='all_courses',
                          current_sort=sort_by,
                          student_info=student_info,
                          filter_student_id=filter_student_id,
                          graduating_filter_info=graduating_filter_info,
                          include_graduating_only=include_graduating_only,
                          global_achievement_levels=GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all(),
                          get_achievement_level=get_achievement_level)

@calculation_bp.route('/all_courses_loading', endpoint='all_courses_loading')
def all_courses_loading():
    """Redirects to all_courses for backward compatibility"""
    return redirect(url_for('calculation.all_courses'))

def get_cross_course_student_info(student_id):
    """
    Get student information across all courses efficiently using database indexes.
    
    This function uses the new performance indexes:
    - idx_student_student_id_global: For fast student ID lookup
    - idx_student_student_id_course_lookup: For student-to-courses mapping
    
    Returns:
    - student_courses: List of courses the student is enrolled in
    - student_name: Student's name (from first course found)
    - total_courses: Total number of courses student is in
    """
    if not student_id:
        return [], None, 0
    
    # Use indexed query to find all students with this student_id across all courses
    # This leverages idx_student_student_id_global for performance
    students = Student.query.filter_by(student_id=student_id).all()
    
    if not students:
        return [], None, 0
    
    # Get course information and student name
    student_courses = []
    student_name = None
    
    for student in students:
        # Get the course for this enrollment
        course = Course.query.get(student.course_id)
        if course:
            student_courses.append(course)
            # Use the first student name we find (should be consistent across courses)
            if not student_name:
                # Combine first_name and last_name, handle null last_name
                if student.last_name:
                    student_name = f"{student.first_name} {student.last_name}"
                else:
                    student_name = student.first_name
    
    return student_courses, student_name, len(student_courses)

def filter_courses_by_student(courses, student_id):
    """
    Filter courses list to only include courses where the student is enrolled.
    Uses the cross-course student lookup for efficient filtering.
    
    Parameters:
    - courses: List of courses to filter
    - student_id: Student ID to filter by
    
    Returns:
    - filtered_courses: List of courses where student is enrolled
    - student_info: Dict with student name and enrollment info
    """
    if not student_id:
        return courses, {}
    
    # Get student's course enrollments
    student_courses, student_name, total_courses = get_cross_course_student_info(student_id)
    
    if not student_courses:
        return [], {'name': None, 'total_courses': 0, 'filtered_courses': 0}
    
    # Create a set of course IDs for efficient lookup
    student_course_ids = {course.id for course in student_courses}
    
    # Filter the courses list
    filtered_courses = [course for course in courses if course.id in student_course_ids]
    
    student_info = {
        'name': student_name,
        'total_courses': total_courses,
        'filtered_courses': len(filtered_courses)
    }
    
    return filtered_courses, student_info

@calculation_bp.route('/all_courses/export', endpoint='export_all_courses')
def export_all_courses():
    """Export program outcome scores for all courses to CSV"""
    # Check if we need to set up default global achievement levels
    achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
    if not achievement_levels:
        # Add default achievement levels
        default_levels = [
            {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
            {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
            {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
            {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
            {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
        ]
        
        for level_data in default_levels:
            level = GlobalAchievementLevel(
                name=level_data["name"],
                min_score=level_data["min_score"],
                max_score=level_data["max_score"],
                color=level_data["color"],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.session.add(level)
        
        # Log action
        log = Log(action="ADD_DEFAULT_GLOBAL_ACHIEVEMENT_LEVELS", 
                 description="Added default global achievement levels from all_courses/export page")
        db.session.add(log)
        db.session.commit()
        
        # Refresh achievement levels
        achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
    
    # Get sort parameters from query string, default to course_code_asc
    sort_by = request.args.get('sort_by', 'course_code_asc')
    
    # Get filter parameters
    filter_year = request.args.get('year', '')
    search_query = request.args.get('search', '').lower()
    filter_student_id = request.args.get('student_id', '').strip()
    include_graduating_only = request.args.get('graduating_only', '').lower() == 'true'
    
    # Get the display method from session or default to absolute
    display_method = session.get('display_method', 'absolute')
    
    # Get all courses
    courses = Course.query.all()
    
    # Filter by year if provided
    if filter_year:
        courses = [c for c in courses if filter_year in c.semester]
    
    # Filter by search query if provided
    if search_query:
        courses = [c for c in courses if search_query in c.code.lower() or search_query in c.name.lower()]
    
    # Filter by student ID if provided
    student_info = {}
    if filter_student_id:
        courses, student_info = filter_courses_by_student(courses, filter_student_id)
    
    # Filter by graduating students if requested
    # Always get graduating filter info to enable/disable checkbox properly
    courses, graduating_filter_info = filter_courses_by_graduating_students(courses, include_graduating_only)
    
    # Preload all program outcomes in one query
    program_outcomes = ProgramOutcome.query.all()
    
    # Initialize data structure to hold results for all courses
    all_results = {}
    
    # Prepare aggregation structures for program outcomes
    po_scores = {}    # Dict mapping po_id to list of scores from each course
    po_counts = {}    # Dict counting valid courses for each po_id
    
    # Track excluded courses separately
    excluded_courses = []
    
    # Calculate results for each course
    for course in courses:
        # Check if course is excluded
        is_excluded = course.settings and course.settings.excluded
        if is_excluded:
            excluded_courses.append(course)
            # Add excluded course to all_results to make it visible in the UI
            all_results[f"{course.code}_{course.semester}"] = {
                'course': course,
                'program_outcome_results': {},
                'settings': course.settings,
                'avg_outcome_score': 0,
                'excluded': True
            }
            continue
            
        # Skip courses with no outcomes or exams
        if not hasattr(course, 'course_outcomes') or not course.course_outcomes:
            continue
        
        if not hasattr(course, 'exams') or not course.exams:
            continue
        
        # Calculate course results
        result = calculate_single_course_results(course.id, display_method)
        
        # Skip courses that don't have valid data for aggregation
        if not result['is_valid_for_aggregation']:
            continue
        
        # Format program outcome results for this course for display
        program_outcome_results = {}
        for po in program_outcomes:
            po_score = result['program_outcome_scores'].get(po.id)
            contributes = po.id in result['contributing_po_ids']
            
            program_outcome_results[po.code] = {
                'description': po.description,
                'percentage': po_score if po_score is not None else 0,
                'contributes': contributes
            }
            
            # Aggregate scores for program outcomes
            if contributes and po_score is not None:
                if po.id not in po_scores:
                    po_scores[po.id] = []
                    po_counts[po.id] = 0
                
                # Store the original score and weight separately without pre-multiplying
                po_scores[po.id].append((po_score, Decimal(str(course.course_weight))))
                po_counts[po.id] += 1
        
        # Calculate average outcome score for this course
        course_avg_outcome_score = calculate_avg_outcome_score(program_outcome_results)
        
        # Store results for this course
        all_results[f"{course.code}_{course.semester}"] = {
            'course': course,
            'program_outcome_results': program_outcome_results,
            'settings': course.settings,
            'avg_outcome_score': course_avg_outcome_score
        }
    
    # Calculate average scores for each program outcome across all courses
    po_averages = {}
    for po in program_outcomes:
        if po.id in po_scores and po_counts[po.id] > 0:
            # Calculate weighted average: sum(weight * score) / sum(weights)
            weighted_scores = po_scores[po.id]
            sum_weighted_scores = sum(Decimal(str(score)) * weight for score, weight in weighted_scores)
            sum_weights = sum(weight for _, weight in weighted_scores)
            
            if sum_weights > 0:
                po_averages[po.code] = sum_weighted_scores / sum_weights
            else:
                po_averages[po.code] = None
        else:
            po_averages[po.code] = None
    
    # Sort the results according to the sort parameter
    sorted_results = {}
    
    if sort_by == 'course_code_asc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: (k.split('_')[0], k.split('_', 1)[1] if '_' in k else ''))
    elif sort_by == 'course_code_desc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: (k.split('_')[0], k.split('_', 1)[1] if '_' in k else ''), reverse=True)
    elif sort_by == 'course_name_asc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: all_results[k]['course'].name.lower())
    elif sort_by == 'course_name_desc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: all_results[k]['course'].name.lower(), reverse=True)
    elif sort_by == 'avg_score_asc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: all_results[k]['avg_outcome_score'])
    elif sort_by == 'avg_score_desc':
        sorted_keys = sorted(all_results.keys(), key=lambda k: all_results[k]['avg_outcome_score'], reverse=True)
    else:
        # Default to course code ascending
        sorted_keys = sorted(all_results.keys(), key=lambda k: (k.split('_')[0], k.split('_', 1)[1] if '_' in k else ''))
    
    for key in sorted_keys:
        sorted_results[key] = all_results[key]
    
    # Prepare data for CSV export
    csv_data = []
    
    # Add student info to CSV if filtered by student
    if filter_student_id and student_info:
        csv_data.append(['STUDENT FILTER INFORMATION'])
        csv_data.append(['Student ID', filter_student_id])
        if student_info.get('name'):
            csv_data.append(['Student Name', student_info['name']])
        csv_data.append(['Total Enrolled Courses', student_info.get('total_courses', 0)])
        csv_data.append(['Filtered Courses Shown', student_info.get('filtered_courses', 0)])
        csv_data.append([])  # Empty row separator
    
    # Create header row with program outcome codes
    headers = ['Course Code', 'Course Name', 'Semester', 'Course Weight', 'Average PO Score']
    po_codes = [po.code for po in program_outcomes]
    headers.extend(po_codes)
    
    # Add data rows for each course
    for course_code, course_data in sorted_results.items():
        course = course_data['course']
        row = [course.code, course.name, course.semester, course.course_weight, f"{course_data['avg_outcome_score']:.2f}%"]
        
        # Add percentage for each program outcome
        for po_code in po_codes:
            if po_code in course_data['program_outcome_results']:
                po_data = course_data['program_outcome_results'][po_code]
                if po_data['contributes'] and po_data['percentage'] is not None:
                    row.append(f"{float(po_data['percentage']):.2f}%")
                else:
                    row.append("N/A")
            else:
                row.append("N/A")
        
        csv_data.append(row)
    
    # Add average row at the bottom
    avg_row = ['AVERAGE', '', '', '', '']
    for po_code in po_codes:
        if po_code in po_averages and po_averages[po_code] is not None:
            avg_row.append(f"{float(po_averages[po_code]):.2f}%")
        else:
            avg_row.append("N/A")
    
    csv_data.append(avg_row)
    
    # Add excluded courses section if there are any
    if excluded_courses:
        csv_data.append([])  # Empty row as separator
        csv_data.append(['EXCLUDED COURSES'])
        csv_data.append(['Course Code', 'Course Name', 'Semester', 'Course Weight'])
        
        for course in excluded_courses:
            csv_data.append([course.code, course.name, course.semester, course.course_weight])
    
    # Get global achievement levels to include in export
    global_achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
    
    # Add global achievement levels to the CSV export at the bottom
    if global_achievement_levels:
        # Add a blank row as a separator
        csv_data.append([])
        # Add a header row for Achievement Levels
        csv_data.append(['GLOBAL ACHIEVEMENT LEVELS'])
        csv_data.append(['Level Name', 'Min Score (%)', 'Max Score (%)', 'Color'])
        
        # Add each achievement level
        for level in global_achievement_levels:
            csv_data.append([level.name, level.min_score, level.max_score, level.color])
    
    # Log action
    log_description = f"Exported program outcome scores for all courses to CSV"
    if filter_student_id:
        log_description += f" (filtered by student ID: {filter_student_id})"
    log = Log(action="EXPORT_ALL_COURSES", description=log_description)
    db.session.add(log)
    db.session.commit()
    
    # Convert data to CSV
    return export_to_excel_csv(csv_data, "all_courses_results", headers)

@calculation_bp.route('/course/<int:course_id>/settings', methods=['POST'])
def update_course_settings(course_id):
    """Update course calculation settings"""
    course = Course.query.get_or_404(course_id)
    
    # Get the settings or create new if it doesn't exist
    settings = CourseSettings.query.filter_by(course_id=course_id).first()
    if not settings:
        settings = CourseSettings(course_id=course_id)
        db.session.add(settings)
    
    # Update settings
    settings.success_rate_method = request.form.get('success_rate_method', 'absolute')
    try:
        settings.relative_success_threshold = Decimal(request.form.get('relative_success_threshold', '60.0'))
    except:
        settings.relative_success_threshold = Decimal('60.0')
    
    # Update excluded status
    settings.excluded = 'excluded' in request.form
    
    # Update course weight if provided
    course_weight = request.form.get('course_weight')
    if course_weight:
        try:
            course.course_weight = float(course_weight)
        except ValueError:
            flash('Course weight must be a valid number. Using previous value.', 'warning')
    
    db.session.commit()
    
    # Log action
    log = Log(action="UPDATE_COURSE_SETTINGS",
             description=f"Updated calculation settings for course: {course.code}")
    db.session.add(log)
    db.session.commit()
    
    flash('Course calculation settings updated successfully.', 'success')
    
    # Return to the appropriate page
    referer = request.referrer
    if referer and 'all_courses' in referer:
        return redirect(url_for('calculation.all_courses'))
    else:
        return redirect(url_for('calculation.course_calculations', course_id=course_id))

@calculation_bp.route('/exam/<int:exam_id>/toggle_mandatory', methods=['POST'])
def toggle_mandatory_exam(exam_id):
    """Toggle the mandatory status of an exam"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    
    # Toggle the status
    exam.is_mandatory = not exam.is_mandatory
    db.session.commit()
    
    # Log action
    status = "mandatory" if exam.is_mandatory else "optional"
    log = Log(action="TOGGLE_MANDATORY_EXAM",
             description=f"Changed exam '{exam.name}' in course '{course.code}' to {status}")
    db.session.add(log)
    db.session.commit()
    
    flash(f"Exam '{exam.name}' is now {status}.", 'success')
    return redirect(url_for('exam.manage_exams', course_id=course.id))

@calculation_bp.route('/course/<int:course_id>/toggle_exclusion', methods=['POST'])
def toggle_course_exclusion(course_id):
    """Toggle the exclusion status of a course"""
    course = Course.query.get_or_404(course_id)
    
    # Get the settings or create new if it doesn't exist
    settings = CourseSettings.query.filter_by(course_id=course_id).first()
    if not settings:
        settings = CourseSettings(course_id=course_id)
        db.session.add(settings)
    
    # Toggle the status
    settings.excluded = not settings.excluded
    db.session.commit()
    
    # Log action
    status = "excluded" if settings.excluded else "included"
    log = Log(action="TOGGLE_COURSE_EXCLUSION",
             description=f"Changed course '{course.code}' to {status}")
    db.session.add(log)
    db.session.commit()
    
    flash(f"Course '{course.code}' is now {status}.", 'success')
    
    # Check referrer to determine where to redirect
    referer = request.referrer
    if referer and 'calculation/course' in referer:
        return redirect(url_for('calculation.course_calculations', course_id=course_id))
    return redirect(url_for('calculation.all_courses'))

@calculation_bp.route('/update_display_method', methods=['POST'])
def update_display_method():
    """Update display method preference in session"""
    if request.method == 'POST':
        display_method = request.form.get('display_method')
        if display_method in ['absolute', 'relative']:
            # Store the display method in session
            session['display_method'] = display_method
            return jsonify({'status': 'success', 'reload': True})
    return jsonify({'status': 'error'})

def calculate_student_exam_score_optimized(student_id, exam_id, scores_dict, questions, attendance_dict=None):
    """Calculate a student's total score for an exam using preloaded data.
    
    This improved version uses an explicit check for None so that a valid score of 0 is not skipped.
    It also checks if the student attended the exam and returns None if they didn't.
    If the student didn't attend a mandatory exam, it returns None to indicate they should be excluded.
    For non-mandatory exams, missing is treated as 0.
    """
    if not questions:
        return None
        
    # Get the exam to check if it's mandatory
    exam = Exam.query.get(exam_id)
    is_mandatory = exam and exam.is_mandatory
        
    # Check if the student attended the exam
    if attendance_dict is not None:
        # Use the attendance dict if provided
        attended = attendance_dict.get((student_id, exam_id), True)  # Default to True if no record
        if not attended:
            if is_mandatory:
                return None  # Return None for mandatory exams to signal absence (to be checked with makeup)
            else:
                return Decimal('0')  # Student didn't attend non-mandatory exam, treat as 0
    else:
        # Check the database directly if no dict provided
        attendance = StudentExamAttendance.query.filter_by(
            student_id=student_id, 
            exam_id=exam_id
        ).first()
        
        # If there's an attendance record and the student didn't attend
        if attendance and not attendance.attended:
            if is_mandatory:
                return None  # Return None for mandatory exams to signal absence
            else:
                return Decimal('0')  # Non-mandatory absences counted as 0

    total_score = Decimal('0')
    total_possible = Decimal('0')

    # Calculate score based on available data
    has_scores = False
    for question in questions:
        score_value = scores_dict.get((student_id, question.id, exam_id))
        # Use explicit check for None to include a valid score of 0
        if score_value is not None:
            has_scores = True
            total_score += Decimal(str(score_value))
        total_possible += question.max_score

    # If no scores were found, treat according to exam type
    if not has_scores:
        if is_mandatory:
            # For mandatory exams without scores, return 0
            return Decimal('0')
        else:
            # Non-mandatory exams without scores are treated as 0%
            return Decimal('0')

    if total_possible == Decimal('0'):
        return None

    return (total_score / total_possible) * Decimal('100')

def calculate_course_outcome_score_optimized(student_id, outcome_id, scores_dict, outcome_questions, normalized_weights=None, attendance_dict=None):
    """Calculate a student's score for a course outcome using preloaded data
    
    This function calculates a student's achievement for a specific Course Outcome (CO)
    using the master course weights to ensure proper relative importance of each exam.
    
    Parameters:
    - student_id: The student's ID
    - outcome_id: The Course Outcome ID
    - scores_dict: Dictionary containing all scores for fast lookup
    - outcome_questions: Dictionary mapping outcome_id to list of questions
    - normalized_weights: Pre-calculated, normalized weights for all exams in the course
                         (if None, will calculate weights only for exams with questions for this outcome)
    - attendance_dict: Dictionary mapping (student_id, exam_id) to attendance status
    """
    questions = outcome_questions.get(outcome_id, [])

    if not questions:
        return Decimal('0')  # Return 0 instead of None when no questions linked to this outcome

    # Group questions by exam to properly apply exam weights
    questions_by_exam = {}
    for question in questions:
        exam_id = question.exam_id
        if exam_id not in questions_by_exam:
            questions_by_exam[exam_id] = []
        questions_by_exam[exam_id].append(question)
    
    # Get all exams
    exam_ids = list(questions_by_exam.keys())
    exams = Exam.query.filter(Exam.id.in_(exam_ids)).all()
    
    # Create a map from original exam to makeup exam
    makeup_map = {}
    for exam in exams:
        if exam.is_makeup and exam.makeup_for:
            makeup_map[exam.makeup_for] = exam.id
    
    # Filter out base exams that have makeup exams if student attended the makeup
    filtered_exam_ids = []
    for exam_id in exam_ids:
        # Find if this is a base exam with a makeup
        exam = next((e for e in exams if e.id == exam_id), None)
        
        # If this is a makeup exam, always include it
        if exam and exam.is_makeup:
            filtered_exam_ids.append(exam_id)
            continue
            
        # If this is a base exam, check if it has a makeup that the student attended
        if exam and not exam.is_makeup and exam.id in makeup_map:
            makeup_id = makeup_map[exam.id]
            
            # FIXED: Check attendance using attendance_dict if available, otherwise fall back to direct query
            attended_makeup = False
            if attendance_dict is not None:
                # Use the attendance dictionary if available - default to attended (True) if no record
                attended_makeup = attendance_dict.get((student_id, makeup_id), True)
            else:
                # Fall back to database query if no dictionary provided
                attended_makeup = StudentExamAttendance.query.filter_by(
                    student_id=student_id, 
                    exam_id=makeup_id,
                    attended=True
                ).first() is not None
            
            # If student attended makeup, skip this base exam
            if attended_makeup and makeup_id in questions_by_exam:
                continue
        
        # Include the base exam if no makeup was attended
        filtered_exam_ids.append(exam_id)
    
    # --- START: Fetch Q-CO Weights for this specific outcome ---
    question_co_weights = {}
    outcome_question_ids = [q.id for q in questions] # Get IDs of questions linked to *this* outcome
    if outcome_question_ids:
        from sqlalchemy import text, inspect # Ensure imports
        try:
            inspector = inspect(db.engine)
            qco_columns = [c['name'] for c in inspector.get_columns('question_course_outcome')]
            has_relative_weight = 'relative_weight' in qco_columns

            if has_relative_weight:
                # Use proper SQLAlchemy query with manual IN clause construction for SQLite compatibility
                from sqlalchemy import text
                if outcome_question_ids:
                    # Create placeholders for IN clause
                    placeholders = ','.join([':param_' + str(i) for i in range(len(outcome_question_ids))])
                    query = f"SELECT question_id, relative_weight FROM question_course_outcome WHERE course_outcome_id = :outcome_id AND question_id IN ({placeholders})"
                    
                    # Create parameters dictionary
                    params = {"outcome_id": outcome_id}
                    for i, q_id in enumerate(outcome_question_ids):
                        params[f'param_{i}'] = q_id
                    
                    weights_result = db.session.execute(text(query), params).fetchall()
                    
                    for q_id, weight in weights_result:
                        question_co_weights[q_id] = Decimal(str(weight)) if weight is not None else Decimal('1.0')
                
                # Set default weights for questions not found in the mapping
                for q_id in outcome_question_ids:
                    if q_id not in question_co_weights:
                        question_co_weights[q_id] = Decimal('1.0')
            else:
                # Default to 1.0 if column doesn't exist
                for q_id in outcome_question_ids:
                    question_co_weights[q_id] = Decimal('1.0')

        except Exception as e:
            # Only log at ERROR level for actual errors, not warnings
            logging.error(f"Error fetching Q-CO weights for CO {outcome_id}: {e}")
            # Default all weights to 1.0 on error
            for q_id in outcome_question_ids:
               question_co_weights[q_id] = Decimal('1.0')
    # --- END: Fetch Q-CO Weights ---
    
    # If normalized_weights is None, we need to calculate them only for the relevant exams
    # This is the old behavior and should only be used if no master weights are provided
    if normalized_weights is None:
        # Get exam weights
        weights = {}
        total_weight = Decimal('0')
        for exam_id in filtered_exam_ids:
            weight_record = ExamWeight.query.filter_by(exam_id=exam_id).first()
            if weight_record:
                weights[exam_id] = weight_record.weight
                total_weight += weight_record.weight
            else:
                weights[exam_id] = Decimal('0')
        
        # If no valid weights, return None or default to equal weights
        if total_weight == Decimal('0'):
            if len(filtered_exam_ids) > 0:
                # Default to equal weights if no weights defined
                equal_weight = Decimal('1') / Decimal(str(len(filtered_exam_ids)))
                for exam_id in filtered_exam_ids:
                    weights[exam_id] = equal_weight
                total_weight = Decimal('1')
            else:
                return Decimal('0')  # Return 0 instead of None when no valid exam weights found
        
        # Normalize weights
        exam_weights = {}
        for exam_id, weight in weights.items():
            exam_weights[exam_id] = weight / total_weight
    else:
        # Use the provided master course weights
        exam_weights = normalized_weights
    
    # --- START: Modified Weighted Score Calculation ---
    total_weighted_score_contribution = Decimal('0')
    total_applied_weight_contribution = Decimal('0') # Sum of (exam_weight * qco_weight)

    for exam_id in filtered_exam_ids:
        if exam_id not in questions_by_exam:
            continue

        exam_questions_for_outcome = questions_by_exam[exam_id]

        if exam_id not in exam_weights: # Use the correct weight dict (normalized_weights or exam_weights)
             logging.warning(f"Missing normalized weight for exam {exam_id} when calculating CO {outcome_id}")
             continue

        exam_weight = exam_weights[exam_id] # This is the Exam's weight in the course (0-1)

        # Calculate score for this exam's relevant questions
        exam_outcome_total_possible = Decimal('0')
        exam_outcome_total_score = Decimal('0')
        exam_total_qco_weight = Decimal('0') # Sum of Q-CO weights for this exam's questions

        for question in exam_questions_for_outcome:
            score_value = scores_dict.get((student_id, question.id, exam_id))
            qco_weight = question_co_weights.get(question.id, Decimal('1.0')) # Get Q-CO weight

            if score_value is not None:
                # Accumulate weighted score and weighted max score for this exam
                exam_outcome_total_score += Decimal(str(score_value)) * qco_weight
                exam_outcome_total_possible += question.max_score * qco_weight
                exam_total_qco_weight += qco_weight # Track the sum of weights used

        # Calculate the achievement percentage *for this exam's contribution* to the CO
        if exam_outcome_total_possible > Decimal('0'):
            exam_outcome_percentage = (exam_outcome_total_score / exam_outcome_total_possible) * Decimal('100')

            # Weight this exam's contribution by the exam's weight in the course
            # AND by the sum of Q-CO weights for this exam (to normalize contribution)
            # This weight represents the "importance" of this exam's contribution to the CO
            effective_weight = exam_weight * exam_total_qco_weight

            total_weighted_score_contribution += exam_outcome_percentage * effective_weight
            total_applied_weight_contribution += effective_weight
        elif exam_total_qco_weight > Decimal('0'):
             # If max score is 0 but weights exist, treat contribution as 0 achievement with weight applied
             effective_weight = exam_weight * exam_total_qco_weight
             total_weighted_score_contribution += Decimal('0') * effective_weight
             total_applied_weight_contribution += effective_weight


    # Final CO score is the weighted average across contributing exams
    if total_applied_weight_contribution == Decimal('0'):
        return Decimal('0') # Avoid division by zero

    final_co_score = total_weighted_score_contribution / total_applied_weight_contribution
    return final_co_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) # Ensure consistent rounding
    # --- END: Modified Weighted Score Calculation ---

# Optimized helper function to calculate a student's score for a program outcome
def calculate_program_outcome_score_optimized(student_id, outcome_id, course_id, scores_dict, 
                                             program_to_course_outcomes, outcome_questions, 
                                             normalized_weights=None, attendance_dict=None):
    """Calculate a student's score for a program outcome using preloaded data
    
    Parameters:
    - student_id: The student's ID
    - outcome_id: The Program Outcome ID
    - course_id: The Course ID
    - scores_dict: Dictionary containing all scores for fast lookup
    - program_to_course_outcomes: Map of program outcomes to related course outcomes
    - outcome_questions: Dictionary mapping outcome_id to list of questions
    - normalized_weights: Pre-calculated, normalized weights for all exams in the course
    - attendance_dict: Dictionary mapping (student_id, exam_id) to attendance status
    """
    # Get related course outcomes from the preloaded mapping
    related_course_outcomes = program_to_course_outcomes.get(outcome_id, [])
    
    if not related_course_outcomes:
        return Decimal('0')  # Return 0 instead of None when no related course outcomes
    
    # Get course-specific settings for weighting
    course = Course.query.get(course_id)
    if not course:
        return Decimal('0')  # Return 0 instead of None when course not found
    
    # Initialize variables for weighted calculation
    total_weighted_score = Decimal('0')
    total_weight = Decimal('0')
    
    # Get CO-PO relative weights from the database
    co_po_weights = {}
    co_ids = [co.id for co in related_course_outcomes]
    
    try:
        # Properly handle SQLite IN clause
        if co_ids:
            from sqlalchemy import text
            
            # Use proper SQLAlchemy query with manual IN clause construction for SQLite compatibility
            if co_ids:
                # Create placeholders for IN clause
                placeholders = ','.join([':param_' + str(i) for i in range(len(co_ids))])
                query = f"SELECT course_outcome_id, program_outcome_id, relative_weight FROM course_outcome_program_outcome WHERE program_outcome_id = :po_id AND course_outcome_id IN ({placeholders})"
                
                # Create parameters dictionary
                params = {"po_id": outcome_id}
                for i, co_id in enumerate(co_ids):
                    params[f'param_{i}'] = co_id
                
                weights_result = db.session.execute(text(query), params).fetchall()
                
                for co_id, po_id, weight in weights_result:
                    co_po_weights[(co_id, po_id)] = Decimal(str(weight))
            
    except Exception as e:
        logging.error(f"Error retrieving CO-PO weights: {str(e)}")
        # Fall back to default weights of 1.0
    
    # Store all score and weight pairs for final calculation
    co_scores_and_weights = []
    
    # Get individual course outcome scores and apply weights
    for course_outcome in related_course_outcomes:
        # Calculate the score for this course outcome, passing through the normalized weights and attendance_dict
        co_score = calculate_course_outcome_score_optimized(
            student_id, course_outcome.id, scores_dict, outcome_questions, 
            normalized_weights, attendance_dict
        )
        
        if co_score is not None:
            # Get the relative weight for this CO-PO pair, default to 1.0 if not found
            weight_key = (course_outcome.id, outcome_id)
            relative_weight = co_po_weights.get(weight_key, Decimal('1.0'))
            
            # Add to our collection for weighted average calculation
            co_scores_and_weights.append((co_score, relative_weight))
            
            # Add to running totals
            total_weighted_score += co_score * relative_weight
            total_weight += relative_weight
    
    # Calculate weighted average
    if total_weight > Decimal('0'):
        final_score = total_weighted_score / total_weight
        return final_score
    else:
        return Decimal('0')  # Return 0 instead of None when no valid scores

def calculate_single_course_results(course_id, calculation_method='absolute'):
    """Calculate results for a single course and return data for aggregation
    
    This is a core calculation function that centralizes the logic for course result calculations.
    It's used by both single-course views and the all-courses aggregation to ensure consistent results.
    
    The function handles:
    - Fetching all necessary course data (exams, questions, outcomes, students, scores)
    - Checking if student should be excluded based on mandatory exam attendance
    - Calculating individual student scores for each Course Outcome (CO)
    - Calculating the course's overall contribution to each Program Outcome (PO)
    - Supporting both 'absolute' and 'relative' calculation methods
    
    For makeup exams, the function:
    - Uses the makeup exam score if the student attended the makeup
    - Uses the same weight as the original exam when calculating the weighted score
    
    Parameters:
    - course_id (int): The ID of the course to calculate
    - calculation_method (str): Either 'absolute' (default) or 'relative'
    
    Returns:
    - Dictionary containing:
      - program_outcome_scores: Dict mapping program_outcome_id to calculated contribution percentage
      - contributing_po_ids: Set of program_outcome_ids that this course contributes to
      - is_valid_for_aggregation: Boolean indicating if course results should be included in aggregation
      - student_count_used: Number of students included in the calculation after exclusions
      - course: Course object for reference
    """
    # Get the course and check if it's manually excluded
    course = Course.query.get(course_id)
    if not course:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': None
        }
    
    # Get course settings
    settings = course.settings
    if not settings:
        settings = CourseSettings(
            course_id=course_id,
            success_rate_method=calculation_method,
            relative_success_threshold=60.0
        )
        db.session.add(settings)
        db.session.commit()
    
    # Check if course is excluded in settings
    if settings.excluded:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Get regular and makeup exams separately
    regular_exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()
    makeup_exams = Exam.query.filter_by(course_id=course_id, is_makeup=True).all()
    
    # Combined list of all exams
    all_exams = regular_exams + makeup_exams
    
    # Get list of mandatory exams
    mandatory_exams = [exam for exam in regular_exams if exam.is_mandatory]
    
    # Check for necessary data
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    if not course_outcomes:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': set(),
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Get all program outcomes associated with this course's outcomes
    program_outcomes = set()
    for co in course_outcomes:
        for po in co.program_outcomes:
            program_outcomes.add(po)
    # Sort program outcomes numerically by extracting the number from the code
    program_outcomes = sorted(list(program_outcomes), key=lambda po: int(''.join(filter(str.isdigit, po.code))) if any(c.isdigit() for c in po.code) else po.code)
    
    # Create set of contributing PO IDs
    contributing_po_ids = {po.id for po in program_outcomes}
    
    # Check if there are exam questions
    has_exam_questions = False
    for exam in all_exams:
        if len(exam.questions) > 0:
            has_exam_questions = True
            break
    
    if not has_exam_questions:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Get students
    students = Student.query.filter_by(course_id=course_id).all()
    if not students:
        return {
            'program_outcome_scores': {},
            'contributing_po_ids': contributing_po_ids,
            'is_valid_for_aggregation': False,
            'student_count_used': 0,
            'course': course
        }
    
    # Check exam weights and validate
    total_weight = Decimal('0')
    exam_weights = {}
    
    # Get all weights for this course
    weights = ExamWeight.query.filter_by(course_id=course_id).all()
    for weight in weights:
        exam_weights[weight.exam_id] = weight.weight
    
    # Check all regular exams have weights
    for exam in regular_exams:
        if exam.id not in exam_weights:
            exam_weights[exam.id] = Decimal('0')
        total_weight += exam_weights[exam.id]
    
    # Normalize weights if they don't add up to 1.0
    normalized_weights = {}
    for exam_id, weight in exam_weights.items():
        if total_weight > Decimal('0'):
            normalized_weights[exam_id] = weight / total_weight
        else:
            normalized_weights[exam_id] = weight
    
    # Create maps for efficient lookups
    # Create a map of exams to their questions
    questions_by_exam = {}
    for exam in all_exams:
        questions_by_exam[exam.id] = exam.questions
    
    # Create a map of course outcomes to their related questions
    outcome_questions = {}
    for co in course_outcomes:
        outcome_questions[co.id] = co.questions
    
    # Create a map of program outcomes to their related course outcomes
    program_to_course_outcomes = {}
    for po in program_outcomes:
        related_cos = [co for co in course_outcomes if po in co.program_outcomes]
        program_to_course_outcomes[po.id] = related_cos
    
    # Create a map from original exam to makeup exam
    makeup_map = {}
    for makeup in makeup_exams:
        if makeup.makeup_for:
            makeup_map[makeup.makeup_for] = makeup
    
    # Preload all scores for all exams and students
    scores_dict = {}
    student_ids = [s.id for s in students]
    exam_ids = [e.id for e in all_exams]
    
    # Query all scores for these students and exams
    if student_ids and exam_ids:
        all_scores = Score.query.filter(
            Score.student_id.in_(student_ids),
            Score.exam_id.in_(exam_ids)
        ).all()
        
        # Build a dictionary for O(1) lookups
        for score in all_scores:
            scores_dict[(score.student_id, score.question_id, score.exam_id)] = score.score
    
    # Preload attendance information
    attendance_dict = {}
    if student_ids and exam_ids:
        attendances = StudentExamAttendance.query.filter(
            StudentExamAttendance.student_id.in_(student_ids),
            StudentExamAttendance.exam_id.in_(exam_ids)
        ).all()
        
        for attendance in attendances:
            attendance_dict[(attendance.student_id, attendance.exam_id)] = attendance.attended
    
    # Calculate student results
    student_results = {}
    success_count = 0
    total_valid_students = 0
    
    for student in students:
        # Initialize student data
        student_data = {
            'student_id': student.student_id,
            'name': f"{student.first_name} {student.last_name}".strip(),
            'course_outcomes': {},
            'program_outcomes': {},
            'weighted_score': Decimal('0'),
            'skip': False,
            'excluded': getattr(student, 'excluded', False)
        }
        
        # Check if student should be excluded due to excluded flag
        if student_data['excluded']:
            student_data['skip'] = True
            student_results[student.id] = student_data
            continue
        
        # Check if student should be excluded due to mandatory exam policy
        if mandatory_exams:
            skip_student = False
            for exam in mandatory_exams:
                # Check if student attended the regular exam (default to True if no record)
                regular_attended = attendance_dict.get((student.id, exam.id), True)
                
                # Check if there's a makeup exam for this mandatory exam
                makeup_exam = next((m for m in makeup_exams if m.makeup_for == exam.id), None)
                makeup_attended = False
                
                if makeup_exam:
                    # FIXED: For makeup exams, default to attended (True) if no record
                    makeup_attended = attendance_dict.get((student.id, makeup_exam.id), True)
                
                # FIXED: If student attended either the regular exam OR its makeup, they satisfy the attendance requirement
                # Only skip if they missed BOTH the regular exam AND its makeup
                if not regular_attended and (not makeup_exam or not makeup_attended):
                    skip_student = True
                    break
            
            if skip_student:
                student_data['skip'] = True
                student_data['missing_mandatory'] = True  # Add flag for UI to show
                student_results[student.id] = student_data
                continue
        
        # Calculate total weighted score
        total_weighted_score = Decimal('0')
        
        for exam in regular_exams:
            # Check if there's a makeup for this exam
            makeup_exam = next((m for m in makeup_exams if m.makeup_for == exam.id), None)
            
            # If there's a makeup exam, check if student attended it
            if makeup_exam:
                # FIXED: Changed to properly check attendance without requiring valid scores
                makeup_attended = attendance_dict.get((student.id, makeup_exam.id), True)  # Default to True
                
                # If student attended the makeup, use that score exclusively
                if makeup_attended:
                    makeup_score = calculate_student_exam_score_optimized(
                        student.id, makeup_exam.id, scores_dict, 
                        questions_by_exam[makeup_exam.id], attendance_dict
                    )
                    # Use makeup score even if it's 0 (as long as it's not None)
                    if makeup_score is not None:
                        total_weighted_score += makeup_score * normalized_weights.get(exam.id, Decimal('0'))
                        continue  # Skip the original exam completely
                    else:
                        # Even if makeup score is None, still skip original exam if student attended makeup
                        # This ensures we completely ignore the original exam score
                        makeup_score = Decimal('0')
                        total_weighted_score += makeup_score * normalized_weights.get(exam.id, Decimal('0'))
                        continue
            
            # If no makeup was attended or makeup score is None, use regular exam score
            exam_score = calculate_student_exam_score_optimized(
                student.id, exam.id, scores_dict,
                questions_by_exam[exam.id], attendance_dict
            )
            
            # For non-mandatory exams, ensure None is treated as 0
            if exam_score is None and not exam.is_mandatory:
                exam_score = Decimal('0')
                
            if exam_score is not None:
                total_weighted_score += exam_score * normalized_weights.get(exam.id, Decimal('0'))
        
        student_data['weighted_score'] = total_weighted_score
        
        # Calculate course outcome scores
        for outcome in course_outcomes:
            co_score = calculate_course_outcome_score_optimized(
                student.id, outcome.id, scores_dict, outcome_questions, normalized_weights, attendance_dict
            )
            student_data['course_outcomes'][outcome.id] = co_score
        
        # Calculate program outcome scores
        for outcome in program_outcomes:
            po_score = calculate_program_outcome_score_optimized(
                student.id, outcome.id, course_id, scores_dict, 
                program_to_course_outcomes, outcome_questions, normalized_weights, attendance_dict
            )
            student_data['program_outcomes'][outcome.id] = po_score
        
        # Store student results
        student_results[student.id] = student_data
        
        # Track student totals for relative method calculation
        total_valid_students += 1
        if total_weighted_score >= settings.relative_success_threshold:
            success_count += 1
    
    # Calculate program outcome scores based on method
    program_outcome_scores = {}
    
    for outcome in program_outcomes:
        # Only include valid students in the scores calculation
        valid_scores = [r['program_outcomes'][outcome.id] for r in student_results.values() 
                       if not r.get('skip') and r['program_outcomes'][outcome.id] is not None]
        
        if valid_scores:
            if calculation_method == 'absolute':
                # For absolute method: average of all student scores
                avg_score = sum(valid_scores) / len(valid_scores)
                program_outcome_scores[outcome.id] = avg_score
            else:  # 'relative'
                # For relative method: percentage of students who achieved the threshold
                success_students = sum(1 for score in valid_scores if score >= settings.relative_success_threshold)
                success_rate = (success_students / len(valid_scores) * 100) if len(valid_scores) > 0 else 0
                program_outcome_scores[outcome.id] = success_rate
        else:
            program_outcome_scores[outcome.id] = Decimal('0')
    
    # Calculate course outcome scores based on student data
    course_outcome_scores = {}
    
    for outcome in course_outcomes:
        # Only include valid students in the scores calculation - exclude those with skip=True
        valid_scores = [r['course_outcomes'][outcome.id] for r in student_results.values() 
                      if not r.get('skip') and r['course_outcomes'][outcome.id] is not None]
        
        if valid_scores:
            if calculation_method == 'absolute':
                # For absolute method: average of all student scores
                avg_score = sum(valid_scores) / len(valid_scores)
                course_outcome_scores[outcome.id] = avg_score
            else:  # 'relative'
                # For relative method: percentage of students who achieved the threshold
                success_students = sum(1 for score in valid_scores if score >= settings.relative_success_threshold)
                success_rate = (success_students / len(valid_scores) * 100) if len(valid_scores) > 0 else 0
                course_outcome_scores[outcome.id] = success_rate
        else:
            course_outcome_scores[outcome.id] = Decimal('0')
    
    # Return the results
    return {
        'program_outcome_scores': program_outcome_scores,
        'course_outcome_scores': course_outcome_scores,
        'contributing_po_ids': contributing_po_ids,
        'is_valid_for_aggregation': True,
        'student_count_used': total_valid_students,
        'course': course,
        'student_results': student_results  # Include the student results
    }

@calculation_bp.route('/course/<int:course_id>/debug')
def debug_calculations(course_id):
    """Debug route to show calculation data"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()
    makeup_exams = Exam.query.filter_by(course_id=course_id, is_makeup=True).all()
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    program_outcomes = ProgramOutcome.query.all()
    students = Student.query.filter_by(course_id=course_id).all()
    
    # Get exam weights
    weights = {}
    total_weight = Decimal('0')
    for exam in exams:
        weight = ExamWeight.query.filter_by(exam_id=exam.id).first()
        if weight:
            weights[exam.id] = weight.weight
            total_weight += weight.weight
        else:
            weights[exam.id] = Decimal('0')
    
    # Create a map of exams to their questions
    questions_by_exam = {}
    for exam in exams + makeup_exams:
        questions_by_exam[exam.id] = exam.questions
    
    # Create a map of course outcomes to their related questions
    outcome_questions = {}
    for co in course_outcomes:
        outcome_questions[co.id] = co.questions
    
    # Create a map of program outcomes to their related course outcomes
    program_to_course_outcomes = {}
    for po in program_outcomes:
        related_cos = [co for co in course_outcomes if po in co.program_outcomes]
        program_to_course_outcomes[po.id] = related_cos
    
    # Preload all scores for this course
    student_ids = [s.id for s in students]
    exam_ids = [e.id for e in exams + makeup_exams]
    scores_dict = {}
    
    if student_ids and exam_ids:
        scores = Score.query.filter(
            Score.student_id.in_(student_ids),
            Score.exam_id.in_(exam_ids)
        ).all()
        
        for score in scores:
            key = (score.student_id, score.question_id, score.exam_id)
            scores_dict[key] = score.score
    
    # Preload attendance information
    attendance_dict = {}
    if student_ids and exam_ids:
        attendances = StudentExamAttendance.query.filter(
            StudentExamAttendance.student_id.in_(student_ids),
            StudentExamAttendance.exam_id.in_(exam_ids)
        ).all()
        
        for attendance in attendances:
            attendance_dict[(attendance.student_id, attendance.exam_id)] = attendance.attended
    
    # Calculate student results
    student_results = {}
    for student in students:
        # Initialize results for this student
        student_results[student.id] = {
            'student': student,
            'exam_scores': {},  # Raw scores per exam
            'weighted_score': Decimal('0'),  # Final weighted score
            'course_outcome_scores': {},  # Scores per course outcome
            'program_outcome_scores': {},  # Scores per program outcome
            'skip': False,  # Track if student should be excluded from calculations
            'missing_mandatory': False,
            'excluded': student.excluded  # Add excluded flag
        }
        
        # Skip student if manually excluded
        if student.excluded:
            student_results[student.id]['skip'] = True
            student_results[student.id]['missing_mandatory'] = True
            student_results[student.id]['overall_percentage'] = 0
            continue

        # Check if student should be skipped due to mandatory exam policy
        if mandatory_exams:
            skip_student = False
            for exam in mandatory_exams:
                # Check if student attended the regular exam
                regular_attended = attendance_dict.get((student.id, exam.id), True)
                regular_score = None
                if regular_attended:
                    regular_score = calculate_student_exam_score_optimized(
                        student.id, exam.id, scores_dict, questions_by_exam[exam.id], attendance_dict
                    )
                
                # Check if there's a makeup exam for this mandatory exam
                makeup_exam = next((m for m in makeup_exams if m.makeup_for == exam.id), None)
                makeup_attended = False
                makeup_score = None
                
                if makeup_exam:
                    # FIXED: For makeup exams, default to attended (True) if no record
                    makeup_attended = attendance_dict.get((student.id, makeup_exam.id), True)
                    if makeup_attended:
                        makeup_score = calculate_student_exam_score_optimized(
                            student.id, makeup_exam.id, scores_dict, questions_by_exam[makeup_exam.id], attendance_dict
                        )
                
                # Skip student if they missed both the mandatory exam and its makeup (if exists)
                if (not regular_attended or regular_score is None) and (not makeup_exam or not makeup_attended or makeup_score is None):
                    skip_student = True
                    break
            
            if skip_student:
                student_results[student.id]['skip'] = True
                student_results[student.id]['missing_mandatory'] = True
                student_results[student.id]['overall_percentage'] = 0
                student_results[student.id] = student_results[student.id]
                continue
        
        # Calculate exam scores for student
        for exam in exams:
            # Check if there's a makeup for this exam
            makeup_exam = next((m for m in makeup_exams if m.makeup_for == exam.id), None)
            
            # If there's a makeup exam, check if student attended it
            if makeup_exam:
                # FIXED: Default to attended (True) if no record exists
                makeup_attended = attendance_dict.get((student.id, makeup_exam.id), True)
                
                # If student attended the makeup, use that score exclusively
                if makeup_attended:
                    makeup_score = calculate_student_exam_score_optimized(
                        student.id, makeup_exam.id, scores_dict, 
                        questions_by_exam[makeup_exam.id], attendance_dict
                    )
                    # Use makeup score even if it's 0 (as long as it's not None)
                    if makeup_score is not None:
                        student_results[student.id]['exam_scores'][exam.id] = makeup_score
                        continue
                
                # Even if makeup score is None, if student attended makeup, use 0 and skip original
                student_results[student.id]['exam_scores'][exam.id] = Decimal('0')
                continue
            
            # If no makeup was attended or makeup score is None, use regular exam score
            exam_score = calculate_student_exam_score_optimized(
                student.id, exam.id, scores_dict,
                questions_by_exam[exam.id], attendance_dict
            )
            
            # For non-mandatory exams, ensure None is treated as 0
            if exam_score is None and not exam.is_mandatory:
                exam_score = Decimal('0')
                
            if exam_score is not None:
                student_results[student.id]['exam_scores'][exam.id] = exam_score
        
        # Calculate weighted score using normalized weights
        weighted_score = Decimal('0')
        total_used_weight = Decimal('0')
        
        for exam_id, score in student_results[student.id]['exam_scores'].items():
            # Ensure weight exists before calculation
            if exam_id in weights:
                weighted_score += score * weights[exam_id]
                total_used_weight += weights[exam_id]
            else:
                print(f"Debug Warning: Missing weight for exam_id {exam_id} for student {student.id}")

        # Normalize the weighted score if total_used_weight doesn't equal total_weight
        if total_used_weight > Decimal('0') and total_used_weight != total_weight:
            weighted_score = weighted_score / total_used_weight * total_weight

        student_results[student.id]['weighted_score'] = weighted_score
        
        # Calculate course outcome scores
        for outcome in course_outcomes:
            score = calculate_course_outcome_score_optimized(
                student.id, outcome.id, scores_dict, outcome_questions, normalized_weights, attendance_dict
            )
            student_results[student.id]['course_outcome_scores'][outcome.id] = score
        
        # Calculate program outcome scores
        for outcome in program_outcomes:
            score = calculate_program_outcome_score_optimized(
                student.id, outcome.id, course_id, scores_dict, program_to_course_outcomes, outcome_questions, normalized_weights, attendance_dict
            )
            student_results[student.id]['program_outcome_scores'][outcome.id] = score
    
    # Calculate average scores for the whole class
    class_results = {
        'course_outcome_scores': {},
        'program_outcome_scores': {}
    }
    
    # Calculate average course outcome scores
    for outcome in course_outcomes:
        scores = [r['course_outcome_scores'][outcome.id] for r in student_results.values() 
                 if r['course_outcome_scores'][outcome.id] is not None]
        if scores:
            class_results['course_outcome_scores'][outcome.id] = sum(scores) / len(scores)
        else:
            class_results['course_outcome_scores'][outcome.id] = None
    
    # Calculate average program outcome scores
    for outcome in program_outcomes:
        scores = [r['program_outcome_scores'][outcome.id] for r in student_results.values() 
                 if r['program_outcome_scores'][outcome.id] is not None]
        if scores:
            class_results['program_outcome_scores'][outcome.id] = sum(scores) / len(scores)
        else:
            class_results['program_outcome_scores'][outcome.id] = None
    
    # Create course_outcome_results and program_outcome_results for template
    course_outcome_results = {}
    program_outcome_results = {}
    
    # Format course outcome results
    for outcome in course_outcomes:
        avg_score = class_results['course_outcome_scores'].get(outcome.id)
        course_outcome_results[outcome.code] = {
            'description': outcome.description,
            'percentage': avg_score if avg_score is not None else 0,
            'program_outcomes': [po.code for po in outcome.program_outcomes],
            'achievement_level': get_achievement_level(float(avg_score) if avg_score is not None else 0, achievement_levels)
        }
    
    # Format program outcome results
    for outcome in program_outcomes:
        avg_score = class_results['program_outcome_scores'].get(outcome.id)
        
        # Check if this program outcome is linked to any course outcomes for this course
        contributes = False
        for co in course.course_outcomes:
            if outcome in co.program_outcomes:
                contributes = True
                break
                
        program_outcome_results[outcome.code] = {
            'description': outcome.description,
            'percentage': avg_score if avg_score is not None else 0,
            'contributes': contributes,
            'achievement_level': get_achievement_level(float(avg_score) if avg_score is not None else 0, achievement_levels)
        }
    
    # Format student results for template
    formatted_student_results = {}
    for student_id, data in student_results.items():
        if 'student' in data:
            student = data['student']
            
            # Format course outcome scores - ensure percentages are numbers not dictionaries
            course_outcome_scores = {}
            for outcome in course_outcomes:
                percentage = data['course_outcome_scores'].get(outcome.id)
                course_outcome_scores[outcome.code] = percentage if percentage is not None else 0
            
            # Format exam scores to include names
            exam_scores = {}
            for exam_id, score in data['exam_scores'].items():
                exam = next((e for e in exams if e.id == exam_id), None)
                if exam:
                    exam_scores[exam.name] = score
            
            formatted_student_results[student_id] = {
                'student_id': student.student_id,
                'name': f"{student.first_name} {student.last_name}".strip(),
                'overall_percentage': data.get('weighted_score', 0),
                'course_outcomes': course_outcome_scores,
                'exam_scores': exam_scores,
                'excluded': getattr(student, 'excluded', False)
            }
    
    # Check if questions are linked to course outcomes
    has_exam_questions = False
    for exam in exams:
        questions = Question.query.filter_by(exam_id=exam.id).all()
        for question in questions:
            if question.course_outcomes:
                has_exam_questions = True
                break
        if has_exam_questions:
            break
    
    # Check if we have student scores
    has_student_scores = Score.query.join(Question).join(Exam).filter(Exam.course_id == course_id).first() is not None
    
    # Check if weights are valid
    has_valid_weights = abs(total_weight - Decimal('1.0')) <= Decimal('0.01')
   
    # Create a debug response
    debug_info = {
        'course': {
            'id': course.id,
            'code': course.code,
            'name': course.name
        },
        'exams': [{'id': exam.id, 'name': exam.name} for exam in exams],
        'makeup_exams': [{'id': exam.id, 'name': exam.name} for exam in makeup_exams],
        'course_outcomes': [{'id': co.id, 'code': co.code} for co in course_outcomes],
        'program_outcomes': [{'id': po.id, 'code': po.code} for po in program_outcomes],
        'students': [{'id': s.id, 'student_id': s.student_id, 'name': f"{s.first_name} {s.last_name}"} for s in students],
        'weights': {str(k): float(v) for k, v in weights.items()},
        'total_weight': float(total_weight),
        'has_exam_questions': has_exam_questions,
        'has_student_scores': has_student_scores,
        'has_valid_weights': has_valid_weights,
        'scores_count': len(scores_dict),
        'student_results_count': len(student_results),
        'formatted_student_results_count': len(formatted_student_results),
        'course_outcome_results': {k: {
            'description': v['description'][:30] + '...' if len(v['description']) > 30 else v['description'],
            'percentage': float(v['percentage']),
            'program_outcomes_count': len(v['program_outcomes'])
        } for k, v in course_outcome_results.items()},
        'program_outcome_results': {k: {
            'description': v['description'][:30] + '...' if len(v['description']) > 30 else v['description'],
            'percentage': float(v['percentage']),
            'course_outcomes_count': len(v['course_outcomes'])
        } for k, v in program_outcome_results.items()}
    }
    
    # Format as pre-formatted text
    import json
    debug_html = f"<pre>{json.dumps(debug_info, indent=4)}</pre>"
    
    # Generate chart data to check if it's valid
    chart_data = {
        'po_labels': [po_code for po_code in program_outcome_results],
        'po_data': [float(po_data['percentage']) for _, po_data in program_outcome_results.items()],
        'co_labels': [co_code for co_code in course_outcome_results],
        'co_data': [float(co_data['percentage']) for _, co_data in course_outcome_results.items()],
    }
    
    chart_html = f"<h2>Chart Data</h2><pre>{json.dumps(chart_data, indent=4)}</pre>"
    
    # Check the JS script that would be generated for charts
    po_chart_js = """
    <script>
        // Program Outcomes Chart
        const poCtx = document.getElementById('programOutcomesChart').getContext('2d');
        const poChart = new Chart(poCtx, {
            type: 'bar',
            data: {
                labels: [
                    """ + ", ".join([f"'{po_code}'" for po_code in program_outcome_results]) + """
                ],
                datasets: [{
                    label: 'Achievement Level (%)',
                    data: [
                        """ + ", ".join([f"{po_data['percentage']:.1f}" for _, po_data in program_outcome_results.items()]) + """
                    ],
                    backgroundColor: [
                        """ + ", ".join([f"'rgba(40, 167, 69, 0.7)'" if po_data['percentage'] >= 70 else 
                                       f"'rgba(255, 193, 7, 0.7)'" if po_data['percentage'] >= 50 else
                                       f"'rgba(220, 53, 69, 0.7)'" for _, po_data in program_outcome_results.items()]) + """
                    ],
                    borderColor: [
                        """ + ", ".join([f"'rgba(40, 167, 69, 1)'" if po_data['percentage'] >= 70 else 
                                       f"'rgba(255, 193, 7, 1)'" if po_data['percentage'] >= 50 else
                                       f"'rgba(220, 53, 69, 1)'" for _, po_data in program_outcome_results.items()]) + """
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Achievement Level (%)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Program Outcomes'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Program Outcome Achievement Levels',
                        font: {
                            size: 16
                        }
                    }
                }
            }
        });
    </script>
    """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Debug Calculation Data</title>
        <style>
            pre {{ max-height: 500px; overflow: auto; }}
        </style>
    </head>
    <body>
        <h1>Debug Calculation Data for {course.code}</h1>
        {debug_html}
        
        {chart_html}
        
        <h2>Generated Chart.js code (for Program Outcomes)</h2>
        <pre>{po_chart_js}</pre>
    </body>
    </html>
    """ 

@calculation_bp.route('/course/<int:course_id>/export_exams')
def export_course_exams(course_id):
    """Export exam details for a course to CSV, including proper makeup exam relationships"""
    course = Course.query.get_or_404(course_id)
    
    # Get all exams for this course
    all_exams = Exam.query.filter_by(course_id=course_id).all()
    
    # Fix any makeup exams with missing relationships
    makeup_exams = [exam for exam in all_exams if exam.is_makeup and exam.makeup_for is None]
    for makeup_exam in makeup_exams:
        name = makeup_exam.name.lower()
        if name.startswith("makeup"):
            base_name = name[6:].strip()  # Remove "Makeup" and any spaces
            
            # Find a matching exam
            for exam in all_exams:
                if not exam.is_makeup and exam.name.lower() == base_name:
                    makeup_exam.makeup_for = exam.id
                    db.session.add(makeup_exam)
                    break
            
            # If exact match not found, try fuzzy matching
            if makeup_exam.makeup_for is None:
                for exam in all_exams:
                    if not exam.is_makeup and base_name in exam.name.lower():
                        makeup_exam.makeup_for = exam.id
                        db.session.add(makeup_exam)
                        break
    
    # Commit any fixes
    if makeup_exams:
        try:
            db.session.commit()
            print(f"Fixed {len(makeup_exams)} makeup exam relationships")
        except Exception as e:
            db.session.rollback()
            print(f"Error fixing makeup exams: {str(e)}")
    
    # Prepare data for export
    headers = ['Exam Name', 'Max Score', 'Date', 'Question Count', 'Is Makeup', 'Makeup For']
    
    # Create a mapping of exam IDs to exam names for lookup
    exam_name_map = {exam.id: exam.name for exam in all_exams}
    
    # Add exam data as a list of dictionaries
    data = []
    
    for exam in all_exams:
        question_count = Question.query.filter_by(exam_id=exam.id).count()
        
        # Get makeup information
        is_makeup = "Yes" if exam.is_makeup else "No"
        makeup_for = "N/A"
        
        # If this is a makeup exam, get the original exam name
        if exam.is_makeup and exam.makeup_for:
            makeup_for = exam_name_map.get(exam.makeup_for, "N/A")
        
        # Create a dictionary for this exam
        exam_data = {
            'Exam Name': exam.name,
            'Max Score': float(exam.max_score) if exam.max_score else 0,
            'Date': exam.exam_date.strftime('%m/%d/%Y') if exam.exam_date else 'N/A',
            'Question Count': question_count,
            'Is Makeup': is_makeup,
            'Makeup For': makeup_for
        }
        
        data.append(exam_data)
    
    # Log export action
    log = Log(action="EXPORT_EXAMS", 
             description=f"Exported exam details for course: {course.code}")
    db.session.add(log)
    db.session.commit()
    
    # Export data as a list of dictionaries
    return export_to_excel_csv(data, f"exams_{course.code}", headers)

@calculation_bp.route('/all_utilities')
def all_utilities():
    """Redirect to the utilities page"""
    return redirect(url_for('utility.index'))

@calculation_bp.route('/course/<int:course_id>/achievement-levels', methods=['GET', 'POST'])
def manage_achievement_levels(course_id):
    """Manage achievement levels for a course"""
    course = Course.query.get_or_404(course_id)
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    if request.method == 'POST':
        # Process form submission
        action = request.form.get('action')
        level_id = request.form.get('level_id')
        
        if action == 'save':
            # Validate form input
            name = request.form.get('name', '').strip()
            min_score = request.form.get('min_score', '')
            max_score = request.form.get('max_score', '')
            color = request.form.get('color', '')
            
            # Validate inputs
            if not name:
                flash("Level name is required", "error")
                return redirect(url_for('calculation.manage_achievement_levels', course_id=course_id))
            
            try:
                min_score = float(min_score)
                max_score = float(max_score)
                
                if min_score < 0 or min_score > 100:
                    flash("Minimum score must be between 0 and 100", "error")
                    return redirect(url_for('calculation.manage_achievement_levels', course_id=course_id))
                
                if max_score < 0 or max_score > 100:
                    flash("Maximum score must be between 0 and 100", "error")
                    return redirect(url_for('calculation.manage_achievement_levels', course_id=course_id))
                
                if min_score >= max_score:
                    flash("Minimum score must be less than maximum score", "error")
                    return redirect(url_for('calculation.manage_achievement_levels', course_id=course_id))
                
            except ValueError:
                flash("Score values must be valid numbers", "error")
                return redirect(url_for('calculation.manage_achievement_levels', course_id=course_id))
            
            # Validate color
            valid_colors = ['primary', 'secondary', 'success', 'danger', 'warning', 'info', 'dark']
            if color not in valid_colors:
                flash("Invalid color selected", "error")
                return redirect(url_for('calculation.manage_achievement_levels', course_id=course_id))
            
            # Check for overlapping ranges with other levels
            query = AchievementLevel.query.filter_by(course_id=course_id)
            if level_id:
                query = query.filter(AchievementLevel.id != level_id)
            
            for existing_level in query.all():
                # Check if ranges overlap
                if (min_score <= existing_level.max_score and max_score >= existing_level.min_score):
                    flash(f"Score range overlaps with existing level '{existing_level.name}' ({existing_level.min_score}% - {existing_level.max_score}%)", "error")
                    return redirect(url_for('calculation.manage_achievement_levels', course_id=course_id))
            
            # Save new or update existing
            try:
                if level_id:
                    level = AchievementLevel.query.get_or_404(level_id)
                    level.name = name
                    level.min_score = min_score
                    level.max_score = max_score
                    level.color = color
                    level.updated_at = datetime.now()
                    
                    # Log action
                    log_action = "EDIT_ACHIEVEMENT_LEVEL"
                    log_description = f"Edited achievement level '{name}' for course: {course.code}"
                else:
                    level = AchievementLevel(
                        course_id=course_id,
                        name=name,
                        min_score=min_score,
                        max_score=max_score,
                        color=color
                    )
                    db.session.add(level)
                    
                    # Log action
                    log_action = "ADD_ACHIEVEMENT_LEVEL"
                    log_description = f"Added achievement level '{name}' to course: {course.code}"
                
                # Log action
                log = Log(action=log_action, description=log_description)
                db.session.add(log)
                
                db.session.commit()
                flash(f"Achievement level '{name}' saved successfully", 'success')
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error saving achievement level: {str(e)}")
                flash(f"Error saving achievement level: {str(e)}", 'error')
            
            return redirect(url_for('calculation.manage_achievement_levels', course_id=course_id))
            
        elif action == 'delete':
            try:
                level = AchievementLevel.query.get_or_404(level_id)
                level_name = level.name
                
                # Log action before deletion
                log = Log(action="DELETE_ACHIEVEMENT_LEVEL", 
                         description=f"Deleted achievement level '{level_name}' from course: {course.code}")
                db.session.add(log)
                
                db.session.delete(level)
                db.session.commit()
                flash(f"Achievement level '{level_name}' deleted successfully", 'success')
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error deleting achievement level: {str(e)}")
                flash(f"Error deleting achievement level: {str(e)}", 'error')
            
            return redirect(url_for('calculation.manage_achievement_levels', course_id=course_id))
    
    # For GET request, check if we need to set up default levels
    if not achievement_levels:
        # Add default achievement levels
        default_levels = [
            {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
            {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
            {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
            {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
            {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
        ]
        
        for level_data in default_levels:
            level = AchievementLevel(
                course_id=course_id,
                name=level_data["name"],
                min_score=level_data["min_score"],
                max_score=level_data["max_score"],
                color=level_data["color"]
            )
            db.session.add(level)
        
        # Log action
        log = Log(action="ADD_DEFAULT_ACHIEVEMENT_LEVELS", 
                 description=f"Added default achievement levels to course: {course.code}")
        db.session.add(log)
        db.session.commit()
        
        # Refresh achievement levels
        achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    return render_template('calculation/achievement_levels.html', 
                         course=course, 
                         achievement_levels=achievement_levels, 
                         active_page='courses') 

@calculation_bp.route('/course/<int:course_id>/export_student_results')
def export_student_results(course_id):
    """Export detailed student results including exam scores and course outcome achievements"""
    course = Course.query.get_or_404(course_id)
    
    # Get sorting parameters from query string
    sort_by = request.args.get('sort_by', '')
    sort_direction = request.args.get('sort_direction', 'asc')
    
    # Get regular and makeup exams separately
    regular_exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).order_by(Exam.created_at).all()
    makeup_exams = Exam.query.filter_by(course_id=course_id, is_makeup=True).order_by(Exam.created_at).all()
    
    # Combined list of all exams
    all_exams = regular_exams + makeup_exams
    
    # Create a map from original exam to makeup exam
    makeup_map = {}
    for makeup in makeup_exams:
        if makeup.makeup_for:
            makeup_map[makeup.makeup_for] = makeup
    
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()
    
    # Apply student sorting based on parameters (we'll sort the final data later)
    students = Student.query.filter_by(course_id=course_id)
    
    # Default sorting for students when retrieving from database
    if sort_by == 'student_id':
        students = students.order_by(Student.student_id.asc() if sort_direction == 'asc' else Student.student_id.desc())
    elif sort_by == 'name':
        students = students.order_by(
            Student.first_name.asc() if sort_direction == 'asc' else Student.first_name.desc(),
            Student.last_name.asc() if sort_direction == 'asc' else Student.last_name.desc()
        )
    else:
        # Default sort by student_id if not sorting by overall_score (which we'll handle later)
        students = students.order_by(Student.student_id)
    
    students = students.all()
    
    # Get achievement levels for this course
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    # Get the calculated results which are used for the display
    results = calculate_single_course_results(course_id)
    student_results = results.get('student_results', {})
    
    # Get exam weights
    weights = {}
    total_weight = Decimal('0')
    for exam in regular_exams:
        weight = ExamWeight.query.filter_by(exam_id=exam.id).first()
        if weight:
            weights[exam.id] = weight.weight
            total_weight += weight.weight
        else:
            weights[exam.id] = Decimal('0')
    
    # Calculate normalized weights
    normalized_weights = {}
    if total_weight > Decimal('0'):
        for exam_id, weight in weights.items():
            normalized_weights[exam_id] = weight / total_weight
    
    # Prepare scores for calculating exam percentages - this matches the course_calculations method
    # Get scores for all students for each regular exam
    exam_scores_dict = {}
    exam_max_scores = {}  # Store max scores for each exam
    
    for exam in regular_exams:
        # Calculate max possible score for this exam
        questions = Question.query.filter_by(exam_id=exam.id).all()
        exam_max_scores[exam.id] = sum(float(q.max_score) for q in questions) if questions else 0
        
        # Get all scores for this exam
        exam_scores = Score.query.filter_by(exam_id=exam.id).all()
        
        # Initialize dictionary for this exam
        student_total_scores = {}
        
        # Sum up scores for each student across all questions
        for score in exam_scores:
            if score.student_id not in student_total_scores:
                student_total_scores[score.student_id] = 0
            student_total_scores[score.student_id] += float(score.score)
        
        # Store the summed scores
        exam_scores_dict[exam.id] = student_total_scores
    
    # Get scores for all students for each makeup exam
    makeup_scores_dict = {}
    for exam in makeup_exams:
        # Calculate max possible score for this makeup exam
        questions = Question.query.filter_by(exam_id=exam.id).all()
        exam_max_scores[exam.id] = sum(float(q.max_score) for q in questions) if questions else 0
        
        # Get all scores for this makeup exam
        makeup_scores = Score.query.filter_by(exam_id=exam.id).all()
        
        # Initialize dictionary for this exam
        student_total_scores = {}
        
        # Sum up scores for each student across all questions
        for score in makeup_scores:
            if score.student_id not in student_total_scores:
                student_total_scores[score.student_id] = 0
            student_total_scores[score.student_id] += float(score.score)
        
        # Store the summed scores
        makeup_scores_dict[exam.id] = student_total_scores
    
    # Preload attendance information
    attendance_dict = {}
    student_ids = [s.id for s in students]
    exam_ids = [e.id for e in all_exams]
    
    if student_ids and exam_ids:
        attendances = StudentExamAttendance.query.filter(
            StudentExamAttendance.student_id.in_(student_ids),
            StudentExamAttendance.exam_id.in_(exam_ids)
        ).all()
        
        for attendance in attendances:
            attendance_dict[(attendance.student_id, attendance.exam_id)] = attendance.attended
    
    # Define headers for CSV
    headers = ['Student ID', 'Student Name']
    
    # Add exam score headers - include both regular and makeup exams
    for exam in regular_exams:
        headers.append(f'{exam.name} Score (%)')
        # Check if this exam has a makeup
        if exam.id in makeup_map:
            headers.append(f'{exam.name} - Used Makeup?')
            headers.append(f'{makeup_map[exam.id].name} Score (%)')
    
    # Add course outcome headers
    for co in course_outcomes:
        headers.append(f'{co.code} Achievement (%)')
        headers.append(f'{co.code} Achievement Level')
    
    # Add overall percentage header
    headers.append('Overall Weighted Score (%)')
    headers.append('Overall Achievement Level')
    
    # Prepare data rows for export
    data = []
    
    for student in students:
        # Skip excluded students
        if student.excluded:
            continue
        
        # Get pre-calculated data for this student
        student_data = student_results.get(student.id, {})
        if student_data.get('skip', False):
            continue
            
        # Prepare student row as a dictionary
        student_row = {
            'Student ID': student.student_id,
            'Student Name': f"{student.first_name} {student.last_name}".strip()
        }
        
        # Add exam scores using the same calculation as the display
        for exam in regular_exams:
            # Check if this exam has a makeup and if the student took the makeup
            use_makeup = False
            actual_exam_id = exam.id
            makeup_score = 0
            
            if exam.id in makeup_map:
                makeup_exam = makeup_map[exam.id]
                # Default to attended (True) if no record exists
                makeup_attended = attendance_dict.get((student.id, makeup_exam.id), True)
                
                # If student attended makeup, always use it regardless of scores
                if makeup_attended:
                    use_makeup = True
                    actual_exam_id = makeup_exam.id
                    
                    # Calculate makeup exam score
                    if actual_exam_id in makeup_scores_dict and student.id in makeup_scores_dict[actual_exam_id]:
                        raw_score = float(makeup_scores_dict[actual_exam_id][student.id])
                        max_score = exam_max_scores[actual_exam_id]
                        if max_score > 0:
                            makeup_score = (raw_score / max_score) * 100
                    
                    # Add makeup exam info to row
                    student_row[f'{exam.name} - Used Makeup?'] = 'Yes'
                    student_row[f'{makeup_exam.name} Score (%)'] = round(makeup_score, 2)
            
            # Calculate exam score
            exam_score = 0
            # If using makeup exam
            if use_makeup:
                exam_score = makeup_score
            else:
                # Use regular exam score
                if exam.id in exam_scores_dict and student.id in exam_scores_dict[exam.id]:
                    raw_score = float(exam_scores_dict[exam.id][student.id])
                    max_score = exam_max_scores[exam.id]
                    if max_score > 0:
                        exam_score = (raw_score / max_score) * 100
                
                # Add info that makeup wasn't used if there is a makeup for this exam
                if exam.id in makeup_map:
                    student_row[f'{exam.name} - Used Makeup?'] = 'No'
                    student_row[f'{makeup_map[exam.id].name} Score (%)'] = 'N/A'
            
            # Add regular exam score to row
            student_row[f'{exam.name} Score (%)'] = round(exam_score, 2)
        
        # Add course outcome scores from pre-calculated data
        for co in course_outcomes:
            co_id = co.id
            co_code = co.code
            
            # Get pre-calculated course outcome score
            co_score = student_data.get('course_outcomes', {}).get(co_id)
            
            if co_score is not None:
                # Add score and achievement level
                student_row[f'{co_code} Achievement (%)'] = round(float(co_score), 2)
                
                # Get achievement level
                level = get_achievement_level(float(co_score), achievement_levels)
                student_row[f'{co_code} Achievement Level'] = level['name']
            else:
                student_row[f'{co_code} Achievement (%)'] = "N/A"
                student_row[f'{co_code} Achievement Level'] = "N/A"
        
        # Get overall weighted score from pre-calculated data
        if 'weighted_score' in student_data:
            weighted_score = student_data['weighted_score']
            
            # Format for output
            student_row['Overall Weighted Score (%)'] = round(float(weighted_score), 2)
            
            # Get achievement level
            level = get_achievement_level(round(float(weighted_score), 2), achievement_levels)
            student_row['Overall Achievement Level'] = level['name']
            
            # Store the overall score for sorting
            student_row['_overall_score'] = float(weighted_score)
        else:
            student_row['Overall Weighted Score (%)'] = "N/A"
            student_row['Overall Achievement Level'] = "N/A"
            student_row['_overall_score'] = -1
        
        # Add row to data
        data.append(student_row)
    
    # Apply overall_score sorting if requested (needs to be done after all data is collected)
    if sort_by == 'overall_score':
        data.sort(
            key=lambda x: x['_overall_score'], 
            reverse=(sort_direction == 'desc')
        )
    
    # Remove sorting metadata field before exporting
    for row in data:
        if '_overall_score' in row:
            del row['_overall_score']
    
    # Log action
    log = Log(action="EXPORT_STUDENT_RESULTS", 
             description=f"Exported detailed student results for course: {course.code}")
    db.session.add(log)
    db.session.commit()
    
    # Export data using utility function
    return export_to_excel_csv(data, f"student_results_{course.code}", headers)

@calculation_bp.route('/course/<int:course_id>/student_score', methods=['GET'])
def get_student_score(course_id):
    """Get HTML for a student's score after their inclusion/exclusion status changes"""
    student_id = request.args.get('student_id')
    
    if not student_id:
        return jsonify({
            'success': False,
            'message': 'Student ID is required'
        }), 400
    
    try:
        # Load the course and student
        course = Course.query.get_or_404(course_id)
        student = Student.query.get_or_404(student_id)
        
        # Get the achievement levels for this course
        achievement_levels = get_achievement_levels(course_id)
        
        # Perform calculations to get the student's data
        results = calculate_course_results(course, recalculate=True)
        student_results = results.get('student_results', {})
        student_data = student_results.get(int(student_id))
        
        if not student_data:
            return jsonify({
                'success': False,
                'message': 'Student data not found'
            }), 404
        
        # Generate HTML for the score cell
        if student_data.get('excluded') or student_data.get('missing_mandatory'):
            score_html = '''
                <div class="alert alert-danger p-2 mb-0 d-flex align-items-center">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    <span>
                        <strong>{}</strong>
                        <small class="d-block text-muted">
                            <i class="fas fa-info-circle me-1"></i>Score calculations may be inaccurate
                        </small>
                    </span>
                </div>
            '''.format("Manually Excluded" if student_data.get('excluded') else "Missed Mandatory Exam")
        else:
            # Get the percentage and achievement level
            percentage = student_data.get('overall_percentage', 0)
            level = get_achievement_level(percentage, achievement_levels)
            
            score_html = '''
                <div class="progress" style="height: 25px;">
                    <div class="progress-bar bg-{}" 
                         role="progressbar" 
                         style="width: {}%;" 
                         aria-valuenow="{}" 
                         aria-valuemin="0" 
                         aria-valuemax="100">
                        {:.1f}% ({})
                    </div>
                </div>
            '''.format(
                level.get('color', 'secondary'),
                percentage,
                percentage,
                percentage,
                level.get('name', 'N/A')
            )
        
        # Generate HTML for the details section
        details_html = '''
            <div class="p-3 bg-light">
                <h6>Course Outcome Achievement for {}</h6>
                <div class="row">
        '''.format(student_data.get('name'))
        
        # Add course outcomes
        for co_code, percentage in student_data.get('course_outcomes', {}).items():
            level = get_achievement_level(percentage, achievement_levels)
            details_html += '''
                <div class="col-md-6 mb-2">
                    <small><strong>{}:</strong></small>
                    <div class="progress" style="height: 15px;">
                        <div class="progress-bar bg-{}" 
                             role="progressbar" 
                             style="width: {}%;" 
                             aria-valuenow="{}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                            {:.1f}%
                        </div>
                    </div>
                </div>
            '''.format(co_code, level.get('color', 'secondary'), percentage, percentage, percentage)
        
        details_html += '''
                </div>
                
                <h6 class="mt-3">Exam Scores</h6>
                <div class="row">
        '''
        
        # Add exam scores
        for exam_name, percentage in student_data.get('exam_scores', {}).items():
            level = get_achievement_level(percentage, achievement_levels)
            details_html += '''
                <div class="col-md-6 mb-2">
                    <small><strong>{}:</strong></small>
                    <div class="progress" style="height: 15px;">
                        <div class="progress-bar bg-{}" 
                             role="progressbar" 
                             style="width: {}%;" 
                             aria-valuenow="{}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                            {:.1f}%
                        </div>
                    </div>
                </div>
            '''.format(exam_name, level.get('color', 'secondary'), percentage, percentage, percentage)
        
        details_html += '''
                </div>
            </div>
        '''
        
        return jsonify({
            'success': True,
            'scoreHtml': score_html,
            'detailsHtml': details_html
        })
    
    except Exception as e:
        logging.error(f"Error getting student score: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while retrieving student data',
            'error': str(e)
        }), 500

def calculate_individual_student_results(student_id, course_id, bulk_data, calculation_method='absolute'):
    """Calculate program outcome scores for an individual student in a course"""
    course_data = bulk_data.get(course_id)
    if not course_data:
        return {}
    
    # Get the necessary data
    program_outcomes = course_data['program_outcomes']
    scores_dict = course_data['scores_dict']
    program_to_course_outcomes = course_data['program_to_course_outcomes']
    outcome_questions = course_data['outcome_questions']
    normalized_weights = course_data['normalized_weights']
    attendance_dict = course_data['attendance_dict']
    
    # Calculate program outcome scores for this specific student
    student_po_scores = {}
    for po in program_outcomes:
        po_score = calculate_program_outcome_score_optimized(
            student_id, po.id, course_id, scores_dict,
            program_to_course_outcomes, outcome_questions, 
            normalized_weights, attendance_dict
        )
        student_po_scores[po.id] = po_score
    
    return student_po_scores

# Helper function to calculate average outcome score
def calculate_avg_outcome_score(program_outcome_results):
    """Calculate the average program outcome score for a course"""
    # Include 0 values in the calculation, but still exclude None values
    valid_scores = [float(po_data['percentage']) for po_code, po_data in program_outcome_results.items() 
                   if po_data['contributes'] and po_data['percentage'] is not None]
    
    if valid_scores:
        return sum(valid_scores) / len(valid_scores)
    else:
        return 0.0

@calculation_bp.route('/course/<int:course_id>/exam/<exam_name>')
def redirect_to_exam(course_id, exam_name):
    """Redirects to the exam detail page from the results page when an exam name is clicked"""
    # Find the exam based on course_id and exam name
    exam = Exam.query.filter_by(course_id=course_id, name=exam_name).first_or_404()
    
    # Redirect to the exam detail page
    return redirect(url_for('exam.exam_detail', exam_id=exam.id))

@calculation_bp.route('/global-achievement-levels', methods=['GET', 'POST'])
def manage_global_achievement_levels():
    """Manage global achievement levels for all courses page"""
    # Get all existing global achievement levels
    achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
    
    # Handle POST request (form submission)
    if request.method == 'POST':
        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Check request type
        form_type = request.form.get('form_type', '')
        
        # Handle adding a new level
        if form_type == 'add_level':
            name = request.form.get('name', '')
            min_score = request.form.get('min_score', '')
            max_score = request.form.get('max_score', '')
            color = request.form.get('color', 'primary')
            
            # Validate input
            if not name or not min_score or not max_score:
                if is_ajax:
                    return jsonify({'success': False, 'message': 'All fields are required'})
                else:
                    flash('All fields are required', 'danger')
                    return redirect(url_for('calculation.manage_global_achievement_levels'))
            
            try:
                min_score = float(min_score)
                max_score = float(max_score)
                
                # Validate score ranges
                if min_score < 0 or min_score > 100 or max_score < 0 or max_score > 100:
                    if is_ajax:
                        return jsonify({'success': False, 'message': 'Score ranges must be between 0 and 100'})
                    else:
                        flash('Score ranges must be between 0 and 100', 'danger')
                        return redirect(url_for('calculation.manage_global_achievement_levels'))
                
                if min_score >= max_score:
                    if is_ajax:
                        return jsonify({'success': False, 'message': 'Minimum score must be less than maximum score'})
                    else:
                        flash('Minimum score must be less than maximum score', 'danger')
                        return redirect(url_for('calculation.manage_global_achievement_levels'))
                
                # Check for overlapping ranges
                for level in achievement_levels:
                    if (min_score <= float(level.max_score) and max_score >= float(level.min_score)):
                        if is_ajax:
                            return jsonify({'success': False, 'message': f'Score range overlaps with existing level: {level.name}'})
                        else:
                            flash(f'Score range overlaps with existing level: {level.name}', 'danger')
                            return redirect(url_for('calculation.manage_global_achievement_levels'))
                
                # Create new level
                new_level = GlobalAchievementLevel(
                    name=name,
                    min_score=min_score,
                    max_score=max_score,
                    color=color,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.session.add(new_level)
                
                # Log action
                log = Log(action="ADD_GLOBAL_ACHIEVEMENT_LEVEL", 
                         description=f"Added global achievement level: {name}")
                db.session.add(log)
                db.session.commit()
                
                if is_ajax:
                    return jsonify({'success': True, 'message': 'Achievement level added successfully'})
                else:
                    flash('Achievement level added successfully', 'success')
                    return redirect(url_for('calculation.manage_global_achievement_levels'))
            
            except ValueError:
                if is_ajax:
                    return jsonify({'success': False, 'message': 'Invalid score values'})
                else:
                    flash('Invalid score values', 'danger')
                    return redirect(url_for('calculation.manage_global_achievement_levels'))
        
        # Handle updating a level
        elif form_type == 'update_level':
            level_id = request.form.get('level_id', '')
            name = request.form.get('name', '')
            min_score = request.form.get('min_score', '')
            max_score = request.form.get('max_score', '')
            color = request.form.get('color', 'primary')
            
            # Validate input
            if not level_id or not name or not min_score or not max_score:
                if is_ajax:
                    return jsonify({'success': False, 'message': 'All fields are required'})
                else:
                    flash('All fields are required', 'danger')
                    return redirect(url_for('calculation.manage_global_achievement_levels'))
            
            try:
                level_id = int(level_id)
                min_score = float(min_score)
                max_score = float(max_score)
                
                # Get the level to update
                level = GlobalAchievementLevel.query.get(level_id)
                if not level:
                    if is_ajax:
                        return jsonify({'success': False, 'message': 'Achievement level not found'})
                    else:
                        flash('Achievement level not found', 'danger')
                        return redirect(url_for('calculation.manage_global_achievement_levels'))
                
                # Validate score ranges
                if min_score < 0 or min_score > 100 or max_score < 0 or max_score > 100:
                    if is_ajax:
                        return jsonify({'success': False, 'message': 'Score ranges must be between 0 and 100'})
                    else:
                        flash('Score ranges must be between 0 and 100', 'danger')
                        return redirect(url_for('calculation.manage_global_achievement_levels'))
                
                if min_score >= max_score:
                    if is_ajax:
                        return jsonify({'success': False, 'message': 'Minimum score must be less than maximum score'})
                    else:
                        flash('Minimum score must be less than maximum score', 'danger')
                        return redirect(url_for('calculation.manage_global_achievement_levels'))
                
                # Check for overlapping ranges with other levels
                for other_level in achievement_levels:
                    if other_level.id != level_id and (min_score <= float(other_level.max_score) and max_score >= float(other_level.min_score)):
                        if is_ajax:
                            return jsonify({'success': False, 'message': f'Score range overlaps with existing level: {other_level.name}'})
                        else:
                            flash(f'Score range overlaps with existing level: {other_level.name}', 'danger')
                            return redirect(url_for('calculation.manage_global_achievement_levels'))
                
                # Update level
                level.name = name
                level.min_score = min_score
                level.max_score = max_score
                level.color = color
                level.updated_at = datetime.now()
                
                # Log action
                log = Log(action="UPDATE_GLOBAL_ACHIEVEMENT_LEVEL", 
                         description=f"Updated global achievement level: {name}")
                db.session.add(log)
                db.session.commit()
                
                if is_ajax:
                    return jsonify({'success': True, 'message': 'Achievement level updated successfully'})
                else:
                    flash('Achievement level updated successfully', 'success')
                    return redirect(url_for('calculation.manage_global_achievement_levels'))
            
            except ValueError:
                if is_ajax:
                    return jsonify({'success': False, 'message': 'Invalid input values'})
                else:
                    flash('Invalid input values', 'danger')
                    return redirect(url_for('calculation.manage_global_achievement_levels'))
        
        # Handle deleting a level
        elif form_type == 'delete_level':
            level_id = request.form.get('level_id', '')
            
            if not level_id:
                if is_ajax:
                    return jsonify({'success': False, 'message': 'Achievement level ID is required'})
                else:
                    flash('Achievement level ID is required', 'danger')
                    return redirect(url_for('calculation.manage_global_achievement_levels'))
            
            try:
                level_id = int(level_id)
                
                # Get the level to delete
                level = GlobalAchievementLevel.query.get(level_id)
                if not level:
                    if is_ajax:
                        return jsonify({'success': False, 'message': 'Achievement level not found'})
                    else:
                        flash('Achievement level not found', 'danger')
                        return redirect(url_for('calculation.manage_global_achievement_levels'))
                
                # Store level name for log
                level_name = level.name
                
                # Delete the level
                db.session.delete(level)
                
                # Log action
                log = Log(action="DELETE_GLOBAL_ACHIEVEMENT_LEVEL", 
                         description=f"Deleted global achievement level: {level_name}")
                db.session.add(log)
                db.session.commit()
                
                if is_ajax:
                    return jsonify({'success': True, 'message': 'Achievement level deleted successfully'})
                else:
                    flash('Achievement level deleted successfully', 'success')
                    return redirect(url_for('calculation.manage_global_achievement_levels'))
            
            except ValueError:
                if is_ajax:
                    return jsonify({'success': False, 'message': 'Invalid achievement level ID'})
                else:
                    flash('Invalid achievement level ID', 'danger')
                    return redirect(url_for('calculation.manage_global_achievement_levels'))
        
        # Reset to default levels
        elif form_type == 'reset_to_default':
            # Delete all existing global achievement levels
            GlobalAchievementLevel.query.delete()
            
            # Add default global achievement levels
            default_levels = [
                {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
                {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
                {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
                {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
                {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
            ]
            
            for level_data in default_levels:
                level = GlobalAchievementLevel(
                    name=level_data["name"],
                    min_score=level_data["min_score"],
                    max_score=level_data["max_score"],
                    color=level_data["color"],
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.session.add(level)
            
            # Log action
            log = Log(action="RESET_GLOBAL_ACHIEVEMENT_LEVELS", 
                     description="Reset global achievement levels to default")
            db.session.add(log)
            db.session.commit()
            
            if is_ajax:
                return jsonify({'success': True, 'message': 'Global achievement levels reset to default'})
            else:
                flash('Global achievement levels reset to default', 'success')
                return redirect(url_for('calculation.manage_global_achievement_levels'))
    
    # For GET request, check if we need to set up default levels
    if not achievement_levels:
        # Add default achievement levels
        default_levels = [
            {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
            {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
            {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
            {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
            {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
        ]
        
        for level_data in default_levels:
            level = GlobalAchievementLevel(
                name=level_data["name"],
                min_score=level_data["min_score"],
                max_score=level_data["max_score"],
                color=level_data["color"],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.session.add(level)
        
        # Log action
        log = Log(action="ADD_DEFAULT_GLOBAL_ACHIEVEMENT_LEVELS", 
                 description="Added default global achievement levels")
        db.session.add(log)
        db.session.commit()
        
        # Refresh achievement levels
        achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
    
    return render_template('calculation/global_achievement_levels.html', 
                         achievement_levels=achievement_levels, 
                         active_page='all_courses')

@calculation_bp.route('/cross_course_outcomes', methods=['GET'])
def cross_course_outcomes():
    """
    Analyze and compare similar course outcomes across different courses
    using similarity matching and showing their success rates.
    """
    # Check if we need to set up default global achievement levels
    achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
    if not achievement_levels:
        # Add default achievement levels
        default_levels = [
            {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
            {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
            {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
            {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
            {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
        ]
        
        for level_data in default_levels:
            level = GlobalAchievementLevel(
                name=level_data["name"],
                min_score=level_data["min_score"],
                max_score=level_data["max_score"],
                color=level_data["color"],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.session.add(level)
        
        # Log action
        log = Log(action="ADD_DEFAULT_GLOBAL_ACHIEVEMENT_LEVELS", 
                 description="Added default global achievement levels from cross_course_outcomes page")
        db.session.add(log)
        db.session.commit()
    
    # Get similarity threshold from request parameter (default to 0.9 / 90%)
    raw_similarity = request.args.get('similarity', 90, type=float)
    # Convert from percentage to decimal (divide by 100)
    similarity_threshold = raw_similarity / 100
    # Get search query if any
    search_query = request.args.get('search', '')
    # Get sort parameter
    sort_by = request.args.get('sort', 'code_asc')
    # Get refresh parameter to force recalculation
    force_refresh = request.args.get('refresh', False, type=bool)
    # Get show non-grouped parameter (checkbox presence indicates True)
    show_non_grouped = 'show_non_grouped' in request.args
    
    print(f"DEBUG [cross_course_outcomes]: Request started - show_non_grouped={show_non_grouped}, force_refresh={force_refresh}")
    
    # Check if we have cached results from a previous calculation during this app runtime
    cached_results = getattr(cross_course_outcomes, 'cached_results', None)
    cached_threshold = getattr(cross_course_outcomes, 'cached_threshold', None)
    cached_non_grouped = getattr(cross_course_outcomes, 'cached_non_grouped', None)
    
    print(f"DEBUG [cross_course_outcomes]: Cache state - cached_results={cached_results is not None}, cached_threshold={cached_threshold}, cached_non_grouped={len(cached_non_grouped) if cached_non_grouped else 0} items")
    
    # Force refresh if cached_non_grouped is None but show_non_grouped is True
    if show_non_grouped and cached_non_grouped is None:
        force_refresh = True
        print("DEBUG [cross_course_outcomes]: Forcing refresh because show_non_grouped is True but cached_non_grouped is None")
    
    if cached_results is None or cached_threshold != similarity_threshold or force_refresh:
        # We need to compute groups - this may take time
        try:
            print(f"DEBUG [cross_course_outcomes]: Computing new groups with threshold={similarity_threshold}")
            # Import Jaro-Winkler similarity
            import jellyfish
            
            # Get all course outcomes
            course_outcomes = CourseOutcome.query.all()
            print(f"DEBUG [cross_course_outcomes]: Found {len(course_outcomes)} total course outcomes in database")
            
            if not course_outcomes:
                flash('No course outcomes found in the database', 'warning')
                return render_template('calculation/cross_course_outcomes.html',
                                    similarity=similarity_threshold,
                                    raw_similarity=raw_similarity,
                                    search=search_query,
                                    sort=sort_by,
                                    outcome_groups=[],
                                    non_grouped_outcomes=[],
                                    show_non_grouped=show_non_grouped,
                                    loading=False,
                                    active_page='calculations')
            
            # Group outcomes by similarity
            outcome_groups = []
            processed_outcomes = set()
            
            for i, outcome1 in enumerate(course_outcomes):
                if outcome1.id in processed_outcomes:
                    continue
                
                # Create a new group with this outcome as the representative
                group = {
                    'representative': outcome1,
                    'outcomes': [outcome1],
                    'course_ids': set([outcome1.course_id]),
                    'courses': [outcome1.course]
                }
                processed_outcomes.add(outcome1.id)
                
                # Track if this outcome has any similar ones
                has_similar = False
                
                # Find similar outcomes
                for j, outcome2 in enumerate(course_outcomes):
                    if i == j or outcome2.id in processed_outcomes:
                        continue
                    
                    # Calculate similarity using Jaro-Winkler
                    description_similarity = jellyfish.jaro_winkler_similarity(
                        outcome1.description.lower(),
                        outcome2.description.lower()
                    )
                    
                    # Check if similarity meets threshold
                    if description_similarity >= similarity_threshold:
                        group['outcomes'].append(outcome2)
                        group['course_ids'].add(outcome2.course_id)
                        group['courses'].append(outcome2.course)
                        processed_outcomes.add(outcome2.id)
                        has_similar = True
                
                # Only add groups with multiple outcomes
                if has_similar:
                    outcome_groups.append(group)
                else:
                    # Remove the outcome from processed_outcomes if it doesn't have similar ones
                    processed_outcomes.remove(outcome1.id)
            
            # Get non-grouped outcomes by finding all outcomes that aren't in processed_outcomes
            non_grouped_outcomes = [o for o in course_outcomes if o.id not in processed_outcomes]
            
            print(f"DEBUG [cross_course_outcomes]: Computation results - {len(outcome_groups)} groups, {len(non_grouped_outcomes)} non-grouped outcomes")
            print(f"DEBUG [cross_course_outcomes]: First few non-grouped outcomes: {[o.code for o in non_grouped_outcomes[:5]] if non_grouped_outcomes else 'None'}")
            
            # Cache the results for future requests
            cross_course_outcomes.cached_results = outcome_groups
            cross_course_outcomes.cached_threshold = similarity_threshold
            cross_course_outcomes.cached_non_grouped = non_grouped_outcomes
            
            print(f"DEBUG [cross_course_outcomes]: Cached {len(outcome_groups)} groups and {len(non_grouped_outcomes)} non-grouped outcomes")
            print(f"DEBUG [cross_course_outcomes]: Rendering template with show_non_grouped={show_non_grouped}, passing {len(non_grouped_outcomes) if show_non_grouped else 0} non-grouped outcomes")
            
            # Return template with the groups but mark as loading
            # The actual scores will be calculated via AJAX
            return render_template('calculation/cross_course_outcomes.html',
                                similarity=similarity_threshold,
                                raw_similarity=raw_similarity,
                                search=search_query,
                                sort=sort_by,
                                outcome_groups=outcome_groups,
                                non_grouped_outcomes=non_grouped_outcomes if show_non_grouped else [],
                                show_non_grouped=show_non_grouped,
                                loading=True,
                                active_page='calculations')
                                
        except ImportError:
            flash('The jellyfish library is required for outcome similarity analysis. Please install it with "pip install jellyfish".', 'error')
            return render_template('calculation/cross_course_outcomes.html',
                                similarity=similarity_threshold,
                                raw_similarity=raw_similarity,
                                search=search_query,
                                sort=sort_by,
                                outcome_groups=[],
                                non_grouped_outcomes=[],
                                show_non_grouped=show_non_grouped,
                                loading=False,
                                active_page='calculations')
    else:
        # Use cached results
        outcome_groups = cached_results
        non_grouped_outcomes = cached_non_grouped if cached_non_grouped is not None and show_non_grouped else []
        
        print(f"DEBUG [cross_course_outcomes]: Using cached results - {len(outcome_groups)} groups")
        print(f"DEBUG [cross_course_outcomes]: show_non_grouped={show_non_grouped}")
        print(f"DEBUG [cross_course_outcomes]: Non-grouped outcomes before filtering: {len(non_grouped_outcomes)}")
        
        # Filter by search query if provided
        if search_query:
            filtered_groups = []
            for group in outcome_groups:
                rep = group['representative']
                if (search_query.lower() in rep.code.lower() or 
                    search_query.lower() in rep.description.lower()):
                    filtered_groups.append(group)
            outcome_groups = filtered_groups
            
            # Also filter non-grouped outcomes
            if show_non_grouped and non_grouped_outcomes:
                filtered_non_grouped = []
                for outcome in non_grouped_outcomes:
                    if (search_query.lower() in outcome.code.lower() or 
                        search_query.lower() in outcome.description.lower()):
                        filtered_non_grouped.append(outcome)
                non_grouped_outcomes = filtered_non_grouped
                print(f"DEBUG [cross_course_outcomes]: Non-grouped outcomes after search filtering: {len(non_grouped_outcomes)}")
        
        # Sort the groups
        if sort_by == 'code_asc':
            outcome_groups.sort(key=lambda g: g['representative'].code)
        elif sort_by == 'code_desc':
            outcome_groups.sort(key=lambda g: g['representative'].code, reverse=True)
        elif sort_by == 'description_asc':
            outcome_groups.sort(key=lambda g: g['representative'].description)
        elif sort_by == 'description_desc':
            outcome_groups.sort(key=lambda g: g['representative'].description, reverse=True)
        elif sort_by == 'count_asc':
            outcome_groups.sort(key=lambda g: len(g['outcomes']))
        elif sort_by == 'count_desc':
            outcome_groups.sort(key=lambda g: len(g['outcomes']), reverse=True)
            
        # Sort non-grouped outcomes
        if non_grouped_outcomes:
            if sort_by == 'code_asc':
                non_grouped_outcomes.sort(key=lambda o: o.code)
            elif sort_by == 'code_desc':
                non_grouped_outcomes.sort(key=lambda o: o.code, reverse=True)
            elif sort_by == 'description_asc':
                non_grouped_outcomes.sort(key=lambda o: o.description)
            elif sort_by == 'description_desc':
                non_grouped_outcomes.sort(key=lambda o: o.description, reverse=True)
        
        # Final check before rendering
        final_non_grouped = non_grouped_outcomes if show_non_grouped else []
        print(f"DEBUG [cross_course_outcomes]: Final rendering with show_non_grouped={show_non_grouped}, passing {len(final_non_grouped)} non-grouped outcomes")
        print(f"DEBUG [cross_course_outcomes]: First few non-grouped outcomes: {[o.code for o in final_non_grouped[:5]] if final_non_grouped else 'None'}")
        
        return render_template('calculation/cross_course_outcomes.html',
                            similarity=similarity_threshold,
                            raw_similarity=raw_similarity,
                            search=search_query,
                            sort=sort_by,
                            outcome_groups=outcome_groups,
                            non_grouped_outcomes=final_non_grouped,
                            show_non_grouped=show_non_grouped,
                            loading=False,
                            active_page='calculations')

@calculation_bp.route('/cross_course_outcomes/data', methods=['POST'])
def cross_course_outcomes_data():
    """API endpoint to calculate course outcome scores for cross-course analysis"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        outcome_ids = data.get('outcome_ids', [])
        if not outcome_ids:
            return jsonify({'success': False, 'message': 'No outcome IDs provided'}), 400
        
        # Get global achievement levels for display
        achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
        if not achievement_levels:
            # Create default achievement levels if none exist
            default_levels = [
                {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
                {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
                {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
                {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
                {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
            ]
            
            for level_data in default_levels:
                level = GlobalAchievementLevel(
                    name=level_data["name"],
                    min_score=level_data["min_score"],
                    max_score=level_data["max_score"],
                    color=level_data["color"]
                )
                db.session.add(level)
            
            db.session.commit()
            achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
        
        # Get course outcomes
        outcomes = CourseOutcome.query.filter(CourseOutcome.id.in_(outcome_ids)).all()
        if not outcomes:
            return jsonify({'success': False, 'message': 'No outcomes found with the provided IDs'}), 404
        
        # Calculate results for each outcome
        results = []
        total_weighted_score = Decimal('0')
        total_weight = Decimal('0')
        
        for outcome in outcomes:
            # Get course for this outcome
            course = Course.query.get(outcome.course_id)
            if not course:
                continue
            
            # Calculate the course results to get outcome scores
            course_results = calculate_single_course_results(course.id, 'absolute')
            if not course_results or not course_results.get('is_valid_for_aggregation'):
                continue
            
            # Get outcome score from course results
            outcome_score = None
            if 'course_outcome_scores' in course_results:
                outcome_score = course_results['course_outcome_scores'].get(outcome.id)
            
            if outcome_score is not None:
                # Get achievement level for this score
                achievement_level = {
                    'name': 'Unknown',
                    'color': 'secondary'
                }
                
                for level in achievement_levels:
                    if float(outcome_score) >= float(level.min_score) and float(outcome_score) <= float(level.max_score):
                        achievement_level = {
                            'name': level.name,
                            'color': level.color
                        }
                        break
                
                # Add to results
                results.append({
                    'outcome_id': outcome.id,
                    'outcome_code': outcome.code,
                    'outcome_description': outcome.description,
                    'course_id': course.id,
                    'course_code': course.code,
                    'course_name': course.name,
                    'course_semester': course.semester,
                    'course_weight': float(course.course_weight),
                    'score': float(outcome_score),
                    'achievement_level': achievement_level
                })
                
                # Add to weighted average calculation
                total_weighted_score += Decimal(str(outcome_score)) * Decimal(str(course.course_weight))
                total_weight += Decimal(str(course.course_weight))
        
        # Calculate overall weighted average
        overall_average = None
        if total_weight > Decimal('0'):
            overall_average = float(total_weighted_score / total_weight)
            
            # Get overall achievement level
            overall_level = {
                'name': 'Unknown',
                'color': 'secondary'
            }
            
            for level in achievement_levels:
                if overall_average >= float(level.min_score) and overall_average <= float(level.max_score):
                    overall_level = {
                        'name': level.name,
                        'color': level.color
                    }
                    break
        
        return jsonify({
            'success': True,
            'results': results,
            'overall_average': overall_average,
            'overall_level': overall_level if overall_average is not None else None
        })
        
    except Exception as e:
        logging.error(f"Error calculating cross-course outcome data: {str(e)}")
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500

# ================================
# GRADUATING STUDENTS MANAGEMENT
# ================================

@calculation_bp.route('/graduating_students', methods=['GET', 'POST'])
def manage_graduating_students():
    """
    Manage graduating students for MÜDEK filtering.
    Migration-safe route that handles table existence gracefully.
    """
    from db_migrations import graduating_students_table_exists, ensure_graduating_students_table
    
    # Check if table exists, create if needed
    table_available = graduating_students_table_exists()
    migration_message = None
    
    if not table_available:
        # Try to create the table
        success = ensure_graduating_students_table()
        if success:
            table_available = True
            migration_message = "Graduating students table was automatically created for your database."
        else:
            # Table creation failed, show error page
            return render_template('calculation/graduating_students.html',
                                 error="Unable to create graduating students table. Please check your database permissions.",
                                 graduating_students=[],
                                 total_count=0,
                                 table_available=False,
                                 active_page='calculations')
    
    # Handle POST requests (add students)
    if request.method == 'POST':
        if not table_available:
            flash('Graduating students feature is not available.', 'error')
            return redirect(url_for('calculation.manage_graduating_students'))
        
        action = request.form.get('action')
        
        if action == 'add_single':
            student_id = request.form.get('student_id', '').strip()
            if student_id:
                try:
                    # Check if already exists
                    existing = GraduatingStudent.query.filter_by(student_id=student_id).first()
                    if existing:
                        flash(f'Student ID {student_id} is already in the graduating students list.', 'warning')
                    else:
                        # Add new graduating student
                        graduating_student = GraduatingStudent(student_id=student_id)
                        db.session.add(graduating_student)
                        db.session.commit()
                        
                        # Log action
                        log = Log(action="ADD_GRADUATING_STUDENT", 
                                description=f"Added graduating student: {student_id}")
                        db.session.add(log)
                        db.session.commit()
                        
                        flash(f'Successfully added student ID {student_id} to graduating students.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error adding student: {str(e)}', 'error')
            else:
                flash('Please enter a valid student ID.', 'error')
        
        elif action == 'add_bulk':
            bulk_data = request.form.get('bulk_student_ids', '').strip()
            if bulk_data:
                try:
                    # Split by newlines and clean up
                    student_ids = [line.strip() for line in bulk_data.split('\n') if line.strip()]
                    added_count = 0
                    skipped_count = 0
                    
                    for student_id in student_ids:
                        # Check if already exists
                        existing = GraduatingStudent.query.filter_by(student_id=student_id).first()
                        if existing:
                            skipped_count += 1
                        else:
                            graduating_student = GraduatingStudent(student_id=student_id)
                            db.session.add(graduating_student)
                            added_count += 1
                    
                    db.session.commit()
                    
                    # Log action
                    log = Log(action="BULK_ADD_GRADUATING_STUDENTS", 
                            description=f"Bulk added {added_count} graduating students, skipped {skipped_count} duplicates")
                    db.session.add(log)
                    db.session.commit()
                    
                    flash(f'Successfully added {added_count} students. Skipped {skipped_count} duplicates.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error adding students: {str(e)}', 'error')
            else:
                flash('Please enter student IDs (one per line).', 'error')
        
        elif action == 'clear_all':
            try:
                count = GraduatingStudent.query.count()
                GraduatingStudent.query.delete()
                db.session.commit()
                
                # Log action
                log = Log(action="CLEAR_ALL_GRADUATING_STUDENTS", 
                        description=f"Cleared all {count} graduating students")
                db.session.add(log)
                db.session.commit()
                
                flash(f'Successfully cleared {count} graduating students.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error clearing students: {str(e)}', 'error')
        
        return redirect(url_for('calculation.manage_graduating_students'))
    
    # GET request - display the management page
    graduating_students = []
    total_count = 0
    
    if table_available:
        try:
            graduating_students = GraduatingStudent.query.order_by(GraduatingStudent.student_id).all()
            total_count = len(graduating_students)
        except Exception as e:
            flash(f'Error loading graduating students: {str(e)}', 'error')
    
    return render_template('calculation/graduating_students.html',
                         graduating_students=graduating_students,
                         total_count=total_count,
                         table_available=table_available,
                         migration_message=migration_message,
                         active_page='calculations')

@calculation_bp.route('/graduating_students/delete/<int:student_id>', methods=['POST'])
def delete_graduating_student(student_id):
    """Delete a specific graduating student"""
    from db_migrations import graduating_students_table_exists
    
    if not graduating_students_table_exists():
        flash('Graduating students feature is not available.', 'error')
        return redirect(url_for('calculation.manage_graduating_students'))
    
    try:
        graduating_student = GraduatingStudent.query.get_or_404(student_id)
        student_id_value = graduating_student.student_id
        
        db.session.delete(graduating_student)
        db.session.commit()
        
        # Log action
        log = Log(action="DELETE_GRADUATING_STUDENT", 
                description=f"Deleted graduating student: {student_id_value}")
        db.session.add(log)
        db.session.commit()
        
        flash(f'Successfully removed student ID {student_id_value} from graduating students.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'error')
    
    return redirect(url_for('calculation.manage_graduating_students'))

@calculation_bp.route('/graduating_students/export', methods=['GET'])
def export_graduating_students():
    """Export graduating students list as CSV"""
    from db_migrations import graduating_students_table_exists
    
    if not graduating_students_table_exists():
        flash('Graduating students feature is not available.', 'error')
        return redirect(url_for('calculation.manage_graduating_students'))
    
    try:
        graduating_students = GraduatingStudent.query.order_by(GraduatingStudent.student_id).all()
        
        # Prepare data for export
        export_data = []
        for student in graduating_students:
            export_data.append({
                'Student ID': student.student_id,
                'Added Date': student.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Use existing export utility
        return export_to_excel_csv(export_data, 'graduating_students')
        
    except Exception as e:
        flash(f'Error exporting graduating students: {str(e)}', 'error')
        return redirect(url_for('calculation.manage_graduating_students'))

def get_graduating_student_ids():
    """
    Helper function to get all graduating student IDs.
    Returns empty list if table doesn't exist or on error.
    """
    from db_migrations import graduating_students_table_exists
    
    try:
        if not graduating_students_table_exists():
            return []
        
        graduating_students = GraduatingStudent.query.all()
        return [gs.student_id for gs in graduating_students]
    except Exception:
        return []

def is_graduating_student(student_id):
    """
    Check if a student ID is in the graduating students list.
    Returns False if table doesn't exist or on error.
    """
    from db_migrations import graduating_students_table_exists
    
    try:
        if not graduating_students_table_exists():
            return False
        
        return GraduatingStudent.query.filter_by(student_id=student_id).first() is not None
    except Exception:
        return False

@calculation_bp.route('/all_courses/pdf_individual', methods=['POST'])
def generate_individual_student_pdfs():
    """Generate individual PDF reports for all students or filtered students"""
    from weasyprint import HTML, CSS
    from weasyprint.html import get_html_document
    import tempfile
    import zipfile
    from flask import make_response
    import io
    
    try:
        # Get filter parameters from form data
        filter_year = request.form.get('year', '')
        search_query = request.form.get('search', '').lower()
        filter_student_id = request.form.get('student_id', '').strip()
        include_graduating_only = request.form.get('graduating_only', '').lower() == 'true'
        
        # Get the display method from session or default to absolute
        display_method = session.get('display_method', 'absolute')
        
        # Get all courses with same filtering as all_courses route
        courses = Course.query.all()
        
        # Apply filters
        if filter_year:
            courses = [c for c in courses if filter_year in c.semester]
        
        if search_query:
            courses = [c for c in courses if search_query in c.code.lower() or search_query in c.name.lower()]
        
        if filter_student_id:
            courses, _ = filter_courses_by_student(courses, filter_student_id)
        
        if include_graduating_only:
            courses, _ = filter_courses_by_graduating_students(courses, include_graduating_only)
        
        # Get all unique students from the filtered courses
        all_students = set()
        for course in courses:
            course_students = Student.query.filter_by(course_id=course.id).all()
            for student in course_students:
                # If graduating students filter is enabled, only include graduating students
                if include_graduating_only:
                    if is_graduating_student(student.student_id):
                        all_students.add(student.student_id)
                else:
                    all_students.add(student.student_id)
        
        if not all_students:
            flash('No students found matching the current filters.', 'warning')
            return redirect(url_for('calculation.all_courses'))
        
        # Create a ZIP file to contain all individual PDFs
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for student_id in sorted(all_students):
                # Generate PDF for this student
                pdf_content = generate_student_pdf_content(student_id, courses, display_method, include_graduating_only)
                
                if pdf_content:
                    # Get student name for filename
                    student_name = get_student_name(student_id)
                    safe_name = "".join(c for c in student_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    filename = f"{student_id}_{safe_name}.pdf".replace(' ', '_')
                    
                    zip_file.writestr(filename, pdf_content)
        
        zip_buffer.seek(0)
        
        # Create response
        response = make_response(zip_buffer.getvalue())
        response.headers['Content-Type'] = 'application/zip'
        
        # Generate filename with timestamp and filter info
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filter_suffix = ""
        if include_graduating_only:
            filter_suffix += "_graduating"
        if filter_student_id:
            filter_suffix += f"_student_{filter_student_id}"
        
        filename = f"individual_student_reports{filter_suffix}_{timestamp}.zip"
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Log action
        log = Log(action="GENERATE_INDIVIDUAL_STUDENT_PDFS", 
                 description=f"Generated individual PDF reports for {len(all_students)} students{filter_suffix}")
        db.session.add(log)
        db.session.commit()
        
        return response
        
    except Exception as e:
        logging.error(f"Error generating individual student PDFs: {e}")
        flash(f'Error generating PDF reports: {str(e)}', 'danger')
        return redirect(url_for('calculation.all_courses'))

@calculation_bp.route('/all_courses/pdf_bulk', methods=['POST'])
def generate_bulk_student_pdf():
    """Generate a single bulk PDF report containing all students"""
    from weasyprint import HTML, CSS
    import tempfile
    from flask import make_response
    
    try:
        # Get filter parameters from form data
        filter_year = request.form.get('year', '')
        search_query = request.form.get('search', '').lower()
        filter_student_id = request.form.get('student_id', '').strip()
        include_graduating_only = request.form.get('graduating_only', '').lower() == 'true'
        
        # Get the display method from session or default to absolute
        display_method = session.get('display_method', 'absolute')
        
        # Get all courses with same filtering as all_courses route
        courses = Course.query.all()
        
        # Apply filters
        if filter_year:
            courses = [c for c in courses if filter_year in c.semester]
        
        if search_query:
            courses = [c for c in courses if search_query in c.code.lower() or search_query in c.name.lower()]
        
        if filter_student_id:
            courses, _ = filter_courses_by_student(courses, filter_student_id)
        
        if include_graduating_only:
            courses, _ = filter_courses_by_graduating_students(courses, include_graduating_only)
        
        # Generate bulk PDF content
        try:
            # Try WeasyPrint first, fall back to ReportLab if it fails
            from weasyprint import HTML
            html_content = generate_bulk_pdf_content(courses, display_method, include_graduating_only)
            html_doc = HTML(string=html_content)
            pdf_content = html_doc.write_pdf()
        except (ImportError, OSError) as e:
            logging.warning(f"WeasyPrint not available ({e}), using ReportLab fallback for bulk PDF")
            pdf_content = generate_bulk_pdf_with_reportlab(courses, display_method, include_graduating_only)
        
        # Create response
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        
        # Generate filename with timestamp and filter info
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filter_suffix = ""
        if include_graduating_only:
            filter_suffix += "_graduating"
        if filter_student_id:
            filter_suffix += f"_student_{filter_student_id}"
        
        filename = f"bulk_student_report{filter_suffix}_{timestamp}.pdf"
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Log action
        log = Log(action="GENERATE_BULK_STUDENT_PDF", 
                 description=f"Generated bulk PDF report for {len(courses)} courses{filter_suffix}")
        db.session.add(log)
        db.session.commit()
        
        return response
        
    except Exception as e:
        logging.error(f"Error generating bulk student PDF: {e}")
        flash(f'Error generating PDF report: {str(e)}', 'danger')
        return redirect(url_for('calculation.all_courses'))

def filter_courses_by_graduating_students(courses, include_graduating_only=False):
    """
    Filter courses based on graduating students enrollment.
    Migration-safe function that handles table existence gracefully.
    
    Parameters:
    - courses: List of courses to filter
    - include_graduating_only: If True, only include courses with graduating students
    
    Returns:
    - filtered_courses: List of courses (filtered or original if feature unavailable)
    - filter_info: Dict with filtering information and statistics
    """
    from db_migrations import graduating_students_table_exists
    
    # If feature is disabled or table doesn't exist, return original courses
    if not include_graduating_only or not graduating_students_table_exists():
        return courses, {
            'enabled': include_graduating_only,
            'available': graduating_students_table_exists(),
            'total_graduating_students': 0,
            'courses_with_graduating_students': 0,
            'filtered_courses': len(courses),
            'original_courses': len(courses)
        }
    
    try:
        # Get all graduating student IDs
        graduating_student_ids = get_graduating_student_ids()
        
        if not graduating_student_ids:
            # No graduating students defined, return empty list
            return [], {
                'enabled': True,
                'available': True,
                'total_graduating_students': 0,
                'courses_with_graduating_students': 0,
                'filtered_courses': 0,
                'original_courses': len(courses)
            }
        
        # Filter courses that have at least one graduating student enrolled
        filtered_courses = []
        courses_with_graduating_students = 0
        
        for course in courses:
            # Check if any graduating students are enrolled in this course
            course_students = Student.query.filter_by(course_id=course.id).all()
            course_student_ids = {student.student_id for student in course_students}
            
            # Check if any graduating students are in this course
            has_graduating_students = any(student_id in graduating_student_ids 
                                        for student_id in course_student_ids)
            
            if has_graduating_students:
                filtered_courses.append(course)
                courses_with_graduating_students += 1
        
        filter_info = {
            'enabled': True,
            'available': True,
            'total_graduating_students': len(graduating_student_ids),
            'courses_with_graduating_students': courses_with_graduating_students,
            'filtered_courses': len(filtered_courses),
            'original_courses': len(courses)
        }
        
        return filtered_courses, filter_info
        
    except Exception as e:
        # On error, return original courses and log the issue
        logging.error(f"Error filtering courses by graduating students: {e}")
        return courses, {
            'enabled': include_graduating_only,
            'available': False,
            'error': str(e),
            'total_graduating_students': 0,
            'courses_with_graduating_students': 0,
            'filtered_courses': len(courses),
            'original_courses': len(courses)
        }

def get_student_name(student_id):
    """Get student name from student ID across all courses"""
    student = Student.query.filter_by(student_id=student_id).first()
    if student:
        if student.last_name:
            return f"{student.first_name} {student.last_name}"
        else:
            return student.first_name
    return f"Student {student_id}"

def generate_student_pdf_content(student_id, courses, display_method='absolute', include_graduating_only=False):
    """Generate PDF content for a single student across all their courses"""
    try:
        # Try WeasyPrint first, fall back to ReportLab if it fails
        try:
            from weasyprint import HTML
            return generate_student_pdf_with_weasyprint(student_id, courses, display_method, include_graduating_only)
        except (ImportError, OSError) as e:
            logging.warning(f"WeasyPrint not available ({e}), using ReportLab fallback")
            return generate_student_pdf_with_reportlab(student_id, courses, display_method, include_graduating_only)
    except Exception as e:
        logging.error(f"Error generating PDF for student {student_id}: {e}")
        return None

def generate_student_pdf_with_weasyprint(student_id, courses, display_method='absolute', include_graduating_only=False):
    """Generate PDF using WeasyPrint (HTML/CSS approach)"""
    from weasyprint import HTML
    
    try:
        # Get student information
        student_name = get_student_name(student_id)
        
        # Build HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Student Report - {student_name}</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    margin: 20px; 
                    line-height: 1.4;
                }}
                .header {{ 
                    text-align: center; 
                    margin-bottom: 30px;
                    border-bottom: 2px solid #333;
                    padding-bottom: 20px;
                }}
                .student-info {{ 
                    background: #f8f9fa; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin-bottom: 20px;
                }}
                .course {{ 
                    margin-bottom: 25px; 
                    page-break-inside: avoid;
                }}
                .course-header {{ 
                    background: #007bff; 
                    color: white; 
                    padding: 10px; 
                    margin-bottom: 10px;
                }}
                table {{ 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin-bottom: 15px;
                }}
                th, td {{ 
                    border: 1px solid #ddd; 
                    padding: 8px; 
                    text-align: center;
                }}
                th {{ 
                    background: #f8f9fa;
                }}
                .success {{ background: #d4edda; }}
                .info {{ background: #d1ecf1; }}
                .primary {{ background: #cce5ff; }}
                .warning {{ background: #fff3cd; }}
                .danger {{ background: #f8d7da; }}
                .na {{ background: #e9ecef; }}
                .summary {{ 
                    background: #e8f4f8; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin-top: 20px;
                }}
                .footer {{ 
                    text-align: center; 
                    margin-top: 30px; 
                    font-size: 12px; 
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Student Academic Report</h1>
                <h2>{student_name} (ID: {student_id})</h2>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                {'<p><strong>Graduating Student Report</strong></p>' if include_graduating_only else ''}
            </div>
        """
        
        # Get program outcomes
        program_outcomes = ProgramOutcome.query.all()
        
        # Track aggregated scores for summary
        total_scores = {}
        total_weights = {}
        course_count = 0
        
        # Process each course
        for course in courses:
            # Check if student is enrolled in this course
            student_in_course = Student.query.filter_by(student_id=student_id, course_id=course.id).first()
            if not student_in_course:
                continue
                
            course_count += 1
            
            # Get bulk data for optimization
            bulk_data = bulk_load_course_data([course.id], display_method)
            
            # Calculate individual student results
            individual_result = calculate_individual_student_results(student_in_course.id, course.id, bulk_data, display_method)
            
            # Get course outcome results for display  
            course_result = calculate_course_results_from_bulk_data_v2_optimized(course.id, bulk_data, display_method)
            
            html_content += f"""
            <div class="course">
                <div class="course-header">
                    <h3>{course.code} - {course.name}</h3>
                    <p>Semester: {course.semester} | Weight: {course.course_weight}</p>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>Program Outcome</th>
                            <th>Description</th>
                            <th>Student Score (%)</th>
                            <th>Achievement Level</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            # Add program outcome rows
            for po in program_outcomes:
                po_score = individual_result.get(po.id)
                contributes = po.id in course_result.get('contributing_po_ids', [])
                
                if contributes and po_score is not None:
                    # Get achievement level
                    achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
                    level = get_achievement_level(po_score, achievement_levels)
                    
                    # Aggregate for summary
                    if po.id not in total_scores:
                        total_scores[po.id] = 0
                        total_weights[po.id] = 0
                    total_scores[po.id] += po_score * float(course.course_weight)
                    total_weights[po.id] += float(course.course_weight)
                    
                    html_content += f"""
                    <tr class="{level.color if level else ''}">
                        <td><strong>{po.code}</strong></td>
                        <td>{po.description}</td>
                        <td>{po_score:.2f}%</td>
                        <td>{level.name if level else 'N/A'}</td>
                    </tr>
                    """
                else:
                    html_content += f"""
                    <tr class="na">
                        <td><strong>{po.code}</strong></td>
                        <td>{po.description}</td>
                        <td>N/A</td>
                        <td>Not Applicable</td>
                    </tr>
                    """
            
            html_content += """
                    </tbody>
                </table>
            </div>
            """
        
        # Add summary section
        html_content += """
        <div class="summary">
            <h3>Overall Program Outcome Summary</h3>
            <table>
                <thead>
                    <tr>
                        <th>Program Outcome</th>
                        <th>Overall Score (%)</th>
                        <th>Achievement Level</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
        
        for po in program_outcomes:
            if po.id in total_scores and total_weights[po.id] > 0:
                avg_score = total_scores[po.id] / total_weights[po.id]
                level = get_achievement_level(avg_score, achievement_levels)
                
                html_content += f"""
                <tr class="{level.color if level else ''}">
                    <td><strong>{po.code}</strong></td>
                    <td>{avg_score:.2f}%</td>
                    <td>{level.name if level else 'N/A'}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr class="na">
                    <td><strong>{po.code}</strong></td>
                    <td>N/A</td>
                    <td>Not Applicable</td>
                </tr>
                """
        
        html_content += f"""
                </tbody>
            </table>
            <p><strong>Total Courses:</strong> {course_count}</p>
        </div>
        
        <div class="footer">
            <p>This report was generated by Accredit Helper Pro</p>
            <p>Report includes {course_count} courses for student {student_name}</p>
        </div>
        </body>
        </html>
        """
        
        # Convert to PDF
        html_doc = HTML(string=html_content)
        return html_doc.write_pdf()
        
    except Exception as e:
        logging.error(f"Error generating PDF for student {student_id}: {e}")
        return None

def generate_bulk_pdf_content(courses, display_method='absolute', include_graduating_only=False):
    """Generate bulk PDF content containing all students from filtered courses"""
    try:
        # Get all unique students from the courses
        all_students = {}  # student_id -> student_name
        
        for course in courses:
            course_students = Student.query.filter_by(course_id=course.id).all()
            for student in course_students:
                if include_graduating_only:
                    if is_graduating_student(student.student_id):
                        all_students[student.student_id] = get_student_name(student.student_id)
                else:
                    all_students[student.student_id] = get_student_name(student.student_id)
        
        # Build HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Bulk Student Report</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    margin: 20px; 
                    line-height: 1.4;
                }}
                .header {{ 
                    text-align: center; 
                    margin-bottom: 30px;
                    border-bottom: 2px solid #333;
                    padding-bottom: 20px;
                }}
                .student-section {{ 
                    margin-bottom: 40px; 
                    page-break-before: always;
                }}
                .student-section:first-child {{ 
                    page-break-before: auto;
                }}
                .student-header {{ 
                    background: #28a745; 
                    color: white; 
                    padding: 15px; 
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .course {{ 
                    margin-bottom: 20px;
                }}
                .course-header {{ 
                    background: #007bff; 
                    color: white; 
                    padding: 8px; 
                    margin-bottom: 8px;
                    font-size: 14px;
                }}
                table {{ 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin-bottom: 15px;
                    font-size: 12px;
                }}
                th, td {{ 
                    border: 1px solid #ddd; 
                    padding: 6px; 
                    text-align: center;
                }}
                th {{ 
                    background: #f8f9fa;
                    font-size: 11px;
                }}
                .success {{ background: #d4edda; }}
                .info {{ background: #d1ecf1; }}
                .primary {{ background: #cce5ff; }}
                .warning {{ background: #fff3cd; }}
                .danger {{ background: #f8d7da; }}
                .na {{ background: #e9ecef; }}
                .summary {{ 
                    background: #e8f4f8; 
                    padding: 10px; 
                    border-radius: 5px; 
                    margin-top: 15px;
                }}
                .footer {{ 
                    text-align: center; 
                    margin-top: 30px; 
                    font-size: 10px; 
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Bulk Student Academic Report</h1>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Total Students: {len(all_students)} | Total Courses: {len(courses)}</p>
                {'<p><strong>Graduating Students Only</strong></p>' if include_graduating_only else ''}
            </div>
        """
        
        # Process each student
        for student_id in sorted(all_students.keys()):
            student_name = all_students[student_id]
            
            html_content += f"""
            <div class="student-section">
                <div class="student-header">
                    <h2>{student_name} (ID: {student_id})</h2>
                </div>
            """
            
            # Get student's courses from the filtered list
            student_courses = []
            for course in courses:
                if Student.query.filter_by(student_id=student_id, course_id=course.id).first():
                    student_courses.append(course)
            
            if student_courses:
                program_outcomes = ProgramOutcome.query.all()
                
                # Compact table for all courses
                html_content += """
                <table>
                    <thead>
                        <tr>
                            <th>Course</th>
                """
                
                for po in program_outcomes[:6]:  # Limit to first 6 POs for space
                    html_content += f"<th>{po.code}</th>"
                
                html_content += """
                        </tr>
                    </thead>
                    <tbody>
                """
                
                for course in student_courses:
                    student_in_course = Student.query.filter_by(student_id=student_id, course_id=course.id).first()
                    if student_in_course:
                        bulk_data = bulk_load_course_data([course.id], display_method)
                        individual_result = calculate_individual_student_results(student_in_course.id, course.id, bulk_data, display_method)
                        
                        html_content += f"""
                        <tr>
                            <td><strong>{course.code}</strong><br>{course.semester}</td>
                        """
                        
                        for po in program_outcomes[:6]:
                            po_score = individual_result.get(po.id)
                            if po_score is not None:
                                achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
                                level = get_achievement_level(po_score, achievement_levels)
                                html_content += f'<td class="{level.color if level else ""}">{po_score:.1f}%</td>'
                            else:
                                html_content += '<td class="na">N/A</td>'
                        
                        html_content += "</tr>"
                
                html_content += f"""
                    </tbody>
                </table>
                <p><strong>Courses:</strong> {len(student_courses)}</p>
                """
            else:
                html_content += "<p>No courses found for this student.</p>"
            
            html_content += "</div>"
        
        html_content += f"""
        <div class="footer">
            <p>This bulk report was generated by Accredit Helper Pro</p>
            <p>Report includes {len(all_students)} students across {len(courses)} courses</p>
        </div>
        </body>
        </html>
        """
        
        return html_content
        
    except Exception as e:
        logging.error(f"Error generating bulk PDF content: {e}")
        raise

def generate_student_pdf_with_reportlab(student_id, courses, display_method='absolute', include_graduating_only=False):
    """Generate PDF using ReportLab (programmatic approach) - Windows-friendly fallback"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    try:
        # Get student information
        student_name = get_student_name(student_id)
        
        # Create PDF buffer
        buffer = io.BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        
        # Build document content
        story = []
        
        # Title
        story.append(Paragraph("Student Academic Report", title_style))
        story.append(Paragraph(f"<b>{student_name}</b> (ID: {student_id})", styles['Heading2']))
        story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        
        if include_graduating_only:
            story.append(Paragraph("<b>Graduating Student Report</b>", styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        # Get program outcomes
        program_outcomes = ProgramOutcome.query.all()
        
        # Track aggregated scores for summary
        total_scores = {}
        total_weights = {}
        course_count = 0
        
        # Process each course
        for course in courses:
            # Check if student is enrolled in this course
            student_in_course = Student.query.filter_by(student_id=student_id, course_id=course.id).first()
            if not student_in_course:
                continue
                
            course_count += 1
            
            # Course header
            story.append(Paragraph(f"<b>{course.code} - {course.name}</b>", styles['Heading3']))
            story.append(Paragraph(f"Semester: {course.semester} | Weight: {course.course_weight}", styles['Normal']))
            story.append(Spacer(1, 10))
            
            # Get bulk data for optimization
            bulk_data = bulk_load_course_data([course.id], display_method)
            
            # Calculate individual student results
            individual_result = calculate_individual_student_results(student_in_course.id, course.id, bulk_data, display_method)
            
            # Get course outcome results for display  
            course_result = calculate_course_results_from_bulk_data_v2_optimized(course.id, bulk_data, display_method)
            
            # Create table data
            table_data = [['Program Outcome', 'Description', 'Student Score (%)', 'Achievement Level']]
            
            # Add program outcome rows
            for po in program_outcomes:
                po_score = individual_result.get(po.id)
                contributes = po.id in course_result.get('contributing_po_ids', [])
                
                if contributes and po_score is not None:
                    # Get achievement level
                    achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
                    level = get_achievement_level(po_score, achievement_levels)
                    
                    # Aggregate for summary
                    if po.id not in total_scores:
                        total_scores[po.id] = 0
                        total_weights[po.id] = 0
                    total_scores[po.id] += po_score * float(course.course_weight)
                    total_weights[po.id] += float(course.course_weight)
                    
                    table_data.append([
                        po.code,
                        po.description[:30] + "..." if len(po.description) > 30 else po.description,
                        f"{po_score:.2f}%",
                        level.name if level else 'N/A'
                    ])
                else:
                    table_data.append([
                        po.code,
                        po.description[:30] + "..." if len(po.description) > 30 else po.description,
                        'N/A',
                        'Not Applicable'
                    ])
            
            # Create and style table
            table = Table(table_data, colWidths=[1*inch, 2.5*inch, 1*inch, 1.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(table)
            story.append(Spacer(1, 20))
        
        # Add summary section
        if course_count > 1:  # Only add summary if multiple courses
            story.append(PageBreak())
            story.append(Paragraph("<b>Overall Program Outcome Summary</b>", styles['Heading2']))
            story.append(Spacer(1, 10))
            
            # Summary table
            summary_data = [['Program Outcome', 'Overall Score (%)', 'Achievement Level']]
            achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
            
            for po in program_outcomes:
                if po.id in total_scores and total_weights[po.id] > 0:
                    avg_score = total_scores[po.id] / total_weights[po.id]
                    level = get_achievement_level(avg_score, achievement_levels)
                    
                    summary_data.append([
                        po.code,
                        f"{avg_score:.2f}%",
                        level.name if level else 'N/A'
                    ])
                else:
                    summary_data.append([
                        po.code,
                        'N/A',
                        'Not Applicable'
                    ])
            
            summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 20))
        
        story.append(Paragraph(f"<b>Total Courses:</b> {course_count}", styles['Normal']))
        
        # Footer
        story.append(Spacer(1, 30))
        story.append(Paragraph("This report was generated by Accredit Helper Pro", styles['Normal']))
        story.append(Paragraph(f"Report includes {course_count} courses for student {student_name}", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
        
    except Exception as e:
        logging.error(f"Error generating ReportLab PDF for student {student_id}: {e}")
        return None

def generate_bulk_pdf_with_reportlab(courses, display_method='absolute', include_graduating_only=False):
    """Generate bulk PDF using ReportLab (programmatic approach) - Windows-friendly fallback"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    try:
        # Get all unique students from the courses
        all_students = {}  # student_id -> student_name
        
        for course in courses:
            course_students = Student.query.filter_by(course_id=course.id).all()
            for student in course_students:
                if include_graduating_only:
                    if is_graduating_student(student.student_id):
                        all_students[student.student_id] = get_student_name(student.student_id)
                else:
                    all_students[student.student_id] = get_student_name(student.student_id)
        
        # Create PDF buffer
        buffer = io.BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        
        # Build document content
        story = []
        
        # Main title
        story.append(Paragraph("Bulk Student Academic Report", title_style))
        story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        story.append(Paragraph(f"Total Students: {len(all_students)} | Total Courses: {len(courses)}", styles['Normal']))
        
        if include_graduating_only:
            story.append(Paragraph("<b>Graduating Students Only</b>", styles['Normal']))
        
        story.append(Spacer(1, 30))
        
        # Get program outcomes for compact display (limit to first 6)
        program_outcomes = ProgramOutcome.query.all()[:6]
        
        # Process each student (compact format for bulk report)
        for idx, student_id in enumerate(sorted(all_students.keys())):
            student_name = all_students[student_id]
            
            # Student header
            story.append(Paragraph(f"<b>{student_name}</b> (ID: {student_id})", styles['Heading3']))
            
            # Get student's courses from the filtered list
            student_courses = []
            for course in courses:
                if Student.query.filter_by(student_id=student_id, course_id=course.id).first():
                    student_courses.append(course)
            
            if student_courses:
                # Create compact table for all courses
                table_data = [['Course'] + [po.code for po in program_outcomes]]
                
                for course in student_courses:
                    student_in_course = Student.query.filter_by(student_id=student_id, course_id=course.id).first()
                    if student_in_course:
                        # Get individual results
                        bulk_data = bulk_load_course_data([course.id], display_method)
                        individual_result = calculate_individual_student_results(student_in_course.id, course.id, bulk_data, display_method)
                        
                        # Build row data
                        row_data = [f"{course.code}\\n{course.semester}"]
                        
                        for po in program_outcomes:
                            po_score = individual_result.get(po.id)
                            if po_score is not None:
                                row_data.append(f"{po_score:.1f}%")
                            else:
                                row_data.append('N/A')
                        
                        table_data.append(row_data)
                
                # Create and style table
                col_widths = [1.5*inch] + [0.8*inch] * len(program_outcomes)
                table = Table(table_data, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.green),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                
                story.append(table)
                story.append(Paragraph(f"Courses: {len(student_courses)}", styles['Normal']))
            else:
                story.append(Paragraph("No courses found for this student.", styles['Normal']))
            
            story.append(Spacer(1, 15))
            
            # Add page break every 3 students to avoid overcrowding
            if (idx + 1) % 3 == 0 and idx < len(all_students) - 1:
                story.append(PageBreak())
        
        # Footer
        story.append(Spacer(1, 30))
        story.append(Paragraph("This bulk report was generated by Accredit Helper Pro", styles['Normal']))
        story.append(Paragraph(f"Report includes {len(all_students)} students across {len(courses)} courses", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
        
    except Exception as e:
        logging.error(f"Error generating bulk ReportLab PDF: {e}")
        return None