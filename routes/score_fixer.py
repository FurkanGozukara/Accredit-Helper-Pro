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
        'exams_with_question_score_issues': 0,
        'exams_with_underscored_question_sums': 0,
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
                'invalid_scores_count': 0,
                'question_scores_sum_issue': False,
                'question_scores_undersum_issue': False,
                'question_scores_sum': 0,
                'exam_max_score': exam.max_score
            }
            
            # Check if question scores sum exceeds or is less than exam max score
            questions = Question.query.filter_by(exam_id=exam.id).all()
            if questions:
                question_scores_sum = sum(q.max_score for q in questions)
                exam_stats['question_scores_sum'] = question_scores_sum
                if question_scores_sum > exam.max_score:
                    exam_stats['question_scores_sum_issue'] = True
                    stats['exams_with_question_score_issues'] += 1
                elif question_scores_sum < exam.max_score:
                    exam_stats['question_scores_undersum_issue'] = True
                    stats['exams_with_underscored_question_sums'] += 1
            
            # Find scores that exceed question max_score
            invalid_scores = db.session.query(Score, Question).join(
                Question, Score.question_id == Question.id
            ).filter(
                Score.exam_id == exam.id,
                Score.score > Question.max_score
            ).all()
            
            # If there are any issues (invalid scores or question sum issues), add to details
            if invalid_scores or exam_stats['question_scores_sum_issue'] or exam_stats['question_scores_undersum_issue']:
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
        
        # Also get exams where question scores sum exceeds exam max score
        exams_with_question_score_issues = db.session.query(Exam).all()
        exams_to_process = set()
        
        # Add exams with invalid scores
        for exam in exams_with_invalid_scores:
            exams_to_process.add(exam)
        
        # Add exams with question score sum issues
        for exam in exams_with_question_score_issues:
            questions = Question.query.filter_by(exam_id=exam.id).all()
            if questions:
                question_scores_sum = sum(q.max_score for q in questions)
                if question_scores_sum > exam.max_score:
                    exams_to_process.add(exam)
        
        log_entries.append(f"Found {len(exams_to_process)} exams that need processing")
        log_entries.append("")
        
        for exam in exams_to_process:
            results['processed_exams'] += 1
            log_entries.append(f"Processing Exam: {exam.name} (ID: {exam.id})")
            log_entries.append(f"Course: {exam.course.code} - {exam.course.name}")
            log_entries.append("-" * 60)
            
            # STEP 1: Fix question scores if their sum exceeds exam max score
            question_fix_result = fix_exam_question_scores(exam, log_entries)
            if question_fix_result['questions_adjusted'] > 0:
                results['total_questions_fixed'] += question_fix_result['questions_adjusted']
                log_entries.append(f"  Fixed {question_fix_result['questions_adjusted']} question max scores")
            
            # STEP 2: Get students with invalid scores in this exam (check again after question fixes)
            students_with_invalid_scores = db.session.query(Student).join(
                Score, Student.id == Score.student_id
            ).join(
                Question, Score.question_id == Question.id
            ).filter(
                Score.exam_id == exam.id,
                Score.score > Question.max_score
            ).distinct().all()
            
            # STEP 3: Fix student scores using proportional distribution
            for student in students_with_invalid_scores:
                fix_result = fix_student_exam_scores(student, exam, log_entries)
                if fix_result['fixed']:
                    results['fixed_students'] += 1
                    results['total_questions_fixed'] += fix_result['questions_fixed']
            
            # STEP 4: Cap student scores that exceed exam max score
            all_students_in_exam = db.session.query(Student).join(
                Score, Student.id == Score.student_id
            ).filter(
                Score.exam_id == exam.id
            ).distinct().all()
            
            for student in all_students_in_exam:
                cap_result = cap_student_exam_total(student, exam, log_entries)
                if cap_result['capped']:
                    results['fixed_students'] += 1
            
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

def cap_student_exam_total(student, exam, log_entries):
    """Cap student's total exam score if it exceeds exam max score"""
    result = {
        'capped': False,
        'original_total': Decimal('0'),
        'new_total': Decimal('0')
    }
    
    try:
        # Get all questions for this exam
        questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.number).all()
        
        if not questions:
            return result
        
        # Get all scores for this student in this exam
        scores = Score.query.filter_by(
            student_id=student.id,
            exam_id=exam.id
        ).all()
        
        if not scores:
            return result
        
        # Calculate current total
        current_total = sum(score.score for score in scores)
        result['original_total'] = current_total
        
        # Check if total exceeds exam max score
        if current_total > exam.max_score:
            log_entries.append(f"  Student {student.student_id}: Total score {current_total} exceeds exam max {exam.max_score}")
            
            # Create mapping of question_id to score
            score_map = {score.question_id: score for score in scores}
            
            # Use integer-based proportional reduction to cap at exam max score
            reduction_factor = float(exam.max_score) / float(current_total)
            distributed_sum_so_far = 0
            exam_max_int = int(exam.max_score)
            
            # Apply integer-based proportional reduction to all scores except the last one
            for i in range(len(questions) - 1):
                question = questions[i]
                if question.id in score_map:
                    old_score = score_map[question.id].score
                    
                    # Calculate proportional integer score
                    proportional_score = float(old_score) * reduction_factor
                    new_score_int = max(0, int(round(proportional_score)))
                    
                    # Ensure score doesn't exceed question max
                    question_max_int = int(question.max_score)
                    if new_score_int > question_max_int:
                        new_score_int = question_max_int
                    
                    new_score = Decimal(str(new_score_int))
                    score_map[question.id].score = new_score
                    score_map[question.id].updated_at = datetime.now()
                    distributed_sum_so_far += new_score_int
            
            # Handle the last question - gets the remainder
            if len(questions) > 0:
                last_question = questions[-1]
                if last_question.id in score_map:
                    old_score = score_map[last_question.id].score
                    
                    # Last question gets whatever is left to reach exam max
                    remaining_score = max(0, exam_max_int - distributed_sum_so_far)
                    
                    # Ensure score doesn't exceed question max
                    question_max_int = int(last_question.max_score)
                    if remaining_score > question_max_int:
                        remaining_score = question_max_int
                    
                    new_score = Decimal(str(remaining_score))
                    score_map[last_question.id].score = new_score
                    score_map[last_question.id].updated_at = datetime.now()
            
            # Calculate new total
            new_total = sum(score.score for score in scores)
            result['new_total'] = new_total
            result['capped'] = True
            
            log_entries.append(f"    Capped total score: {current_total} → {new_total}")
        else:
            result['new_total'] = current_total
    
    except Exception as e:
        log_entries.append(f"  ERROR capping student {student.student_id} total: {str(e)}")
        logging.error(f"Error capping student {student.student_id} total for exam {exam.id}: {str(e)}")
    
    return result

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
        
        # Cap the target total at the maximum possible score and convert to integer
        target_total_decimal = min(current_total, max_possible_total)
        target_total_int = int(round(float(target_total_decimal)))
        max_possible_int = int(max_possible_total)
        
        log_entries.append(f"    Target total score: {target_total_int} (max possible: {max_possible_int})")
        
        # Use integer-based proportional distribution
        distributed_sum_so_far = 0
        new_scores = {}
        
        # Distribute scores for all questions proportionally, except the last one
        for i in range(len(questions) - 1):
            question = questions[i]
            
            # Calculate proportional integer score: (question_max / total_max) * target_total
            if max_possible_int > 0:
                proportional_score = (float(question.max_score) / float(max_possible_total)) * target_total_int
                q_score_int = max(0, int(round(proportional_score)))
            else:
                q_score_int = 0
            
            # Ensure score doesn't exceed question max
            question_max_int = int(question.max_score)
            if q_score_int > question_max_int:
                q_score_int = question_max_int
            
            q_score = Decimal(str(q_score_int))
            new_scores[question.id] = q_score
            distributed_sum_so_far += q_score_int
        
        # Calculate the score for the last question - gets the remainder
        last_question = questions[-1]
        last_q_score_int = max(0, target_total_int - distributed_sum_so_far)
        
        # Ensure last question score doesn't exceed max
        last_question_max_int = int(last_question.max_score)
        if last_q_score_int > last_question_max_int:
            last_q_score_int = last_question_max_int
        
        new_scores[last_question.id] = Decimal(str(last_q_score_int))
        
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

def fix_exam_question_scores(exam, log_entries):
    """Fix question max scores if their sum exceeds exam max score"""
    result = {
        'questions_adjusted': 0,
        'original_total': Decimal('0'),
        'new_total': Decimal('0')
    }
    
    try:
        # Get all questions for this exam
        questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.number).all()
        
        if not questions:
            return result
        
        # Calculate sum of question max scores
        question_scores_sum = sum(q.max_score for q in questions)
        exam_max_score = exam.max_score
        
        result['original_total'] = question_scores_sum
        
        # Check if question scores sum exceeds exam max score
        if question_scores_sum > exam_max_score:
            log_entries.append(f"    Question scores sum ({question_scores_sum}) exceeds exam max score ({exam_max_score})")
            log_entries.append(f"    Adjusting question scores proportionally...")
            
            # Calculate reduction factor and convert to float
            reduction_factor = float(exam_max_score) / float(question_scores_sum)
            
            # Apply integer-based proportional reduction to all questions except the last one
            distributed_sum_so_far = 0
            exam_max_int = int(exam_max_score)
            
            for i in range(len(questions) - 1):
                question = questions[i]
                old_max_score = question.max_score
                
                # Calculate proportional integer score
                proportional_score = float(old_max_score) * reduction_factor
                new_max_int = max(1, int(round(proportional_score)))  # Ensure at least 1
                new_max_score = Decimal(str(new_max_int))
                
                if old_max_score != new_max_score:
                    question.max_score = new_max_score
                    question.updated_at = datetime.now()
                    log_entries.append(f"      Q{question.number}: {old_max_score} → {new_max_score}")
                    result['questions_adjusted'] += 1
                
                distributed_sum_so_far += new_max_int
            
            # Handle the last question - gets the remainder
            if len(questions) > 0:
                last_question = questions[-1]
                old_max_score = last_question.max_score
                
                # Last question gets whatever is left to make total equal exam max
                remaining_score = max(1, exam_max_int - distributed_sum_so_far)
                new_max_score = Decimal(str(remaining_score))
                
                if old_max_score != new_max_score:
                    last_question.max_score = new_max_score
                    last_question.updated_at = datetime.now()
                    log_entries.append(f"      Q{last_question.number}: {old_max_score} → {new_max_score}")
                    result['questions_adjusted'] += 1
            
            # Calculate new total
            new_question_scores_sum = sum(q.max_score for q in questions)
            result['new_total'] = new_question_scores_sum
            log_entries.append(f"    New question scores sum: {new_question_scores_sum}")
        else:
            result['new_total'] = question_scores_sum
            log_entries.append(f"    Question scores sum ({question_scores_sum}) is within exam max score ({exam_max_score})")
    
    except Exception as e:
        log_entries.append(f"    ERROR adjusting question scores: {str(e)}")
        logging.error(f"Error adjusting question scores for exam {exam.id}: {str(e)}")
    
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