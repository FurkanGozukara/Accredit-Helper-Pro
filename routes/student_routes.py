from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from models import Student, Course, Exam, Question, Score, Log
from datetime import datetime
import logging
import csv
import io
import re

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/course/<int:course_id>/import', methods=['GET', 'POST'])
def import_students(course_id):
    """Import students from CSV or text file"""
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        # Check if file is provided
        if 'student_file' not in request.files and not request.form.get('student_data'):
            flash('You must provide either a file or paste student data', 'error')
            return render_template('student/import.html', 
                                 course=course,
                                 active_page='courses')
        
        student_data = ""
        
        # Get data from file or textarea
        if 'student_file' in request.files and request.files['student_file'].filename:
            file = request.files['student_file']
            try:
                student_data = file.read().decode('utf-8')
            except UnicodeDecodeError:
                try:
                    # Try another common encoding
                    student_data = file.read().decode('latin-1')
                except:
                    flash('Could not decode the file. Please ensure it is a text file.', 'error')
                    return render_template('student/import.html', 
                                         course=course,
                                         active_page='courses')
        else:
            student_data = request.form.get('student_data', '')
        
        if not student_data.strip():
            flash('No student data provided', 'error')
            return render_template('student/import.html', 
                                 course=course,
                                 active_page='courses')
        
        # Process the data
        lines = student_data.strip().split('\n')
        students_added = 0
        errors = []
        
        for i, line in enumerate(lines, 1):
            # Skip empty lines
            if not line.strip():
                continue
            
            # Try to parse the line
            try:
                # Split by tab, semicolon, or multiple spaces
                parts = re.split(r'[\t;]|\s{2,}', line.strip())
                parts = [p.strip() for p in parts if p.strip()]
                
                if len(parts) < 2:
                    errors.append(f"Line {i}: Not enough data (expected at least student ID and name)")
                    continue
                
                student_id = parts[0]
                
                # Handle different name formats
                if len(parts) == 2:
                    # Only one name field, treat as full name
                    full_name = parts[1]
                    name_parts = full_name.split()
                    if len(name_parts) == 1:
                        first_name = name_parts[0]
                        last_name = ""
                    else:
                        first_name = " ".join(name_parts[:-1])
                        last_name = name_parts[-1]
                else:
                    # Multiple name fields
                    first_name = parts[1]
                    last_name = " ".join(parts[2:])
                
                # Check if student already exists in this course
                existing_student = Student.query.filter_by(student_id=student_id, course_id=course_id).first()
                if existing_student:
                    errors.append(f"Line {i}: Student with ID {student_id} already exists in this course")
                    continue
                
                # Create new student
                new_student = Student(
                    student_id=student_id,
                    first_name=first_name,
                    last_name=last_name,
                    course_id=course_id
                )
                
                db.session.add(new_student)
                students_added += 1
                
            except Exception as e:
                errors.append(f"Line {i}: Error processing line - {str(e)}")
        
        if students_added > 0:
            try:
                # Log action
                log = Log(action="IMPORT_STUDENTS", 
                         description=f"Imported {students_added} students to course: {course.code}")
                db.session.add(log)
                
                db.session.commit()
                flash(f'Successfully imported {students_added} students', 'success')
                
                if errors:
                    flash(f'There were {len(errors)} errors during import. See details below.', 'warning')
                
                return render_template('student/import_result.html', 
                                     course=course,
                                     students_added=students_added,
                                     errors=errors,
                                     active_page='courses')
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error committing student import: {str(e)}")
                flash('An error occurred while importing students', 'error')
                return render_template('student/import.html', 
                                     course=course,
                                     active_page='courses')
        else:
            flash('No students were imported. Please check the errors below.', 'error')
            return render_template('student/import_result.html', 
                                 course=course,
                                 students_added=0,
                                 errors=errors,
                                 active_page='courses')
    
    # GET request
    return render_template('student/import.html', 
                         course=course,
                         active_page='courses')

@student_bp.route('/course/<int:course_id>/list')
def list_students(course_id):
    """List all students in a course"""
    course = Course.query.get_or_404(course_id)
    students = Student.query.filter_by(course_id=course_id).order_by(Student.student_id).all()
    
    return render_template('student/list.html', 
                         course=course,
                         students=students,
                         active_page='courses')

@student_bp.route('/delete/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    """Delete a student after confirmation"""
    student = Student.query.get_or_404(student_id)
    course_id = student.course_id
    
    try:
        # Log action before deletion
        log = Log(action="DELETE_STUDENT", 
                 description=f"Deleted student {student.student_id} from course: {student.course.code}")
        db.session.add(log)
        
        db.session.delete(student)
        db.session.commit()
        flash(f'Student {student.student_id} deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting student: {str(e)}")
        flash('An error occurred while deleting the student', 'error')
    
    return redirect(url_for('student.list_students', course_id=course_id))

@student_bp.route('/exam/<int:exam_id>/scores', methods=['GET', 'POST'])
def manage_scores(exam_id):
    """Manage student scores for an exam"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.number).all()
    students = Student.query.filter_by(course_id=course.id).order_by(Student.student_id).all()
    
    if not questions:
        flash('No questions found for this exam. Please add questions first.', 'warning')
        return redirect(url_for('exam.exam_detail', exam_id=exam_id))
    
    if not students:
        flash('No students found for this course. Please import students first.', 'warning')
        return redirect(url_for('student.import_students', course_id=course.id))
    
    if request.method == 'POST':
        try:
            # Optional: update existing scores instead of removing them all
            existing_scores = {}
            for existing_score in Score.query.filter_by(exam_id=exam_id).all():
                key = f"{existing_score.student_id}_{existing_score.question_id}"
                existing_scores[key] = existing_score
            
            # Process scores for each student and question
            for student in students:
                for question in questions:
                    score_value = request.form.get(f'score_{student.id}_{question.id}', '')
                    
                    # Skip empty scores
                    if score_value.strip() == '':
                        continue
                    
                    try:
                        score_value = float(score_value)
                        # Validate score is within range
                        if score_value < 0:
                            score_value = 0
                        elif score_value > question.max_score:
                            score_value = question.max_score
                        
                        # Check if score already exists
                        key = f"{student.id}_{question.id}"
                        if key in existing_scores:
                            # Update existing score
                            existing_scores[key].score = score_value
                        else:
                            # Create new score
                            new_score = Score(
                                score=score_value,
                                student_id=student.id,
                                question_id=question.id,
                                exam_id=exam_id
                            )
                            db.session.add(new_score)
                    
                    except ValueError:
                        # Skip invalid scores
                        continue
            
            # Log action
            log = Log(action="SAVE_SCORES", 
                     description=f"Updated scores for exam: {exam.name} in course: {course.code}")
            db.session.add(log)
            
            db.session.commit()
            flash('Scores saved successfully', 'success')
            return redirect(url_for('exam.exam_detail', exam_id=exam_id))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating scores: {str(e)}")
            flash('An error occurred while updating scores', 'error')
    
    # For GET request
    return render_template('student/scores.html', 
                         exam=exam,
                         course=course,
                         students=students,
                         questions=questions,
                         scores=Score.query.filter_by(exam_id=exam_id).all(),
                         active_page='courses')

@student_bp.route('/exam/<int:exam_id>/scores/auto-save', methods=['POST'])
def auto_save_score(exam_id):
    """Auto-save a single score via AJAX"""
    exam = Exam.query.get_or_404(exam_id)
    
    try:
        data = request.get_json()
        
        if not data or 'student_id' not in data or 'question_id' not in data:
            return jsonify({'success': False, 'error': 'Missing required data'})
        
        student_id = int(data['student_id'])
        question_id = int(data['question_id'])
        score_value = data.get('score', '')
        
        # Get the question to check max score
        question = Question.query.get_or_404(question_id)
        
        # Handle empty score (delete if exists)
        if score_value == '':
            existing_score = Score.query.filter_by(
                student_id=student_id,
                question_id=question_id,
                exam_id=exam_id
            ).first()
            
            if existing_score:
                db.session.delete(existing_score)
                db.session.commit()
            
            return jsonify({'success': True})
        
        # Convert and validate score
        try:
            score_value = float(score_value)
            
            if score_value < 0:
                score_value = 0
            elif score_value > question.max_score:
                score_value = question.max_score
                
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid score value'})
        
        # Get or create score record
        score = Score.query.filter_by(
            student_id=student_id,
            question_id=question_id,
            exam_id=exam_id
        ).first()
        
        if score:
            score.score = score_value
            score.updated_at = datetime.now()
        else:
            score = Score(
                score=score_value,
                student_id=student_id,
                question_id=question_id,
                exam_id=exam_id
            )
            db.session.add(score)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error auto-saving score: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}) 