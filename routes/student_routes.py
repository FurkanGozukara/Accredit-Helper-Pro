from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app as app
from app import db
from models import Student, Course, Exam, Question, Score, Log
from datetime import datetime
import logging
import csv
import io
import re
from routes.utility_routes import export_to_excel_csv
from decimal import Decimal

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
        
        # Keep track of student IDs for uniqueness validation during import
        imported_student_ids = set()
        
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
                
                # Check for duplicate student IDs in the current import batch
                if student_id in imported_student_ids:
                    errors.append(f"Line {i}: Duplicate student ID {student_id} in import data")
                    continue
                
                imported_student_ids.add(student_id)
                
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
                        score_value = Decimal(score_value)
                        # Validate score is within range
                        if score_value < 0:
                            score_value = Decimal('0')
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
            score_value = Decimal(score_value)
            
            if score_value < 0:
                score_value = Decimal('0')
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

@student_bp.route('/exam/<int:exam_id>/import-scores', methods=['POST'])
def import_scores(exam_id):
    """Import scores from CSV/text data"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    
    # Get all questions for this exam, indexed by number
    questions = {q.number: q for q in Question.query.filter_by(exam_id=exam_id).all()}
    
    if not questions:
        flash('No questions found for this exam. Please add questions first.', 'warning')
        return redirect(url_for('exam.exam_detail', exam_id=exam_id))
    
    # Get all students for this course, indexed by student_id
    students_dict = {s.student_id: s for s in Student.query.filter_by(course_id=course.id).all()}
    
    if not students_dict:
        flash('No students found for this course. Please import students first.', 'warning')
        return redirect(url_for('student.import_students', course_id=course.id))
    
    # Get score data from file or textarea
    scores_data = ""
    if 'scores_file' in request.files and request.files['scores_file'].filename:
        file = request.files['scores_file']
        try:
            scores_data = file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                scores_data = file.read().decode('latin-1')
            except:
                flash('Could not decode the file. Please ensure it is a text file.', 'error')
                return redirect(url_for('student.manage_scores', exam_id=exam_id))
    else:
        scores_data = request.form.get('scores_data', '')
    
    if not scores_data.strip():
        flash('No score data provided', 'error')
        return redirect(url_for('student.manage_scores', exam_id=exam_id))
    
    # Process data
    lines = scores_data.strip().split('\n')
    scores_added = 0
    errors = []
    
    for i, line in enumerate(lines, 1):
        # Skip empty lines
        if not line.strip():
            continue
        
        # Try to parse the line
        try:
            # Split by semicolons
            parts = [p.strip() for p in line.split(';') if p.strip()]
            
            if len(parts) < 3:  # Need at least student_id, name, and one score
                errors.append(f"Line {i}: Not enough data (expected at least student ID, name, and one score)")
                continue
            
            student_id = parts[0]
            # We don't use the name part (parts[1]) as we match by student_id
            
            # Find the student
            if student_id not in students_dict:
                errors.append(f"Line {i}: Student with ID {student_id} not found in this course")
                continue
            
            student = students_dict[student_id]
            
            # Process scores (format q1:score1;q2:score2;...)
            for j, score_str in enumerate(parts[2:], 1):
                # Skip empty scores
                if not score_str:
                    continue
                
                # Map score to question number
                if j > len(questions):
                    errors.append(f"Line {i}: Too many scores provided (only {len(questions)} questions exist)")
                    break
                
                # Try to convert score to number
                try:
                    score_value = Decimal(score_str)
                    
                    # Get corresponding question
                    question = questions[j]
                    
                    # Validate score is within range
                    if score_value < 0:
                        score_value = Decimal('0')
                    elif score_value > question.max_score:
                        score_value = question.max_score
                        
                    # Update or create score
                    score = Score.query.filter_by(
                        student_id=student.id,
                        question_id=question.id,
                        exam_id=exam_id
                    ).first()
                    
                    if score:
                        score.score = score_value
                    else:
                        score = Score(
                            score=score_value,
                            student_id=student.id,
                            question_id=question.id,
                            exam_id=exam_id
                        )
                        db.session.add(score)
                    
                    scores_added += 1
                    
                except (ValueError, KeyError) as e:
                    errors.append(f"Line {i}: Error processing score {score_str} for question {j}: {str(e)}")
                    continue
        
        except Exception as e:
            errors.append(f"Line {i}: Error processing line - {str(e)}")
    
    if scores_added > 0:
        try:
            # Log action
            log = Log(action="IMPORT_SCORES", 
                     description=f"Imported {scores_added} scores for exam: {exam.name} in course: {course.code}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Successfully imported {scores_added} scores', 'success')
            
            if errors:
                flash(f'There were {len(errors)} errors during import. See details below.', 'warning')
                for error in errors[:10]:  # Show first 10 errors
                    flash(error, 'warning')
                if len(errors) > 10:
                    flash(f'... and {len(errors) - 10} more errors', 'warning')
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error committing score import: {str(e)}")
            flash(f'An error occurred while importing scores: {str(e)}', 'error')
    else:
        flash('No scores were imported. Please check the data format and try again.', 'error')
        for error in errors[:10]:  # Show first 10 errors
            flash(error, 'warning')
        if len(errors) > 10:
            flash(f'... and {len(errors) - 10} more errors', 'warning')
    
    return redirect(url_for('student.manage_scores', exam_id=exam_id))

@student_bp.route('/course/<int:course_id>/export')
def export_students(course_id):
    """Export students from a course to a CSV file"""
    course = Course.query.get_or_404(course_id)
    students = Student.query.filter_by(course_id=course_id).order_by(Student.student_id).all()
    
    # Prepare data for export
    data = []
    headers = ['Student ID', 'First Name', 'Last Name', 'Full Name']
    
    for student in students:
        data.append({
            'Student ID': student.student_id,
            'First Name': student.first_name,
            'Last Name': student.last_name,
            'Full Name': f"{student.first_name} {student.last_name}".strip()
        })
    
    # Export data using utility function
    return export_to_excel_csv(data, f"students_{course.code}", headers)

@student_bp.route('/edit/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    """Edit an existing student"""
    student = Student.query.get_or_404(student_id)
    course = Course.query.get_or_404(student.course_id)
    
    if request.method == 'POST':
        student_id_new = request.form.get('student_id')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        # Basic validation
        if not student_id_new or not first_name:
            flash('Student ID and First Name are required', 'error')
            return render_template('student/edit.html', 
                                student=student,
                                course=course,
                                active_page='courses')
        
        # Check if student ID already exists in this course (if changed)
        if student_id_new != student.student_id:
            existing_student = Student.query.filter_by(student_id=student_id_new, course_id=course.id).first()
            if existing_student:
                flash(f'Student with ID {student_id_new} already exists in this course', 'error')
                return render_template('student/edit.html', 
                                    student=student,
                                    course=course,
                                    active_page='courses')
        
        # Update student
        student.student_id = student_id_new
        student.first_name = first_name
        student.last_name = last_name
        student.updated_at = datetime.now()
        
        # Log action
        log = Log(action="EDIT_STUDENT", 
                description=f"Edited student {student_id_new} in course: {course.code}")
        db.session.add(log)
        
        try:
            db.session.commit()
            flash(f'Student {student_id_new} updated successfully', 'success')
            return redirect(url_for('course.course_detail', course_id=course.id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating student: {str(e)}")
            flash('An error occurred while updating the student', 'error')
            return render_template('student/edit.html', 
                                student=student,
                                course=course,
                                active_page='courses')
    
    # GET request
    return render_template('student/edit.html', 
                        student=student,
                        course=course,
                        active_page='courses')

@student_bp.route('/course/<int:course_id>/add', methods=['GET', 'POST'])
def add_student(course_id):
    """Add a new student to a course"""
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        # Basic validation
        if not student_id or not first_name:
            flash('Student ID and First Name are required', 'error')
            return render_template('student/add.html', 
                                course=course,
                                active_page='courses')
        
        # Check if student ID already exists in this course
        existing_student = Student.query.filter_by(student_id=student_id, course_id=course_id).first()
        if existing_student:
            flash(f'Student with ID {student_id} already exists in this course', 'error')
            return render_template('student/add.html', 
                                course=course,
                                active_page='courses')
        
        # Create new student
        new_student = Student(
            student_id=student_id,
            first_name=first_name,
            last_name=last_name,
            course_id=course_id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Log action
        log = Log(action="ADD_STUDENT", 
                description=f"Added student {student_id} to course: {course.code}")
        db.session.add(log)
        db.session.add(new_student)
        
        try:
            db.session.commit()
            flash(f'Student {student_id} added successfully', 'success')
            return redirect(url_for('course.course_detail', course_id=course.id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding student: {str(e)}")
            flash('An error occurred while adding the student', 'error')
            return render_template('student/add.html', 
                                course=course,
                                active_page='courses')
    
    # GET request
    return render_template('student/add.html', 
                        course=course,
                        active_page='courses') 