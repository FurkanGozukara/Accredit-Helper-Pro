from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app import db
from models import Course, Exam, Question, CourseOutcome, ExamWeight, Log, Score, Student, AchievementLevel
from datetime import datetime
import logging
import io
import csv
from decimal import Decimal, InvalidOperation
from sqlalchemy import text
from sqlalchemy.orm import joinedload, contains_eager # Added imports

from routes.utility_routes import export_to_excel_csv

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
        is_final = True if request.form.get('is_final') else False
        is_mandatory = True if request.form.get('is_mandatory') else False
        makeup_for = request.form.get('makeup_for')
        relative_weight = request.form.get('relative_weight', '40')

        # Basic validation
        if not name or not max_score:
            flash('Name and maximum score are required', 'error')
            return render_template('exam/form.html',
                                 course=course,
                                 active_page='courses')

        try:
            max_score = Decimal(max_score)
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
                is_makeup=is_makeup,
                is_final=is_final,
                is_mandatory=is_mandatory
            )

            # Set makeup exam relationship if applicable
            if is_makeup and makeup_for:
                new_exam.makeup_for = int(makeup_for)

            db.session.add(new_exam)

            # Create default weight
            # If it's a makeup exam, it should inherit the weight from the original exam
            weight_value = Decimal(relative_weight) / Decimal('100')
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
                         exam_weight=None,
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
        is_final = True if request.form.get('is_final') else False
        is_mandatory = True if request.form.get('is_mandatory') else False
        makeup_for = request.form.get('makeup_for')
        relative_weight = request.form.get('relative_weight', '40')

        # Basic validation
        if not name or not max_score:
            flash('Name and maximum score are required', 'error')
            return render_template('exam/form.html',
                                 course=course,
                                 exam=exam,
                                 active_page='courses')

        try:
            max_score = Decimal(max_score)
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

            # Save the original state to track changes
            was_makeup = exam.is_makeup
            old_makeup_for = exam.makeup_for

            # Update exam
            exam.name = name
            exam.max_score = max_score
            exam.exam_date = exam_date
            exam.is_makeup = is_makeup
            exam.is_final = is_final
            exam.is_mandatory = is_mandatory
            exam.updated_at = datetime.now()

            # Handle makeup relationship changes
            if is_makeup and makeup_for:
                new_makeup_for = int(makeup_for)
                exam.makeup_for = new_makeup_for

                # If this is a new makeup relationship, or makeup parent has changed,
                # we need to sync the weight with the original exam
                if not was_makeup or old_makeup_for != new_makeup_for:
                    # Get original exam's weight
                    original_weight = ExamWeight.query.filter_by(
                        exam_id=new_makeup_for,
                        course_id=course.id
                    ).first()

                    if original_weight:
                        # Update or create weight for this makeup exam
                        makeup_weight = ExamWeight.query.filter_by(
                            exam_id=exam_id,
                            course_id=course.id
                        ).first()

                        if makeup_weight:
                            makeup_weight.weight = original_weight.weight
                        else:
                            new_weight = ExamWeight(
                                exam_id=exam_id,
                                course_id=course.id,
                                weight=original_weight.weight
                            )
                            db.session.add(new_weight)
            elif not is_makeup:
                # If exam was a makeup but is no longer, remove the makeup relationship
                exam.makeup_for = None

                # Update the weight value if not a makeup exam
                weight_value = Decimal(relative_weight) / Decimal('100')
                exam_weight = ExamWeight.query.filter_by(exam_id=exam_id, course_id=course.id).first()
                if exam_weight:
                    exam_weight.weight = weight_value
                else:
                    new_weight = ExamWeight(
                        exam_id=exam_id,
                        course_id=course.id,
                        weight=weight_value
                    )
                    db.session.add(new_weight)

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
    exam_weight = ExamWeight.query.filter_by(exam_id=exam_id, course_id=exam.course_id).first()

    return render_template('exam/form.html',
                         course=course,
                         exam=exam,
                         other_exams=other_exams,
                         exam_weight=exam_weight,
                         active_page='courses')

@exam_bp.route('/delete/<int:exam_id>', methods=['POST'])
def delete_exam(exam_id):
    """Delete an exam after confirmation"""
    exam = Exam.query.get_or_404(exam_id)
    course_id = exam.course_id

    try:
        # Count related data for logging purposes
        questions_count = Question.query.filter_by(exam_id=exam_id).count()
        scores_count = Score.query.filter_by(exam_id=exam_id).count()

        # Log action before deletion
        description = f"Deleted exam: {exam.name} from course: {exam.course.code}"
        if questions_count > 0 or scores_count > 0:
            detail_message = []
            if questions_count > 0:
                detail_message.append(f"{questions_count} questions")
            if scores_count > 0:
                detail_message.append(f"{scores_count} student scores")
            description += f" with related data ({', '.join(detail_message)})"

        log = Log(action="DELETE_EXAM", description=description)
        db.session.add(log)

        # Also delete any exam weights
        exam_weight = ExamWeight.query.filter_by(exam_id=exam_id).first()
        if exam_weight:
            db.session.delete(exam_weight)

        # Delete the exam (will cascade delete questions and scores due to relationship configuration)
        db.session.delete(exam)
        db.session.commit()

        success_message = f'Exam {exam.name} deleted successfully'
        if questions_count > 0 or scores_count > 0:
            success_message += f' along with all related data'
        flash(success_message, 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting exam: {str(e)}")
        flash(f'An error occurred while deleting the exam: {str(e)}', 'error')

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

    # Calculate the sum of all question scores
    total_question_score = sum(float(q.max_score) for q in questions) if questions else 0

    return render_template('exam/detail.html',
                         exam=exam,
                         course=course,
                         questions=questions,
                         course_outcomes=course_outcomes,
                         exam_weight=exam_weight,
                         total_question_score=total_question_score,
                         active_page='courses')

@exam_bp.route('/course/<int:course_id>/weights', methods=['GET', 'POST'])
def manage_weights(course_id):
    """Manage weights for each exam in a course"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()

    # Get existing weights
    weights = ExamWeight.query.filter_by(course_id=course_id).all()

    # Create a dictionary to map exam_id to its weight
    exam_weight_map = {w.exam_id: w for w in weights}

    if request.method == 'POST':
        try:
            total_weight = Decimal('0')
            exam_weights = {}

            # Process each exam weight
            for exam in exams:
                weight_key = f'weight_{exam.id}'
                weight_value = request.form.get(weight_key, '0')

                try:
                    # Ensure the weight value is properly formatted and handled as Decimal
                    # First, strip any whitespace
                    weight_value = weight_value.strip()

                    # Handle various decimal separators (both . and ,)
                    if ',' in weight_value and '.' not in weight_value:
                        weight_value = weight_value.replace(',', '.')

                    # Force string conversion for Decimal to handle properly
                    decimal_weight = Decimal(str(weight_value))

                    # Convert from percentage (0-100) to decimal (0-1)
                    decimal_weight = decimal_weight / Decimal('100')

                    # Ensure value is within valid range
                    if decimal_weight < Decimal('0'):
                        decimal_weight = Decimal('0')
                    if decimal_weight > Decimal('1'):
                        decimal_weight = Decimal('1')

                    # Store the properly converted decimal value
                    exam_weights[exam.id] = decimal_weight
                    total_weight += decimal_weight
                except (ValueError, InvalidOperation) as e:
                    flash(f'Invalid weight value for {exam.name}: {str(e)}', 'error')
                    return redirect(url_for('exam.manage_weights', course_id=course_id))

            # Ensure weights sum to 1 (100%)
            if abs(total_weight - Decimal('1.0')) > Decimal('0.01'):  # Allow small decimal error
                # Display a warning but don't prevent saving
                flash(f'Warning: The sum of weights is {(total_weight * Decimal("100")).quantize(Decimal("0.1"))}% (not 100%)', 'warning')

            # Log action
            log = Log(action="UPDATE_EXAM_WEIGHTS",
                     description=f"Updated exam weights for course: {course.code}")
            db.session.add(log)

            # Update weights in the database
            for exam_id, weight in exam_weights.items():
                # Check if the weight already exists
                existing_weight = ExamWeight.query.filter_by(exam_id=exam_id, course_id=course_id).first()

                if existing_weight:
                    # Update the existing weight
                    existing_weight.weight = weight
                else:
                    # Create a new weight
                    new_weight = ExamWeight(exam_id=exam_id, course_id=course_id, weight=weight)
                    db.session.add(new_weight)

                # Also update weights for any makeup exams
                makeup_exams = Exam.query.filter_by(makeup_for=exam_id).all()
                for makeup_exam in makeup_exams:
                    makeup_weight = ExamWeight.query.filter_by(exam_id=makeup_exam.id, course_id=course_id).first()
                    if makeup_weight:
                        makeup_weight.weight = weight
                    else:
                        new_makeup_weight = ExamWeight(exam_id=makeup_exam.id, course_id=course_id, weight=weight)
                        db.session.add(new_makeup_weight)

            try:
                # Commit the changes
                db.session.commit()
                flash('Exam weights updated successfully', 'success')
                return redirect(url_for('exam.manage_weights', course_id=course_id))
            except Exception as e:
                db.session.rollback()
                flash(f'Database error while updating weights: {str(e)}', 'error')

        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating exam weights: {str(e)}")
            flash(f'An error occurred while updating exam weights: {str(e)}', 'error')

    # Prepare weights for the template
    weights_for_template = []
    for exam in exams:
        # Check if there's an existing weight
        if exam.id in exam_weight_map:
            weight = exam_weight_map[exam.id]
            # Convert weight from decimal (0-1) to percentage (0-100) for display
            weight.display_value = weight.weight * Decimal('100')
            weights_for_template.append(weight)
        else:
            # Create a temporary weight object (not in DB)
            temp_weight = ExamWeight(exam_id=exam.id, course_id=course_id, weight=Decimal('0'))
            temp_weight.exam = exam
            temp_weight.display_value = Decimal('0')  # For display as percentage
            weights_for_template.append(temp_weight)

    return render_template('exam/weights.html',
                         course=course,
                         exams=exams,
                         weights=weights_for_template,
                         active_page='courses')

@exam_bp.route('/course/<int:course_id>/export')
def export_exams(course_id):
    """Export all exams for a course to CSV"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id).order_by(Exam.name).all()

    # Fix any missing makeup relationships before exporting
    regular_exams = [e for e in exams if not e.is_makeup]
    makeup_exams = [e for e in exams if e.is_makeup]

    # Counter for fixes
    fixes_count = 0

    # Process makeup exams to find their original counterparts
    for makeup_exam in makeup_exams:
        # Skip if already properly set
        if makeup_exam.makeup_for:
            # Verify the relationship is valid
            original = Exam.query.get(makeup_exam.makeup_for)
            if original and original.course_id == course_id:
                continue

        # Try to find the original exam by analyzing the name
        makeup_name = makeup_exam.name.lower()
        if 'makeup' in makeup_name:
            base_name = makeup_name.replace('makeup', '', 1).strip()

            # First try exact name match
            matched = False
            for regular_exam in regular_exams:
                if regular_exam.name.lower() == base_name:
                    makeup_exam.makeup_for = regular_exam.id
                    fixes_count += 1
                    matched = True
                    break

            # If no exact match, try partial name match
            if not matched:
                for regular_exam in regular_exams:
                    # Check if base_name contains the regular exam name or vice versa
                    if base_name in regular_exam.name.lower() or regular_exam.name.lower() in base_name:
                        makeup_exam.makeup_for = regular_exam.id
                        fixes_count += 1
                        break

    # Commit any fixes that were made
    if fixes_count > 0:
        try:
            db.session.commit()
            log = Log(action="AUTO_FIX_MAKEUP_EXAMS",
                     description=f"Automatically fixed {fixes_count} makeup exam relationships for course: {course.code}")
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()

    # Refresh exam list after possible changes
    exams = Exam.query.filter_by(course_id=course_id).order_by(Exam.name).all()

    # Create a mapping of exam IDs to exam names
    exam_id_to_name = {exam.id: exam.name for exam in exams}

    # Get exam weights
    weights = {}
    for exam in exams:
        weight = ExamWeight.query.filter_by(exam_id=exam.id).first()
        if weight:
            weights[exam.id] = weight.weight

    # Prepare data for export
    data = []
    headers = ['Exam Name', 'Max Score', 'Date', 'Question Count', 'Is Makeup', 'Makeup For', 'Weight (%)']

    for exam in exams:
        question_count = Question.query.filter_by(exam_id=exam.id).count()

        # Determine makeup_for value
        makeup_for = 'N/A'

        # Simple approach now that relationships are fixed
        if exam.is_makeup and exam.makeup_for and exam.makeup_for in exam_id_to_name:
            makeup_for = exam_id_to_name[exam.makeup_for]

        exam_data = {
            'Exam Name': exam.name,
            'Max Score': float(exam.max_score),
            'Date': exam.exam_date.strftime('%m/%d/%Y') if exam.exam_date else 'N/A',
            'Question Count': question_count,
            'Is Makeup': 'Yes' if exam.is_makeup else 'No',
            'Makeup For': makeup_for,
            'Weight (%)': float(weights.get(exam.id, 0)) * 100 if exam.id in weights else 'N/A'
        }

        data.append(exam_data)

    # Get achievement levels
    achievement_levels = AchievementLevel.query.filter_by(course_id=course_id).order_by(AchievementLevel.min_score.desc()).all()

    # If no achievement levels exist, add default ones
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

    # Add a blank row as a separator
    data.append({key: "" for key in headers})

    # Add a header row for Achievement Levels
    achievement_header = {
        'Exam Name': 'ACHIEVEMENT LEVELS',
        'Max Score': '',
        'Date': '',
        'Question Count': '',
        'Is Makeup': '',
        'Makeup For': '',
        'Weight (%)': ''
    }
    data.append(achievement_header)

    # Add each achievement level
    for level in achievement_levels:
        level_data = {
            'Exam Name': level.name,
            'Max Score': f"{float(level.min_score)}% - {float(level.max_score)}%",
            'Date': level.color,
            'Question Count': '',
            'Is Makeup': '',
            'Makeup For': '',
            'Weight (%)': ''
        }
        data.append(level_data)

    # Get course outcomes
    course_outcomes = CourseOutcome.query.filter_by(course_id=course_id).order_by(CourseOutcome.code).all()

    # Add a blank row as a separator
    data.append({key: "" for key in headers})

    # Add a header row for Course Outcomes
    outcomes_header = {
        'Exam Name': 'COURSE OUTCOMES',
        'Max Score': '',
        'Date': '',
        'Question Count': '',
        'Is Makeup': '',
        'Makeup For': '',
        'Weight (%)': ''
    }
    data.append(outcomes_header)

    # Add each course outcome
    for outcome in course_outcomes:
        # Get associated program outcomes
        po_codes = [po.code for po in outcome.program_outcomes]
        po_text = ', '.join(po_codes) if po_codes else 'None'

        outcome_data = {
            'Exam Name': outcome.code,
            'Max Score': outcome.description,
            'Date': po_text,
            'Question Count': '',
            'Is Makeup': '',
            'Makeup For': '',
            'Weight (%)': ''
        }
        data.append(outcome_data)

    # Log export action
    log = Log(action="EXPORT_EXAMS",
             description=f"Exported exam details, achievement levels, and course outcomes for course: {course.code}")
    db.session.add(log)
    db.session.commit()

    # Export data using utility function
    return export_to_excel_csv(data, f"exams_{course.code}", headers)

# <<< MODIFIED FUNCTION START >>>
@exam_bp.route('/<int:exam_id>/export_scores')
def export_exam_scores(exam_id):
    """Export scores for a specific exam to CSV"""
    exam = Exam.query.get_or_404(exam_id)
    course = Course.query.get_or_404(exam.course_id)

    # Get questions and max scores in one efficient query
    questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.number).all()

    # Prepare headers first to avoid recalculating
    headers = ['Import Format', 'Student ID', 'Student Name']
    question_headers = {q.id: f'Q{q.number} (max: {float(q.max_score)})' for q in questions}
    for question in questions:
        headers.append(question_headers[question.id])
    headers.append('Total Score')
    headers.append('Percentage (%)')

    # Calculate max possible score once (use Decimal for precision)
    max_score = sum(Decimal(str(q.max_score)) for q in questions)

    # <<< OPTIMIZED QUERY START >>>
    # Fetch students registered in the course, preloading their scores for THIS exam only.
    # This is more efficient as it focuses on the relevant data directly.
    students_query = Student.query.filter(
        Student.course_id == course.id
    ).outerjoin(
        Score, db.and_(Student.id == Score.student_id, Score.exam_id == exam_id)
    ).options(
        contains_eager(Student.scores) # Use contains_eager with the explicit join
    ).order_by(Student.student_id)
    # <<< OPTIMIZED QUERY END >>>

    # <<< STREAMING GENERATOR START >>>
    # Create a generator function to yield rows one by one
    def generate_student_rows():
        # Iterate directly over the query results
        for student in students_query:
            student_row = {}
            student_row['Student ID'] = student.student_id
            student_row['Student Name'] = f"{student.first_name} {student.last_name}".strip()

            # Create a dictionary of scores for the current student for easy lookup
            # Student.scores now contains only scores for this exam due to contains_eager
            scores_dict = {score.question_id: score.score for score in student.scores}

            # Calculate total score
            total_score = Decimal('0.0') # Use Decimal for precision

            for question in questions:
                question_header_key = question_headers[question.id] # Use pre-calculated header
                score_value = scores_dict.get(question.id)

                if score_value is not None:
                    try:
                        # Ensure score is treated as Decimal
                        current_score = Decimal(str(score_value))
                        student_row[question_header_key] = float(current_score) # Convert back to float for CSV if needed, or keep Decimal
                        total_score += current_score
                    except InvalidOperation:
                         student_row[question_header_key] = 'INVALID' # Or handle error as appropriate
                         logging.warning(f"Invalid score value '{score_value}' for student {student.student_id}, question {question.number}")
                else:
                    student_row[question_header_key] = ''

            # Format total score
            rounded_total = total_score.quantize(Decimal("0.01"))

            # Calculate percentage
            if max_score > 0:
                # Ensure max_score is Decimal for calculation
                decimal_max_score = Decimal(str(max_score))
                percentage = (total_score / decimal_max_score) * Decimal('100')
                rounded_percentage = percentage.quantize(Decimal("0.01"))
                student_row['Total Score'] = "{:.2f}".format(rounded_total)
                student_row['Percentage (%)'] = "{:.2f}".format(rounded_percentage)

                # Add Import Format column
                # Check if the Decimal has fractional part
                if rounded_total == rounded_total.to_integral_value():
                     student_row['Import Format'] = f"{student.student_id};{int(rounded_total)}"
                else:
                     student_row['Import Format'] = f"{student.student_id};{'{:.2f}'.format(rounded_total)}"
            else:
                student_row['Total Score'] = "0.00"
                student_row['Percentage (%)'] = "0.00"
                student_row['Import Format'] = f"{student.student_id};0"

            yield student_row # Yield the row instead of appending

    # Log action
    log = Log(action="EXPORT_EXAM_SCORES",
             description=f"Exported scores for exam: {exam.name} in course: {course.code}")
    db.session.add(log)
    db.session.commit()

    # Export data using the generator
    # Pass the generator function itself, or its result, to the modified export function
    return export_to_excel_csv(generate_student_rows(), f"scores_{course.code}_{exam.name.replace(' ', '_')}", headers)
    # <<< STREAMING GENERATOR END >>>
# <<< MODIFIED FUNCTION END >>>

@exam_bp.route('/course/<int:course_id>/manage_exams')
def manage_exams(course_id):
    """Manage exams, including mandatory exam settings"""
    course = Course.query.get_or_404(course_id)
    exams = Exam.query.filter_by(course_id=course_id).all()
    regular_exams = [e for e in exams if not e.is_makeup]
    makeup_exams = [e for e in exams if e.is_makeup]

    # Get weights for display
    weights = {}
    for exam in exams:
        weight = ExamWeight.query.filter_by(exam_id=exam.id).first()
        if weight:
            weights[exam.id] = weight.weight

    return render_template('exam/manage_exams.html',
                         course=course,
                         regular_exams=regular_exams,
                         makeup_exams=makeup_exams,
                         weights=weights,
                         active_page='courses')

@exam_bp.route('/course/<int:course_id>/fix_makeup_relations')
def fix_makeup_relations(course_id):
    """Fix makeup exam relationships by analyzing exam names"""
    course = Course.query.get_or_404(course_id)

    # Get all exams for the course
    exams = Exam.query.filter_by(course_id=course_id).all()

    # Group exams by regular and makeup
    regular_exams = [e for e in exams if not e.is_makeup]
    makeup_exams = [e for e in exams if e.is_makeup]

    # Counter for fixes
    fixes_count = 0

    # Process makeup exams to find their original counterparts
    for makeup_exam in makeup_exams:
        # Skip if already properly set
        if makeup_exam.makeup_for:
            # Verify the relationship is valid
            original = Exam.query.get(makeup_exam.makeup_for)
            if original and original.course_id == course_id:
                continue

        # Try to find the original exam by analyzing the name
        makeup_name = makeup_exam.name.lower()
        if 'makeup' in makeup_name:
            base_name = makeup_name.replace('makeup', '', 1).strip()

            # First try exact name match
            matched = False
            for regular_exam in regular_exams:
                if regular_exam.name.lower() == base_name:
                    makeup_exam.makeup_for = regular_exam.id
                    fixes_count += 1
                    matched = True
                    break

            # If no exact match, try partial name match
            if not matched:
                for regular_exam in regular_exams:
                    # Check if base_name contains the regular exam name or vice versa
                    if base_name in regular_exam.name.lower() or regular_exam.name.lower() in base_name:
                        makeup_exam.makeup_for = regular_exam.id
                        fixes_count += 1
                        break

    # Commit changes if any fixes were made
    if fixes_count > 0:
        try:
            db.session.commit()
            log = Log(action="FIX_MAKEUP_EXAMS",
                     description=f"Fixed {fixes_count} makeup exam relationships for course: {course.code}")
            db.session.add(log)
            db.session.commit()
            flash(f'Fixed {fixes_count} makeup exam relationships.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error fixing makeup exam relationships: {str(e)}', 'error')
    else:
        flash('No makeup exam relationships needed fixing.', 'info')

    return redirect(url_for('exam.manage_exams', course_id=course_id))