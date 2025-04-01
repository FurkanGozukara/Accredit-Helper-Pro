from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from models import Course, Exam, Question, CourseOutcome, ExamWeight, Log
from datetime import datetime
import logging

exam_bp = Blueprint('exam', __name__, url_prefix='/exam')

@exam_bp.route('/course/<int:course_id>/add', methods=['GET', 'POST'])
def add_exam(course_id):
    """Add a new exam to a course"""
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        max_score = request.form.get('max_score')
        exam_date_str = request.form.get('exam_date')
        is_makeup = True if request.form.get('is_makeup') else False
        makeup_for = request.form.get('makeup_for')
        
        # Basic validation
        if not name or not max_score:
            flash('Name and maximum score are required', 'error')
            return render_template('exam/form.html', 
                                 course=course, 
                                 active_page='courses')
        
        try:
            max_score = float(max_score)
            if max_score <= 0:
                raise ValueError("Score must be positive")
                
            # Handle exam date if provided
            exam_date = None
            if exam_date_str:
                try:
                    exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Invalid date format. Please use YYYY-MM-DD', 'error')
                    return render_template('exam/form.html', 
                                         course=course, 
                                         active_page='courses')
            
            # Create new exam
            new_exam = Exam(
                name=name,
                max_score=max_score,
                exam_date=exam_date,
                course_id=course_id,
                is_makeup=is_makeup
            )
            
            # Set makeup exam relationship if applicable
            if is_makeup and makeup_for:
                new_exam.makeup_for = int(makeup_for)
            
            db.session.add(new_exam)
            
            # Create default weight
            # If it's a makeup exam, it should inherit the weight from the original exam
            weight_value = 0
            if is_makeup and makeup_for:
                original_exam_weight = ExamWeight.query.filter_by(exam_id=int(makeup_for)).first()
                if original_exam_weight:
                    weight_value = original_exam_weight.weight
            
            # Add the exam weight record
            db.session.flush()  # Assign IDs without committing
            
            exam_weight = ExamWeight(
                exam_id=new_exam.id,
                course_id=course_id,
                weight=weight_value
            )
            
            # Log action
            log = Log(action="ADD_EXAM", description=f"Added exam: {name} to course: {course.code}")
            db.session.add(log)
            db.session.add(exam_weight)
            
            db.session.commit()
            flash(f'Exam {name} added successfully', 'success')
            return redirect(url_for('course.course_detail', course_id=course_id))
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
            return render_template('exam/form.html', 
                                 course=course, 
                                 active_page='courses')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding exam: {str(e)}")
            flash('An error occurred while adding the exam', 'error')
            return render_template('exam/form.html', 
                                 course=course, 
                                 active_page='courses')
    
    # For GET request, prepare data for the form
    other_exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()
    
    return render_template('exam/form.html', 
                         course=course, 
                         other_exams=other_exams,
                         active_page='courses')

@exam_bp.route('/edit/<int:exam_id>', methods=['GET', 'POST'])
def edit_exam(exam_id):
    """Edit an existing exam"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        max_score = request.form.get('max_score')
        exam_date_str = request.form.get('exam_date')
        is_makeup = True if request.form.get('is_makeup') else False
        makeup_for = request.form.get('makeup_for')
        
        # Basic validation
        if not name or not max_score:
            flash('Name and maximum score are required', 'error')
            return render_template('exam/form.html', 
                                 course=course, 
                                 exam=exam,
                                 active_page='courses')
        
        try:
            max_score = float(max_score)
            if max_score <= 0:
                raise ValueError("Score must be positive")
                
            # Handle exam date if provided
            exam_date = None
            if exam_date_str:
                try:
                    exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Invalid date format. Please use YYYY-MM-DD', 'error')
                    return render_template('exam/form.html', 
                                         course=course, 
                                         exam=exam,
                                         active_page='courses')
            
            # Update exam
            exam.name = name
            exam.max_score = max_score
            exam.exam_date = exam_date
            exam.is_makeup = is_makeup
            exam.updated_at = datetime.now()
            
            # Update makeup relationship
            if is_makeup and makeup_for:
                exam.makeup_for = int(makeup_for)
            elif not is_makeup:
                exam.makeup_for = None
            
            # Log action
            log = Log(action="EDIT_EXAM", description=f"Edited exam: {name} in course: {course.code}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Exam {name} updated successfully', 'success')
            return redirect(url_for('exam.exam_detail', exam_id=exam_id))
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
            return render_template('exam/form.html', 
                                 course=course, 
                                 exam=exam,
                                 active_page='courses')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating exam: {str(e)}")
            flash('An error occurred while updating the exam', 'error')
            return render_template('exam/form.html', 
                                 course=course, 
                                 exam=exam,
                                 active_page='courses')
    
    # For GET request, prepare data for the form
    other_exams = Exam.query.filter_by(course_id=exam.course_id, is_makeup=False).filter(Exam.id != exam_id).all()
    
    return render_template('exam/form.html', 
                         course=course, 
                         exam=exam,
                         other_exams=other_exams,
                         active_page='courses')

@exam_bp.route('/delete/<int:exam_id>', methods=['POST'])
def delete_exam(exam_id):
    """Delete an exam after confirmation"""
    exam = Exam.query.get_or_404(exam_id)
    course_id = exam.course_id
    
    try:
        # Log action before deletion
        log = Log(action="DELETE_EXAM", description=f"Deleted exam: {exam.name} from course: {exam.course.code}")
        db.session.add(log)
        
        db.session.delete(exam)
        db.session.commit()
        flash(f'Exam {exam.name} deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting exam: {str(e)}")
        flash('An error occurred while deleting the exam', 'error')
    
    return redirect(url_for('course.course_detail', course_id=course_id))

@exam_bp.route('/<int:exam_id>')
def exam_detail(exam_id):
    """Show exam details including questions"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.number).all()
    course_outcomes = CourseOutcome.query.filter_by(course_id=course.id).all()
    
    # Get exam weight
    exam_weight = ExamWeight.query.filter_by(exam_id=exam_id).first()
    
    return render_template('exam/detail.html', 
                         exam=exam, 
                         course=course,
                         questions=questions,
                         course_outcomes=course_outcomes,
                         exam_weight=exam_weight,
                         active_page='courses')

@exam_bp.route('/course/<int:course_id>/weights', methods=['GET', 'POST'])
def manage_weights(course_id):
    """Manage the weights of exams in a course"""
    course = Course.query.get_or_404(course_id)
    
    # Get regular exams (not makeup exams)
    exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()
    
    # If there are no exams, redirect back to course with a message
    if not exams:
        flash('You need to add exams before setting weights', 'warning')
        return redirect(url_for('course.course_detail', course_id=course_id))
    
    # Get weights for all exams
    weights = []
    for exam in exams:
        # Check if a weight already exists
        weight = ExamWeight.query.filter_by(exam_id=exam.id, course_id=course_id).first()
        
        if not weight:
            # Create a default weight
            weight = ExamWeight(
                exam_id=exam.id,
                course_id=course_id,
                weight=0
            )
            db.session.add(weight)
            db.session.commit()
        
        weights.append(weight)
        
        # Also handle makeup exams - they should have same weight as original
        if exam.makeup_exam:
            makeup_weight = ExamWeight.query.filter_by(exam_id=exam.makeup_exam.id, course_id=course_id).first()
            
            if not makeup_weight:
                makeup_weight = ExamWeight(
                    exam_id=exam.makeup_exam.id,
                    course_id=course_id,
                    weight=weight.weight  # Same as original
                )
                db.session.add(makeup_weight)
                db.session.commit()
            
            weights.append(makeup_weight)
    
    if request.method == 'POST':
        try:
            total_weight = 0
            
            # Update weights from form
            for weight in weights:
                weight_value = request.form.get(f'weight_{weight.id}', 0)
                
                try:
                    weight_value = float(weight_value) / 100  # Convert percentage to decimal
                    
                    # Skip makeup exams - their weights are set automatically
                    if Exam.query.get(weight.exam_id).is_makeup:
                        continue
                    
                    # Validate weight
                    if weight_value < 0:
                        weight_value = 0
                    elif weight_value > 1:
                        weight_value = 1
                    
                    weight.weight = weight_value
                    total_weight += weight_value
                    
                    # Update makeup exam weight if exists
                    exam = Exam.query.get(weight.exam_id)
                    if exam.makeup_exam:
                        makeup_weight = ExamWeight.query.filter_by(exam_id=exam.makeup_exam.id, course_id=course_id).first()
                        if makeup_weight:
                            makeup_weight.weight = weight_value
                    
                except ValueError:
                    weight.weight = 0
            
            # Validate total is close to 100%
            if abs(total_weight - 1.0) > 0.01:
                flash(f'Total weight ({total_weight*100:.1f}%) is not 100%. Please adjust the weights.', 'error')
                return render_template('exam/weights.html', 
                                     course=course,
                                     weights=weights,
                                     active_page='courses')
            
            # Log action
            log = Log(action="UPDATE_EXAM_WEIGHTS", 
                     description=f"Updated exam weights for course: {course.code}")
            db.session.add(log)
            
            db.session.commit()
            flash('Exam weights updated successfully', 'success')
            return redirect(url_for('course.course_detail', course_id=course_id))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating exam weights: {str(e)}")
            flash('An error occurred while updating exam weights', 'error')
    
    return render_template('exam/weights.html', 
                         course=course,
                         weights=weights,
                         active_page='courses') 