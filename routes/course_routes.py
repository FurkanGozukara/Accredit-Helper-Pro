from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from models import Course, Exam, CourseOutcome, Student, Log
from datetime import datetime
import logging

course_bp = Blueprint('course', __name__, url_prefix='/course')

@course_bp.route('/')
def list_courses():
    """List all courses"""
    courses = Course.query.all()
    return render_template('course/list.html', courses=courses, active_page='courses')

@course_bp.route('/add', methods=['GET', 'POST'])
def add_course():
    """Add a new course"""
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        semester = request.form.get('semester')
        
        # Basic validation
        if not code or not name or not semester:
            flash('All fields are required', 'error')
            return render_template('course/form.html', active_page='courses')
        
        # Check if a course with the same code and semester already exists
        existing_course = Course.query.filter_by(code=code, semester=semester).first()
        if existing_course:
            flash(f'A course with code {code} in semester {semester} already exists', 'error')
            return render_template('course/form.html', 
                                  course={'code': code, 'name': name, 'semester': semester},
                                  active_page='courses')
        
        # Create new course
        new_course = Course(code=code, name=name, semester=semester)
        db.session.add(new_course)
        
        # Log action
        log = Log(action="ADD_COURSE", description=f"Added course: {code} - {name}")
        db.session.add(log)
        
        try:
            db.session.commit()
            flash(f'Course {code} - {name} added successfully', 'success')
            return redirect(url_for('course.list_courses'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding course: {str(e)}")
            flash('An error occurred while adding the course', 'error')
            return render_template('course/form.html', 
                                 course={'code': code, 'name': name, 'semester': semester},
                                 active_page='courses')
    
    # GET request
    return render_template('course/form.html', active_page='courses')

@course_bp.route('/edit/<int:course_id>', methods=['GET', 'POST'])
def edit_course(course_id):
    """Edit an existing course"""
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        semester = request.form.get('semester')
        
        # Basic validation
        if not code or not name or not semester:
            flash('All fields are required', 'error')
            return render_template('course/form.html', course=course, active_page='courses')
        
        # Check if update would create a duplicate
        existing_course = Course.query.filter_by(code=code, semester=semester).first()
        if existing_course and existing_course.id != course_id:
            flash(f'A course with code {code} in semester {semester} already exists', 'error')
            return render_template('course/form.html', course=course, active_page='courses')
        
        # Update course
        course.code = code
        course.name = name
        course.semester = semester
        course.updated_at = datetime.now()
        
        # Log action
        log = Log(action="EDIT_COURSE", description=f"Edited course: {code} - {name}")
        db.session.add(log)
        
        try:
            db.session.commit()
            flash(f'Course {code} - {name} updated successfully', 'success')
            return redirect(url_for('course.list_courses'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating course: {str(e)}")
            flash('An error occurred while updating the course', 'error')
            return render_template('course/form.html', course=course, active_page='courses')
    
    # GET request
    return render_template('course/form.html', course=course, active_page='courses')

@course_bp.route('/delete/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    """Delete a course after confirmation"""
    course = Course.query.get_or_404(course_id)
    
    try:
        # Log action before deletion
        log = Log(action="DELETE_COURSE", description=f"Deleted course: {course.code} - {course.name}")
        db.session.add(log)
        
        db.session.delete(course)
        db.session.commit()
        flash(f'Course {course.code} - {course.name} deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting course: {str(e)}")
        flash('An error occurred while deleting the course', 'error')
    
    return redirect(url_for('course.list_courses'))

@course_bp.route('/detail/<int:course_id>')
def course_detail(course_id):
    """Show course details including exams and outcomes"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id).all()
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    
    return render_template('course/detail.html', 
                         course=course, 
                         exams=exams, 
                         course_outcomes=course_outcomes,
                         active_page='courses')

@course_bp.route('/search')
def search_courses():
    """Search courses by code or name"""
    search_term = request.args.get('term', '')
    
    if search_term:
        courses = Course.query.filter(
            (Course.code.ilike(f'%{search_term}%')) | 
            (Course.name.ilike(f'%{search_term}%'))
        ).all()
    else:
        courses = Course.query.all()
    
    return render_template('course/list.html', courses=courses, search_term=search_term, active_page='courses') 