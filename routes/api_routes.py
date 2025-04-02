from flask import Blueprint, jsonify, request
from models import Question, CourseOutcome, Log, Student, Exam, Score
from app import db
import logging
from decimal import Decimal

api_bp = Blueprint('api', __name__, url_prefix='/api')

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

@api_bp.route('/student/<int:student_id>/abet-scores/<int:exam_id>', methods=['GET'])
def get_student_abet_scores(student_id, exam_id):
    """API endpoint to get ABET scores for a specific student in an exam"""
    student = Student.query.get_or_404(student_id)
    exam = Exam.query.get_or_404(exam_id)
    
    # Get questions for this exam
    questions = Question.query.filter_by(exam_id=exam_id).all()
    
    # Get student scores for these questions
    scores = Score.query.filter_by(student_id=student_id, exam_id=exam_id).all()
    
    # Create a dictionary of scores by question ID
    score_dict = {}
    for score in scores:
        score_dict[score.question_id] = score.score
    
    # Calculate outcome scores based on question-outcome associations
    outcome_scores = {}
    
    for question in questions:
        for outcome in question.course_outcomes:
            if outcome.id not in outcome_scores:
                outcome_scores[outcome.id] = {
                    'code': outcome.code,
                    'description': outcome.description,
                    'total_score': Decimal('0'),
                    'max_score': Decimal('0')
                }
            
            # Add score for this question/outcome if available
            if question.id in score_dict:
                outcome_scores[outcome.id]['total_score'] += score_dict[question.id]
            
            # Add max possible score
            outcome_scores[outcome.id]['max_score'] += question.max_score
    
    # Calculate percentages
    result = []
    for outcome_id, data in outcome_scores.items():
        if data['max_score'] > 0:
            percentage = (data['total_score'] / data['max_score']) * 100
        else:
            percentage = 0
            
        result.append({
            'outcome_id': outcome_id,
            'code': data['code'],
            'description': data['description'],
            'score': data['total_score'],
            'max_score': data['max_score'],
            'percentage': percentage
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
    # Implementation will be added
    pass

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