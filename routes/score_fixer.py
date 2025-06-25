from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask import current_app, send_file
from app import db
from models import Course, Student, Exam, Question, Score, Log
from datetime import datetime
import logging
import os
import tempfile
import traceback
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func
from collections import defaultdict

score_fixer_bp = Blueprint('score_fixer', __name__, url_prefix='/score_fixer')

@score_fixer_bp.route('/fix_invalid_scores', methods=['GET', 'POST'])
def fix_invalid_scores():
    """Fix scores that exceed maximum question scores by redistributing proportionally"""
    
    if request.method == 'GET':
        # Show a confirmation page with statistics
        stats = get_invalid_scores_statistics()
        return render_template('utility/fix_invalid_scores.html', 
                             stats=stats, 
                             active_page='utilities')
    
    if request.method == 'POST':
        try:
            # Create log file path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"invalid_scores_fix_{timestamp}.txt"
            log_path = os.path.join(current_app.config.get('BACKUP_FOLDER', 'backups'), log_filename)
            
            # Ensure backup directory exists
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            
            # Process the fixes
            results = process_invalid_scores_fix(log_path)
            
            # Flash success message with results
            flash(f"Invalid scores fix completed! {results['fixed_students']} students fixed, "
                  f"{results['total_questions_fixed']} questions adjusted. "
                  f"Log file saved: {log_filename}", 'success')
            
            # Log the action
            log = Log(action="FIX_INVALID_SCORES",
                     description=f"Fixed invalid scores for {results['fixed_students']} students, "
                               f"{results['total_questions_fixed']} questions adjusted. Log: {log_filename}")
            db.session.add(log)
            db.session.commit()
            
            return redirect(url_for('utility.index'))
            
        except Exception as e:
            flash(f'Error fixing invalid scores: {str(e)}', 'error')
            logging.error(f"Error in fix_invalid_scores: {str(e)}\n{traceback.format_exc()}")
            return redirect(url_for('utility.index'))

def get_invalid_scores_statistics():
    """Get statistics about invalid scores in the database"""
    stats = {
        'total_exams': 0,
        'exams_with_invalid_scores': 0,
        'total_students_affected': 0,
        'total_invalid_scores': 0,
        'exams_details': []
    }
    
    try:
        # Get all exams with their questions and scores
        exams = Exam.query.join(Course).all()
        stats['total_exams'] = len(exams)
        
        for exam in exams:
            exam_stats = {
                'exam_id': exam.id,
                'exam_name': exam.name,
                'course_code': exam.course.code,
                'course_name': exam.course.name,
                'students_affected': 0,
                'invalid_scores_count': 0
            }
            
            # Find scores that exceed question max_score
            invalid_scores = db.session.query(Score, Question).join(
                Question, Score.question_id == Question.id
            ).filter(
                Score.exam_id == exam.id,
                Score.score > Question.max_score
            ).all()
            
            if invalid_scores:
                exam_stats['invalid_scores_count'] = len(invalid_scores)
                affected_students = set([score.student_id for score, question in invalid_scores])
                exam_stats['students_affected'] = len(affected_students)
                
                stats['exams_with_invalid_scores'] += 1
                stats['total_students_affected'] += len(affected_students)
                stats['total_invalid_scores'] += len(invalid_scores)
                stats['exams_details'].append(exam_stats)
        
    except Exception as e:
        logging.error(f"Error getting invalid scores statistics: {str(e)}")
    
    return stats

def process_invalid_scores_fix(log_path):
    """Process and fix all invalid scores, writing detailed log"""
    results = {
        'fixed_students': 0,
        'total_questions_fixed': 0,
        'processed_exams': 0
    }
    
    log_entries = []
    log_entries.append(f"Invalid Scores Fix Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_entries.append("=" * 80)
    log_entries.append("")
    
    try:
        # Get all exams that have invalid scores
        exams_with_invalid_scores = db.session.query(Exam).join(
            Score, Exam.id == Score.exam_id
        ).join(
            Question, Score.question_id == Question.id
        ).filter(
            Score.score > Question.max_score
        ).distinct().all()
        
        log_entries.append(f"Found {len(exams_with_invalid_scores)} exams with invalid scores")
        log_entries.append("")
        
        for exam in exams_with_invalid_scores:
            results['processed_exams'] += 1
            log_entries.append(f"Processing Exam: {exam.name} (ID: {exam.id})")
            log_entries.append(f"Course: {exam.course.code} - {exam.course.name}")
            log_entries.append("-" * 60)
            
            # Get students with invalid scores in this exam
            students_with_invalid_scores = db.session.query(Student).join(
                Score, Student.id == Score.student_id
            ).join(
                Question, Score.question_id == Question.id
            ).filter(
                Score.exam_id == exam.id,
                Score.score > Question.max_score
            ).distinct().all()
            
            for student in students_with_invalid_scores:
                fix_result = fix_student_exam_scores(student, exam, log_entries)
                if fix_result['fixed']:
                    results['fixed_students'] += 1
                    results['total_questions_fixed'] += fix_result['questions_fixed']
            
            log_entries.append("")
        
        # Write log file
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_entries))
        
        # Commit all changes
        db.session.commit()
        
        log_entries.append(f"Summary:")
        log_entries.append(f"- Fixed students: {results['fixed_students']}")
        log_entries.append(f"- Total questions adjusted: {results['total_questions_fixed']}")
        log_entries.append(f"- Processed exams: {results['processed_exams']}")
        
    except Exception as e:
        db.session.rollback()
        log_entries.append(f"ERROR: {str(e)}")
        log_entries.append(traceback.format_exc())
        
        # Write error log
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_entries))
        
        raise e
    
    return results

def fix_student_exam_scores(student, exam, log_entries):
    """Fix scores for a specific student in a specific exam using proportional distribution"""
    result = {
        'fixed': False,
        'questions_fixed': 0
    }
    
    try:
        # Get all questions for this exam
        questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.number).all()
        
        if not questions:
            log_entries.append(f"  No questions found for exam {exam.id}")
            return result
        
        # Get all scores for this student in this exam
        scores = Score.query.filter_by(
            student_id=student.id,
            exam_id=exam.id
        ).all()
        
        if not scores:
            log_entries.append(f"  No scores found for student {student.student_id}")
            return result
        
        # Create mapping of question_id to score
        score_map = {score.question_id: score for score in scores}
        
        # Check if student has any invalid scores
        has_invalid_scores = False
        current_total = Decimal('0')
        invalid_questions = []
        
        for question in questions:
            if question.id in score_map:
                score = score_map[question.id].score
                current_total += score
                if score > question.max_score:
                    has_invalid_scores = True
                    invalid_questions.append(f"Q{question.number}: {score}/{question.max_score}")
        
        if not has_invalid_scores:
            return result
        
        log_entries.append(f"  Student: {student.student_id} - {student.first_name} {student.last_name or ''}")
        log_entries.append(f"    Invalid questions: {', '.join(invalid_questions)}")
        log_entries.append(f"    Previous total score: {current_total}")
        
        # Calculate maximum possible total
        max_possible_total = sum(q.max_score for q in questions)
        
        # Cap the target total at the maximum possible score
        target_total = min(current_total, max_possible_total)
        target_total = target_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        log_entries.append(f"    Target total score: {target_total} (max possible: {max_possible_total})")
        
        # Use proportional distribution (same logic as import)
        distributed_sum_so_far = Decimal('0')
        new_scores = {}
        
        # Distribute scores for all questions proportionally, except the last one
        for i in range(len(questions) - 1):
            question = questions[i]
            
            # Calculate proportional score: (question_max / total_max) * target_total
            if max_possible_total > 0:
                proportional_score = (question.max_score / max_possible_total) * target_total
            else:
                proportional_score = Decimal('0')
            
            # Round to 2 decimals
            q_score = proportional_score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Ensure score doesn't exceed max
            if q_score > question.max_score:
                q_score = question.max_score
            
            if q_score < 0:
                q_score = Decimal('0')
            
            new_scores[question.id] = q_score
            distributed_sum_so_far += q_score
        
        # Calculate the score for the last question
        last_question = questions[-1]
        last_q_score = target_total - distributed_sum_so_far
        
        # Ensure last question score doesn't exceed max
        if last_q_score > last_question.max_score:
            last_q_score = last_question.max_score
        
        if last_q_score < 0:
            last_q_score = Decimal('0')
        
        new_scores[last_question.id] = last_q_score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Calculate new total
        new_total = sum(new_scores.values())
        
        # Update scores in database and log changes
        changes_made = []
        for question in questions:
            if question.id in score_map and question.id in new_scores:
                old_score = score_map[question.id].score
                new_score = new_scores[question.id]
                
                if old_score != new_score:
                    score_map[question.id].score = new_score
                    score_map[question.id].updated_at = datetime.now()
                    changes_made.append(f"Q{question.number}: {old_score} → {new_score}")
                    result['questions_fixed'] += 1
        
        if changes_made:
            log_entries.append(f"    Changes made: {', '.join(changes_made)}")
            log_entries.append(f"    New total score: {new_total}")
            result['fixed'] = True
        else:
            log_entries.append(f"    No changes needed")
        
        log_entries.append("")
        
    except Exception as e:
        log_entries.append(f"  ERROR fixing student {student.student_id}: {str(e)}")
        logging.error(f"Error fixing student {student.student_id}: {str(e)}")
    
    return result

@score_fixer_bp.route('/download_log/<filename>')
def download_log(filename):
    """Download a specific log file"""
    try:
        log_path = os.path.join(current_app.config.get('BACKUP_FOLDER', 'backups'), filename)
        if os.path.exists(log_path):
            return send_file(log_path, as_attachment=True, download_name=filename)
        else:
            flash('Log file not found', 'error')
            return redirect(url_for('utility.index'))
    except Exception as e:
        flash(f'Error downloading log file: {str(e)}', 'error')
        return redirect(url_for('utility.index')) 