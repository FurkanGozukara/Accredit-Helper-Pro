from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from models import CourseOutcome, ProgramOutcome, Course, Log
from datetime import datetime
import logging
import io
import csv
from routes.utility_routes import export_to_excel_csv

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
            
            # Associate with program outcomes
            for program_outcome_id in selected_program_outcomes:
                program_outcome = ProgramOutcome.query.get(program_outcome_id)
                if program_outcome:
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
    
    if request.method == 'POST':
        code = request.form.get('code')
        description = request.form.get('description')
        
        # Get selected program outcomes
        selected_program_outcomes = request.form.getlist('program_outcomes')
        
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
            
            # Clear and reassociate with program outcomes
            course_outcome.program_outcomes = []
            for program_outcome_id in selected_program_outcomes:
                program_outcome = ProgramOutcome.query.get(program_outcome_id)
                if program_outcome:
                    course_outcome.program_outcomes.append(program_outcome)
            
            # Log action
            log = Log(action="EDIT_COURSE_OUTCOME", 
                     description=f"Edited course outcome {code} in course: {course.code}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Course outcome {code} updated successfully', 'success')
            return redirect(url_for('course.course_detail', course_id=course.id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating course outcome: {str(e)}")
            flash('An error occurred while updating the course outcome', 'error')
            return render_template('outcome/course_outcome_form.html', 
                                 course=course,
                                 program_outcomes=program_outcomes,
                                 outcome=course_outcome,
                                 active_page='courses')
    
    # GET request
    return render_template('outcome/course_outcome_form.html', 
                         course=course,
                         program_outcomes=program_outcomes,
                         outcome=course_outcome,
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
    associated_count = program_outcome.course_outcomes.count()
    
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

@outcome_bp.route('/course/<int:course_id>/export')
def export_course_outcomes(course_id):
    """Export course outcomes to CSV"""
    course = Course.query.get_or_404(course_id)
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()
    
    # Prepare data for export
    data = []
    headers = ['Code', 'Description', 'Related Program Outcomes', 'Related Questions']
    
    for co in course_outcomes:
        # Get related program outcomes
        po_codes = [po.code for po in co.program_outcomes]
        po_text = ', '.join(po_codes) if po_codes else 'None'
        
        # Get related questions
        question_count = len(co.questions)
        
        co_data = {
            'Code': co.code,
            'Description': co.description,
            'Related Program Outcomes': po_text,
            'Related Questions': question_count
        }
        
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