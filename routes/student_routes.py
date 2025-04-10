from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app as app
from app import db
from models import Student, Course, Exam, Question, Score, Log, StudentExamAttendance
from datetime import datetime
import logging
import csv
import io
import re
from routes.utility_routes import export_to_excel_csv
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
import pandas as pd
import numpy as np
import json
from sqlalchemy import and_, or_
from werkzeug.utils import secure_filename
import os
from chardet import detect
import traceback

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
                # Try to detect encoding with enhanced safety
                raw_data = file.read()
                if not raw_data:
                    flash('Empty file uploaded', 'error')
                    return render_template('student/import.html',
                                         course=course,
                                         active_page='courses')
                
                encoding_result = detect(raw_data)
                file.seek(0)  # Reset file position
                
                # Use detected encoding with high confidence or try multiple fallbacks
                if encoding_result and encoding_result['confidence'] > 0.7:
                    encoding = encoding_result['encoding']
                else:
                    # Try common encodings in order
                    encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']
                    for enc in encodings_to_try:
                        try:
                            student_data = raw_data.decode(enc)
                            logging.info(f"Successfully decoded file with {enc} encoding")
                            break
                        except UnicodeDecodeError:
                            continue
                    
                # If we haven't set student_data yet, use the first detected encoding
                if not student_data and encoding_result:
                    try:
                        student_data = raw_data.decode(encoding_result['encoding'])
                    except UnicodeDecodeError:
                        # Last resort: use latin-1 which should never fail
                        student_data = raw_data.decode('latin-1', errors='replace')
                        logging.warning("Decoded file with latin-1 and error replacement - some characters may be incorrect")
                
                if not student_data:
                    raise UnicodeDecodeError("Could not decode with any common encoding")
                    
            except Exception as e:
                flash(f'Could not decode the file: {str(e)}. Please ensure it is a text file.', 'error')
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
        
        # Determine the delimiter used in the data
        def detect_delimiter(data):
            # Count occurrences of common delimiters
            delimiters = {
                '\t': data.count('\t'),
                ';': data.count(';'),
                ',': data.count(',')
            }
            # Return the most commonly used delimiter, with fallback to tab
            return max(delimiters.items(), key=lambda x: x[1])[0] if any(delimiters.values()) else '\t'
        
        delimiter = detect_delimiter(student_data)
        logging.info(f"Detected delimiter: {repr(delimiter)}")
        
        # Process the data
        lines = student_data.strip().split('\n')
        students_to_add = []
        errors = []
        warnings = []
        
        # Keep track of student IDs for uniqueness validation during import
        imported_student_ids = set()
        
        # Get existing student IDs in this course for validation
        existing_students = Student.query.filter_by(course_id=course_id).all()
        existing_student_ids = {student.student_id for student in existing_students}
        
        # First pass: validate all lines and prepare student objects
        for i, line in enumerate(lines, 1):
            # Skip empty lines
            if not line.strip():
                continue
            
            # Try to parse the line
            try:
                # Step 1: Try to split by detected delimiter
                parts = [p.strip() for p in line.split(delimiter) if p.strip()]
                
                # Step 2: If delimiter doesn't work well, try multiple spaces as delimiter
                if len(parts) < 2:
                    # Split by multiple spaces
                    parts = re.split(r'\s{1,}', line.strip())
                    parts = [p.strip() for p in parts if p.strip()]
                
                # Step 3: If still not enough parts, try other common delimiters
                if len(parts) < 2:
                    for alt_delimiter in ['\t', ';', ',', '|']:
                        if alt_delimiter != delimiter and alt_delimiter in line:
                            temp_parts = [p.strip() for p in line.split(alt_delimiter) if p.strip()]
                            if len(temp_parts) >= 2:
                                parts = temp_parts
                                break
                
                if len(parts) < 2:
                    errors.append(f"Line {i}: Not enough data (expected at least student ID and name)")
                    continue
                
                # Extract student ID from parts (first element is always student ID)
                student_id = parts[0]
                
                # Sanitize student ID - only remove tabs and trim whitespace
                student_id = student_id.replace('\t', '').strip()
                
                # Validate student ID format - check that it's not empty after trimming
                if not student_id:
                    errors.append(f"Line {i}: Empty student ID after trimming whitespace")
                    continue
                
                # Check for length constraints
                if len(student_id) > 20:  # Based on model definition
                    student_id = student_id[:20]
                    warnings.append(f"Line {i}: Student ID truncated to 20 characters: {student_id}")
                
                # Check if student already exists in this course
                if student_id in existing_student_ids:
                    errors.append(f"Line {i}: Student with ID {student_id} already exists in this course")
                    continue
                
                # Check for duplicate student IDs in the current import batch
                if student_id in imported_student_ids:
                    errors.append(f"Line {i}: Duplicate student ID {student_id} in import data")
                    continue
                
                # Robust name parsing logic
                first_name = ""
                last_name = ""
                
                # Handle different name formats based on number of parts and specified format
                name_format = request.form.get('name_format', 'auto')
                
                # Compile all name parts
                name_parts = parts[1:]
                full_name = " ".join(name_parts)
                
                # Handle different name formats
                if name_format == 'eastern':
                    # Eastern format: Last name first, no comma (e.g., "Kim Minjun")
                    if name_parts:
                        last_name = name_parts[0]
                        first_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                elif name_format == 'western':
                    # Western format: First name first (e.g., "John Smith")
                    if name_parts:
                        first_name = " ".join(name_parts[:-1])
                        last_name = name_parts[-1]
                    else:
                        first_name = full_name
                        last_name = ""
                elif name_format == 'comma':
                    # Comma format: "Last, First"
                    if ',' in full_name:
                        name_components = full_name.split(',', 1)
                        last_name = name_components[0].strip()
                        first_name = name_components[1].strip() if len(name_components) > 1 else ""
                    else:
                        # Fallback if comma format specified but no comma found
                        first_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else name_parts[0]
                        last_name = name_parts[-1] if len(name_parts) > 1 else ""
                else:  # Auto-detect
                    # Check for comma-separated format: "LastName, FirstName"
                    if ',' in full_name:
                        name_components = full_name.split(',', 1)
                        last_name = name_components[0].strip()
                        first_name = name_components[1].strip() if len(name_components) > 1 else ""
                    else:
                        # Default to Western format (FirstName LastName)
                        name_parts = full_name.split()
                        if len(name_parts) > 1:
                            first_name = " ".join(name_parts[:-1])
                            last_name = name_parts[-1]
                        else:
                            first_name = full_name
                            last_name = ""
                
                # Trim and sanitize names
                first_name = first_name[:50].strip()  # Limit to model field size
                last_name = last_name[:50].strip()    # Limit to model field size
                
                # Final validation
                if not first_name and not last_name:
                    errors.append(f"Line {i}: Unable to parse name properly")
                    continue
                
                imported_student_ids.add(student_id)
                
                # Create student data dictionary to add later
                students_to_add.append({
                    'student_id': student_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'course_id': course_id,
                    'line_number': i  # Keep track of line number for error reporting
                })
                
            except Exception as e:
                errors.append(f"Line {i}: Error processing line - {str(e)}")
                logging.error(f"Error processing student import line {i}: {str(e)}\n{traceback.format_exc()}")
        
        # Second pass: if no errors or continue_on_errors is selected, add students
        continue_on_errors = request.form.get('continue_on_errors') == 'on'
        
        if (not errors or continue_on_errors) and students_to_add:
            try:
                # Use a session transaction with savepoints for better recovery
                db.session.begin_nested()
                
                students_added = 0
                add_errors = []
                
                # Use batch processing for better performance
                batch_size = 50
                for i in range(0, len(students_to_add), batch_size):
                    batch = students_to_add[i:i+batch_size]
                    
                    # Create a savepoint for this batch
                    if i > 0:
                        db.session.begin_nested()
                    
                    batch_success = True
                    for student_data in batch:
                        line_number = student_data.pop('line_number')  # Remove from data before creating model
                        
                        try:
                            new_student = Student(**student_data)
                            db.session.add(new_student)
                        except Exception as e:
                            add_errors.append(f"Line {line_number}: Database error - {str(e)}")
                            batch_success = False
                            break
                    
                    try:
                        # Validate the entire batch
                        db.session.flush()
                        students_added += len(batch)
                    except IntegrityError as e:
                        # Handle database constraint errors
                        db.session.rollback()
                        batch_success = False
                        error_msg = str(e)
                        if "UNIQUE constraint failed" in error_msg:
                            # Extract student ID from error message if possible
                            match = re.search(r"student_id\s*=\s*['\"]([^'\"]+)['\"]", error_msg)
                            student_id = match.group(1) if match else "unknown"
                            add_errors.append(f"Line {line_number}: Student ID '{student_id}' already exists in this course")
                        else:
                            add_errors.append(f"Line {line_number}: Database error - {error_msg}")
                    except Exception as e:
                        db.session.rollback()
                        batch_success = False
                        add_errors.append(f"Line {line_number}: Database error - {str(e)}")
                
                if add_errors:
                    if continue_on_errors:
                        # Log errors but continue
                        for error in add_errors:
                            logging.warning(f"Student import warning: {error}")
                    else:
                        # Rollback if there are errors and not continuing
                        db.session.rollback()
                        errors.extend(add_errors)
                        return render_template('student/import_result.html', 
                                             course=course,
                                             students_added=0,
                                             errors=errors,
                                             warnings=warnings,
                                             active_page='courses')
                
                if students_added > 0:
                    # Log action
                    log = Log(action="IMPORT_STUDENTS", 
                             description=f"Imported {students_added} students to course: {course.code}")
                    db.session.add(log)
                    
                    db.session.commit()
                    flash(f'Successfully imported {students_added} students', 'success')
                    
                    if errors or add_errors:
                        flash(f'There were {len(errors) + len(add_errors)} warnings during import. See details below.', 'warning')
                    
                    return render_template('student/import_result.html', 
                                         course=course,
                                         students_added=students_added,
                                         errors=errors + add_errors,
                                         warnings=warnings,
                                         active_page='courses')
                else:
                    db.session.rollback()
                    flash('No students were imported. Please check the errors below.', 'error')
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error committing student import: {str(e)}\n{traceback.format_exc()}")
                flash(f'An error occurred while importing students: {str(e)}', 'error')
                return render_template('student/import.html', 
                                     course=course,
                                     active_page='courses')
        else:
            if errors:
                flash(f'{len(errors)} errors found. Please correct them and try again.', 'error')
                # Only show first 10 errors to avoid overwhelming the user
                for error in errors[:10]:
                    flash(error, 'warning')
                if len(errors) > 10:
                    flash(f'... and {len(errors) - 10} more errors', 'warning')
            else:
                flash('No valid student data found for import.', 'error')
            
            return render_template('student/import.html',
                                 course=course,
                                 errors=errors,
                                 active_page='courses')
    
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
        # Check for related scores
        scores_count = Score.query.filter_by(student_id=student_id).count()
        
        if scores_count > 0:
            error_message = f"Cannot delete student: Student has {scores_count} exam scores. "
            error_message += "Delete the student's scores first or use the import/merge utility to transfer data."
            flash(error_message, 'error')
            return redirect(url_for('student.list_students', course_id=course_id))
            
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
        flash(f'An error occurred while deleting the student: {str(e)}', 'error')
    
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
    
    # Get attendance records
    attendances = StudentExamAttendance.query.filter_by(exam_id=exam_id).all()
    attendance_dict = {a.student_id: a.attended for a in attendances}
    
    if request.method == 'POST':
        try:
            # Optional: update existing scores instead of removing them all
            existing_scores = {}
            for existing_score in Score.query.filter_by(exam_id=exam_id).all():
                key = f"{existing_score.student_id}_{existing_score.question_id}"
                existing_scores[key] = existing_score
            
            # Process scores for each student and question
            for student in students:
                # Skip saving scores for students who didn't attend
                if student.id in attendance_dict and not attendance_dict[student.id]:
                    continue
                    
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
            log = Log(
                action="UPDATE_SCORES",
                description=f"Updated scores for exam: {exam.name} in course: {course.code}"
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Scores updated successfully.', 'success')
            return redirect(url_for('exam.exam_detail', exam_id=exam_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving scores: {str(e)}', 'error')
    
    # Get existing scores
    scores = Score.query.filter_by(exam_id=exam_id).all()
    
    return render_template('student/scores.html',
                         exam=exam,
                         course=course,
                         questions=questions,
                         students=students,
                         scores=scores,
                         attendance_dict=attendance_dict,
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
        
        # Check if the student attended the exam
        attendance = StudentExamAttendance.query.filter_by(
            student_id=student_id,
            exam_id=exam_id
        ).first()
        
        # If there's an attendance record and the student didn't attend, don't save the score
        if attendance and not attendance.attended:
            return jsonify({'success': False, 'error': 'Student did not attend the exam'})
        
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
    
    # Get score data from file or textarea
    scores_data = ""
    if 'scores_file' in request.files and request.files['scores_file'].filename:
        file = request.files['scores_file']
        try:
            # Try to detect encoding
            raw_data = file.read()
            if not raw_data:
                flash('Empty file uploaded', 'error')
                return redirect(url_for('student.manage_scores', exam_id=exam_id))
                
            encoding_result = detect(raw_data)
            file.seek(0)  # Reset file position
            
            # Use detected encoding with high confidence or try multiple fallbacks
            if encoding_result and encoding_result['confidence'] > 0.7:
                encoding = encoding_result['encoding']
            else:
                # Try common encodings in order
                encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']
                for enc in encodings_to_try:
                    try:
                        scores_data = raw_data.decode(enc)
                        logging.info(f"Successfully decoded file with {enc} encoding")
                        break
                    except UnicodeDecodeError:
                        continue
                
            # If we haven't set scores_data yet, use the first detected encoding
            if not scores_data and encoding_result:
                try:
                    scores_data = raw_data.decode(encoding_result['encoding'])
                except UnicodeDecodeError:
                    # Last resort: use latin-1 which should never fail
                    scores_data = raw_data.decode('latin-1', errors='replace')
                    logging.warning("Decoded file with latin-1 and error replacement - some characters may be incorrect")
            
            if not scores_data:
                raise UnicodeDecodeError("Could not decode with any common encoding")
                
        except Exception as e:
            flash(f'Could not decode the file: {str(e)}. Please ensure it is a text file.', 'error')
            return redirect(url_for('student.manage_scores', exam_id=exam_id))
    else:
        scores_data = request.form.get('scores_data', '')
    
    if not scores_data.strip():
        flash('No score data provided', 'error')
        return redirect(url_for('student.manage_scores', exam_id=exam_id))
    
    # Determine the delimiter used in the data
    def detect_delimiter(data):
        # Count occurrences of common delimiters
        delimiters = {
            '\t': data.count('\t'),
            ';': data.count(';'),
            ',': data.count(',')
        }
        # Return the most commonly used delimiter, with fallback to tab
        return max(delimiters.items(), key=lambda x: x[1])[0] if any(delimiters.values()) else '\t'
    
    delimiter = detect_delimiter(scores_data)
    logging.info(f"Detected delimiter: {repr(delimiter)}")
    
    # Process data
    lines = scores_data.strip().split('\n')
    scores_to_add = []
    students_to_create = []  # Students that need to be created
    errors = []
    warnings = []
    
    # Flag to determine if we should create missing students automatically
    create_students = request.form.get('create_missing_students') == 'on'
    
    # Process the header row if present to determine question numbers (optional)
    header_mapping = {}
    header_row = request.form.get('has_header') == 'on'
    
    if header_row and lines:
        try:
            header = lines[0]
            header_parts = [p.strip() for p in header.split(delimiter)]
            
            # Map column indices to question numbers
            for i, part in enumerate(header_parts):
                if i < 2:  # Skip student ID and name columns
                    continue
                
                # Try to extract question number from header
                q_match = re.search(r'q(?:uestion)?\s*(\d+)', part.lower())
                if q_match:
                    q_num = int(q_match.group(1))
                    if q_num in questions:
                        header_mapping[i] = q_num
                    else:
                        warnings.append(f"Header column '{part}' refers to question {q_num} which doesn't exist")
            
            # Remove header from lines to process
            lines = lines[1:]
            logging.info(f"Processed header row, found mappings: {header_mapping}")
        except Exception as e:
            logging.warning(f"Error processing header row: {str(e)}")
            warnings.append(f"Error processing header row: {str(e)}")
            # If header processing fails, assume no header
            header_row = False
    
    # First pass: validate and prepare objects
    for i, line in enumerate(lines, 1 if not header_row else 2):  # Adjust line number if we have a header
        # Skip empty lines
        if not line.strip():
            continue
        
        # Try to parse the line
        try:
            # Split by detected delimiter
            parts = [p.strip() for p in line.split(delimiter)]
            
            if len(parts) < 3:  # Need at least student_id, name, and one score
                errors.append(f"Line {i}: Not enough data (expected at least student ID, name, and one score)")
                continue
            
            student_id = parts[0].strip()
            full_name = parts[1].strip()
            
            # Sanitize student ID - only remove tabs and trim whitespace
            student_id = student_id.replace('\t', '').strip()
            
            # Validate student ID format - check that it's not empty after trimming
            if not student_id:
                errors.append(f"Line {i}: Empty student ID after trimming whitespace")
                continue
            
            # Find the student
            student = students_dict.get(student_id)
            
            # Handle creation of new students if needed
            if student is None and create_students:
                # Parse the name
                name_format = request.form.get('name_format', 'auto')
                
                if name_format == 'eastern':
                    # Eastern format: Last name first
                    name_parts = full_name.split()
                    if len(name_parts) > 1:
                        last_name = name_parts[0]
                        first_name = " ".join(name_parts[1:])
                    else:
                        last_name = full_name
                        first_name = ""
                elif name_format == 'western':
                    # Western format: First name first
                    name_parts = full_name.split()
                    if len(name_parts) > 1:
                        first_name = " ".join(name_parts[:-1])
                        last_name = name_parts[-1]
                    else:
                        first_name = full_name
                        last_name = ""
                elif name_format == 'comma':
                    # Comma format: "Last, First"
                    if ',' in full_name:
                        name_components = full_name.split(',', 1)
                        last_name = name_components[0].strip()
                        first_name = name_components[1].strip() if len(name_components) > 1 else ""
                    else:
                        # Fallback if comma format specified but no comma found
                        name_parts = full_name.split()
                        if len(name_parts) > 1:
                            first_name = " ".join(name_parts[:-1])
                            last_name = name_parts[-1]
                        else:
                            first_name = full_name
                            last_name = ""
                else:  # Auto-detect
                    # Check for comma-separated format: "LastName, FirstName"
                    if ',' in full_name:
                        name_components = full_name.split(',', 1)
                        last_name = name_components[0].strip()
                        first_name = name_components[1].strip() if len(name_components) > 1 else ""
                    else:
                        # Default to Western format (FirstName LastName)
                        name_parts = full_name.split()
                        if len(name_parts) > 1:
                            first_name = " ".join(name_parts[:-1])
                            last_name = name_parts[-1]
                        else:
                            first_name = full_name
                            last_name = ""
                
                # Validate and limit name lengths
                first_name = first_name[:50].strip()
                last_name = last_name[:50].strip()
                
                # Check for duplicate student ID in pending creation list
                if any(s['student_id'] == student_id for s in students_to_create):
                    errors.append(f"Line {i}: Duplicate student ID {student_id} in import data")
                    continue
                
                # Add student to creation list
                new_student_data = {
                    'student_id': student_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'course_id': course.id,
                    'line_number': i  # Keep track for error reporting
                }
                students_to_create.append(new_student_data)
                
                # For now, use the student ID as an identifier
                student_identifier = f"NEW:{student_id}"
            elif student is None:
                errors.append(f"Line {i}: Student ID {student_id} not found in this course")
                continue
            else:
                # Use the internal student ID
                student_identifier = student.id
            
            # Process scores for this line
            line_scores = []
            
            # Method 1: Use header mapping if available
            if header_mapping:
                for col_idx, q_num in header_mapping.items():
                    if col_idx < len(parts):
                        score_str = parts[col_idx].strip()
                        
                        # Skip empty scores
                        if not score_str:
                            continue
                        
                        # Validate and convert score
                        try:
                            score_value = Decimal(score_str.replace(',', '.'))  # Handle European decimal format
                        except (ValueError, InvalidOperation):
                            errors.append(f"Line {i}: Invalid score value '{score_str}' for question {q_num}")
                            continue
                        
                        question = questions[q_num]
                        
                        # Always validate score is within range
                        if score_value < 0:
                            errors.append(f"Line {i}: Score {score_value} is negative for question {q_num}")
                            continue
                        elif score_value > question.max_score:
                            errors.append(f"Line {i}: Score {score_value} exceeds max score {question.max_score} for question {q_num}")
                            continue
                        
                        line_scores.append({
                            'student_id': student_identifier,
                            'student_ext_id': student_id,  # Keep original ID for reference
                            'question_id': question.id,
                            'question_num': q_num,
                            'exam_id': exam_id,
                            'score': score_value,
                            'line_number': i
                        })
            else:
                # Method 2: Parse the remaining columns as q:score format
                for score_data in parts[2:]:
                    # Skip empty scores
                    if not score_data.strip():
                        continue
                    
                    # Parse the question number and score
                    try:
                        if ':' in score_data:
                            # Format: q1:10, 1:10, Q1:10, etc.
                            q_part, score_part = score_data.split(':', 1)
                            # Extract the question number (remove 'q' or 'Q' prefix)
                            q_num = int(re.sub(r'^[qQ]', '', q_part.strip()))
                            score_str = score_part.strip()
                        else:
                            # If no question number format is found, assign sequentially
                            q_num = len(line_scores) + 1
                            score_str = score_data.strip()
                        
                        # Check if question exists
                        if q_num not in questions:
                            errors.append(f"Line {i}: Question {q_num} does not exist for this exam")
                            continue
                        
                        # Validate and convert score to Decimal
                        try:
                            score_value = Decimal(score_str.replace(',', '.'))  # Handle European decimal format
                        except (ValueError, InvalidOperation):
                            errors.append(f"Line {i}: Invalid score value '{score_str}' for question {q_num}")
                            continue
                        
                        question = questions[q_num]
                        
                        # Always validate score is within range
                        if score_value < 0:
                            errors.append(f"Line {i}: Score {score_value} is negative for question {q_num}")
                            continue
                        elif score_value > question.max_score:
                            errors.append(f"Line {i}: Score {score_value} exceeds max score {question.max_score} for question {q_num}")
                            continue
                        
                        line_scores.append({
                            'student_id': student_identifier,
                            'student_ext_id': student_id,  # Keep original ID for reference
                            'question_id': question.id,
                            'question_num': q_num,
                            'exam_id': exam_id,
                            'score': score_value,
                            'line_number': i
                        })
                    except ValueError as e:
                        errors.append(f"Line {i}: Error processing score '{score_data}' - {str(e)}")
                        continue
                    except Exception as e:
                        errors.append(f"Line {i}: Error processing score '{score_data}' - {str(e)}")
                        continue
            
            if line_scores:
                scores_to_add.extend(line_scores)
            else:
                errors.append(f"Line {i}: No valid scores found for student {student_id}")
                
        except Exception as e:
            errors.append(f"Line {i}: Error processing line - {str(e)}")
            logging.error(f"Error processing score import line {i}: {str(e)}\n{traceback.format_exc()}")
    
    # SECOND PASS: Start database operations
    continue_on_errors = request.form.get('continue_on_errors') == 'on'
    
    if (not errors or continue_on_errors) and (scores_to_add or students_to_create):
        try:
            # Begin nested transaction
            savepoint = db.session.begin_nested()
            
            # First, create any new students needed
            student_id_map = {}  # Map from "NEW:student_id" to database ID
            
            if students_to_create:
                logging.info(f"Creating {len(students_to_create)} new students")
                
                try:
                    # Process students in batches for better performance
                    batch_size = 50
                    for i in range(0, len(students_to_create), batch_size):
                        batch = students_to_create[i:i+batch_size]
                        
                        # Create savepoint for this batch
                        if i > 0:
                            db.session.begin_nested()
                        
                        for student_data in batch:
                            line_number = student_data.pop('line_number')
                            student_ext_id = student_data['student_id']
                            
                            try:
                                new_student = Student(**student_data)
                                db.session.add(new_student)
                                db.session.flush()  # Get the ID assigned by the database
                                
                                # Add to mapping
                                student_id_map[f"NEW:{student_ext_id}"] = new_student.id
                                # Add to students_dict for lookup in case of multiple occurrences
                                students_dict[student_ext_id] = new_student
                                
                            except IntegrityError as e:
                                if "UNIQUE constraint failed" in str(e):
                                    # Another student with this ID might exist now (race condition)
                                    db.session.rollback()
                                    
                                    # Try to find the student again (might have been added by another process)
                                    existing_student = Student.query.filter_by(student_id=student_ext_id, course_id=course.id).first()
                                    if existing_student:
                                        student_id_map[f"NEW:{student_ext_id}"] = existing_student.id
                                        students_dict[student_ext_id] = existing_student
                                    else:
                                        errors.append(f"Line {line_number}: Could not create student {student_ext_id} - unique constraint error")
                                else:
                                    errors.append(f"Line {line_number}: Database error creating student {student_ext_id} - {str(e)}")
                            except Exception as e:
                                errors.append(f"Line {line_number}: Database error creating student {student_ext_id} - {str(e)}")
                    
                    logging.info(f"Created {len(student_id_map)} new students")
                except Exception as e:
                    if not continue_on_errors:
                        db.session.rollback()
                        flash(f"Error creating students: {str(e)}", "error")
                        return redirect(url_for('student.manage_scores', exam_id=exam_id))
                    else:
                        logging.error(f"Error creating students: {str(e)}")
                        warnings.append(f"Error creating students: {str(e)}")
            
            # Now process scores
            if scores_to_add:
                scores_added = 0
                score_errors = []
                
                # Get existing scores to avoid duplicates
                existing_scores = set()
                for score in Score.query.filter_by(exam_id=exam_id).all():
                    existing_scores.add((score.student_id, score.question_id))
                
                # Process scores in batches
                batch_size = 100
                for i in range(0, len(scores_to_add), batch_size):
                    batch = scores_to_add[i:i+batch_size]
                    
                    # Create savepoint for this batch
                    if i > 0:
                        db.session.begin_nested()
                    
                    batch_error = False
                    for score_data in batch:
                        try:
                            line_number = score_data.pop('line_number')
                            student_ext_id = score_data.pop('student_ext_id')
                            
                            # Resolve student ID
                            student_id_key = score_data['student_id']
                            if isinstance(student_id_key, str) and student_id_key.startswith('NEW:'):
                                # This is a newly created student
                                if student_id_key in student_id_map:
                                    score_data['student_id'] = student_id_map[student_id_key]
                                else:
                                    score_errors.append(f"Line {line_number}: Could not find newly created student {student_ext_id}")
                                    continue
                            
                            # Check for duplicates
                            score_key = (score_data['student_id'], score_data['question_id'])
                            if score_key in existing_scores:
                                # Update existing score instead of creating new one
                                existing_score = Score.query.filter_by(
                                    student_id=score_data['student_id'],
                                    question_id=score_data['question_id'],
                                    exam_id=score_data['exam_id']
                                ).first()
                                
                                if existing_score:
                                    existing_score.score = score_data['score']
                                    existing_score.updated_at = datetime.now()
                                    scores_added += 1
                                    continue
                            
                            # Create new score
                            new_score = Score(
                                student_id=score_data['student_id'],
                                question_id=score_data['question_id'], 
                                exam_id=score_data['exam_id'],
                                score=score_data['score']
                            )
                            db.session.add(new_score)
                            
                            # Add to existing set to avoid duplicates in same import
                            existing_scores.add(score_key)
                            scores_added += 1
                            
                        except Exception as e:
                            batch_error = True
                            score_errors.append(f"Line {line_number}: Error adding score - {str(e)}")
                    
                    # Flush this batch if no errors
                    if not batch_error:
                        try:
                            db.session.flush()
                        except Exception as e:
                            db.session.rollback()
                            score_errors.append(f"Database error in batch {i//batch_size + 1}: {str(e)}")
                
                # Handle score errors
                if score_errors:
                    if continue_on_errors:
                        # Log errors but continue
                        for error in score_errors:
                            logging.warning(f"Score import warning: {error}")
                            warnings.append(error)
                    else:
                        # Rollback if there are errors and not continuing
                        db.session.rollback()
                        errors.extend(score_errors)
                        flash(f"Failed to import scores: {len(score_errors)} errors", "error")
                        return redirect(url_for('student.manage_scores', exam_id=exam_id))
                
                if scores_added > 0:
                    # Log the action
                    log = Log(action="IMPORT_SCORES", 
                             description=f"Imported {scores_added} scores for {exam.name}")
                    db.session.add(log)
                    
                    db.session.commit()
                    
                    flash(f'Successfully imported {scores_added} scores', 'success')
                    if len(student_id_map) > 0:
                        flash(f'Created {len(student_id_map)} new students', 'info')
                    
                    if warnings:
                        flash(f'There were {len(warnings)} warnings during import.', 'warning')
                        for warning in warnings[:5]:  # Show only first 5 warnings
                            flash(warning, 'warning')
                        if len(warnings) > 5:
                            flash(f'... and {len(warnings) - 5} more warnings', 'warning')
                        
                    return redirect(url_for('student.manage_scores', exam_id=exam_id))
                else:
                    db.session.rollback()
                    flash('No scores were imported. Please check the errors below.', 'error')
                    return redirect(url_for('student.manage_scores', exam_id=exam_id))
            else:
                db.session.commit()  # Commit any student creations but no scores
                flash('No valid scores were found to import.', 'warning')
                if len(student_id_map) > 0:
                    flash(f'Created {len(student_id_map)} new students', 'info')
                return redirect(url_for('student.manage_scores', exam_id=exam_id))
                
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error during score import: {str(e)}\n{traceback.format_exc()}")
            flash(f'An error occurred while importing scores: {str(e)}', 'error')
            return redirect(url_for('student.manage_scores', exam_id=exam_id))
    else:
        if errors:
            flash(f'{len(errors)} errors found in import data. Please correct them and try again.', 'error')
            # Only show first 10 errors to avoid overwhelming the user
            for error in errors[:10]:
                flash(error, 'warning')
            if len(errors) > 10:
                flash(f'... and {len(errors) - 10} more errors', 'warning')
        else:
            flash('No valid score data found for import.', 'error')
        
        return redirect(url_for('student.manage_scores', exam_id=exam_id))

@student_bp.route('/course/<int:course_id>/export')
def export_students(course_id):
    """Export students from a course to a CSV file"""
    course = Course.query.get_or_404(course_id)
    students = Student.query.filter_by(course_id=course_id).order_by(Student.student_id).all()
    
    # Prepare data for export
    data = []
    headers = ['Student ID', 'First Name', 'Last Name', 'Full Name', 'Excluded']
    
    for student in students:
        data.append({
            'Student ID': student.student_id,
            'First Name': student.first_name,
            'Last Name': student.last_name,
            'Full Name': f"{student.first_name} {student.last_name}".strip(),
            'Excluded': 'Yes' if student.excluded else 'No'
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

@student_bp.route('/mass_delete', methods=['POST'])
def mass_delete_students():
    """Delete multiple students at once"""
    student_ids = request.form.getlist('student_ids')
    course_id = request.form.get('course_id')
    
    if not course_id:
        flash('Course ID is required', 'error')
        return redirect(url_for('index'))
    
    # Verify course exists
    course = Course.query.get_or_404(int(course_id))
    
    if not student_ids:
        flash('No students selected for deletion', 'warning')
        return redirect(url_for('course.course_detail', course_id=course_id))
    
    deleted_count = 0
    error_count = 0
    
    for student_id in student_ids:
        student = Student.query.get(int(student_id))
        if not student:
            error_count += 1
            continue
            
        try:
            # Check for related scores
            scores_count = Score.query.filter_by(student_id=student.id).count()
            
            if scores_count > 0:
                error_count += 1
                continue
                
            db.session.delete(student)
            deleted_count += 1
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting student: {str(e)}")
            error_count += 1
    
    if deleted_count > 0:
        # Log action
        log = Log(action="MASS_DELETE_STUDENTS", 
                 description=f"Deleted {deleted_count} students from course: {course.code}")
        db.session.add(log)
        
        try:
            db.session.commit()
            flash(f'Successfully deleted {deleted_count} students', 'success')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error committing student deletion: {str(e)}")
            flash('An error occurred while deleting students', 'error')
    
    if error_count > 0:
        flash(f'Failed to delete {error_count} students due to existing scores or other errors', 'warning')
    
    return redirect(url_for('course.course_detail', course_id=course_id))

@student_bp.route('/exam/<int:exam_id>/attendance', methods=['GET', 'POST'])
def manage_attendance(exam_id):
    """Manage student attendance for an exam"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    students = Student.query.filter_by(course_id=course.id).order_by(Student.student_id).all()
    
    # Get existing attendance records
    attendances = StudentExamAttendance.query.filter_by(exam_id=exam_id).all()
    attendance_dict = {a.student_id: a for a in attendances}
    
    if request.method == 'POST':
        try:
            # Process attendance data
            for student in students:
                attended = request.form.get(f'attended_{student.id}', 'off') == 'on'
                
                # Check if record already exists
                if student.id in attendance_dict:
                    # Update existing record
                    record = attendance_dict[student.id]
                    record.attended = attended
                else:
                    # Create new record
                    record = StudentExamAttendance(
                        student_id=student.id,
                        exam_id=exam_id,
                        attended=attended
                    )
                    db.session.add(record)
            
            # Log the action
            log = Log(
                action="UPDATE_EXAM_ATTENDANCE",
                description=f"Updated attendance for {exam.name} in course {course.code}"
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Attendance updated successfully.', 'success')
            return redirect(url_for('exam.exam_detail', exam_id=exam_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating attendance: {str(e)}', 'error')
            
    return render_template('student/attendance.html',
                         exam=exam,
                         course=course,
                         students=students,
                         attendance_dict=attendance_dict,
                         active_page='courses')

@student_bp.route('/exam/<int:exam_id>/attendance/import', methods=['POST'])
def import_attendance(exam_id):
    """Import student attendance data for an exam"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    
    try:
        # Get student mapping
        students = Student.query.filter_by(course_id=course.id).all()
        student_map = {s.student_id: s.id for s in students}
        
        # Process data from form
        attendance_data = request.form.get('attendance_data', '')
        
        if not attendance_data.strip():
            flash('No attendance data provided.', 'warning')
            return redirect(url_for('student.manage_attendance', exam_id=exam_id))
        
        # Determine the delimiter used in the data
        def detect_delimiter(data):
            # Count occurrences of common delimiters
            delimiters = {
                '\t': data.count('\t'),
                ';': data.count(';'),
                ',': data.count(',')
            }
            # Return the most commonly used delimiter, with fallback to tab
            return max(delimiters.items(), key=lambda x: x[1])[0] if any(delimiters.values()) else ';'
        
        delimiter = detect_delimiter(attendance_data)
        logging.info(f"Detected delimiter for attendance import: {repr(delimiter)}")
        
        # Process the data
        lines = attendance_data.strip().split('\n')
        attendance_to_add = []
        errors = []
        warnings = []
        not_found_ids = []
        
        # Define valid attendance values
        attended_values = {'y', 'yes', '1', 'true', 'attended', 'present', 'p', 't'}
        absent_values = {'n', 'no', '0', 'false', 'absent', 'missing', 'a', 'f'}
        
        # Process header row if present
        header_row = request.form.get('has_header') == 'on'
        if header_row and lines:
            lines = lines[1:]  # Skip the header row
        
        # First pass: validate all lines and prepare objects
        for i, line in enumerate(lines, 1 if not header_row else 2):
            # Skip empty lines
            if not line.strip():
                continue
            
            parts = [p.strip() for p in line.split(delimiter)]
            if len(parts) < 2:
                # Try alternative delimiters if the detected one didn't work
                for alt_delimiter in ['\t', ';', ',']:
                    if alt_delimiter != delimiter and alt_delimiter in line:
                        temp_parts = [p.strip() for p in line.split(alt_delimiter) if p.strip()]
                        if len(temp_parts) >= 2:
                            parts = temp_parts
                            break
                
                if len(parts) < 2:
                    errors.append(f"Line {i}: Not enough data (expected format: student_id{delimiter}attendance_status)")
                    continue
            
            student_id = parts[0].strip()
            attended_str = parts[1].strip().lower()
            
            # Sanitize student ID - only remove tabs and trim whitespace
            student_id = student_id.replace('\t', '').strip()
            
            # Validate student ID format - check that it's not empty after trimming
            if not student_id:
                errors.append(f"Line {i}: Empty student ID after trimming whitespace")
                continue
            
            # Check if student exists
            if student_id not in student_map:
                not_found_ids.append(student_id)
                errors.append(f"Line {i}: Student ID {student_id} not found in this course")
                continue
                
            internal_id = student_map[student_id]
            
            # Enhanced attendance status determination
            if attended_str in attended_values:
                attended = True
            elif attended_str in absent_values:
                attended = False
            else:
                # Attempt numeric conversion if it's not in known values
                try:
                    # Try to interpret as numeric (non-zero = attended)
                    attended = bool(float(attended_str))
                    warnings.append(f"Line {i}: Ambiguous attendance value '{attended_str}', interpreted as {'present' if attended else 'absent'}")
                except ValueError:
                    errors.append(f"Line {i}: Invalid attendance value '{attended_str}'. Use 'yes'/'no', 'true'/'false', etc.")
                    continue
            
            # Add to attendance records to process
            attendance_to_add.append({
                'student_id': internal_id,
                'exam_id': exam_id,
                'attended': attended,
                'line_number': i,
                'student_ext_id': student_id  # Keep original ID for reference
            })
        
        # Second pass: process if no errors or if continue_on_errors is selected
        continue_on_errors = request.form.get('continue_on_errors') == 'on'
        
        if (not errors or continue_on_errors) and attendance_to_add:
            imported_count = 0
            add_errors = []
            
            # Start transaction with savepoint
            db.session.begin_nested()
            
            # Get existing attendance records to optimize database operations
            existing_attendance = {}
            for record in StudentExamAttendance.query.filter_by(exam_id=exam_id).all():
                existing_attendance[record.student_id] = record
            
            # Process in batches for better performance
            batch_size = 50
            for i in range(0, len(attendance_to_add), batch_size):
                batch = attendance_to_add[i:i+batch_size]
                
                # Create savepoint for this batch
                if i > 0:
                    db.session.begin_nested()
                
                batch_errors = False
                for attendance_data in batch:
                    try:
                        line_number = attendance_data.pop('line_number')
                        student_ext_id = attendance_data.pop('student_ext_id')
                        student_id = attendance_data['student_id']
                        
                        # Check if record exists
                        if student_id in existing_attendance:
                            # Update existing record
                            record = existing_attendance[student_id]
                            record.attended = attendance_data['attended']
                            record.updated_at = datetime.now()
                        else:
                            # Create new record
                            record = StudentExamAttendance(**attendance_data)
                            db.session.add(record)
                        
                        imported_count += 1
                    except Exception as e:
                        batch_errors = True
                        add_errors.append(f"Line {line_number}: Error processing attendance for student {student_ext_id} - {str(e)}")
                
                # Try to flush the batch
                if not batch_errors:
                    try:
                        db.session.flush()
                    except Exception as e:
                        db.session.rollback()
                        add_errors.append(f"Database error in batch {i//batch_size + 1}: {str(e)}")
            
            if add_errors and not continue_on_errors:
                # Rollback if there are errors and not continuing
                db.session.rollback()
                errors.extend(add_errors)
                for error in errors[:10]:  # Show first 10 errors
                    flash(error, 'warning')
                if len(errors) > 10:
                    flash(f'... and {len(errors) - 10} more errors', 'warning')
                return redirect(url_for('student.manage_attendance', exam_id=exam_id))
            
            if imported_count > 0:
                # Log the action
                log = Log(
                    action="IMPORT_EXAM_ATTENDANCE",
                    description=f"Imported attendance for {imported_count} students in {exam.name}"
                )
                db.session.add(log)
                
                try:
                    db.session.commit()
                    flash(f'Successfully imported attendance for {imported_count} students.', 'success')
                    
                    if errors or add_errors:
                        flash(f'There were {len(errors) + len(add_errors)} warnings during import.', 'warning')
                        for error in (errors + add_errors)[:10]:
                            flash(error, 'warning')
                        if len(errors) + len(add_errors) > 10:
                            flash(f'... and {len(errors) + len(add_errors) - 10} more warnings', 'warning')
                except Exception as e:
                    db.session.rollback()
                    logging.error(f"Error committing attendance data: {str(e)}")
                    flash(f'Database error when saving attendance data: {str(e)}', 'error')
            else:
                db.session.rollback()
                flash('No attendance records were imported.', 'warning')
                
                if not_found_ids:
                    if len(not_found_ids) <= 10:
                        flash(f"Student IDs not found: {', '.join(not_found_ids)}", 'warning')
                    else:
                        flash(f"{len(not_found_ids)} student IDs not found in this course", 'warning')
        else:
            if errors:
                flash(f'No attendance records were imported due to {len(errors)} validation errors.', 'error')
                for error in errors[:10]:  # Show first 10 errors
                    flash(error, 'warning')
                if len(errors) > 10:
                    flash(f'... and {len(errors) - 10} more errors', 'warning')
            else:
                flash('No valid attendance data found for import.', 'error')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error importing attendance data: {str(e)}', 'error')
        logging.error(f"Error in attendance import: {str(e)}\n{traceback.format_exc()}")
    
    return redirect(url_for('student.manage_attendance', exam_id=exam_id))

@student_bp.route('/exam/<int:exam_id>/update-attendance', methods=['POST'])
def update_attendance(exam_id):
    """Update a student's attendance for an exam via AJAX"""
    exam = Exam.query.get_or_404(exam_id)
    
    try:
        data = request.get_json()
        
        if not data or 'student_id' not in data or 'attended' not in data:
            return jsonify({'success': False, 'error': 'Missing required data'})
        
        student_id = int(data['student_id'])
        attended = data['attended']
        
        # Find the student to ensure they exist
        student = Student.query.get_or_404(student_id)
        
        # Get or create attendance record
        attendance = StudentExamAttendance.query.filter_by(
            student_id=student_id,
            exam_id=exam_id
        ).first()
        
        if attendance:
            attendance.attended = attended
            attendance.updated_at = datetime.now()
        else:
            attendance = StudentExamAttendance(
                student_id=student_id,
                exam_id=exam_id,
                attended=attended
            )
            db.session.add(attendance)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating attendance: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@student_bp.route('/<int:student_id>/toggle_exclusion', methods=['POST'])
def toggle_exclusion(student_id):
    """Toggle exclusion status for a student"""
    student = Student.query.get_or_404(student_id)
    course_id = student.course_id
    
    # Toggle exclusion status
    student.excluded = not student.excluded
    
    # Log the action
    action = "EXCLUDE_STUDENT" if student.excluded else "INCLUDE_STUDENT"
    log = Log(action=action, description=f"{action} {student.student_id}: {student.first_name} {student.last_name}")
    
    db.session.add(log)
    
    try:
        db.session.commit()
        status = "excluded from" if student.excluded else "included in"
        message = f'Student {student.student_id} {status} calculations successfully'
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests, return a response that the client can use to update the UI
            return jsonify({
                'success': True,
                'message': message,
                'student_id': student_id,
                'excluded': student.excluded,
                'student_name': f"{student.first_name} {student.last_name}",
                'student_id_text': student.student_id
            })
        
        flash(message, 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error toggling student exclusion: {str(e)}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'An error occurred while updating student status',
                'error': str(e)
            }), 500
        
        flash('An error occurred while updating student status', 'error')
    
    return redirect(url_for('course.course_detail', course_id=course_id)) 