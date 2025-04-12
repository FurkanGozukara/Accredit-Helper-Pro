from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from app import db
from models import CourseOutcome, ProgramOutcome, Course, Log, Question
from datetime import datetime
import logging
import io
import csv
from routes.utility_routes import export_to_excel_csv
import re
import pandas as pd
from io import BytesIO
import json

outcome_bp = Blueprint('outcome', __name__, url_prefix='/outcome')

@outcome_bp.route('/course/<int:course_id>/add', methods=['GET', 'POST'])
def add_course_outcome(course_id):
    """Add a new course outcome to a course"""
    course = Course.query.get_or_404(course_id)
    program_outcomes = ProgramOutcome.query.all()
    
    if request.method == 'POST':
        code = request.form.get('code')
        description = request.form.get('description')
        
        # Get selected program outcomes
        selected_program_outcomes = request.form.getlist('program_outcomes')
        
        # Get weights for program outcomes
        po_weights = {}
        for po_id in selected_program_outcomes:
            weight_key = f'po_weight_{po_id}'
            weight = request.form.get(weight_key, '1.0')
            try:
                weight_value = float(weight)
                # Ensure weight is within valid range (0.00 to 9.99)
                weight_value = max(0.00, min(9.99, weight_value))
                po_weights[po_id] = weight_value
            except ValueError:
                po_weights[po_id] = 1.0  # Default to 1.0 if invalid
        
        # Basic validation
        if not code or not description:
            flash('Code and description are required', 'error')
            return render_template('outcome/course_outcome_form.html', 
                                 course=course,
                                 program_outcomes=program_outcomes,
                                 active_page='courses')
        
        # Check if a course outcome with the same code already exists in this course
        existing_outcome = CourseOutcome.query.filter_by(code=code, course_id=course_id).first()
        if existing_outcome:
            flash(f'A course outcome with code {code} already exists in this course', 'error')
            return render_template('outcome/course_outcome_form.html', 
                                 course=course,
                                 program_outcomes=program_outcomes,
                                 active_page='courses',
                                 outcome={'code': code, 'description': description})
        
        try:
            # Create new course outcome
            new_outcome = CourseOutcome(
                code=code,
                description=description,
                course_id=course_id
            )
            
            db.session.add(new_outcome)
            db.session.flush()  # Assign ID without committing
            
            # Associate with program outcomes with weights
            for program_outcome_id in selected_program_outcomes:
                program_outcome = ProgramOutcome.query.get(program_outcome_id)
                if program_outcome:
                    # Check if we can add the weight directly to the association
                    from sqlalchemy import inspect, text
                    inspector = inspect(db.engine)
                    columns = [c['name'] for c in inspector.get_columns('course_outcome_program_outcome')]
                    
                    if 'relative_weight' in columns:
                        # Add the program outcome with the relative weight
                        relative_weight = po_weights.get(program_outcome_id, 1.0)
                        # Add the PO to the CO
                        new_outcome.program_outcomes.append(program_outcome)
                        # Update the weight in the association table after the flush
                        db.session.flush()
                        db.session.execute(text(
                            "UPDATE course_outcome_program_outcome SET relative_weight = :weight "
                            "WHERE course_outcome_id = :co_id AND program_outcome_id = :po_id"
                        ), {
                            "weight": relative_weight,
                            "co_id": new_outcome.id,
                            "po_id": program_outcome.id
                        })
                    else:
                        # For older installations without relative_weight column
                        new_outcome.program_outcomes.append(program_outcome)
            
            # Log action
            log = Log(action="ADD_COURSE_OUTCOME", 
                     description=f"Added course outcome {code} to course: {course.code}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Course outcome {code} added successfully', 'success')
            return redirect(url_for('course.course_detail', course_id=course_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding course outcome: {str(e)}")
            flash('An error occurred while adding the course outcome', 'error')
            return render_template('outcome/course_outcome_form.html', 
                                 course=course,
                                 program_outcomes=program_outcomes,
                                 active_page='courses',
                                 outcome={'code': code, 'description': description})
    
    # GET request
    return render_template('outcome/course_outcome_form.html', 
                         course=course,
                         program_outcomes=program_outcomes,
                         active_page='courses')

@outcome_bp.route('/course/edit/<int:outcome_id>', methods=['GET', 'POST'])
def edit_course_outcome(outcome_id):
    """Edit an existing course outcome"""
    course_outcome = CourseOutcome.query.get_or_404(outcome_id)
    course = Course.query.get_or_404(course_outcome.course_id)
    program_outcomes = ProgramOutcome.query.all()
    
    # Get current weights if they exist
    current_weights = {}
    try:
        from sqlalchemy import text
        result = db.session.execute(text(
            "SELECT program_outcome_id, relative_weight FROM course_outcome_program_outcome "
            "WHERE course_outcome_id = :co_id"
        ), {"co_id": outcome_id})
        
        for row in result:
            program_outcome_id = row[0]
            relative_weight = float(row[1]) if row[1] is not None else 1.0
            current_weights[program_outcome_id] = relative_weight
    except Exception as e:
        logging.warning(f"Could not retrieve existing weights: {e}")
    
    if request.method == 'POST':
        code = request.form.get('code')
        description = request.form.get('description')
        
        # Get selected program outcomes
        selected_program_outcomes = request.form.getlist('program_outcomes')
        logging.debug(f"Selected program outcomes: {selected_program_outcomes}")
        
        # Get weights for program outcomes from form
        po_weights = {}
        for po_id in selected_program_outcomes:
            weight_key = f'po_weight_{po_id}'
            weight = request.form.get(weight_key, '1.0')
            logging.debug(f"Weight from form for PO {po_id}: {weight}")
            
            try:
                weight_value = float(weight)
                # Ensure weight is within valid range (0.00 to 9.99)
                weight_value = max(0.00, min(9.99, weight_value))
                po_weights[po_id] = weight_value
            except ValueError:
                logging.warning(f"Invalid weight value for PO {po_id}: {weight}")
                po_weights[po_id] = 1.0  # Default to 1.0 if invalid
        
        logging.debug(f"Program outcome weights from form: {po_weights}")
        
        # Basic validation
        if not code or not description:
            flash('Code and description are required', 'error')
            return render_template('outcome/course_outcome_form.html', 
                                 course=course,
                                 program_outcomes=program_outcomes,
                                 outcome=course_outcome,
                                 active_page='courses')
        
        # Check if update would create a duplicate
        existing_outcome = CourseOutcome.query.filter_by(code=code, course_id=course.id).first()
        if existing_outcome and existing_outcome.id != outcome_id:
            flash(f'A course outcome with code {code} already exists in this course', 'error')
            return render_template('outcome/course_outcome_form.html', 
                                 course=course,
                                 program_outcomes=program_outcomes,
                                 outcome=course_outcome,
                                 active_page='courses')
        
        try:
            # Update course outcome
            course_outcome.code = code
            course_outcome.description = description
            course_outcome.updated_at = datetime.now()
            
            # Check if we can add weights
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('course_outcome_program_outcome')]
            has_relative_weight = 'relative_weight' in columns
            logging.debug(f"Has relative_weight column: {has_relative_weight}")
            
            # Begin a subtransaction for the associations update
            db_success = True
            
            # Clear and reassociate with program outcomes only if the database supports it
            if has_relative_weight:
                # Store existing associations to avoid unnecessary removals
                existing_associations = {}
                result = db.session.execute(text(
                    "SELECT program_outcome_id FROM course_outcome_program_outcome "
                    "WHERE course_outcome_id = :co_id"
                ), {"co_id": outcome_id})
                for row in result:
                    existing_associations[row[0]] = True
                
                logging.debug(f"Existing program outcome associations: {existing_associations}")
                
                # Process selected and deselected program outcomes
                for po in program_outcomes:
                    po_id_str = str(po.id)
                    is_selected = po_id_str in selected_program_outcomes
                    was_associated = po.id in existing_associations
                    
                    if is_selected and not was_associated:
                        # Add new association
                        course_outcome.program_outcomes.append(po)
                        db.session.flush()
                        
                        # Set weight
                        weight_value = po_weights.get(po_id_str, 1.0)
                        try:
                            result = db.session.execute(text(
                                "UPDATE course_outcome_program_outcome SET relative_weight = :weight "
                                "WHERE course_outcome_id = :co_id AND program_outcome_id = :po_id"
                            ), {
                                "weight": weight_value,
                                "co_id": course_outcome.id,
                                "po_id": po.id
                            })
                            logging.debug(f"Added new association for PO {po.id} with weight {weight_value}, rows affected: {result.rowcount}")
                        except Exception as e:
                            logging.error(f"Error setting weight for new association with PO {po.id}: {str(e)}")
                            db_success = False
                            
                    elif is_selected and was_associated:
                        # Update existing association weight
                        weight_value = po_weights.get(po_id_str, 1.0)
                        try:
                            result = db.session.execute(text(
                                "UPDATE course_outcome_program_outcome SET relative_weight = :weight "
                                "WHERE course_outcome_id = :co_id AND program_outcome_id = :po_id"
                            ), {
                                "weight": weight_value,
                                "co_id": course_outcome.id,
                                "po_id": po.id
                            })
                            logging.debug(f"Updated weight for existing PO {po.id} to {weight_value}, rows affected: {result.rowcount}")
                        except Exception as e:
                            logging.error(f"Error updating weight for PO {po.id}: {str(e)}")
                            db_success = False
                            
                    elif not is_selected and was_associated:
                        # Remove association
                        try:
                            result = db.session.execute(text(
                                "DELETE FROM course_outcome_program_outcome "
                                "WHERE course_outcome_id = :co_id AND program_outcome_id = :po_id"
                            ), {
                                "co_id": course_outcome.id,
                                "po_id": po.id
                            })
                            logging.debug(f"Removed association with PO {po.id}, rows affected: {result.rowcount}")
                        except Exception as e:
                            logging.error(f"Error removing association with PO {po.id}: {str(e)}")
                            db_success = False
            else:
                # For databases without relative_weight column
                logging.warning("Database doesn't support weights. Using standard SQLAlchemy relationship management.")
                # Clear all program outcomes
                course_outcome.program_outcomes = []
                db.session.flush()
                
                # Add selected program outcomes
                for po_id in selected_program_outcomes:
                    po = ProgramOutcome.query.get(po_id)
                    if po:
                        course_outcome.program_outcomes.append(po)
            
            if not db_success:
                db.session.rollback()
                flash('Failed to update program outcome associations. Please try again.', 'error')
                return render_template('outcome/course_outcome_form.html',
                                     course=course,
                                     program_outcomes=program_outcomes,
                                     outcome=course_outcome,
                                     current_weights=po_weights,
                                     active_page='courses')
            
            # Log action
            log = Log(action="EDIT_COURSE_OUTCOME", 
                     description=f"Edited course outcome {code} in course: {course.code}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Course outcome {code} updated successfully', 'success')
            return redirect(url_for('outcome.edit_course_outcome', outcome_id=outcome_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating course outcome: {str(e)}")
            flash('An error occurred while updating the course outcome', 'error')
            return render_template('outcome/course_outcome_form.html', 
                                 course=course,
                                 program_outcomes=program_outcomes,
                                 outcome=course_outcome,
                                 current_weights=current_weights,
                                 active_page='courses')
    
    # GET request
    return render_template('outcome/course_outcome_form.html', 
                         course=course,
                         program_outcomes=program_outcomes,
                         outcome=course_outcome,
                         current_weights=current_weights,
                         active_page='courses')

@outcome_bp.route('/course/delete/<int:outcome_id>', methods=['POST'])
def delete_course_outcome(outcome_id):
    """Delete a course outcome after confirmation"""
    course_outcome = CourseOutcome.query.get_or_404(outcome_id)
    course_id = course_outcome.course_id
    
    try:
        # Check for related data (questions associated with this outcome)
        question_count = len(course_outcome.questions)
        
        if question_count > 0:
            error_message = f"Cannot delete course outcome: It is associated with {question_count} exam questions. "
            error_message += "Remove these associations first."
            flash(error_message, 'error')
            return redirect(url_for('course.course_detail', course_id=course_id))
            
        # Log action before deletion
        log = Log(action="DELETE_COURSE_OUTCOME", 
                 description=f"Deleted course outcome {course_outcome.code} from course: {course_outcome.course.code}")
        db.session.add(log)
        
        db.session.delete(course_outcome)
        db.session.commit()
        flash(f'Course outcome {course_outcome.code} deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting course outcome: {str(e)}")
        flash(f'An error occurred while deleting the course outcome: {str(e)}', 'error')
    
    return redirect(url_for('course.course_detail', course_id=course_id))

@outcome_bp.route('/course/mass-delete', methods=['POST'])
def mass_delete_outcomes():
    """Batch delete multiple course outcomes"""
    course_id = request.form.get('course_id', type=int)
    outcome_ids = request.form.getlist('outcome_ids', type=int)
    
    if not course_id or not outcome_ids:
        flash('No course outcomes selected for deletion', 'error')
        return redirect(url_for('course.course_detail', course_id=course_id))
    
    course = Course.query.get_or_404(course_id)
    deleted_count = 0
    error_count = 0
    
    for outcome_id in outcome_ids:
        outcome = CourseOutcome.query.get(outcome_id)
        
        if outcome and outcome.course_id == course_id:
            # Check for related data (questions associated with this outcome)
            question_count = len(outcome.questions)
            
            if question_count > 0:
                flash(f"Cannot delete '{outcome.code}': It is associated with {question_count} exam questions", 'warning')
                error_count += 1
                continue
                
            try:
                # Log action before deletion
                log = Log(action="DELETE_COURSE_OUTCOME", 
                         description=f"Deleted course outcome {outcome.code} from course: {course.code}")
                db.session.add(log)
                
                db.session.delete(outcome)
                deleted_count += 1
            except Exception as e:
                logging.error(f"Error deleting outcome {outcome.code}: {str(e)}")
                error_count += 1
                flash(f'Error deleting outcome {outcome.code}: {str(e)}', 'error')
    
    try:
        db.session.commit()
        if deleted_count > 0:
            flash(f'Successfully deleted {deleted_count} course outcomes', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in batch deletion transaction: {str(e)}")
        flash(f'An error occurred during batch deletion: {str(e)}', 'error')
    
    if error_count > 0:
        flash(f'Failed to delete {error_count} course outcomes due to associations with exam questions', 'warning')
    
    return redirect(url_for('course.course_detail', course_id=course_id))

@outcome_bp.route('/course/<int:course_id>/mass_edit', methods=['GET', 'POST'])
def mass_edit_outcomes(course_id):
    """Mass edit multiple course outcomes for a course"""
    course = Course.query.get_or_404(course_id)
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()
    program_outcomes = ProgramOutcome.query.all()
    
    if request.method == 'POST':
        try:
            # Track which outcomes were updated
            updated_outcomes = []
            
            # Process each outcome
            for outcome in course_outcomes:
                # Get updated values from form
                code_key = f'code_{outcome.id}'
                desc_key = f'description_{outcome.id}'
                
                new_code = request.form.get(code_key, outcome.code)
                new_description = request.form.get(desc_key, outcome.description)
                
                # Check if outcome has changed
                if new_code != outcome.code or new_description != outcome.description:
                    # Validate code isn't empty
                    if not new_code.strip():
                        flash(f'Code cannot be empty for outcome {outcome.code}', 'error')
                        continue
                        
                    # Check for duplicate code (excluding the current outcome)
                    duplicate = CourseOutcome.query.filter(
                        CourseOutcome.course_id == course_id,
                        CourseOutcome.code == new_code,
                        CourseOutcome.id != outcome.id
                    ).first()
                    
                    if duplicate:
                        flash(f'A course outcome with code {new_code} already exists', 'error')
                        continue
                    
                    # Update the outcome
                    outcome.code = new_code
                    outcome.description = new_description
                    outcome.updated_at = datetime.now()
                    updated_outcomes.append(outcome.code)
            
            # If any outcomes were updated
            if updated_outcomes:
                # Log the action
                log = Log(
                    action="MASS_EDIT_COURSE_OUTCOMES",
                    description=f"Mass edited {len(updated_outcomes)} course outcomes in course: {course.code}"
                )
                db.session.add(log)
                
                # Commit changes
                db.session.commit()
                flash(f'Successfully updated {len(updated_outcomes)} course outcomes', 'success')
                return redirect(url_for('outcome.mass_edit_outcomes', course_id=course_id))
            else:
                flash('No outcomes were modified', 'info')
        
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error mass editing course outcomes: {str(e)}")
            flash(f'An error occurred: {str(e)}', 'error')
    
    # GET request or after POST
    return render_template('outcome/mass_edit_outcomes.html',
                         course=course,
                         course_outcomes=course_outcomes,
                         program_outcomes=program_outcomes,
                         active_page='courses')

@outcome_bp.route('/program')
def list_program_outcomes():
    """List all program outcomes"""
    program_outcomes = ProgramOutcome.query.all()
    return render_template('outcome/program_outcomes.html', 
                         program_outcomes=program_outcomes,
                         active_page='program_outcomes')

@outcome_bp.route('/program/edit/<int:outcome_id>', methods=['GET', 'POST'])
def edit_program_outcome(outcome_id):
    """Edit an existing program outcome"""
    program_outcome = ProgramOutcome.query.get_or_404(outcome_id)
    
    if request.method == 'POST':
        code = request.form.get('code')
        description = request.form.get('description')
        
        # Basic validation
        if not code or not description:
            flash('Code and description are required', 'error')
            return render_template('outcome/program_outcome_form.html', 
                                 outcome=program_outcome,
                                 active_page='program_outcomes')
        
        # Check if update would create a duplicate
        existing_outcome = ProgramOutcome.query.filter_by(code=code).first()
        if existing_outcome and existing_outcome.id != outcome_id:
            flash(f'A program outcome with code {code} already exists', 'error')
            return render_template('outcome/program_outcome_form.html', 
                                 outcome=program_outcome,
                                 active_page='program_outcomes')
        
        try:
            # Update program outcome
            program_outcome.code = code
            program_outcome.description = description
            program_outcome.updated_at = datetime.now()
            
            # Log action
            log = Log(action="EDIT_PROGRAM_OUTCOME", 
                     description=f"Edited program outcome {code}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Program outcome {code} updated successfully', 'success')
            return redirect(url_for('outcome.list_program_outcomes'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating program outcome: {str(e)}")
            flash('An error occurred while updating the program outcome', 'error')
            return render_template('outcome/program_outcome_form.html', 
                                 outcome=program_outcome,
                                 active_page='program_outcomes')
    
    # GET request
    return render_template('outcome/program_outcome_form.html', 
                         outcome=program_outcome,
                         active_page='program_outcomes')

@outcome_bp.route('/program/add', methods=['GET', 'POST'])
def add_program_outcome():
    """Add a new program outcome"""
    if request.method == 'POST':
        code = request.form.get('code')
        description = request.form.get('description')
        
        # Basic validation
        if not code or not description:
            flash('Code and description are required', 'error')
            return render_template('outcome/program_outcome_form.html', 
                                 active_page='program_outcomes')
        
        # Check if a program outcome with the same code already exists
        existing_outcome = ProgramOutcome.query.filter_by(code=code).first()
        if existing_outcome:
            flash(f'A program outcome with code {code} already exists', 'error')
            return render_template('outcome/program_outcome_form.html', 
                                 active_page='program_outcomes',
                                 outcome={'code': code, 'description': description})
        
        try:
            # Create new program outcome
            new_outcome = ProgramOutcome(
                code=code,
                description=description
            )
            
            db.session.add(new_outcome)
            
            # Log action
            log = Log(action="ADD_PROGRAM_OUTCOME", 
                     description=f"Added program outcome {code}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Program outcome {code} added successfully', 'success')
            return redirect(url_for('outcome.list_program_outcomes'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding program outcome: {str(e)}")
            flash('An error occurred while adding the program outcome', 'error')
            return render_template('outcome/program_outcome_form.html', 
                                 active_page='program_outcomes',
                                 outcome={'code': code, 'description': description})
    
    # GET request
    return render_template('outcome/program_outcome_form.html', 
                         active_page='program_outcomes')

@outcome_bp.route('/program/delete/<int:outcome_id>', methods=['POST'])
def delete_program_outcome(outcome_id):
    """Delete a program outcome after confirmation"""
    program_outcome = ProgramOutcome.query.get_or_404(outcome_id)
    
    # Check if this program outcome is associated with any course outcomes
    associated_count = len(program_outcome.course_outcomes)
    
    if associated_count > 0:
        flash(f'Cannot delete: This program outcome is associated with {associated_count} course outcomes. Remove these associations first.', 'error')
        return redirect(url_for('outcome.list_program_outcomes'))
    
    try:
        # Log action before deletion
        log = Log(action="DELETE_PROGRAM_OUTCOME", 
                 description=f"Deleted program outcome {program_outcome.code}")
        db.session.add(log)
        
        db.session.delete(program_outcome)
        db.session.commit()
        flash(f'Program outcome {program_outcome.code} deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting program outcome: {str(e)}")
        flash('An error occurred while deleting the program outcome', 'error')
    
    return redirect(url_for('outcome.list_program_outcomes'))

@outcome_bp.route('/program/batch-delete', methods=['POST'])
def batch_delete_program_outcomes():
    """Batch delete multiple program outcomes"""
    outcome_ids = request.form.getlist('outcome_ids', type=int)
    
    if not outcome_ids:
        flash('No program outcomes selected for deletion', 'error')
        return redirect(url_for('outcome.list_program_outcomes'))
    
    deleted_count = 0
    error_count = 0
    
    for outcome_id in outcome_ids:
        outcome = ProgramOutcome.query.get(outcome_id)
        
        if outcome:
            # Check if this program outcome is associated with any course outcomes
            associated_count = len(outcome.course_outcomes)
            
            if associated_count > 0:
                flash(f"Cannot delete '{outcome.code}': It is associated with {associated_count} course outcomes", 'warning')
                error_count += 1
                continue
                
            try:
                # Log action before deletion
                log = Log(action="DELETE_PROGRAM_OUTCOME", 
                         description=f"Deleted program outcome {outcome.code}")
                db.session.add(log)
                
                db.session.delete(outcome)
                deleted_count += 1
            except Exception as e:
                logging.error(f"Error deleting outcome {outcome.code}: {str(e)}")
                error_count += 1
                flash(f'Error deleting outcome {outcome.code}: {str(e)}', 'error')
    
    try:
        db.session.commit()
        if deleted_count > 0:
            flash(f'Successfully deleted {deleted_count} program outcomes', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in batch deletion transaction: {str(e)}")
        flash(f'An error occurred during batch deletion: {str(e)}', 'error')
    
    if error_count > 0:
        flash(f'Failed to delete {error_count} program outcomes due to associations with course outcomes', 'warning')
    
    return redirect(url_for('outcome.list_program_outcomes'))

@outcome_bp.route('/program/batch-import', methods=['POST'])
def batch_import_program_outcomes():
    """Import multiple program outcomes from a text input with tab or semicolon delimiters"""
    if 'outcome_data' not in request.form or not request.form['outcome_data'].strip():
        flash('No data provided for import', 'error')
        return redirect(url_for('outcome.list_program_outcomes'))
        
    data = request.form['outcome_data'].strip()
    lines = data.split('\n')
    
    # Process each line
    added_count = 0
    error_count = 0
    updated_count = 0
    existing_count = 0
    
    for line in lines:
        if not line.strip():
            continue
            
        # Split by tab or semicolon, whichever appears first
        if '\t' in line:
            parts = line.split('\t', 1)
        elif ';' in line:
            parts = line.split(';', 1)
        else:
            flash(f'Invalid format in line: {line}. Use tab or semicolon as separator.', 'error')
            error_count += 1
            continue
            
        if len(parts) < 2:
            flash(f'Invalid format in line: {line}. Missing code or description.', 'error')
            error_count += 1
            continue
            
        code = parts[0].strip()
        description = parts[1].strip()
        
        if not code or not description:
            flash(f'Invalid data: Code and description are required', 'error')
            error_count += 1
            continue
            
        # Check if outcome already exists
        existing_outcome = ProgramOutcome.query.filter_by(code=code).first()
        
        try:
            if existing_outcome:
                # Check if different and needs update
                if existing_outcome.description != description:
                    existing_outcome.description = description
                    existing_outcome.updated_at = datetime.now()
                    
                    # Log update action
                    log = Log(action="UPDATE_PROGRAM_OUTCOME",
                             description=f"Updated program outcome {code} via batch import")
                    db.session.add(log)
                    updated_count += 1
                else:
                    existing_count += 1
            else:
                # Create new outcome
                new_outcome = ProgramOutcome(
                    code=code,
                    description=description
                )
                db.session.add(new_outcome)
                
                # Log action
                log = Log(action="ADD_PROGRAM_OUTCOME",
                         description=f"Added program outcome {code} via batch import")
                db.session.add(log)
                added_count += 1
                
        except Exception as e:
            logging.error(f"Error processing outcome {code}: {str(e)}")
            error_count += 1
            flash(f'Error processing outcome {code}: {str(e)}', 'error')
    
    try:
        db.session.commit()
        
        summary = []
        if added_count > 0:
            summary.append(f"Added {added_count} new outcomes")
        if updated_count > 0:
            summary.append(f"Updated {updated_count} existing outcomes")
        if existing_count > 0:
            summary.append(f"Skipped {existing_count} unchanged outcomes")
            
        if summary:
            flash('Import completed: ' + '; '.join(summary), 'success')
            
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in batch import transaction: {str(e)}")
        flash(f'An error occurred during batch import: {str(e)}', 'error')
    
    if error_count > 0:
        flash(f'Failed to process {error_count} outcomes due to errors', 'warning')
    
    return redirect(url_for('outcome.list_program_outcomes'))

@outcome_bp.route('/course/<int:course_id>/export')
def export_course_outcomes(course_id):
    """Export course outcomes to CSV"""
    course = Course.query.get_or_404(course_id)
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()
    
    # Check if relative_weight column exists
    has_relative_weight = False
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('course_outcome_program_outcome')]
        has_relative_weight = 'relative_weight' in columns
    except Exception as e:
        logging.warning(f"Could not check for relative_weight column: {e}")
    
    # Prepare data for export
    data = []
    headers = ['Code', 'Description']
    
    # Add PO columns with weights if available
    po_headers = []
    if has_relative_weight:
        # Get all program outcomes used by this course
        program_outcomes = set()
        for co in course_outcomes:
            for po in co.program_outcomes:
                program_outcomes.add(po)
        # Sort program outcomes by code
        program_outcomes = sorted(list(program_outcomes), key=lambda po: po.code)
        
        # Add each program outcome as two columns: one for relation, one for weight
        for po in program_outcomes:
            po_headers.append(f'PO: {po.code}')
            po_headers.append(f'Weight: {po.code}')
    else:
        headers.append('Related Program Outcomes')
    
    # Combine headers
    headers.extend(po_headers)
    headers.append('Related Questions')
    
    # Get CO-PO weights if available
    co_po_weights = {}
    if has_relative_weight:
        try:
            from sqlalchemy import text
            for co in course_outcomes:
                co_po_weights[co.id] = {}
                result = db.session.execute(text(
                    "SELECT program_outcome_id, relative_weight FROM course_outcome_program_outcome "
                    "WHERE course_outcome_id = :co_id"
                ), {"co_id": co.id})
                
                for row in result:
                    co_po_weights[co.id][row[0]] = float(row[1]) if row[1] is not None else 1.0
        except Exception as e:
            logging.warning(f"Could not retrieve CO-PO weights: {e}")
    
    for co in course_outcomes:
        co_data = {
            'Code': co.code,
            'Description': co.description,
        }
        
        # Add program outcome relations and weights
        if has_relative_weight:
            # Get all program outcomes
            for po in program_outcomes:
                # Check if this CO is related to this PO
                is_related = po in co.program_outcomes
                co_data[f'PO: {po.code}'] = 'Yes' if is_related else 'No'
                
                # Get weight if related
                weight = co_po_weights.get(co.id, {}).get(po.id, 1.0) if is_related else '-'
                co_data[f'Weight: {po.code}'] = weight
        else:
            # Simple list of related POs without weights
            po_codes = [po.code for po in co.program_outcomes]
            co_data['Related Program Outcomes'] = ', '.join(po_codes) if po_codes else 'None'
        
        # Get related questions
        question_count = len(co.questions)
        co_data['Related Questions'] = question_count
        
        data.append(co_data)
    
    # Export data using utility function
    return export_to_excel_csv(data, f"outcomes_{course.code}", headers)

@outcome_bp.route('/program/export')
def export_program_outcomes():
    """Export program outcomes to CSV"""
    program_outcomes = ProgramOutcome.query.order_by(ProgramOutcome.code).all()
    
    # Prepare data for export
    data = []
    headers = ['Code', 'Description']
    
    for po in program_outcomes:
        po_data = {
            'Code': po.code,
            'Description': po.description
        }
        
        data.append(po_data)
    
    # Export data using utility function
    return export_to_excel_csv(data, "program_outcomes", headers)

@outcome_bp.route('/course/<int:course_id>/import_outcomes', methods=['GET', 'POST'])
def import_outcomes_from_course(course_id):
    """Import course outcomes from another course"""
    target_course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        source_course_id = request.form.get('source_course_id')
        
        if not source_course_id:
            flash('Please select a source course', 'error')
            return redirect(url_for('outcome.import_outcomes_from_course', course_id=course_id))
        
        try:
            source_course = Course.query.get(source_course_id)
            if not source_course:
                flash(f'Source course not found', 'error')
                return redirect(url_for('outcome.import_outcomes_from_course', course_id=course_id))
            
            # Get course outcomes from source course
            source_outcomes = CourseOutcome.query.filter_by(course_id=source_course.id).all()
            if not source_outcomes:
                flash(f'No course outcomes found in source course', 'warning')
                return redirect(url_for('outcome.import_outcomes_from_course', course_id=course_id))
            
            outcomes_imported = 0
            outcomes_skipped = 0
            
            # Check if we can handle weights
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('course_outcome_program_outcome')]
            has_relative_weight = 'relative_weight' in columns
            
            # Import each outcome
            for source_outcome in source_outcomes:
                # Check if outcome already exists in target course
                existing = CourseOutcome.query.filter_by(
                    code=source_outcome.code, 
                    course_id=target_course.id
                ).first()
                
                if existing:
                    outcomes_skipped += 1
                    continue
                
                # Create new outcome in target course
                new_outcome = CourseOutcome(
                    code=source_outcome.code,
                    description=source_outcome.description,
                    course_id=target_course.id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                db.session.add(new_outcome)
                db.session.flush()  # Ensure the new outcome has an ID
                
                # Get program outcomes and weights from source outcome
                if has_relative_weight:
                    # Get weights from the association table
                    result = db.session.execute(text(
                        "SELECT program_outcome_id, relative_weight FROM course_outcome_program_outcome "
                        "WHERE course_outcome_id = :co_id"
                    ), {"co_id": source_outcome.id})
                    
                    for row in result:
                        program_outcome_id = row[0]
                        relative_weight = row[1]
                        
                        # Get the program outcome
                        program_outcome = ProgramOutcome.query.get(program_outcome_id)
                        if program_outcome:
                            # Add the program outcome to the new course outcome
                            new_outcome.program_outcomes.append(program_outcome)
                            db.session.flush()
                            
                            # Set the weight
                            db.session.execute(text(
                                "UPDATE course_outcome_program_outcome SET relative_weight = :weight "
                                "WHERE course_outcome_id = :co_id AND program_outcome_id = :po_id"
                            ), {
                                "weight": relative_weight,
                                "co_id": new_outcome.id,
                                "po_id": program_outcome.id
                            })
                else:
                    # Just copy the program outcomes without weights
                    for program_outcome in source_outcome.program_outcomes:
                        new_outcome.program_outcomes.append(program_outcome)
                
                outcomes_imported += 1
            
            # Log action
            log = Log(action="IMPORT_COURSE_OUTCOMES", 
                     description=f"Imported {outcomes_imported} course outcomes from {source_course.code} to {target_course.code}")
            db.session.add(log)
            
            db.session.commit()
            
            if outcomes_imported > 0:
                flash(f'Successfully imported {outcomes_imported} course outcomes from {source_course.code}', 'success')
            if outcomes_skipped > 0:
                flash(f'Skipped {outcomes_skipped} outcomes that already existed in the target course', 'info')
                
            return redirect(url_for('course.course_detail', course_id=course_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error importing course outcomes: {str(e)}")
            flash(f'An error occurred while importing course outcomes: {str(e)}', 'error')
            return redirect(url_for('outcome.import_outcomes_from_course', course_id=course_id))
    
    # GET request
    # Get all courses except the target course
    courses = Course.query.filter(Course.id != course_id).all()
    return render_template('outcome/import_outcomes.html', 
                         target_course=target_course,
                         courses=courses,
                         active_page='courses')

@outcome_bp.route('/update_weights', methods=['POST'])
def update_outcome_weights():
    """AJAX endpoint to update CO-PO weights"""
    try:
        data = request.get_json()
        logging.debug(f"Received weight update request: {data}")
        
        if not data:
            logging.warning("No data provided in weight update request")
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        course_outcome_id = data.get('course_outcome_id')
        program_outcome_id = data.get('program_outcome_id')
        weight = data.get('weight')
        
        if not course_outcome_id or not program_outcome_id or weight is None:
            logging.warning(f"Missing required data. CO: {course_outcome_id}, PO: {program_outcome_id}, Weight: {weight}")
            return jsonify({'success': False, 'message': 'Missing required data'}), 400
        
        # Validate weight
        try:
            weight_value = float(weight)
            # Ensure weight is within valid range (0.00 to 9.99)
            weight_value = max(0.00, min(9.99, weight_value))
        except ValueError:
            logging.warning(f"Invalid weight value: {weight}")
            return jsonify({'success': False, 'message': 'Invalid weight value'}), 400
        
        # Check if we can update the weight (column exists)
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('course_outcome_program_outcome')]
        
        if 'relative_weight' in columns:
            # Check if the association exists first
            assoc_exists = db.session.execute(text(
                "SELECT 1 FROM course_outcome_program_outcome "
                "WHERE course_outcome_id = :co_id AND program_outcome_id = :po_id"
            ), {
                "co_id": course_outcome_id,
                "po_id": program_outcome_id
            }).fetchone()
            
            if not assoc_exists:
                logging.warning(f"Association does not exist between CO {course_outcome_id} and PO {program_outcome_id}")
                # Add the association first
                co = CourseOutcome.query.get(course_outcome_id)
                po = ProgramOutcome.query.get(program_outcome_id)
                
                if not co or not po:
                    return jsonify({'success': False, 'message': 'Course outcome or program outcome not found'}), 404
                
                # Add the association
                co.program_outcomes.append(po)
                db.session.flush()
                
                logging.debug(f"Created new association between CO {course_outcome_id} and PO {program_outcome_id}")
            
            # Update the weight in the association table
            result = db.session.execute(text(
                "UPDATE course_outcome_program_outcome SET relative_weight = :weight "
                "WHERE course_outcome_id = :co_id AND program_outcome_id = :po_id"
            ), {
                "weight": weight_value,
                "co_id": course_outcome_id,
                "po_id": program_outcome_id
            })
            
            rows_affected = result.rowcount
            logging.debug(f"Weight update affected {rows_affected} rows")
            
            if rows_affected == 0:
                logging.warning(f"Weight update didn't affect any rows. CO: {course_outcome_id}, PO: {program_outcome_id}")
                return jsonify({'success': False, 'message': 'No association found to update'}), 404
            
            # Log the update
            co = CourseOutcome.query.get(course_outcome_id)
            po = ProgramOutcome.query.get(program_outcome_id)
            
            log_message = f"Updated weight for {co.code if co else 'unknown CO'} -> {po.code if po else 'unknown PO'} to {weight_value}"
            log = Log(action="UPDATE_CO_PO_WEIGHT", description=log_message)
            db.session.add(log)
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Weight updated successfully', 'new_weight': weight_value})
        else:
            logging.warning("Database schema does not support weights (relative_weight column not found)")
            return jsonify({'success': False, 'message': 'Database schema does not support weights'}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating CO-PO weight: {str(e)}")
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500 