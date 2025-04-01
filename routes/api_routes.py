from flask import Blueprint, jsonify, request
from models import Question, CourseOutcome, Log
from app import db
import logging

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