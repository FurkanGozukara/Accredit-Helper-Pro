from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from models import Question, Exam, Course, CourseOutcome, Log, Score
from datetime import datetime
import logging
import io
import csv
from routes.utility_routes import export_to_excel_csv
from decimal import Decimal, InvalidOperation
from sqlalchemy import text, inspect

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
        text_content = request.form.get('text')
        max_score = request.form.get('max_score')
        
        # Get selected course outcomes
        selected_outcomes = request.form.getlist('course_outcomes')
        
        # Get next question number for form
        next_question_number = 1
        last_question = Question.query.filter_by(exam_id=exam_id).order_by(Question.number.desc()).first()
        if last_question:
            next_question_number = last_question.number + 1
        
        # Store form data for possible re-rendering
        form_data = {
            'text': text_content,
            'max_score': max_score,
            'selected_outcomes': selected_outcomes
        }
        
        # Basic validation
        if not max_score:
            flash('Maximum score is required', 'error')
            return render_template('question/form.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 next_number=next_question_number,
                                 active_page='courses')
        
        if not selected_outcomes:
            flash('At least one course outcome must be selected', 'error')
            return render_template('question/form.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 next_number=next_question_number,
                                 active_page='courses')
        
        try:
            max_score = Decimal(max_score)
            if max_score <= 0:
                raise ValueError("Score must be positive")
            
            # Create new question
            new_question = Question(
                text=text_content,
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
            
            # --- START: Process Weights ---
            has_relative_weight = False
            try:
                inspector = inspect(db.engine)
                qco_columns = [c['name'] for c in inspector.get_columns('question_course_outcome')]
                has_relative_weight = 'relative_weight' in qco_columns
            except Exception as e:
                logging.warning(f"Could not check for relative_weight column: {e}")

            if has_relative_weight:
                for outcome_id_str in selected_outcomes:
                    try:
                        outcome_id = int(outcome_id_str)
                        weight_str = request.form.get(f'weight_{outcome_id}', '1.0')
                        
                        # Fix: Ensure weight_str is a string before converting to Decimal
                        if weight_str is not None:
                            weight_value = Decimal(str(weight_str))
                            weight_value = max(Decimal('0.01'), min(Decimal('9.99'), weight_value)).quantize(Decimal('0.01'))
                            
                            # Fix: Convert Decimal to float for SQLite compatibility
                            weight_float = float(weight_value)
                            
                            # Fix: Use proper SQL syntax with parameters
                            sql_query = "UPDATE question_course_outcome SET relative_weight = :weight WHERE question_id = :qid AND course_outcome_id = :coid"
                            params = {"weight": weight_float, "qid": new_question.id, "coid": outcome_id}
                            db.session.execute(text(sql_query), params)
                    except (ValueError, InvalidOperation) as ve:
                        flash(f'Invalid weight provided for outcome ID {outcome_id}, using default 1.0: {ve}', 'warning')
                    except Exception as e:
                        flash(f'Error setting weight for outcome ID {outcome_id}: {str(e)}', 'error')
                
                db.session.commit()
            # --- END: Process Weights ---
                
            flash(f'Question {next_question_number} added successfully', 'success')
            return redirect(url_for('exam.exam_detail', exam_id=exam_id))
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
            return render_template('question/form.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 next_number=next_question_number,
                                 active_page='courses')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding question: {str(e)}")
            flash('An error occurred while adding the question', 'error')
            return render_template('question/form.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 next_number=next_question_number,
                                 active_page='courses')
    
    # GET request - calculate next question number
    next_question_number = 1
    last_question = Question.query.filter_by(exam_id=exam_id).order_by(Question.number.desc()).first()
    if last_question:
        next_question_number = last_question.number + 1
        
    return render_template('question/form.html', 
                         exam=exam, 
                         course=course,
                         course_outcomes=course_outcomes,
                         next_number=next_question_number,
                         active_page='courses')

@question_bp.route('/edit/<int:question_id>', methods=['GET', 'POST'])
def edit_question(question_id):
    """Edit an existing question"""
    question = Question.query.get_or_404(question_id)
    exam = Exam.query.get_or_404(question.exam_id)
    course = Course.query.get_or_404(exam.course_id)
    course_outcomes = CourseOutcome.query.filter_by(course_id=course.id).all()
    
    # GET request - Fetch existing weights
    question_weights = {}
    try:
        inspector = inspect(db.engine)
        qco_columns = [c['name'] for c in inspector.get_columns('question_course_outcome')]
        has_relative_weight = 'relative_weight' in qco_columns
        
        if has_relative_weight:
            # Using explicit SQL query with proper parameters
            sql_query = "SELECT course_outcome_id, relative_weight FROM question_course_outcome WHERE question_id = :qid"
            params = {"qid": question.id}
            result = db.session.execute(text(sql_query), params)
            
            for row in result:
                question_weights[row[0]] = float(row[1]) if row[1] is not None else 1.0
    except Exception as e:
        logging.warning(f"Could not retrieve question weights for Q:{question.id}: {str(e)}")
    
    if request.method == 'POST':
        text_content = request.form.get('text')
        max_score = request.form.get('max_score')
        
        # Get selected course outcomes
        selected_outcomes = request.form.getlist('course_outcomes')
        
        # Store form data for possible re-rendering
        form_data = {
            'text': text_content,
            'max_score': max_score,
            'selected_outcomes': selected_outcomes
        }
        
        # Basic validation
        if not max_score:
            flash('Maximum score is required', 'error')
            return render_template('question/form.html', 
                                 question=question,
                                 question_id=question_id,
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 active_page='courses')
        
        if not selected_outcomes:
            flash('At least one course outcome must be selected', 'error')
            return render_template('question/form.html', 
                                 question=question,
                                 question_id=question_id,
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 active_page='courses')
        
        try:
            max_score = Decimal(max_score)
            if max_score <= 0:
                raise ValueError("Score must be positive")
            
            # Update question
            question.text = text_content
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
            
            # --- START: Process Weights ---
            has_relative_weight = False
            try:
                inspector = inspect(db.engine)
                qco_columns = [c['name'] for c in inspector.get_columns('question_course_outcome')]
                has_relative_weight = 'relative_weight' in qco_columns
            except Exception as e:
                logging.warning(f"Could not check for relative_weight column: {e}")

            if has_relative_weight:
                # Update weights for the currently associated outcomes
                for outcome_id_str in selected_outcomes:
                    try:
                        outcome_id = int(outcome_id_str)
                        weight_str = request.form.get(f'weight_{outcome_id}', '1.0')
                        
                        # Fix: Ensure weight_str is a string before converting to Decimal
                        if weight_str is not None:
                            weight_value = Decimal(str(weight_str))
                            weight_value = max(Decimal('0.01'), min(Decimal('9.99'), weight_value)).quantize(Decimal('0.01'))

                            # Fix: Convert Decimal to float for SQLite compatibility
                            weight_float = float(weight_value)
                            
                            # Fix: Use proper SQL syntax with parameters
                            sql_query = "UPDATE question_course_outcome SET relative_weight = :weight WHERE question_id = :qid AND course_outcome_id = :coid"
                            params = {"weight": weight_float, "qid": question.id, "coid": outcome_id}
                            db.session.execute(text(sql_query), params)
                    except (ValueError, InvalidOperation) as ve:
                        flash(f'Invalid weight provided for outcome ID {outcome_id}, using default 1.0: {ve}', 'warning')
                    except Exception as e:
                        flash(f'Error setting weight for outcome ID {outcome_id}: {str(e)}', 'error')
                
                db.session.commit()
            # --- END: Process Weights ---
            
            flash(f'Question {question.number} updated successfully', 'success')
            
            # Stay on the same page after update
            # Fetch updated weights for the next render
            updated_question_weights = {}
            try:
                if has_relative_weight:
                    # Fix: Use proper SQL syntax with parameters
                    sql_query = "SELECT course_outcome_id, relative_weight FROM question_course_outcome WHERE question_id = :qid"
                    params = {"qid": question.id}
                    result = db.session.execute(text(sql_query), params)
                    
                    for row in result:
                        updated_question_weights[row[0]] = float(row[1]) if row[1] is not None else 1.0
            except Exception as e:
                logging.warning(f"Could not retrieve updated question weights for Q:{question.id}: {str(e)}")
                
            return render_template('question/form.html', 
                                 question=question,
                                 question_id=question_id,
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 question_weights=updated_question_weights,
                                 active_page='courses')
                                 
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'error')
            return render_template('question/form.html', 
                                 question=question,
                                 question_id=question_id,
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 active_page='courses')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating question: {str(e)}")
            flash('An error occurred while updating the question', 'error')
            return render_template('question/form.html', 
                                 question=question,
                                 question_id=question_id,
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 active_page='courses')
    
    return render_template('question/form.html', 
                         question=question,
                         question_id=question_id,
                         exam=exam, 
                         course=course,
                         course_outcomes=course_outcomes,
                         question_weights=question_weights,
                         active_page='courses')

@question_bp.route('/delete/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    """Delete a question after confirmation
    
    IMPORTANT: When a question is deleted, the question numbers of all subsequent
    questions are decremented. However, the question IDs remain the same.
    
    This means that Score records will still refer to the correct Question objects via
    their IDs, but the question.number field will have changed. Applications using
    these records should be aware of this behavior.
    
    For example, if Q1, Q2, Q3, Q4, Q5 exist and Q2 is deleted:
    - Q1 remains Q1 (same ID, same number)
    - Q2 is deleted (ID and number gone)
    - Q3 becomes the new Q2 (same ID, number changed from 3 to 2)
    - Q4 becomes the new Q3 (same ID, number changed from 4 to 3)
    - Q5 becomes the new Q4 (same ID, number changed from 5 to 4)
    
    All Score records for the original Q3, Q4, Q5 will point to the same Question objects,
    but those Question objects now have different numbers.
    """
    question = Question.query.get_or_404(question_id)
    exam_id = question.exam_id
    question_number = question.number
    
    try:
        # Log action before deletion with detailed warning
        log = Log(action="DELETE_QUESTION", 
                 description=f"Deleted question {question_number} from exam: {question.exam.name}. WARNING: This will renumber subsequent questions while keeping the same IDs.")
        db.session.add(log)
        
        # Get all questions that will be renumbered
        remaining_questions = Question.query.filter_by(exam_id=exam_id).filter(Question.number > question_number).all()
        
        # Log which questions will be renumbered
        renumbering_log = ""
        for q in remaining_questions:
            renumbering_log += f"Question ID {q.id} will change from number {q.number} to {q.number-1}. "
        
        if renumbering_log:
            renumber_log = Log(action="RENUMBER_QUESTIONS", 
                              description=renumbering_log)
            db.session.add(renumber_log)
        
        # Delete the question (this will cascade delete its scores)
        db.session.delete(question)
        
        # Reorder remaining questions in the exam
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
        equal_score = Decimal(exam.max_score) / len(questions)
        
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
        
        # Create form_data dictionary to store submitted values
        form_data = {
            'num_questions': num_questions,
            'questions': []
        }
        
        # Gather all posted form data
        for i in range(num_questions):
            question_data = {
                'text': request.form.get(f'text_{i}', ''),
                'max_score': request.form.get(f'max_score_{i}', 0),
                'selected_outcomes': request.form.getlist(f'course_outcomes_{i}')
            }
            form_data['questions'].append(question_data)
        
        if num_questions <= 0:
            flash('Please specify a valid number of questions to add', 'error')
            return render_template('question/batch_add.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 num_questions=max(1, num_questions),
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
                    max_score = Decimal(max_score)
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
                    
                    # --- START: Process Weights ---
                    from sqlalchemy import text # Ensure text is imported

                    # Check if relative_weight column exists
                    has_relative_weight = False
                    try:
                        inspector = inspect(db.engine)
                        qco_columns = [c['name'] for c in inspector.get_columns('question_course_outcome')]
                        has_relative_weight = 'relative_weight' in qco_columns
                    except Exception: pass

                    if has_relative_weight:
                        # Associate with course outcomes and set weights
                        for outcome_id_str in selected_outcomes:
                            outcome_id = int(outcome_id_str)
                            outcome = CourseOutcome.query.get(outcome_id)
                            if outcome:
                                new_question.course_outcomes.append(outcome)
                                db.session.flush() # Flush to ensure association is made

                                # Get weight from form
                                weight_str = request.form.get(f'weight_{i}_{outcome_id}', '1.0')
                                try:
                                    weight_value = Decimal(weight_str)
                                    weight_value = max(Decimal('0.01'), min(Decimal('9.99'), weight_value)).quantize(Decimal('0.01'))

                                    # Fix: Convert Decimal to float for SQLite compatibility
                                    weight_float = float(weight_value)
                                    
                                    # Fix: Use proper SQL syntax with parameters
                                    sql_query = "UPDATE question_course_outcome SET relative_weight = :weight WHERE question_id = :qid AND course_outcome_id = :coid"
                                    params = {"weight": weight_float, "qid": new_question.id, "coid": outcome_id}
                                    db.session.execute(text(sql_query), params)
                                except (ValueError, InvalidOperation):
                                     flash(f'Invalid weight for Q{i+1}-CO{outcome_id}, using 1.0', 'warning')
                                except Exception as e:
                                     flash(f'Error setting weight for Q{i+1}-CO{outcome_id}: {e}', 'error')
                    else:
                         # Fallback for older DBs: Just associate without weight
                         for outcome_id_str in selected_outcomes:
                             outcome_id = int(outcome_id_str)
                             outcome = CourseOutcome.query.get(outcome_id)
                             if outcome:
                                 new_question.course_outcomes.append(outcome)
                    # --- END: Process Weights ---
                    
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
                return render_template('question/batch_add.html', 
                                     exam=exam, 
                                     course=course,
                                     course_outcomes=course_outcomes,
                                     form_data=form_data,
                                     num_questions=num_questions,
                                     active_page='courses')
                
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding batch questions: {str(e)}")
            flash('An error occurred while adding the questions', 'error')
            return render_template('question/batch_add.html', 
                                 exam=exam, 
                                 course=course,
                                 course_outcomes=course_outcomes,
                                 form_data=form_data,
                                 num_questions=num_questions,
                                 active_page='courses')
    
    # Get num_questions from URL parameter if provided (for GET requests)
    num_questions = request.args.get('num_questions')
    if num_questions and num_questions.isdigit():
        num_questions = int(num_questions)
        if num_questions <= 0 or num_questions > 100:
            num_questions = 40  # Default if invalid
    else:
        num_questions = 40  # Default number
    
    return render_template('question/batch_add.html', 
                         exam=exam, 
                         course=course,
                         course_outcomes=course_outcomes,
                         num_questions=num_questions,
                         active_page='courses')

@question_bp.route('/mass-associate/<int:course_id>', methods=['GET', 'POST'])
def mass_associate_outcomes(course_id):
    """Mass associate questions with course outcomes"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id).all()
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    
    # Check for exam_id in the URL query parameters for auto-filtering
    selected_exam_id = request.args.get('exam_id')
    
    if not course_outcomes:
        flash('You need to define course outcomes first', 'warning')
        return redirect(url_for('outcome.add_course_outcome', course_id=course_id))
    
    if not exams:
        flash('You need to create exams first', 'warning')
        return redirect(url_for('course.course_detail', course_id=course_id))
    
    # Check if relative_weight column exists
    has_relative_weight = False
    try:
        inspector = inspect(db.engine)
        qco_columns = [c['name'] for c in inspector.get_columns('question_course_outcome')]
        has_relative_weight = 'relative_weight' in qco_columns
    except Exception as e:
        logging.warning(f"Could not check for relative_weight column: {e}")
    
    # Get all question-outcome weights from database
    question_outcome_weights = {}
    if has_relative_weight:
        try:
            # Get all questions for this course to fetch their weights
            question_ids_query = db.session.query(Question.id).join(Exam).filter(Exam.course_id == course_id).all()
            question_ids = [q[0] for q in question_ids_query]
            
            if question_ids:
                # Fetch weights for all questions in one query
                placeholders = ', '.join(f':q{i}' for i in range(len(question_ids)))
                query = f"SELECT question_id, course_outcome_id, relative_weight FROM question_course_outcome WHERE question_id IN ({placeholders})"
                
                # Create params dictionary
                params = {f'q{i}': q_id for i, q_id in enumerate(question_ids)}
                
                weights_result = db.session.execute(text(query), params).fetchall()
                
                # Organize weights by question_id and outcome_id
                for q_id, co_id, weight in weights_result:
                    if q_id not in question_outcome_weights:
                        question_outcome_weights[q_id] = {}
                    question_outcome_weights[q_id][co_id] = float(weight) if weight is not None else 1.0
        except Exception as e:
            logging.warning(f"Could not fetch question-outcome weights: {e}")
    
    questions = []
    for exam in exams:
        exam_questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.number).all()
        for question in exam_questions:
            # Create a question dictionary with all required data
            question_dict = {
                'id': question.id,
                'exam_id': exam.id,
                'exam_name': exam.name,
                'number': question.number,
                'text': question.text,
                'max_score': question.max_score,
                'outcomes': [outcome.id for outcome in question.course_outcomes],
                'weights': question_outcome_weights.get(question.id, {})  # Add weights to each question
            }
            questions.append(question_dict)
    
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
                         selected_exam_id=selected_exam_id,
                         active_page='courses')

@question_bp.route('/mass-associate/<int:course_id>/export')
def export_mass_associate_outcomes(course_id):
    """Export all questions and their associated outcomes for a course"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id).all()
    
    # Prepare data for export
    data = []
    headers = ['Exam', 'Question Number', 'Question Text', 'Max Score', 'Associated Outcomes']
    
    for exam in exams:
        questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.number).all()
        for question in questions:
            # Get related course outcomes
            co_codes = [co.code for co in question.course_outcomes]
            co_text = ', '.join(co_codes) if co_codes else 'None'
            
            question_data = {
                'Exam': exam.name,
                'Question Number': question.number,
                'Question Text': question.text or '',
                'Max Score': question.max_score,
                'Associated Outcomes': co_text
            }
            
            data.append(question_data)
    
    # Export data using utility function
    return export_to_excel_csv(data, f"questions_outcomes_{course.code}", headers)

@question_bp.route('/mass-associate/exam/<int:exam_id>', methods=['GET'])
def mass_associate_by_exam(exam_id):
    """Redirect to mass association page with auto-filtering for a specific exam"""
    exam = Exam.query.get_or_404(exam_id)
    return redirect(url_for('question.mass_associate_outcomes', course_id=exam.course_id, exam_id=exam_id))

@question_bp.route('/exam/<int:exam_id>/export')
def export_exam_questions(exam_id):
    """Export questions for a specific exam to CSV"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.number).all()
    
    # Prepare data for export
    data = []
    headers = ['Number', 'Text', 'Max Score', 'Related Course Outcomes']
    
    for question in questions:
        # Get related course outcomes
        co_codes = [co.code for co in question.course_outcomes]
        co_text = ', '.join(co_codes) if co_codes else 'None'
        
        question_data = {
            'Number': question.number,
            'Text': question.text or '',
            'Max Score': question.max_score,
            'Related Course Outcomes': co_text
        }
        
        data.append(question_data)
    
    # Export data using utility function
    return export_to_excel_csv(data, f"questions_{course.code}_{exam.name.replace(' ', '_')}", headers) 