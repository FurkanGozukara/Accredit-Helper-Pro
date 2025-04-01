from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from models import CourseOutcome, ProgramOutcome, Course, Log
from datetime import datetime
import logging

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
        flash('An error occurred while deleting the course outcome', 'error')
    
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