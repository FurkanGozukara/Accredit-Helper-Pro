from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app as app
from app import db
from models import Student, Course, Exam, Question, Score, Log, StudentExamAttendance
from datetime import datetime
import logging
import csv
import io
import re
from routes.utility_routes import export_to_excel_csv
from decimal import Decimal, DivisionByZero, InvalidOperation, ROUND_HALF_UP
from sqlalchemy.exc import IntegrityError
import pandas as pd
import numpy as np
import json
from sqlalchemy import and_, or_
from werkzeug.utils import secure_filename
import os
from chardet import detect
import traceback
from sqlalchemy.sql import text

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
    
    # Get attendance records - more efficient with a dictionary
    attendances = StudentExamAttendance.query.filter_by(exam_id=exam_id).all()
    attendance_dict = {a.student_id: a.attended for a in attendances}
    
    # Handle form submission
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
                            # Check if exceeding max score is allowed
                            allow_exceed_max = request.form.get('allowExceedMaxScore') == 'on'
                            if not allow_exceed_max:
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
    
    # Get existing scores and create an optimized lookup dictionary
    scores = Score.query.filter_by(exam_id=exam_id).all()
    scores_dict = {}
    for score in scores:
        scores_dict[(score.student_id, score.question_id)] = score
    
    return render_template('student/scores.html',
                         exam=exam,
                         course=course,
                         questions=questions,
                         students=students,
                         scores=scores,
                         scores_dict=scores_dict,
                         attendance_dict=attendance_dict,
                         active_page='courses')

@student_bp.route('/exam/<int:exam_id>/scores/auto-save', methods=['POST'])
def auto_save_score(exam_id):
    """Auto-save a single score via AJAX"""
    try:
        data = request.get_json()
        
        if not data or 'student_id' not in data or 'question_id' not in data:
            return jsonify({'success': False, 'error': 'Missing required data'})
        
        student_id = int(data['student_id'])
        question_id = int(data['question_id'])
        score_value = data.get('score', '')
        
        # Check attendance and get question in a single query 
        # to reduce database round-trips
        attendance_status = db.session.query(
            StudentExamAttendance.attended, 
            Question.max_score
        ).outerjoin(
            StudentExamAttendance, 
            db.and_(
                StudentExamAttendance.student_id == student_id,
                StudentExamAttendance.exam_id == exam_id
            )
        ).filter(
            Question.id == question_id
        ).first()
        
        if not attendance_status:
            return jsonify({'success': False, 'error': 'Question not found'})
            
        # Extract values from the query result
        attended = True if attendance_status[0] is None else attendance_status[0]
        max_score = attendance_status[1]
        
        # If student didn't attend, don't save
        if not attended:
            return jsonify({'success': False, 'error': 'Student did not attend the exam'})
        
        # Handle empty score (delete if exists)
        if score_value == '':
            # Use direct SQL for faster deletion
            db.session.execute(
                text("DELETE FROM score WHERE student_id = :student_id AND question_id = :question_id AND exam_id = :exam_id"),
                {"student_id": student_id, "question_id": question_id, "exam_id": exam_id}
            )
            db.session.commit()
            return jsonify({'success': True})
        
        # Convert and validate score
        try:
            score_value = Decimal(str(score_value))
            
            if score_value < 0:
                score_value = Decimal('0')
            elif score_value > max_score:
                # Check if exceeding max score is allowed
                allow_exceed_max = data.get('allow_exceed_max_score', False)
                if not allow_exceed_max:
                    score_value = max_score
                
        except (ValueError, InvalidOperation):
            return jsonify({'success': False, 'error': 'Invalid score value'})
        
        # Convert Decimal to float for SQLite compatibility
        score_float = float(score_value)
        current_time = datetime.now()
        
        # Use upsert (insert or update) pattern for more efficiency
        # First try to update existing score
        result = db.session.execute(
            text("""
                UPDATE score 
                SET score = :score, updated_at = :updated_at
                WHERE student_id = :student_id 
                  AND question_id = :question_id 
                  AND exam_id = :exam_id
            """),
            {
                "score": score_float,  # Use float instead of Decimal
                "updated_at": current_time,
                "student_id": student_id,
                "question_id": question_id,
                "exam_id": exam_id
            }
        )
        
        # If no rows were updated, insert new score
        if result.rowcount == 0:
            db.session.execute(
                text("""
                    INSERT INTO score (score, student_id, question_id, exam_id, created_at, updated_at)
                    VALUES (:score, :student_id, :question_id, :exam_id, :created_at, :updated_at)
                """),
                {
                    "score": score_float,  # Use float instead of Decimal
                    "student_id": student_id,
                    "question_id": question_id,
                    "exam_id": exam_id,
                    "created_at": current_time,
                    "updated_at": current_time
                }
            )
        
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
    
    # Get the selected import format
    import_format = request.form.get('import_format', 'detailed') # Default to detailed
    
    # Flag to validate scores against max score
    allow_exceed_max = request.form.get('allowExceedMaxScore') == 'on'
    
    # Flag to continue on errors
    continue_on_errors = request.form.get('continue_on_errors') == 'on'
    
    # Process the header row if present (only relevant for detailed format)
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
    
    # Prepare a dictionary to temporarily hold newly created student IDs if create_students is true
    student_id_map = {}

    # First pass: Process students if 'create_students' is enabled
    if create_students:
        temp_students_to_create = []
        for i, line in enumerate(lines, 1 if not header_row else 2):
            if not line.strip():
                continue
            try:
                parts = [p.strip() for p in line.split(delimiter)]
                
                if import_format == 'detailed' and len(parts) < 2: # Need ID and Name for detailed
                     if not continue_on_errors: errors.append(f"Line {i}: Not enough data (expected at least student ID and name for detailed format)")
                     continue
                elif import_format == 'total_only' and len(parts) < 1: # Need at least ID for total_only
                     if not continue_on_errors: errors.append(f"Line {i}: Not enough data (expected at least student ID for total score format)")
                     continue

                student_id = parts[0].strip().replace('\\t', '')
                if not student_id:
                    if not continue_on_errors: errors.append(f"Line {i}: Empty student ID after trimming")
                    continue
                
                if student_id not in students_dict:
                    full_name = parts[1].strip() if import_format == 'detailed' and len(parts) > 1 else f"Imported {student_id}"
                    
                    # Deduplicate based on student_id before adding to temp list
                    if not any(s['student_id'] == student_id for s in temp_students_to_create):
                         name_parts = full_name.split(maxsplit=1)
                         first_name = name_parts[0][:50].strip() if name_parts else ""
                         last_name = name_parts[1][:50].strip() if len(name_parts) > 1 else ""
                         
                         temp_students_to_create.append({
                             'student_id': student_id,
                             'first_name': first_name,
                             'last_name': last_name,
                             'course_id': course.id,
                             'line_number': i
                         })
            except Exception as e:
                if not continue_on_errors: errors.append(f"Line {i}: Error processing student data: {str(e)}")
                continue

        # Batch create students if any are found
        if temp_students_to_create:
            try:
                # Use bulk insert for potentially better performance
                db.session.bulk_insert_mappings(Student, temp_students_to_create)
                db.session.commit()
                flash(f"Successfully created {len(temp_students_to_create)} new students.", 'info')
                
                # Re-fetch students to update the students_dict and get new IDs
                students_dict = {s.student_id: s for s in Student.query.filter_by(course_id=course.id).all()}
                
                # Populate student_id_map for later score assignment
                for created_data in temp_students_to_create:
                    created_student = students_dict.get(created_data['student_id'])
                    if created_student:
                        student_id_map[created_data['student_id']] = created_student.id
                    else:
                         # This case should ideally not happen if commit was successful and re-fetch worked
                         warnings.append(f"Could not find newly created student {created_data['student_id']} after commit.")
                         
            except IntegrityError as e:
                 db.session.rollback()
                 # Check if the error is due to duplicate student ID
                 if 'UNIQUE constraint failed: student.student_id' in str(e):
                     # Attempt to identify the problematic student ID(s)
                     problematic_ids = []
                     for student_data in temp_students_to_create:
                         existing_student = Student.query.filter_by(student_id=student_data['student_id'], course_id=course.id).first()
                         if existing_student:
                             problematic_ids.append(student_data['student_id'])
                             # Add to students_dict if somehow missed earlier
                             students_dict[student_data['student_id']] = existing_student
                             
                     if problematic_ids:
                         error_msg = f"Error creating students: The following student IDs already exist in this course: {', '.join(problematic_ids)}. Please uncheck 'Create missing students' or remove them from the import data."
                         errors.append(error_msg)
                         flash(error_msg, 'error')
                         # Decide whether to continue processing scores for existing students
                         if not continue_on_errors:
                              return redirect(url_for('student.manage_scores', exam_id=exam_id))
                     else:
                          # Generic integrity error
                          errors.append(f"Database error creating students: {str(e)}")
                          flash(f"Database error creating students: {str(e)}", 'error')
                          if not continue_on_errors: return redirect(url_for('student.manage_scores', exam_id=exam_id))
                         
            except Exception as e:
                db.session.rollback()
                errors.append(f"Error creating students: {str(e)}")
                flash(f"Error creating students: {str(e)}", 'error')
                if not continue_on_errors: return redirect(url_for('student.manage_scores', exam_id=exam_id))
                
    # Second pass: Process scores
    scores_to_add = []
    processed_students = set() # Track processed students per line to avoid duplicate processing
    
    for i, line in enumerate(lines, 1 if not header_row else 2):
        processed_students.clear() # Reset for each new line
        if not line.strip():
            continue
        
        try:
            # Add debug info to help identify problematic lines
            raw_line = repr(line)  # Show raw representation including special characters
            parts = [p.strip() for p in line.split(delimiter)]
            
            # --- Student ID and Identification ---
            if not parts: continue # Skip empty lines after split

            student_id_ext = parts[0].strip().replace('\\t', '')
            if not student_id_ext:
                warnings.append(f"Line {i}: Empty student ID found - skipping line")
                continue

            student = students_dict.get(student_id_ext)
            student_db_id = None

            if student:
                student_db_id = student.id
            elif create_students and student_id_ext in student_id_map:
                 # Student was created in the first pass
                 student_db_id = student_id_map[student_id_ext]
                 student = Student.query.get(student_db_id) # Get the actual student object
                 if not student: # Should not happen, but safety check
                      # Treat this as a warning, but skip this line's scores
                      warnings.append(f"Line {i}: Could not retrieve newly created student {student_id_ext}. Scores for this line skipped.")
                      continue
            else:
                 # Student not found and not created (or creation failed/disabled)
                 # Change this from an error to a warning and skip the line
                 warnings.append(f"Line {i}: Student ID {student_id_ext} not found in course. Scores for this line skipped.")
                 continue # Skip processing scores for this student
                 
            # Additional safety check to ensure student_db_id is valid
            if student_db_id is None:
                warnings.append(f"Line {i}: Student {student_id_ext} could not be resolved to a valid database ID. Scores for this line skipped.")
                continue
                 
            # Avoid processing the same student multiple times if they appear on the same line (unlikely but possible)
            if student_db_id in processed_students:
                 continue
            processed_students.add(student_db_id)

            # --- Score Parsing based on Format ---
            line_scores = [] # Scores parsed from this line

            if import_format == 'detailed':
                # --- DETAILED FORMAT PARSING ---
                if len(parts) < 2: # Need ID and Name minimum for this format, even if scores are missing
                     warnings.append(f"Line {i}, Student {student_id_ext}: Not enough data for detailed format (expected student ID and name). Raw line: {raw_line}. Student will be marked as not attended.")
                     # Mark student as not attended
                     try:
                         attendance_record = StudentExamAttendance.query.filter_by(
                             student_id=student_db_id, 
                             exam_id=exam_id
                         ).first()
                         
                         if attendance_record:
                             attendance_record.attended = False
                         else:
                             # Create new attendance record
                             new_attendance = StudentExamAttendance(
                                 student_id=student_db_id,
                                 exam_id=exam_id,
                                 attended=False
                             )
                             db.session.add(new_attendance)
                         
                     except Exception as e:
                         warnings.append(f"Line {i}, Student {student_id_ext}: Could not update attendance: {str(e)}")
                     continue
                
                score_data_parts = parts[2:] # Scores start from the 3rd element

                # Method 1: Use header mapping if available
                if header_mapping:
                    for col_idx, q_num in header_mapping.items():
                        if col_idx < len(parts):
                            score_str = parts[col_idx].strip().replace(',', '.') # Handle comma decimal sep
                            if not score_str: continue # Skip empty scores
                            
                            try:
                                score_value = Decimal(score_str)
                                question = questions.get(q_num)
                                if not question:
                                     warnings.append(f"Line {i}: Header refers to non-existent question {q_num} for student {student_id_ext}")
                                     continue # Skip this score if question not found

                                # Validate against max score if needed
                                if not allow_exceed_max and score_value > question.max_score:
                                     warnings.append(f"Line {i}, Student {student_id_ext}, Q{q_num}: Score {score_value} capped at max {question.max_score}")
                                     score_value = question.max_score
                                elif allow_exceed_max and score_value > question.max_score:
                                    # If allow_exceed_max is True, we don't cap, but we might still want a warning if it's unusually high or for logging.
                                    # For now, let's assume no warning is needed if explicitly allowed.
                                    pass # Score is allowed to exceed max_score
                                elif score_value > question.max_score: # This case implies allow_exceed_max is False
                                     warnings.append(f"Line {i}, Student {student_id_ext}, Q{q_num}: Score {score_value} capped at max {question.max_score}")
                                     score_value = question.max_score # Cap if continuing
                                elif score_value < 0:
                                    warnings.append(f"Line {i}, Student {student_id_ext}, Q{q_num}: Score {score_value} set to 0")
                                    score_value = Decimal('0')
                                    
                                line_scores.append({
                                    'student_id': student_db_id,
                                    'student_ext_id': student_id_ext, # Keep original ID for reference/error reporting
                                    'question_id': question.id,
                                    'question_num': q_num,
                                    'exam_id': exam_id,
                                    'score': score_value,
                                    'line_number': i
                                })
                            except InvalidOperation: # For Decimal conversion errors
                                warnings.append(f"Line {i}, Student {student_id_ext}, Q{q_num}: Invalid score format '{parts[col_idx]}', skipped")
                                continue
                            except Exception as e: # Catch other potential errors
                                 warnings.append(f"Line {i}, Student {student_id_ext}, Q{q_num}: Error processing score: {str(e)}, skipped")
                                 continue
                                 
                # Method 2: Parse remaining columns (Original Logic Style Restoration)
                elif score_data_parts: 
                    temp_line_scores = [] # Use temp list for sequential numbering fallback
                    for score_data in score_data_parts:
                        if not score_data.strip(): continue # Skip empty parts
                        
                        q_num = None
                        score_str = ""
                        question = None

                        try:
                            # Try q#:score format first
                            if ':' in score_data:
                                q_part, score_part = score_data.split(':', 1)
                                q_num_match = re.search(r'\d+', q_part)
                                if q_num_match:
                                    q_num = int(q_num_match.group(0))
                                    score_str = score_part.strip().replace(',', '.')
                                else:
                                    # If format is like ":5", treat as invalid for q:score
                                    warnings.append(f"Line {i}, Student {student_id_ext}: Invalid question format '{q_part}' in '{score_data}', skipped")
                                    continue # Skip this part
                            else:
                                # Fallback: Treat as sequential score if no colon
                                q_num = len(temp_line_scores) + 1 # Base sequential number on successful scores so far FOR THIS LINE
                                score_str = score_data.strip().replace(',', '.')
                            
                            # Validate question number
                            if q_num is None:
                                # Should not happen with the logic above, but safety check
                                warnings.append(f"Line {i}, Student {student_id_ext}: Could not determine question number for '{score_data}', skipped")
                                continue
                            
                            question = questions.get(q_num)
                            if not question:
                                warnings.append(f"Line {i}, Student {student_id_ext}: Question number {q_num} not found for this exam (from '{score_data}'), skipped")
                                continue # Skip score for non-existent question
                                
                            # Validate score string
                            if not score_str: continue # Skip empty score parts (e.g., "q5:")

                            # Convert score to Decimal
                            score_value = Decimal(score_str)

                            # Validate/Cap score value
                            if not allow_exceed_max and score_value > question.max_score:
                                warnings.append(f"Line {i}, Student {student_id_ext}, Q{q_num}: Score {score_value} capped at max {question.max_score}")
                                score_value = question.max_score
                            elif allow_exceed_max and score_value > question.max_score:
                                # If allow_exceed_max is True, we don't cap.
                                pass # Score is allowed to exceed max_score
                            elif score_value > question.max_score: # This case implies allow_exceed_max is False
                                warnings.append(f"Line {i}, Student {student_id_ext}, Q{q_num}: Score {score_value} capped at max {question.max_score}")
                                score_value = question.max_score
                            elif score_value < 0:
                                warnings.append(f"Line {i}, Student {student_id_ext}, Q{q_num}: Score {score_value} set to 0")
                                score_value = Decimal('0')
                            
                            # Add successfully parsed score to temp list for this line
                            temp_line_scores.append({
                                'student_id': student_db_id,
                                'student_ext_id': student_id_ext,
                                'question_id': question.id,
                                'question_num': q_num,
                                'exam_id': exam_id,
                                'score': score_value,
                                'line_number': i
                            })

                        except (ValueError, InvalidOperation): # Handles split error or Decimal conversion error
                             warnings.append(f"Line {i}, Student {student_id_ext}: Invalid score format or value in '{score_data}', skipped")
                             continue # Skip this specific score_data part
                        except Exception as e: # Catch other unexpected errors
                             warnings.append(f"Line {i}, Student {student_id_ext}: Error processing score data '{score_data}': {str(e)}, skipped")
                             continue # Skip this specific score_data part
                    
                    # After processing all parts for the line, add the valid scores
                    line_scores.extend(temp_line_scores)

            elif import_format == 'simple':
                # --- SIMPLE FORMAT PARSING ---
                # Format: student_no<delimiter>q1<delimiter>q2<delimiter>q3<delimiter>...
                # If no valid score, should be 0
                # If student has no scores at all, mark as not entered the exam
                
                if len(parts) < 2:  # Need at least student_id and potentially score fields
                    # Only student ID provided, no delimiter or score fields
                    warnings.append(f"Line {i}, Student {student_id_ext}: No delimiter or score fields found. Expected format: student_id<delimiter>score1<delimiter>score2... Raw line: {raw_line}. Student will be marked as not attended.")
                    # Mark student as not attended
                    try:
                        attendance_record = StudentExamAttendance.query.filter_by(
                            student_id=student_db_id, 
                            exam_id=exam_id
                        ).first()
                        
                        if attendance_record:
                            attendance_record.attended = False
                        else:
                            # Create new attendance record
                            new_attendance = StudentExamAttendance(
                                student_id=student_db_id,
                                exam_id=exam_id,
                                attended=False
                            )
                            db.session.add(new_attendance)
                        
                    except Exception as e:
                        warnings.append(f"Line {i}, Student {student_id_ext}: Could not update attendance: {str(e)}")
                    continue
                
                score_data_parts = parts[1:]  # Scores start from the 2nd element
                sorted_questions = sorted(questions.values(), key=lambda q: q.number)  # Ensure consistent order
                
                # Check if student has any valid scores (not just zeros)
                has_valid_scores = False
                temp_line_scores = []
                missing_scores_count = 0
                
                # Process all questions in the exam, not just the ones with provided scores
                for idx, question in enumerate(sorted_questions):
                    score_str = ""
                    
                    if idx < len(score_data_parts):
                        score_str = score_data_parts[idx].strip().replace(',', '.')
                    
                    # Handle missing or empty scores
                    if not score_str:
                        # Missing score - set to 0 and count it
                        score_value = Decimal('0')
                        missing_scores_count += 1
                    else:
                        try:
                            score_value = Decimal(score_str)
                        except (ValueError, InvalidOperation):
                            warnings.append(f"Line {i}, Student {student_id_ext}, Q{question.number}: Invalid score format '{score_str}', set to 0")
                            score_value = Decimal('0')
                            missing_scores_count += 1
                        except Exception as e:
                            warnings.append(f"Line {i}, Student {student_id_ext}, Q{question.number}: Error processing score: {str(e)}, set to 0")
                            score_value = Decimal('0')
                            missing_scores_count += 1
                    
                    # Check if this is a valid score (not zero means student participated)
                    if score_value > 0:
                        has_valid_scores = True
                    
                    # Validate/Cap score value
                    if not allow_exceed_max and score_value > question.max_score:
                        warnings.append(f"Line {i}, Student {student_id_ext}, Q{question.number}: Score {score_value} capped at max {question.max_score}")
                        score_value = question.max_score
                    elif allow_exceed_max and score_value > question.max_score:
                        # If allow_exceed_max is True, we don't cap.
                        pass # Score is allowed to exceed max_score
                    elif score_value > question.max_score: # This case implies allow_exceed_max is False
                        warnings.append(f"Line {i}, Student {student_id_ext}, Q{question.number}: Score {score_value} capped at max {question.max_score}")
                        score_value = question.max_score
                    elif score_value < 0:
                        warnings.append(f"Line {i}, Student {student_id_ext}, Q{question.number}: Score {score_value} set to 0")
                        score_value = Decimal('0')
                    
                    temp_line_scores.append({
                        'student_id': student_db_id,
                        'student_ext_id': student_id_ext,
                        'question_id': question.id,
                        'question_num': question.number,
                        'exam_id': exam_id,
                        'score': score_value,
                        'line_number': i
                    })
                
                # Check for extra scores provided beyond available questions
                if len(score_data_parts) > len(sorted_questions):
                    extra_count = len(score_data_parts) - len(sorted_questions)
                    warnings.append(f"Line {i}, Student {student_id_ext}: {extra_count} extra score(s) provided beyond available questions, ignored")
                
                # Notify about missing scores
                if missing_scores_count > 0:
                    warnings.append(f"Line {i}, Student {student_id_ext}: {missing_scores_count} missing score(s) set to 0")
                

                
                # If student has no valid scores (all zeros or no scores), mark as not attended
                if not has_valid_scores and temp_line_scores:
                    # Check if all scores are zero
                    all_zeros = all(score['score'] == Decimal('0') for score in temp_line_scores)
                    if all_zeros:
                        warnings.append(f"Line {i}, Student {student_id_ext}: All scores are 0, student will be marked as not attended")
                        # Set attendance to False for this student
                        try:
                            attendance_record = StudentExamAttendance.query.filter_by(
                                student_id=student_db_id, 
                                exam_id=exam_id
                            ).first()
                            
                            if attendance_record:
                                attendance_record.attended = False
                            else:
                                # Create new attendance record
                                new_attendance = StudentExamAttendance(
                                    student_id=student_db_id,
                                    exam_id=exam_id,
                                    attended=False
                                )
                                db.session.add(new_attendance)
                            
                            # Don't add the zero scores to the database
                            temp_line_scores = []
                            
                        except Exception as e:
                            warnings.append(f"Line {i}, Student {student_id_ext}: Could not update attendance: {str(e)}")
                
                # Handle case where student has no scores at all (empty after student_id)
                elif not temp_line_scores:
                    warnings.append(f"Line {i}, Student {student_id_ext}: No scores provided, student will be marked as not entered the exam")
                    # Set attendance to False for this student
                    try:
                        attendance_record = StudentExamAttendance.query.filter_by(
                            student_id=student_db_id, 
                            exam_id=exam_id
                        ).first()
                        
                        if attendance_record:
                            attendance_record.attended = False
                        else:
                            # Create new attendance record
                            new_attendance = StudentExamAttendance(
                                student_id=student_db_id,
                                exam_id=exam_id,
                                attended=False
                            )
                            db.session.add(new_attendance)
                        
                    except Exception as e:
                        warnings.append(f"Line {i}, Student {student_id_ext}: Could not update attendance: {str(e)}")
                
                # Add the scores for this line
                line_scores.extend(temp_line_scores)

            elif import_format == 'total_only':
                # --- TOTAL SCORE ONLY PARSING ---
                # Check if we have at least student ID and potentially a score field
                if len(parts) < 2:
                    # Only student ID provided, no delimiter or score field
                    warnings.append(f"Line {i}, Student {student_id_ext}: No delimiter or score field found. Expected format: student_id<delimiter>score or student_id<delimiter> (empty score). Raw line: {raw_line}. Student will be marked as not attended.")
                    # Mark student as not attended
                    try:
                        attendance_record = StudentExamAttendance.query.filter_by(
                            student_id=student_db_id, 
                            exam_id=exam_id
                        ).first()
                        
                        if attendance_record:
                            attendance_record.attended = False
                        else:
                            # Create new attendance record
                            new_attendance = StudentExamAttendance(
                                student_id=student_db_id,
                                exam_id=exam_id,
                                attended=False
                            )
                            db.session.add(new_attendance)
                        
                    except Exception as e:
                        warnings.append(f"Line {i}, Student {student_id_ext}: Could not update attendance: {str(e)}")
                    continue
                
                total_score_str = parts[1].strip().replace(',', '.')
                if not total_score_str:
                    # If total score string is empty, skip score processing for this student on this line.
                    warnings.append(f"Line {i}, Student {student_id_ext}: Empty total score provided. Raw line: {raw_line}. Student will be marked as not attended.")
                    # Mark student as not attended
                    try:
                        attendance_record = StudentExamAttendance.query.filter_by(
                            student_id=student_db_id, 
                            exam_id=exam_id
                        ).first()
                        
                        if attendance_record:
                            attendance_record.attended = False
                        else:
                            # Create new attendance record
                            new_attendance = StudentExamAttendance(
                                student_id=student_db_id,
                                exam_id=exam_id,
                                attended=False
                            )
                            db.session.add(new_attendance)
                        
                    except Exception as e:
                        warnings.append(f"Line {i}, Student {student_id_ext}: Could not update attendance: {str(e)}")
                    continue # Skip to the next line in the input file
                else:
                    try:
                        total_score_value = Decimal(total_score_str)
                        if total_score_value < 0:
                             warnings.append(f"Line {i}, Student {student_id_ext}: Negative total score {total_score_value} treated as 0.")
                             total_score_value = Decimal('0')
                    except InvalidOperation:
                        # Check if this is the first line, possibly a header
                        is_first_line = (i == (1 if not header_row else 2))
                        if is_first_line:
                            warnings.append(f"Line {i}: Skipped line - assumed header row for 'Total Score Only' format (Invalid score: '{parts[1]}').")
                            continue # Skip this line entirely
                        else:
                            # If not the first line, treat as a warning instead of error for better robustness
                            warnings.append(f"Line {i}, Student {student_id_ext}: Invalid total score format '{parts[1]}'. Raw line: {raw_line}. Student will be marked as not attended.")
                            # Mark student as not attended
                            try:
                                attendance_record = StudentExamAttendance.query.filter_by(
                                    student_id=student_db_id, 
                                    exam_id=exam_id
                                ).first()
                                
                                if attendance_record:
                                    attendance_record.attended = False
                                else:
                                    # Create new attendance record
                                    new_attendance = StudentExamAttendance(
                                        student_id=student_db_id,
                                        exam_id=exam_id,
                                        attended=False
                                    )
                                    db.session.add(new_attendance)
                                
                            except Exception as e:
                                warnings.append(f"Line {i}, Student {student_id_ext}: Could not update attendance: {str(e)}")
                            continue # Skip processing scores for this student on this line
                
                num_questions = len(questions)
                if num_questions == 0:
                    # This case is checked at the beginning, but double-check here
                    errors.append(f"Line {i}, Student {student_id_ext}: Cannot distribute score - no questions found for this exam.")
                    flash("Import failed: Cannot import scores as there are no questions defined for this exam.", 'error')
                    return redirect(url_for('student.manage_scores', exam_id=exam_id))

                # Calculate the target total score, capped by the exam's max possible score
                max_possible_total = sum(q.max_score for q in questions.values())
                target_total = min(total_score_value, max_possible_total)
                target_total = target_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                
                # Distribute score proportionally based on each question's max score
                distributed_sum_so_far = Decimal('0')
                final_scores_per_question = {} # Store final score for each question_id
                sorted_questions = sorted(questions.values(), key=lambda q: q.number) # Ensure consistent order

                # Calculate proportional score for each question based on its max_score
                # Distribute scores for all questions proportionally, except the last one
                for k in range(num_questions - 1):
                    question = sorted_questions[k]
                    
                    # Calculate proportional score: (question_max / total_max) * target_total
                    if max_possible_total > 0:
                        proportional_score = (question.max_score / max_possible_total) * target_total
                    else:
                        proportional_score = Decimal('0')
                    
                    # Round to 2 decimals for this question
                    q_score = proportional_score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    
                    # Validate/Cap the score for this question
                    original_q_score = q_score # Keep for potential warning/error message
                    if not allow_exceed_max and q_score > question.max_score:
                        if not continue_on_errors:
                            errors.append(f"Line {i}, Student {student_id_ext}, Q{question.number}: Distributed score {original_q_score} exceeds max {question.max_score}. Cannot adjust last question accurately.")
                            final_scores_per_question = {} # Clear scores for this student
                            break # Stop processing questions for this student
                        else:
                            warnings.append(f"Line {i}, Student {student_id_ext}, Q{question.number}: Distributed score {original_q_score} capped at max {question.max_score}")
                            q_score = question.max_score
                    elif allow_exceed_max and q_score > question.max_score:
                        # If allow_exceed_max is True, we don't cap.
                        pass # Score is allowed to exceed max_score
                    elif q_score > question.max_score: # This case implies allow_exceed_max is False
                        warnings.append(f"Line {i}, Student {student_id_ext}, Q{question.number}: Distributed score {original_q_score} capped at max {question.max_score}")
                        q_score = question.max_score
                    
                    if q_score < 0: q_score = Decimal('0')
                    
                    final_scores_per_question[question.id] = q_score
                    distributed_sum_so_far += q_score
                
                # If errors occurred and we're stopping, break out of the student loop
                if not final_scores_per_question and not continue_on_errors and any(f"Line {i}, Student {student_id_ext}" in e for e in errors):
                    continue # Skip to next line/student

                # Calculate the score for the last question (or only question if num_questions == 1)
                last_question = sorted_questions[-1]
                last_q_score = target_total - distributed_sum_so_far
                
                # Validate/Cap the last question's score
                original_last_q_score = last_q_score # Keep for potential warning/error message
                if not allow_exceed_max and last_q_score > last_question.max_score:
                     if not continue_on_errors:
                          errors.append(f"Line {i}, Student {student_id_ext}, Last Q({last_question.number}): Calculated score {original_last_q_score} exceeds max {last_question.max_score} to match total.")
                          final_scores_per_question = {} # Clear scores for this student
                          continue # Skip to next line/student
                     else:
                         warnings.append(f"Line {i}, Student {student_id_ext}, Last Q({last_question.number}): Calculated score {original_last_q_score} capped at max {last_question.max_score} to match total. Final total might be lower than imported.")
                         last_q_score = last_question.max_score
                elif allow_exceed_max and last_q_score > last_question.max_score:
                    # If allow_exceed_max is True, we don't cap.
                    pass # Score is allowed to exceed max_score
                elif last_q_score > last_question.max_score: # This case implies allow_exceed_max is False
                     warnings.append(f"Line {i}, Student {student_id_ext}, Last Q({last_question.number}): Calculated score {original_last_q_score} capped at max {last_question.max_score}. Final total might be lower than imported.")
                     last_q_score = last_question.max_score
                
                if last_q_score < 0:
                    warnings.append(f"Line {i}, Student {student_id_ext}, Last Q({last_question.number}): Calculated score {original_last_q_score} was negative, set to 0. Final total might be higher than imported.")
                    last_q_score = Decimal('0')
                
                # Ensure the final score is rounded correctly (though calculation should already be precise)
                final_scores_per_question[last_question.id] = last_q_score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                # Add the final calculated scores for this student if no fatal errors occurred
                if final_scores_per_question:
                    # Double check the final sum (optional, for debugging/verification)
                    final_total_check = sum(final_scores_per_question.values())
                    if final_total_check != target_total:
                         # This might happen if the last score was capped
                         warnings.append(f"Line {i}, Student {student_id_ext}: Final calculated total {final_total_check} does not exactly match target {target_total} due to capping/rounding adjustments.")

                    for question_id, final_score in final_scores_per_question.items():
                        # Find the original question object again (could optimize by storing obj earlier)
                        question = next((q for q in questions.values() if q.id == question_id), None)
                        if question: # Should always find it
                            line_scores.append({
                                'student_id': student_db_id,
                                'student_ext_id': student_id_ext,
                                'question_id': question.id,
                                'question_num': question.number,
                                'exam_id': exam_id,
                                'score': final_score,
                                'line_number': i
                            })
            
            # Add parsed scores for the line to the main list
            scores_to_add.extend(line_scores)

        except Exception as e:
            error_msg = f"Line {i}: Unexpected error processing line: {str(e)}"
            logging.error(f"Import Error on Line {i}: {traceback.format_exc()}") # Log detailed traceback
            # Always treat unexpected errors as warnings to make the import more robust
            warnings.append(f"{error_msg}. Raw line: {raw_line if 'raw_line' in locals() else 'N/A'}")
            continue
                
    # --- End of Line Processing Loop ---

    # Check if any errors occurred and we are not continuing
    if errors and not continue_on_errors:
        flash("Errors occurred during processing. No scores were imported.", 'error')
        # Display specific errors
        for error in errors:
            flash(error, 'danger') # Use danger for errors that stopped the import
        if warnings: # Show warnings too
             for warning in warnings: flash(warning, 'warning')
        return redirect(url_for('student.manage_scores', exam_id=exam_id))
    
    # If continue_on_errors is true, show errors/warnings but proceed with valid data
    if errors:
        flash("Some errors occurred during processing. Only valid entries were imported.", 'warning')
        for error in errors:
            flash(error, 'danger') # Use danger for errors that were skipped
    if warnings:
        flash("Some warnings occurred during processing:", 'warning')
        for warning in warnings:
            flash(warning, 'warning')

    # Final step: Add scores to the database
    if scores_to_add:
        try:
            # Optional: Delete existing scores for the imported students first
            # delete_existing = request.form.get('delete_existing') == 'on'
            # if delete_existing:
            #     student_ids_in_import = {s['student_id'] for s in scores_to_add}
            #     if student_ids_in_import:
            #         Score.query.filter(Score.exam_id == exam_id, Score.student_id.in_(student_ids_in_import)).delete(synchronize_session=False)
            #         db.session.commit() # Commit deletion before adding new scores
            
            scores_updated = 0
            scores_added = 0
            db_errors = []
            
            # Get existing scores more efficiently using a dictionary lookup
            existing_scores_query = Score.query.filter(Score.exam_id == exam_id)
            existing_scores = {(s.student_id, s.question_id): s for s in existing_scores_query}
            
            scores_to_insert = []
            scores_to_update = []

            processed_keys = set() # Ensure we don't try to insert/update the same student/question twice from the import list

            for score_data in scores_to_add:
                score_key = (score_data['student_id'], score_data['question_id'])
                
                # Avoid duplicate processing from the import list itself
                if score_key in processed_keys:
                     warnings.append(f"Duplicate score for Student {score_data['student_ext_id']} Q{score_data['question_num']} in import data (line {score_data['line_number']}). Using first occurrence.")
                     continue
                processed_keys.add(score_key)

                if score_key in existing_scores:
                    # Update existing score
                    existing_score = existing_scores[score_key]
                    # Only update if the score is different to minimize db writes
                    if existing_score.score != score_data['score']:
                         existing_score.score = score_data['score']
                         existing_score.updated_at = datetime.now()
                         scores_to_update.append(existing_score) # Can bulk update later if needed, or just rely on session tracking
                         scores_updated += 1
                    # If score is the same, do nothing for this entry
                else:
                    # Prepare new score for insertion
                    # Ensure we don't add a score for a student that failed creation or wasn't found
                    if score_data['student_id'] is not None:
                         new_score = Score(
                             score=score_data['score'],
                             student_id=score_data['student_id'],
                             question_id=score_data['question_id'],
                             exam_id=exam_id
                         )
                         scores_to_insert.append(new_score)
                         scores_added += 1
                         # Add key to existing_scores conceptually to prevent duplicates within the same import batch if not using processed_keys
                         # existing_scores[score_key] = new_score # Add placeholder or the object itself
                    else:
                         # This should be caught earlier, but safeguard
                         db_errors.append(f"Attempted to add score for unknown student (Ext ID: {score_data['student_ext_id']}, Line: {score_data['line_number']})")

            # Perform bulk insertion if possible
            if scores_to_insert:
                 try:
                      db.session.bulk_save_objects(scores_to_insert)
                 except Exception as e:
                      db_errors.append(f"Error during bulk insertion: {str(e)}")
                      # Rollback might be needed here depending on overall transaction strategy
                      db.session.rollback() # Rollback bulk insert attempt
                      # Optionally, attempt individual inserts if bulk fails and continue_on_errors
                      if continue_on_errors:
                           flash("Bulk insertion failed, attempting individual inserts...", 'warning')
                           scores_added = 0 # Reset count
                           for score_obj in scores_to_insert:
                                try:
                                     db.session.add(score_obj)
                                     db.session.flush() # Flush to catch errors per object
                                     scores_added += 1
                                except Exception as e_ind:
                                     db_errors.append(f"Error inserting score for Student Ext ID {score_data['student_ext_id']} Q{score_data['question_num']}: {str(e_ind)}")
                                     db.session.rollback() # Rollback only the failed insert
                                     db.session.begin() # Start a new transaction context if needed
                           if scores_added > 0: db.session.commit() # Commit successful individual inserts
                      else:
                          # If not continuing, report error and stop
                          flash(f"Database error during score insertion: {str(e)}. Import failed.", 'error')
                          return redirect(url_for('student.manage_scores', exam_id=exam_id))


            # Commit all updates (tracked by the session) and successful inserts
            db.session.commit()

            # Log action
            log = Log(
                action="IMPORT_SCORES",
                description=f"Imported {scores_added} scores, updated {scores_updated} scores for exam: {exam.name} (Format: {import_format})."
            )
            db.session.add(log)
            db.session.commit()
            
            success_msg = f"Scores imported successfully: {scores_added} added, {scores_updated} updated."
            if db_errors:
                 flash(success_msg + " Some database errors occurred.", 'warning')
                 for db_err in db_errors: flash(db_err, 'danger')
            else:
                 flash(success_msg, 'success')
                 
        except Exception as e:
            db.session.rollback()
            flash(f"Database error saving scores: {str(e)}", 'error')
            logging.error(f"Database error during score import commit: {traceback.format_exc()}")
            
    elif not errors: # No scores to add and no errors reported
        flash("No valid score data found to import.", 'info')
        
    # Redirect back to the scores page regardless of outcome (unless fatal error occurred earlier)
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
            return max(delimiters.items(), key=lambda x: x[1])[0] if any(delimiters.values()) else '\t'
        
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
            else:
                if imported_count > 0:
                    # Log the action
                    log = Log(
                        action="IMPORT_EXAM_ATTENDANCE",
                        description=f"Imported attendance for {imported_count} students in {exam.name}"
                    )
                    db.session.add(log)
                    
                    db.session.commit()
                    
                    flash(f'Successfully imported attendance for {imported_count} students.', 'success')
                else:
                    db.session.rollback()
                    flash('No attendance records were imported.', 'warning')
        else:
            if errors:
                flash(f'No attendance records were imported due to {len(errors)} validation errors.', 'error')
                for error in errors[:10]:  # Show first 10 errors
                    flash(error, 'warning')
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
