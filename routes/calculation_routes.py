from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from app import db
from models import Course, Exam, Question, CourseOutcome, ProgramOutcome, Student, Score, ExamWeight, Log, CourseSettings
from datetime import datetime
import logging
import csv
import io
import os
from sqlalchemy import func
from routes.utility_routes import export_to_excel_csv
from decimal import Decimal
from flask import session

calculation_bp = Blueprint('calculation', __name__, url_prefix='/calculation')

@calculation_bp.route('/course/<int:course_id>')
def course_calculations(course_id):
    """Show calculation results for a course"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()
    makeup_exams = Exam.query.filter_by(course_id=course_id, is_makeup=True).all()
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    program_outcomes = ProgramOutcome.query.all()
    students = Student.query.filter_by(course_id=course_id).all()
    
    # Check if we have all necessary data
    if not exams:
        flash('No exams found for this course. Please add exams first.', 'warning')
        return redirect(url_for('course.course_detail', course_id=course_id))
    
    if not course_outcomes:
        flash('No course outcomes found for this course. Please add course outcomes first.', 'warning')
        return redirect(url_for('outcome.add_course_outcome', course_id=course_id))
    
    if not students:
        flash('No students found for this course. Please import students first.', 'warning')
        return redirect(url_for('student.import_students', course_id=course_id))
    
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
    
    # Check if weights are properly set
    if abs(total_weight - Decimal('1.0')) > Decimal('0.01'):  # Allow small decimal error
        flash(f'Exam weights do not add up to 100%. Current total: {total_weight*100:.1f}%. Please update weights.', 'warning')
        return redirect(url_for('exam.manage_weights', course_id=course_id))
    
    # Calculate student results
    student_results = {}
    for student in students:
        # Initialize results for this student
        student_results[student.id] = {
            'student': student,
            'exam_scores': {},  # Raw scores per exam
            'weighted_score': Decimal('0'),  # Final weighted score
            'course_outcome_scores': {},  # Scores per course outcome
            'program_outcome_scores': {}  # Scores per program outcome
        }
        
        # Calculate exam scores for student
        has_final_or_makeup = False
        for exam in exams:
            if exam.name.lower() in ['final', 'final exam']:
                has_final_or_makeup = True
                
            # Check if student has a makeup exam for this exam
            makeup_exam = next((m for m in makeup_exams if m.makeup_for == exam.id), None)
            
            # If student has a makeup, use that instead
            if makeup_exam:
                makeup_score = calculate_student_exam_score(student.id, makeup_exam.id)
                if makeup_score is not None:
                    has_final_or_makeup = True
                    student_results[student.id]['exam_scores'][exam.id] = makeup_score
                    continue
            
            # Otherwise use regular exam score
            exam_score = calculate_student_exam_score(student.id, exam.id)
            if exam_score is not None:
                student_results[student.id]['exam_scores'][exam.id] = exam_score
        
        # Skip student if they didn't take final or makeup
        if not has_final_or_makeup:
            student_results[student.id]['skip'] = True
            continue
        
        # Calculate weighted score
        weighted_score = Decimal('0')
        for exam_id, score in student_results[student.id]['exam_scores'].items():
            weighted_score += score * weights[exam_id]
        
        student_results[student.id]['weighted_score'] = weighted_score
        
        # Calculate course outcome scores
        for outcome in course_outcomes:
            score = calculate_course_outcome_score(student.id, outcome.id)
            student_results[student.id]['course_outcome_scores'][outcome.id] = score
        
        # Calculate program outcome scores
        for outcome in program_outcomes:
            score = calculate_program_outcome_score(student.id, outcome.id, course_id)
            student_results[student.id]['program_outcome_scores'][outcome.id] = score
    
    # Calculate average scores for the whole class
    class_results = {
        'course_outcome_scores': {},
        'program_outcome_scores': {}
    }
    
    # Calculate average course outcome scores
    for outcome in course_outcomes:
        scores = [r['course_outcome_scores'][outcome.id] for r in student_results.values() 
                 if not r.get('skip') and r['course_outcome_scores'][outcome.id] is not None]
        if scores:
            class_results['course_outcome_scores'][outcome.id] = sum(scores) / len(scores)
        else:
            class_results['course_outcome_scores'][outcome.id] = None
    
    # Calculate average program outcome scores
    for outcome in program_outcomes:
        scores = [r['program_outcome_scores'][outcome.id] for r in student_results.values() 
                 if not r.get('skip') and r['program_outcome_scores'][outcome.id] is not None]
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
            'program_outcomes': [po.code for po in outcome.program_outcomes]
        }
    
    # Format program outcome results
    for outcome in program_outcomes:
        avg_score = class_results['program_outcome_scores'].get(outcome.id)
        related_course_outcomes = [co.code for co in outcome.course_outcomes if co.course_id == course_id]
        program_outcome_results[outcome.code] = {
            'description': outcome.description,
            'percentage': avg_score if avg_score is not None else 0,
            'course_outcomes': related_course_outcomes
        }
    
    # Format student results for template
    formatted_student_results = {}
    for student_id, data in student_results.items():
        if data.get('skip'):
            continue
            
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
            'overall_percentage': data['weighted_score'],
            'course_outcomes': course_outcome_scores,
            'exam_scores': exam_scores
        }
    
    # Check if we have questions with course outcomes
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
    
    # Check if weights are valid (already calculated above)
    has_valid_weights = abs(total_weight - Decimal('1.0')) <= Decimal('0.01')
    
    # Log calculation action
    log = Log(action="CALCULATE_RESULTS", 
             description=f"Calculated Accredit results for course: {course.code}")
    db.session.add(log)
    db.session.commit()
    
    return render_template('calculation/results.html', 
                         course=course,
                         exams=exams,
                         course_outcomes=course_outcomes,
                         program_outcomes=program_outcomes,
                         students=students,
                         student_results=formatted_student_results,
                         course_outcome_results=course_outcome_results,
                         program_outcome_results=program_outcome_results,
                         class_results=class_results,
                         weights=weights,
                         has_course_outcomes=bool(course_outcomes),
                         has_exam_questions=has_exam_questions,
                         has_student_scores=has_student_scores,
                         has_valid_weights=has_valid_weights,
                         active_page='courses')

@calculation_bp.route('/course/<int:course_id>/export')
def export_results(course_id):
    """Export calculation results to CSV in Excel-compatible format"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()
    makeup_exams = Exam.query.filter_by(course_id=course_id, is_makeup=True).all()
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    program_outcomes = ProgramOutcome.query.all()
    students = Student.query.filter_by(course_id=course_id).order_by(Student.student_id).all()
    
    # Prepare data for export
    data = []
    
    # Create human-readable headers
    headers = ['Student ID', 'Student Name', 'Final Score (%)']
    
    # Add exam headers
    for exam in exams:
        headers.append(f'{exam.name} Score (%)')
    
    # Add course outcome headers
    for co in course_outcomes:
        headers.append(f'CO: {co.code} (%)')
    
    # Add program outcome headers
    for po in program_outcomes:
        # Check if program outcome is linked to any course outcome
        has_link = False
        for co in course_outcomes:
            if po in co.program_outcomes:
                has_link = True
                break
        
        if has_link:
            headers.append(f'PO: {po.code} (%)')
    
    # Calculate and add student results
    for student in students:
        has_final_or_makeup = False
        final_score = Decimal('0')
        weights = {}
        
        # Get exam weights
        for exam in exams:
            weight = ExamWeight.query.filter_by(exam_id=exam.id).first()
            weights[exam.id] = weight.weight if weight else Decimal('0')
            
            if exam.name.lower() in ['final', 'final exam']:
                has_final_or_makeup = True
        
        # Calculate weighted score
        for exam in exams:
            # Check if student has a makeup exam for this exam
            makeup_exam = next((m for m in makeup_exams if m.makeup_for == exam.id), None)
            
            # If student has a makeup, use that instead
            if makeup_exam:
                makeup_score = calculate_student_exam_score(student.id, makeup_exam.id)
                if makeup_score is not None:
                    has_final_or_makeup = True
                    final_score += makeup_score * weights[exam.id]
                    continue
            
            # Otherwise use regular exam score
            exam_score = calculate_student_exam_score(student.id, exam.id)
            if exam_score is not None:
                final_score += exam_score * weights[exam.id]
        
        # Skip student if they didn't take final or makeup
        if not has_final_or_makeup:
            continue
        
        # Create student data row
        student_row = {
            'Student ID': student.student_id,
            'Student Name': f"{student.first_name} {student.last_name}".strip(),
            'Final Score (%)': round(final_score, 2)
        }
        
        # Add exam scores
        for exam in exams:
            exam_score = calculate_student_exam_score(student.id, exam.id)
            student_row[f'{exam.name} Score (%)'] = round(exam_score, 2) if exam_score is not None else ''
        
        # Add course outcome scores
        for co in course_outcomes:
            co_score = calculate_course_outcome_score(student.id, co.id)
            student_row[f'CO: {co.code} (%)'] = round(co_score, 2) if co_score is not None else ''
        
        # Add program outcome scores
        for po in program_outcomes:
            # Check if program outcome is linked to any course outcome
            has_link = False
            for co in course_outcomes:
                if po in co.program_outcomes:
                    has_link = True
                    break
            
            if has_link:
                po_score = calculate_program_outcome_score(student.id, po.id, course_id)
                student_row[f'PO: {po.code} (%)'] = round(po_score, 2) if po_score is not None else ''
        
        data.append(student_row)
    
    # Export data using the utility function
    return export_to_excel_csv(data, f"accredit_results_{course.code}", headers)

# Helper function to calculate a student's score for an exam
def calculate_student_exam_score(student_id, exam_id):
    """Calculate a student's total score for an exam as a percentage of possible points"""
    exam = Exam.query.get(exam_id)
    questions = Question.query.filter_by(exam_id=exam_id).all()
    
    if not questions:
        return None
    
    total_score = Decimal('0')
    total_possible = Decimal('0')
    
    for question in questions:
        score = Score.query.filter_by(
            student_id=student_id,
            question_id=question.id,
            exam_id=exam_id
        ).first()
        
        if score:
            total_score += score.score
        
        total_possible += question.max_score
    
    if total_possible == Decimal('0'):
        return None
    
    return (total_score / total_possible) * Decimal('100')

def calculate_course_outcome_score(student_id, outcome_id):
    """Calculate a student's score for a course outcome based on related questions"""
    outcome = CourseOutcome.query.get(outcome_id)
    if not outcome:
        # Added check if outcome exists
        return None

    # Get all questions associated with this course outcome
    questions = outcome.questions

    if not questions:
        # No questions linked to this outcome
        return None

    # --- Correction Start ---
    # 1. Calculate the total possible score from ALL relevant questions first.
    total_possible = sum(q.max_score for q in questions)

    # Handle cases where an outcome might be linked only to 0-point questions
    if total_possible == Decimal('0'):
        # Similar logic as optimized: check if student scored any points on these 0-max_score questions
        student_score_exists_positive = False
        for question in questions:
            score = Score.query.filter_by(
                student_id=student_id,
                question_id=question.id
                # Note: This filter might still be ambiguous if question.id appears in multiple exams.
                # The optimized version correctly uses (student_id, question.id, exam_id)
            ).first()
            if score and score.score > 0:
                student_score_exists_positive = True
                break
        # Return 100% if they scored positive points on 0-possible, else 0%
        return Decimal('100.0') if student_score_exists_positive else Decimal('0.0')

    # 2. Calculate the student's total score, treating missing scores as 0.
    total_score = Decimal('0')
    for question in questions:
        # Query for the specific score
        score = Score.query.filter_by(
            student_id=student_id,
            question_id=question.id
            # Ambiguity concern noted above still applies here.
        ).first()

        if score: # Check if score record exists
            # Ensure score is Decimal
            total_score += Decimal(score.score)
        # Implicitly, if score record doesn't exist, we add 0, which is correct.

    # 3. Calculate the percentage.
    # total_possible is guaranteed non-zero here.
    return (total_score / total_possible) * Decimal('100')

# Helper function to calculate a student's score for a program outcome
def calculate_program_outcome_score(student_id, outcome_id, course_id):
    """Calculate a student's score for a program outcome based on related course outcomes"""
    program_outcome = ProgramOutcome.query.get(outcome_id)
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    
    # Find course outcomes associated with this program outcome
    related_course_outcomes = [co for co in course_outcomes if program_outcome in co.program_outcomes]
    
    if not related_course_outcomes:
        return None
    
    total_score = Decimal('0')
    count = 0
    
    for course_outcome in related_course_outcomes:
        score = calculate_course_outcome_score(student_id, course_outcome.id)
        if score is not None:
            total_score += score
            count += 1
    
    if count == 0:
        return None
    
    return total_score / count 

@calculation_bp.route('/all_courses')
def all_courses_calculations():
    """Show program outcome scores for all courses"""
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Improved query with eager loading to reduce database hits
    courses = Course.query.options(
        db.joinedload(Course.course_outcomes),
        db.joinedload(Course.exams),
        db.joinedload(Course.students),
        db.joinedload(Course.settings)
    ).all()
    
    # Preload all program outcomes in one query
    program_outcomes = ProgramOutcome.query.all()
    program_outcomes_dict = {po.id: po for po in program_outcomes}
    
    # Get the display method from session or default to absolute
    display_method = session.get('display_method', 'absolute')
    
    # Initialize data structure to hold results for all courses
    all_results = {}
    
    # Total number of courses for progress calculation
    total_courses = len([c for c in courses if c.course_outcomes and c.exams])
    processed_courses = 0
    
    # Prepare mapping tables to reduce lookups
    # Get all exam weights and score data in batches
    all_exam_weights = {}
    
    # Get all exam weights in a single query
    exam_weights = ExamWeight.query.all()
    for weight in exam_weights:
        all_exam_weights[(weight.exam_id)] = weight.weight
    
    for course in courses:
        # Skip courses with no outcomes or exams
        if not course.course_outcomes or not course.exams:
            continue
            
        # Update progress - useful for frontend progress tracking
        processed_courses += 1
        current_progress = int((processed_courses / total_courses) * 100) if total_courses > 0 else 100
        
        course_id = course.id
        course_code = course.code
        
        # Get the course settings or create default - use the preloaded relation
        settings = course.settings
        if not settings:
            settings = CourseSettings(
                course_id=course_id,
                success_rate_method=display_method,
                relative_success_threshold=60.0
            )
            db.session.add(settings)
            db.session.commit()
        
        # Update the calculation method based on session if needed
        settings.success_rate_method = display_method
        
        # Filter preloaded exams instead of new queries
        exams = [e for e in course.exams if not e.is_makeup]
        makeup_exams = [e for e in course.exams if e.is_makeup]
        
        # Get students for this course - use preloaded relation
        students = course.students
        
        # Check if we have all necessary data to calculate results
        if not exams or not students:
            continue
            
        # Get mandatory exams - filter in-memory
        mandatory_exams = [exam for exam in exams if exam.is_mandatory]
        
        # Get exam weights - use preloaded weights dict
        weights = {}
        for exam in exams:
            weight = all_exam_weights.get(exam.id)
            weights[exam.id] = weight if weight is not None else Decimal('0')
        
        # Preload all course outcomes for this course
        course_outcomes = course.course_outcomes
        
        # Preload all question-course outcome associations for this course
        question_ids = []
        for exam in exams:
            question_ids.extend([q.id for q in exam.questions])
        
        # Create a map of course outcomes to their related questions
        outcome_questions = {}
        for co in course_outcomes:
            outcome_questions[co.id] = co.questions
        
        # Create a map of program outcomes to their related course outcomes
        program_to_course_outcomes = {}
        for po in program_outcomes:
            related_cos = [co for co in course_outcomes if po in co.program_outcomes]
            program_to_course_outcomes[po.id] = related_cos
        
        # Calculate student results based on selected method
        student_results = {}
        success_count = 0
        total_students = 0
        
        # Preload scores for this course to reduce database hits
        # Get all scores for this course's students in one query
        student_ids = [s.id for s in students]
        exam_ids = [e.id for e in exams + makeup_exams]
        
        # Only load scores if we have students and exams
        if student_ids and exam_ids:
            # Preload scores in batches if there are many students/exams
            batch_size = 100
            all_scores = {}
            
            for i in range(0, len(student_ids), batch_size):
                batch_student_ids = student_ids[i:i+batch_size]
                scores = Score.query.filter(
                    Score.student_id.in_(batch_student_ids),
                    Score.exam_id.in_(exam_ids)
                ).all()
                
                for score in scores:
                    key = (score.student_id, score.question_id, score.exam_id)
                    all_scores[key] = score.score
        
        for student in students:
            # Initialize student results
            student_results[student.id] = {
                'student': student,
                'exam_scores': {},  # Raw scores per exam
                'weighted_score': Decimal('0'),  # Final weighted score
                'program_outcome_scores': {},  # Scores per program outcome
                'skip': False
            }
            
            # Check if student should be skipped due to mandatory exam policy
            if mandatory_exams:
                skip_student = True
                for exam in mandatory_exams:
                    # Check regular exam
                    exam_score = calculate_student_exam_score_optimized(
                        student.id, exam.id, all_scores, exam.questions
                    )
                    if exam_score is not None and exam_score > 0:
                        skip_student = False
                        break
                        
                    # Check makeup exam if exists
                    makeup_exam = next((m for m in makeup_exams if m.makeup_for == exam.id), None)
                    if makeup_exam:
                        makeup_score = calculate_student_exam_score_optimized(
                            student.id, makeup_exam.id, all_scores, makeup_exam.questions
                        )
                        if makeup_score is not None and makeup_score > 0:
                            skip_student = False
                            break
                
                if skip_student:
                    student_results[student.id]['skip'] = True
                    continue
            
            # Calculate exam scores for student
            for exam in exams:
                # Check if student has a makeup exam for this exam
                makeup_exam = next((m for m in makeup_exams if m.makeup_for == exam.id), None)
                
                # If student has a makeup, use that instead
                if makeup_exam:
                    makeup_score = calculate_student_exam_score_optimized(
                        student.id, makeup_exam.id, all_scores, makeup_exam.questions
                    )
                    if makeup_score is not None:
                        student_results[student.id]['exam_scores'][exam.id] = makeup_score
                        continue
                
                # Otherwise use regular exam score
                exam_score = calculate_student_exam_score_optimized(
                    student.id, exam.id, all_scores, exam.questions
                )
                if exam_score is not None:
                    student_results[student.id]['exam_scores'][exam.id] = exam_score
            
            # Calculate weighted score
            weighted_score = Decimal('0')
            for exam_id, score in student_results[student.id]['exam_scores'].items():
                weighted_score += score * weights.get(exam_id, Decimal('0'))
            
            student_results[student.id]['weighted_score'] = weighted_score
            
            # Calculate program outcome scores
            for outcome in program_outcomes:
                score = calculate_program_outcome_score_optimized(
                    student.id, outcome.id, course_id, all_scores, program_to_course_outcomes, outcome_questions
                )
                student_results[student.id]['program_outcome_scores'][outcome.id] = score
                
            # Count successes for relative method
            total_students += 1
            if weighted_score >= settings.relative_success_threshold:
                success_count += 1
        
        # Calculate success rate based on method
        class_results = {
            'program_outcome_scores': {},
            'total_students': total_students,
            'success_count': success_count,
            'success_rate': (success_count / total_students * 100) if total_students > 0 else 0
        }
        
        # Calculate average program outcome scores
        for outcome in program_outcomes:
            scores = [r['program_outcome_scores'][outcome.id] for r in student_results.values() 
                    if not r.get('skip') and r['program_outcome_scores'][outcome.id] is not None]
            
            if scores:
                # For absolute method: average of all student scores
                if settings.success_rate_method == 'absolute':
                    avg_score = sum(scores) / len(scores)
                    class_results['program_outcome_scores'][outcome.id] = avg_score
                # For relative method: percentage of students who achieved the threshold
                else:  # 'relative'
                    success_students = sum(1 for score in scores if score >= settings.relative_success_threshold)
                    success_rate = (success_students / len(scores) * 100) if len(scores) > 0 else 0
                    class_results['program_outcome_scores'][outcome.id] = success_rate
            else:
                class_results['program_outcome_scores'][outcome.id] = None
        
        # Format program outcome results for template
        program_outcome_results = {}
        for outcome in program_outcomes:
            avg_score = class_results['program_outcome_scores'].get(outcome.id)
            program_outcome_results[outcome.code] = {
                'description': outcome.description,
                'percentage': avg_score if avg_score is not None else 0
            }
        
        # Store results for this course
        all_results[course_code] = {
            'course': course,
            'program_outcome_results': program_outcome_results,
            'settings': settings
        }
    
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
                    'name': v['course'].name
                },
                'program_outcome_results': v['program_outcome_results'],
                'settings': {
                    'success_rate_method': v['settings'].success_rate_method,
                    'relative_success_threshold': float(v['settings'].relative_success_threshold)
                }
            } for k, v in all_results.items()},
            'program_outcomes': [{'id': po.id, 'code': po.code, 'description': po.description} for po in program_outcomes],
            'progress': 100  # Always 100 when returning final results
        })
    
    # For regular requests, render the template
    return render_template('calculation/all_courses.html', 
                          all_results=all_results,
                          program_outcomes=program_outcomes,
                          active_page='all_courses')

@calculation_bp.route('/all_courses_loading')
def all_courses_loading():
    """Shows a loading page for all courses calculations"""
    # Get program outcomes for the basic structure
    program_outcomes = ProgramOutcome.query.all()
    
    return render_template('calculation/all_courses_loading.html', 
                          program_outcomes=program_outcomes,
                          active_page='all_courses')

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
        return redirect(url_for('calculation.all_courses_loading'))
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

@calculation_bp.route('/update_display_method', methods=['POST'])
def update_display_method():
    """Update display method preference in session"""
    if request.method == 'POST':
        display_method = request.form.get('display_method')
        if display_method in ['absolute', 'relative']:
            # Store the display method in session
            session['display_method'] = display_method
            return jsonify({'status': 'success'})
    return jsonify({'status': 'error'})

# Optimized helper function to calculate a student's score without database hits
def calculate_student_exam_score_optimized(student_id, exam_id, scores_dict, questions):
    """Calculate a student's total score for an exam using preloaded data"""
    if not questions:
        return None
    
    total_score = Decimal('0')
    total_possible = Decimal('0')
    
    for question in questions:
        score_value = scores_dict.get((student_id, question.id, exam_id))
        
        if score_value:
            total_score += score_value
        
        total_possible += question.max_score
    
    if total_possible == Decimal('0'):
        return None
    
    return (total_score / total_possible) * Decimal('100')

def calculate_course_outcome_score_optimized(student_id, outcome_id, all_scores, outcome_questions):
    """Calculate a student's score for a course outcome using preloaded data"""
    questions = outcome_questions.get(outcome_id, [])

    if not questions:
        return None # No questions linked to this outcome

    # --- Correction Start ---
    # 1. Calculate the total possible score from ALL relevant questions first.
    total_possible = sum(q.max_score for q in questions)

    # Handle cases where an outcome might be linked only to 0-point questions
    if total_possible == Decimal('0'):
        # If total possible is 0, achievement is undefined or could be considered 100% if any score > 0 exists?
        # Returning None is safest, or 0 if preferred. Or check if any score > 0.
        # Let's check if any score exists and is positive for this outcome's questions.
        student_score_exists_positive = False
        for question in questions:
            exam_id = question.exam_id
            score_value = all_scores.get((student_id, question.id, exam_id))
            if score_value and score_value > 0:
                student_score_exists_positive = True
                break
        # If possible is 0, but student scored > 0 (extra credit?), return 100%. Otherwise 0 or None.
        # Returning 0 is a reasonable default if no points were possible and none were scored.
        return Decimal('100.0') if student_score_exists_positive else Decimal('0.0')


    # 2. Calculate the student's total score, treating missing scores as 0.
    total_score = Decimal('0')
    for question in questions:
        exam_id = question.exam_id
        # Use .get() which returns None if the key is not found
        score_value = all_scores.get((student_id, question.id, exam_id))

        if score_value is not None: # Check if score exists
             # Ensure score_value is Decimal for consistency
            total_score += Decimal(score_value)
        # Implicitly, if score_value is None, we add 0, which is correct.

    # 3. Calculate the percentage.
    # total_possible is guaranteed non-zero here due to the check above.
    return (total_score / total_possible) * Decimal('100')

# Optimized helper function to calculate a student's score for a program outcome
def calculate_program_outcome_score_optimized(student_id, outcome_id, course_id, all_scores, 
                                             program_to_course_outcomes, outcome_questions):
    """Calculate a student's score for a program outcome using preloaded data"""
    # Get related course outcomes from the preloaded mapping
    related_course_outcomes = program_to_course_outcomes.get(outcome_id, [])
    
    if not related_course_outcomes:
        return None
    
    total_score = Decimal('0')
    count = 0
    
    for course_outcome in related_course_outcomes:
        score = calculate_course_outcome_score_optimized(
            student_id, course_outcome.id, all_scores, outcome_questions
        )
        if score is not None:
            total_score += score
            count += 1
    
    if count == 0:
        return None
    
    return total_score / count 