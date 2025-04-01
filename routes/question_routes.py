from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from models import Question, Exam, Course, CourseOutcome, Log
from datetime import datetime
import logging

question_bp = Blueprint('question', __name__, url_prefix='/question')

@question_bp.route('/exam/<int:exam_id>/add', methods=['GET', 'POST'])
def add_question(exam_id):
    """Add a new question to an exam"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    course_outcomes = CourseOutcome.query.filter_by(course_id=course.id).all()
    
    # Check if there are any course outcomes defined
    if not course_outcomes:
        flash('You need to define course outcomes before adding questions', 'warning')
        return redirect(url_for('outcome.add_course_outcome', course_id=course.id))
    
    if request.method == 'POST':
        text = request.form.get('text')
        max_score = request.form.get('max_score')
        
        # Get selected course outcomes
        selected_outcomes = request.form.getlist('course_outcomes')
        
        # Basic validation
        if not max_score:
            flash('Maximum score is required', 'error')
            return render_template('question/form.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 active_page='courses')
        
        if not selected_outcomes:
            flash('At least one course outcome must be selected', 'error')
            return render_template('question/form.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 active_page='courses')
        
        try:
            max_score = float(max_score)
            if max_score <= 0:
                raise ValueError("Score must be positive")
            
            # Get next question number
            next_question_number = 1
            last_question = Question.query.filter_by(exam_id=exam_id).order_by(Question.number.desc()).first()
            if last_question:
                next_question_number = last_question.number + 1
            
            # Create new question
            new_question = Question(
                text=text,
                max_score=max_score,
                number=next_question_number,
                exam_id=exam_id
            )
            
            db.session.add(new_question)
            db.session.flush()  # Assign ID without committing
            
            # Associate with course outcomes
            for outcome_id in selected_outcomes:
                outcome = CourseOutcome.query.get(outcome_id)
                if outcome:
                    new_question.course_outcomes.append(outcome)
            
            # Log action
            log = Log(action="ADD_QUESTION", 
                     description=f"Added question {next_question_number} to exam: {exam.name}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Question {next_question_number} added successfully', 'success')
            return redirect(url_for('exam.exam_detail', exam_id=exam_id))
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
            return render_template('question/form.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 active_page='courses')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding question: {str(e)}")
            flash('An error occurred while adding the question', 'error')
            return render_template('question/form.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 active_page='courses')
    
    # GET request
    return render_template('question/form.html', 
                         exam=exam, 
                         course=course,
                         course_outcomes=course_outcomes,
                         active_page='courses')

@question_bp.route('/edit/<int:question_id>', methods=['GET', 'POST'])
def edit_question(question_id):
    """Edit an existing question"""
    question = Question.query.get_or_404(question_id)
    exam = Exam.query.get_or_404(question.exam_id)
    course = Course.query.get_or_404(exam.course_id)
    course_outcomes = CourseOutcome.query.filter_by(course_id=course.id).all()
    
    if request.method == 'POST':
        text = request.form.get('text')
        max_score = request.form.get('max_score')
        
        # Get selected course outcomes
        selected_outcomes = request.form.getlist('course_outcomes')
        
        # Basic validation
        if not max_score:
            flash('Maximum score is required', 'error')
            return render_template('question/form.html', 
                                 question=question,
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 active_page='courses')
        
        if not selected_outcomes:
            flash('At least one course outcome must be selected', 'error')
            return render_template('question/form.html', 
                                 question=question,
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 active_page='courses')
        
        try:
            max_score = float(max_score)
            if max_score <= 0:
                raise ValueError("Score must be positive")
            
            # Update question
            question.text = text
            question.max_score = max_score
            question.updated_at = datetime.now()
            
            # Clear and reassociate with course outcomes
            question.course_outcomes = []
            for outcome_id in selected_outcomes:
                outcome = CourseOutcome.query.get(outcome_id)
                if outcome:
                    question.course_outcomes.append(outcome)
            
            # Log action
            log = Log(action="EDIT_QUESTION", 
                     description=f"Edited question {question.number} in exam: {exam.name}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Question {question.number} updated successfully', 'success')
            return redirect(url_for('exam.exam_detail', exam_id=exam.id))
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
            return render_template('question/form.html', 
                                 question=question,
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 active_page='courses')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating question: {str(e)}")
            flash('An error occurred while updating the question', 'error')
            return render_template('question/form.html', 
                                 question=question,
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 active_page='courses')
    
    # GET request
    return render_template('question/form.html', 
                         question=question,
                         exam=exam, 
                         course=course,
                         course_outcomes=course_outcomes,
                         active_page='courses')

@question_bp.route('/delete/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    """Delete a question after confirmation"""
    question = Question.query.get_or_404(question_id)
    exam_id = question.exam_id
    question_number = question.number
    
    try:
        # Log action before deletion
        log = Log(action="DELETE_QUESTION", 
                 description=f"Deleted question {question_number} from exam: {question.exam.name}")
        db.session.add(log)
        
        db.session.delete(question)
        
        # Reorder remaining questions in the exam
        remaining_questions = Question.query.filter_by(exam_id=exam_id).filter(Question.number > question_number).all()
        for q in remaining_questions:
            q.number -= 1
        
        db.session.commit()
        flash(f'Question {question_number} deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting question: {str(e)}")
        flash('An error occurred while deleting the question', 'error')
    
    return redirect(url_for('exam.exam_detail', exam_id=exam_id))

@question_bp.route('/autoassign/<int:exam_id>', methods=['POST'])
def auto_assign_scores(exam_id):
    """Automatically assign equal max scores to all questions"""
    exam = Exam.query.get_or_404(exam_id)
    questions = Question.query.filter_by(exam_id=exam_id).all()
    
    if not questions:
        flash('No questions to assign scores to', 'warning')
        return redirect(url_for('exam.exam_detail', exam_id=exam_id))
    
    try:
        # Calculate equal score for each question
        equal_score = exam.max_score / len(questions)
        
        # Update all questions
        for question in questions:
            question.max_score = equal_score
        
        # Log action
        log = Log(action="AUTO_ASSIGN_SCORES", 
                 description=f"Auto-assigned equal scores ({equal_score}) to questions in exam: {exam.name}")
        db.session.add(log)
        
        db.session.commit()
        flash(f'Assigned {equal_score} points to each question', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error auto-assigning scores: {str(e)}")
        flash('An error occurred while assigning scores', 'error')
    
    return redirect(url_for('exam.exam_detail', exam_id=exam_id))

@question_bp.route('/exam/<int:exam_id>/batch-add', methods=['GET', 'POST'])
def batch_add_questions(exam_id):
    """Add multiple questions to an exam at once"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    course_outcomes = CourseOutcome.query.filter_by(course_id=course.id).all()
    
    # Check if there are any course outcomes defined
    if not course_outcomes:
        flash('You need to define course outcomes before adding questions', 'warning')
        return redirect(url_for('outcome.add_course_outcome', course_id=course.id))
    
    if request.method == 'POST':
        num_questions = int(request.form.get('num_questions', 0))
        
        if num_questions <= 0:
            flash('Please specify a valid number of questions to add', 'error')
            return render_template('question/batch_add.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 active_page='courses')
        
        # Get next question number
        next_question_number = 1
        last_question = Question.query.filter_by(exam_id=exam_id).order_by(Question.number.desc()).first()
        if last_question:
            next_question_number = last_question.number + 1
        
        try:
            questions_added = 0
            
            for i in range(num_questions):
                text = request.form.get(f'text_{i}', '')
                max_score = request.form.get(f'max_score_{i}', 0)
                selected_outcomes = request.form.getlist(f'course_outcomes_{i}')
                
                try:
                    max_score = float(max_score)
                    if max_score <= 0:
                        continue  # Skip invalid questions
                    
                    # Create new question
                    new_question = Question(
                        text=text,
                        max_score=max_score,
                        number=next_question_number + i,
                        exam_id=exam_id
                    )
                    
                    db.session.add(new_question)
                    db.session.flush()  # Assign ID without committing
                    
                    # Associate with course outcomes
                    for outcome_id in selected_outcomes:
                        outcome = CourseOutcome.query.get(outcome_id)
                        if outcome:
                            new_question.course_outcomes.append(outcome)
                    
                    questions_added += 1
                    
                except ValueError:
                    continue  # Skip invalid questions
            
            if questions_added > 0:
                # Log action
                log = Log(action="BATCH_ADD_QUESTIONS", 
                         description=f"Added {questions_added} questions to exam: {exam.name}")
                db.session.add(log)
                
                db.session.commit()
                flash(f'{questions_added} questions added successfully', 'success')
                return redirect(url_for('exam.exam_detail', exam_id=exam_id))
            else:
                flash('No valid questions were provided', 'warning')
                
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding batch questions: {str(e)}")
            flash('An error occurred while adding the questions', 'error')
    
    return render_template('question/batch_add.html', 
                         exam=exam, 
                         course=course,
                         course_outcomes=course_outcomes,
                         num_questions=40,  # Default number
                         active_page='courses')

@question_bp.route('/mass-associate/<int:course_id>', methods=['GET', 'POST'])
def mass_associate_outcomes(course_id):
    """Mass associate questions with course outcomes"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id).all()
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    
    if not course_outcomes:
        flash('You need to define course outcomes first', 'warning')
        return redirect(url_for('outcome.add_course_outcome', course_id=course_id))
    
    if not exams:
        flash('You need to create exams first', 'warning')
        return redirect(url_for('course.course_detail', course_id=course_id))
    
    questions = []
    for exam in exams:
        exam_questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.number).all()
        for question in exam_questions:
            questions.append({
                'id': question.id,
                'exam_id': exam.id,
                'exam_name': exam.name,
                'number': question.number,
                'text': question.text,
                'max_score': question.max_score,
                'outcomes': [outcome.id for outcome in question.course_outcomes]
            })
    
    if request.method == 'POST':
        try:
            updates = 0
            
            for question in questions:
                question_id = question['id']
                selected_outcomes = request.form.getlist(f'outcomes_{question_id}')
                
                db_question = Question.query.get(question_id)
                if db_question:
                    # Clear and reassociate with course outcomes
                    db_question.course_outcomes = []
                    for outcome_id in selected_outcomes:
                        outcome = CourseOutcome.query.get(outcome_id)
                        if outcome:
                            db_question.course_outcomes.append(outcome)
                    updates += 1
            
            # Log action
            log = Log(action="MASS_ASSOCIATE_OUTCOMES", 
                     description=f"Updated outcome associations for {updates} questions in course: {course.code}")
            db.session.add(log)
            
            db.session.commit()
            flash(f'Updated outcome associations for {updates} questions', 'success')
            return redirect(url_for('question.mass_associate_outcomes', course_id=course_id))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating outcome associations: {str(e)}")
            flash('An error occurred while updating outcome associations', 'error')
    
    return render_template('question/mass_associate.html', 
                         course=course,
                         questions=questions,
                         course_outcomes=course_outcomes,
                         exams=exams,
                         active_page='courses') 