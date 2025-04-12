from flask import Blueprint, jsonify, request
from models import Question, CourseOutcome, Log, Student, Exam, Score, Course, AchievementLevel, ExamWeight, StudentExamAttendance
from app import db
import logging
from decimal import Decimal
from routes.calculation_routes import get_achievement_level, calculate_student_exam_score_optimized, calculate_course_outcome_score_optimized
import re

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/course_outcome_program_outcome/get_weight', methods=['POST'])
def get_co_po_weight():
    """Get the relative weight for a Course Outcome - Program Outcome relationship"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        course_outcome_id = data.get('course_outcome_id')
        program_outcome_id = data.get('program_outcome_id')
        
        if not course_outcome_id or not program_outcome_id:
            return jsonify({'success': False, 'message': 'Missing required parameters'}), 400
            
        # Check if the column exists in the table
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('course_outcome_program_outcome')]
        
        if 'relative_weight' in columns:
            # Query the weight using SQLAlchemy text
            result = db.session.execute(text(
                "SELECT relative_weight FROM course_outcome_program_outcome "
                "WHERE course_outcome_id = :co_id AND program_outcome_id = :po_id"
            ), {
                "co_id": course_outcome_id,
                "po_id": program_outcome_id
            }).fetchone()
            
            if result:
                weight = float(result[0]) if result[0] is not None else 1.0
                return jsonify({'success': True, 'weight': weight})
            else:
                return jsonify({'success': True, 'weight': 1.0})  # Default weight
        else:
            # If the column doesn't exist, return default weight
            return jsonify({'success': True, 'weight': 1.0})
            
    except Exception as e:
        logging.error(f"Error getting CO-PO weight: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@api_bp.route('/exam/<int:exam_id>/question-outcomes', methods=['GET'])
def get_question_outcomes(exam_id):
    """Get all questions for an exam with their associated course outcomes"""
    questions = Question.query.filter_by(exam_id=exam_id).all()
    
    result = {}
    for question in questions:
        outcomes = []
        for outcome in question.course_outcomes:
            outcomes.append({
                'id': outcome.id,
                'code': outcome.code,
                'description': outcome.description
            })
        
        result[question.id] = outcomes
    
    return jsonify(result)

@api_bp.route('/student/<int:student_id>/abet-scores', methods=['GET'])
def get_student_abet_scores(student_id):
    """API endpoint to get a student's ABET scores for all course outcomes"""
    course_id = request.args.get('course_id', type=int)
    if not course_id:
        return jsonify({'error': 'Course ID is required'}), 400
    
    # Get the student
    student = Student.query.filter_by(id=student_id, course_id=course_id).first()
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    
    # Get course outcomes for this course
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).all()
    if not course_outcomes:
        return jsonify({'error': 'No course outcomes found for this course'}), 404
    
    # Get achievement levels for this course
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    # Preload scores data
    # Get all questions for this course
    questions = Question.query.join(Exam).filter(Exam.course_id == course_id).all()
    
    # Create a map of course outcomes to questions
    outcome_questions = {}
    for outcome in course_outcomes:
        outcome_questions[outcome.id] = outcome.questions
    
    # Create scores dictionary
    scores_dict = {}
    scores = Score.query.filter_by(student_id=student_id).join(Question).join(Exam).filter(Exam.course_id == course_id).all()
    for score in scores:
        scores_dict[(score.student_id, score.question_id, score.exam_id)] = score.score
    
    # Create attendance dictionary
    attendance_dict = {}
    attendance_records = StudentExamAttendance.query.filter_by(student_id=student_id).join(Exam).filter(Exam.course_id == course_id).all()
    for record in attendance_records:
        attendance_dict[(record.student_id, record.exam_id)] = record.attended
    
    # Get all exams and calculate normalized weights
    exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()
    exam_weights = {}
    total_weight = Decimal('0')
    
    # Get all weights for this course
    weights = ExamWeight.query.filter_by(course_id=course_id).all()
    for weight in weights:
        exam_weights[weight.exam_id] = weight.weight
    
    # Sum up weights for regular exams
    for exam in exams:
        if exam.id not in exam_weights:
            exam_weights[exam.id] = Decimal('0')
        total_weight += exam_weights[exam.id]
    
    # Normalize weights if they don't add up to 1.0
    normalized_weights = {}
    for exam_id, weight in exam_weights.items():
        if total_weight > Decimal('0'):
            normalized_weights[exam_id] = weight / total_weight
        else:
            normalized_weights[exam_id] = weight
    
    # Calculate outcome scores using helper functions
    result = []
    for outcome in course_outcomes:
        # Use calculate_course_outcome_score_optimized to get consistent results
        outcome_score = calculate_course_outcome_score_optimized(
            student_id, outcome.id, scores_dict, outcome_questions, normalized_weights
        )
        
        if outcome_score is not None:
            percentage = float(outcome_score)
        else:
            percentage = 0
            
        # Get achievement level
        achievement_level = get_achievement_level(percentage, achievement_levels)
            
        result.append({
            'outcome_id': outcome.id,
            'code': outcome.code,
            'description': outcome.description,
            'percentage': percentage,
            'achievement_level': achievement_level
        })
    
    # Sort by outcome code
    result.sort(key=lambda x: x['code'])
    
    return jsonify(result)

@api_bp.route('/batch-add-questions/<int:exam_id>', methods=['POST'])
def batch_add_questions(exam_id):
    """API endpoint for adding multiple questions at once"""
    # Implementation will be added
    pass

@api_bp.route('/mass-associate-outcomes', methods=['POST'])
def mass_associate_outcomes():
    """API endpoint for mass associating questions with course outcomes"""
    data = request.json
    
    if not data or 'exam_id' not in data or 'associations' not in data:
        return jsonify({'success': False, 'message': 'Missing required data'}), 400
    
    exam_id = data['exam_id']
    associations_text = data['associations']
    
    try:
        # Get the exam
        exam = Exam.query.get(exam_id)
        if not exam:
            return jsonify({'success': False, 'message': 'Exam not found'}), 404
        
        # Get the course outcomes for this exam's course
        course_outcomes = CourseOutcome.query.filter_by(course_id=exam.course_id).all()
        outcome_map = {}
        
        # Create a map of outcome numbers to outcome IDs
        for outcome in course_outcomes:
            # Extract numeric part from outcome code (CSE301-1 -> 1)
            code_match = re.search(r'\D*(\d+)$', outcome.code)
            if code_match:
                outcome_map[int(code_match.group(1))] = outcome.id
        
        # Parse the associations text
        associations = associations_text.split(';')
        updates = 0
        errors = []
        
        for assoc in associations:
            if not assoc.strip():
                continue
                
            parts = assoc.split(':')
            if len(parts) < 2:
                errors.append(f"Invalid format for '{assoc}'")
                continue
            
            # Extract question number (q1 -> 1)
            q_match = re.match(r'q(\d+)', parts[0].lower())
            if not q_match:
                errors.append(f"Invalid question format in '{parts[0]}'")
                continue
            
            question_num = int(q_match.group(1))
            
            # Find the question by number in this exam
            question = Question.query.filter_by(exam_id=exam_id, number=question_num).first()
            if not question:
                errors.append(f"Question {question_num} not found in this exam")
                continue
            
            # Extract outcomes (oc1 -> 1)
            outcome_ids = []
            for i in range(1, len(parts)):
                co_match = re.match(r'co(\d+)', parts[i].lower())
                if co_match:
                    outcome_num = int(co_match.group(1))
                    if outcome_num in outcome_map:
                        outcome_ids.append(outcome_map[outcome_num])
                    else:
                        errors.append(f"Outcome {outcome_num} not found in this course")
            
            # Update the question's outcomes
            if outcome_ids:
                # Clear existing associations
                question.course_outcomes = []
                
                # Add the new associations
                for outcome_id in outcome_ids:
                    outcome = CourseOutcome.query.get(outcome_id)
                    if outcome:
                        question.course_outcomes.append(outcome)
                
                updates += 1
        
        if updates > 0:
            # Log the action
            log = Log(
                action="MASS_ASSOCIATE_OUTCOMES",
                description=f"Updated outcome associations for {updates} questions in exam: {exam.name}"
            )
            db.session.add(log)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Updated outcome associations for {updates} questions',
                'errors': errors if errors else None
            })
        else:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': 'No updates were made',
                'errors': errors
            }), 400
            
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error mass associating outcomes: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/update-question-outcome', methods=['POST'])
def update_question_outcome():
    """API endpoint for updating a single question-outcome association"""
    data = request.json
    
    if not data or 'question_id' not in data or 'outcome_id' not in data or 'checked' not in data:
        return jsonify({'success': False, 'message': 'Missing required data'}), 400
    
    question_id = data['question_id']
    outcome_id = data['outcome_id']
    is_checked = data['checked']
    
    try:
        question = Question.query.get(question_id)
        outcome = CourseOutcome.query.get(outcome_id)
        
        if not question or not outcome:
            return jsonify({'success': False, 'message': 'Question or outcome not found'}), 404
        
        # Update the association
        if is_checked and outcome not in question.course_outcomes:
            question.course_outcomes.append(outcome)
            action = "added to"
        elif not is_checked and outcome in question.course_outcomes:
            question.course_outcomes.remove(outcome)
            action = "removed from"
        else:
            # No change needed
            return jsonify({'success': True, 'message': 'No change required'})
        
        # Log the action
        log = Log(
            action="UPDATE_QUESTION_OUTCOME",
            description=f"Outcome {outcome.code} {action} question {question.number} in exam: {question.exam.name}"
        )
        db.session.add(log)
        
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': f'Outcome {outcome.code} {action} question {question.number}'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating question-outcome association: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/course/<int:course_id>/achievement-levels', methods=['GET'])
def get_course_achievement_levels(course_id):
    """API endpoint to get achievement levels for a course"""
    course = Course.query.get_or_404(course_id)
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    # Check if the course has achievement levels, if not, add default ones
    if not achievement_levels:
        # Add default achievement levels
        default_levels = [
            {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
            {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
            {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
            {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
            {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
        ]
        
        for level_data in default_levels:
            level = AchievementLevel(
                course_id=course_id,
                name=level_data["name"],
                min_score=level_data["min_score"],
                max_score=level_data["max_score"],
                color=level_data["color"]
            )
            db.session.add(level)
        
        # Log action
        log = Log(action="ADD_DEFAULT_ACHIEVEMENT_LEVELS", 
                 description=f"Added default achievement levels to course: {course.code}")
        db.session.add(log)
        db.session.commit()
        
        # Refresh achievement levels
        achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()
    
    return jsonify({
        'course': {
            'id': course.id,
            'code': course.code,
            'name': course.name
        },
        'achievement_levels': [{
            'id': level.id,
            'name': level.name,
            'min_score': float(level.min_score),
            'max_score': float(level.max_score),
            'color': level.color
        } for level in achievement_levels]
    }) 