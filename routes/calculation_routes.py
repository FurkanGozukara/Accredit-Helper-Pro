from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from app import db
from models import Course, Exam, Question, CourseOutcome, ProgramOutcome, Student, Score, ExamWeight, Log, CourseSettings, AchievementLevel, StudentExamAttendance
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
    
    # Determine which calculation method to use (from course settings)
    calculation_method = settings.success_rate_method
    
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
            # Get scores for this student from exam_scores_dict
            if exam.id in exam_scores_dict and student.id in exam_scores_dict[exam.id]:
                raw_score = float(exam_scores_dict[exam.id][student.id])
                # Convert raw score to percentage
                max_score = exam_max_scores[exam.id]
                if max_score > 0:
                    exam_score = (raw_score / max_score) * 100
            student_result['exam_scores'][exam.name] = exam_score
        
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

@calculation_bp.route('/all_courses', endpoint='all_courses')
def all_courses_calculations():
    """Show program outcome scores for all courses"""
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Get sort parameters from query string, default to course_code_asc
    sort_by = request.args.get('sort_by', 'course_code_asc')
    
    # Get filter parameters
    filter_year = request.args.get('year', '')
    search_query = request.args.get('search', '').lower()
    
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
    
    # Calculate results for each course
    for course in courses:
        # Check if course is excluded
        is_excluded = course.settings and course.settings.excluded
        if is_excluded:
            excluded_courses.append(course)
            # Add excluded course to all_results to make it visible in the UI
            all_results[course.code] = {
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
        all_results[course.code] = {
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
        sorted_keys = sorted(all_results.keys())
    elif sort_by == 'course_code_desc':
        sorted_keys = sorted(all_results.keys(), reverse=True)
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
        sorted_keys = sorted(all_results.keys())
    
    for key in sorted_keys:
        sorted_results[key] = all_results[key]
    
    # Log action
    log = Log(action="ALL_COURSES_CALCULATIONS", 
             description=f"Viewed program outcome scores for all courses")
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
            'progress': 100,  # Always 100 when returning final results
            'current_sort': sort_by
        })
    
    # For regular requests, render the template
    return render_template('calculation/all_courses.html', 
                          all_results=sorted_results,
                          program_outcomes=program_outcomes,
                          po_averages=po_averages,
                          excluded_courses=excluded_courses,
                          years=years,
                          active_page='all_courses',
                          current_sort=sort_by)

@calculation_bp.route('/all_courses_loading', endpoint='all_courses_loading')
def all_courses_loading():
    """Redirects to all_courses for backward compatibility"""
    return redirect(url_for('calculation.all_courses'))

@calculation_bp.route('/all_courses/export', endpoint='export_all_courses')
def export_all_courses():
    """Export program outcome scores for all courses to CSV"""
    # Get sort parameters from query string, default to course_code_asc
    sort_by = request.args.get('sort_by', 'course_code_asc')
    
    # Get filter parameters
    filter_year = request.args.get('year', '')
    search_query = request.args.get('search', '').lower()
    
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
            all_results[course.code] = {
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
        all_results[course.code] = {
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
        sorted_keys = sorted(all_results.keys())
    elif sort_by == 'course_code_desc':
        sorted_keys = sorted(all_results.keys(), reverse=True)
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
        sorted_keys = sorted(all_results.keys())
    
    for key in sorted_keys:
        sorted_results[key] = all_results[key]
    
    # Prepare data for CSV export
    csv_data = []
    
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
    
    # Log action
    log = Log(action="EXPORT_ALL_COURSES", 
             description=f"Exported program outcome scores for all courses to CSV")
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

def calculate_course_outcome_score_optimized(student_id, outcome_id, scores_dict, outcome_questions, normalized_weights=None):
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
            
            # Check if student attended the makeup
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
    
    # Calculate weighted score for each exam containing questions for this outcome
    weighted_outcome_score = Decimal('0')
    total_applied_weight = Decimal('0')
    
    for exam_id in filtered_exam_ids:
        if exam_id not in questions_by_exam:
            continue
            
        exam_questions = questions_by_exam[exam_id]
        
        # Skip if this exam isn't in the weights (shouldn't happen with proper master weights)
        if exam_id not in exam_weights:
            continue
            
        # Calculate percentage score for this exam's questions related to the outcome
        exam_total_possible = Decimal('0')
        exam_total_score = Decimal('0')
        
        for question in exam_questions:
            score_value = scores_dict.get((student_id, question.id, exam_id))
            if score_value is not None:
                exam_total_score += Decimal(str(score_value))
            exam_total_possible += question.max_score
        
        if exam_total_possible > Decimal('0'):
            exam_percentage = (exam_total_score / exam_total_possible) * Decimal('100')
            # Apply exam weight to this percentage
            weighted_outcome_score += exam_percentage * exam_weights[exam_id]
            total_applied_weight += exam_weights[exam_id]
    
    # If no weights were applied, return 0
    if total_applied_weight == Decimal('0'):
        return Decimal('0')
        
    # Return the weighted outcome score normalized by the total applied weight
    return weighted_outcome_score / total_applied_weight

# Optimized helper function to calculate a student's score for a program outcome
def calculate_program_outcome_score_optimized(student_id, outcome_id, course_id, scores_dict, 
                                             program_to_course_outcomes, outcome_questions, normalized_weights=None):
    """Calculate a student's score for a program outcome using preloaded data
    
    Parameters:
    - student_id: The student's ID
    - outcome_id: The Program Outcome ID
    - course_id: The Course ID
    - scores_dict: Dictionary containing all scores for fast lookup
    - program_to_course_outcomes: Map of program outcomes to related course outcomes
    - outcome_questions: Dictionary mapping outcome_id to list of questions
    - normalized_weights: Pre-calculated, normalized weights for all exams in the course
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
    
    # Get individual course outcome scores and apply weights
    for course_outcome in related_course_outcomes:
        # Calculate the score for this course outcome, passing through the normalized weights
        co_score = calculate_course_outcome_score_optimized(
            student_id, course_outcome.id, scores_dict, outcome_questions, normalized_weights
        )
        
        if co_score is not None:
            # Each course outcome contributes equally by default (can be customized if needed)
            total_weighted_score += co_score
            total_weight += Decimal('1')
    
    # Calculate the weighted average if there are valid scores
    if total_weight > Decimal('0'):
        return total_weighted_score / total_weight
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
                    # For makeup exams, only consider attended if explicitly marked (default is False)
                    makeup_attended = attendance_dict.get((student.id, makeup_exam.id), False)
                
                # Skip student if they didn't attend both the mandatory exam AND its makeup (if exists)
                if not regular_attended and (not makeup_exam or not makeup_attended):
                    skip_student = True
                    break
            
            if skip_student:
                student_data['skip'] = True
                student_results[student.id] = student_data
                continue
        
        # Calculate weighted score for overall course grade
        total_weighted_score = Decimal('0')
        for exam in regular_exams:
            # Check if there's a makeup for this exam
            makeup_exam = next((m for m in makeup_exams if m.makeup_for == exam.id), None)
            
            # If there's a makeup exam, check if student attended it
            if makeup_exam:
                makeup_attended = attendance_dict.get((student.id, makeup_exam.id), False)
                
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
                student.id, outcome.id, scores_dict, outcome_questions, normalized_weights
            )
            student_data['course_outcomes'][outcome.id] = co_score
        
        # Calculate program outcome scores
        for outcome in program_outcomes:
            po_score = calculate_program_outcome_score_optimized(
                student.id, outcome.id, course_id, scores_dict, 
                program_to_course_outcomes, outcome_questions, normalized_weights
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
                    makeup_attended = attendance_dict.get((student.id, makeup_exam.id), False)
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
                makeup_attended = attendance_dict.get((student.id, makeup_exam.id), False)
                
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
            score = calculate_course_outcome_score_optimized(student.id, outcome.id, scores_dict, outcome_questions, normalized_weights)
            student_results[student.id]['course_outcome_scores'][outcome.id] = score
        
        # Calculate program outcome scores
        for outcome in program_outcomes:
            score = calculate_program_outcome_score_optimized(student.id, outcome.id, course_id, scores_dict, program_to_course_outcomes, outcome_questions, normalized_weights)
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
    students = Student.query.filter_by(course_id=course_id).order_by(Student.student_id).all()
    
    # Get achievement levels for this course
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
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
    
    # Create a map of exams to their questions
    questions_by_exam = {}
    for exam in all_exams:
        questions_by_exam[exam.id] = exam.questions
    
    # Create a map of course outcomes to their related questions
    outcome_questions = {}
    for co in course_outcomes:
        outcome_questions[co.id] = co.questions
    
    # Define headers for CSV
    headers = ['Student ID', 'Student Name']
    
    # Add exam score headers
    for exam in regular_exams:
        headers.append(f'{exam.name} Score (%)')
    
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
            
        # Prepare student row as a dictionary
        student_row = {
            'Student ID': student.student_id,
            'Student Name': f"{student.first_name} {student.last_name}".strip()
        }
        
        # Calculate and add exam scores
        weighted_score = Decimal('0')
        total_weight_used = Decimal('0')
        
        for exam in regular_exams:
            # Check if this exam has a makeup and if the student took the makeup
            use_makeup = False
            actual_exam_id = exam.id
            
            if exam.id in makeup_map:
                makeup_exam = makeup_map[exam.id]
                # Check if student has scores for the makeup
                has_makeup_scores = False
                for question in questions_by_exam[makeup_exam.id]:
                    if (student.id, question.id, makeup_exam.id) in scores_dict:
                        has_makeup_scores = True
                        break
                
                if has_makeup_scores:
                    use_makeup = True
                    actual_exam_id = makeup_exam.id
            
            # Calculate score
            exam_score = calculate_student_exam_score_optimized(
                student.id, actual_exam_id, scores_dict, 
                questions_by_exam[actual_exam_id], attendance_dict
            )
            
            if exam_score is not None:
                # Add to student row
                student_row[f'{exam.name} Score (%)'] = round(float(exam_score), 2)
                
                # Add to weighted score if weight exists
                if exam.id in weights and weights[exam.id] > Decimal('0'):
                    weighted_score += exam_score * weights[exam.id]
                    total_weight_used += weights[exam.id]
            else:
                student_row[f'{exam.name} Score (%)'] = "N/A"
        
        # Calculate and add course outcome achievements
        for co in course_outcomes:
            # Calculate course outcome achievement
            co_score = calculate_course_outcome_score_optimized(
                student.id, co.id, scores_dict, outcome_questions, normalized_weights
            )
            
            if co_score is not None:
                # Add score and achievement level
                student_row[f'{co.code} Achievement (%)'] = round(float(co_score), 2)
                
                # Get achievement level
                level = get_achievement_level(float(co_score), achievement_levels)
                student_row[f'{co.code} Achievement Level'] = level['name']
            else:
                student_row[f'{co.code} Achievement (%)'] = "N/A"
                student_row[f'{co.code} Achievement Level'] = "N/A"
        
        # Calculate and add overall weighted score
        if total_weight_used > Decimal('0'):
            overall_percentage = weighted_score / total_weight_used
            student_row['Overall Weighted Score (%)'] = round(float(overall_percentage), 2)
            
            # Get overall achievement level - ensure we're using the properly rounded value
            level = get_achievement_level(round(float(overall_percentage), 2), achievement_levels)
            student_row['Overall Achievement Level'] = level['name']
        else:
            student_row['Overall Weighted Score (%)'] = "N/A"
            student_row['Overall Achievement Level'] = "N/A"
        
        # Add row to data
        data.append(student_row)
    
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