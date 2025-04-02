from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from app import db
from models import Course, Exam, Question, CourseOutcome, ProgramOutcome, Student, Score, ExamWeight, Log
from datetime import datetime
import logging
import csv
import io
import os
from sqlalchemy import func
from routes.utility_routes import export_to_excel_csv
from decimal import Decimal

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

# Helper function to calculate a student's score for a course outcome
def calculate_course_outcome_score(student_id, outcome_id):
    """Calculate a student's score for a course outcome based on related questions"""
    outcome = CourseOutcome.query.get(outcome_id)
    questions = outcome.questions
    
    if not questions:
        return None
    
    total_score = Decimal('0')
    total_possible = Decimal('0')
    
    for question in questions:
        score = Score.query.filter_by(
            student_id=student_id,
            question_id=question.id
        ).first()
        
        if score:
            total_score += score.score
            total_possible += question.max_score
    
    if total_possible == Decimal('0'):
        return None
    
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