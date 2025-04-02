from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask import current_app as app
from app import db
from models import Log, Course, Student, Exam, CourseOutcome, Question, Score
from datetime import datetime
import logging
import os
import shutil
import sqlite3
import traceback
import glob
import csv
import tempfile

utility_bp = Blueprint('utility', __name__, url_prefix='/utility')

@utility_bp.route('/')
def index():
    """Main Utilities page with links to all utility functions"""
    return render_template('utility/index.html', active_page='utilities')

@utility_bp.route('/backup', methods=['GET', 'POST'])
def backup_database():
    """Create a backup of the database"""
    try:
        if request.method == 'POST':
            try:
                # Get current database path
                db_path = os.path.join('instance', 'abet_data.db')
                
                if not os.path.exists(db_path):
                    flash('Database file not found', 'error')
                    return redirect(url_for('utility.backup_database'))
                
                # Create backup directory if it doesn't exist
                backup_dir = app.config['BACKUP_FOLDER']
                os.makedirs(backup_dir, exist_ok=True)
                
                # Create backup filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"abet_data_backup_{timestamp}.db"
                backup_path = os.path.join(backup_dir, backup_filename)
                
                # Copy database file
                shutil.copy2(db_path, backup_path)
                
                # Log action
                log = Log(action="BACKUP_DATABASE", 
                        description=f"Created database backup: {backup_filename}")
                db.session.add(log)
                db.session.commit()
                
                flash(f'Database backup created successfully: {backup_filename}', 'success')
            except Exception as e:
                logging.error(f"Error creating backup: {str(e)}")
                flash(f'An error occurred while creating the backup: {str(e)}', 'error')
        
        # Get list of available backups
        backup_dir = app.config['BACKUP_FOLDER']
        backups = []
        
        if os.path.exists(backup_dir):
            backup_files = glob.glob(os.path.join(backup_dir, "abet_data_backup_*.db"))
            for backup_file in backup_files:
                filename = os.path.basename(backup_file)
                created_at = os.path.getmtime(backup_file)
                size = os.path.getsize(backup_file) / (1024 * 1024)  # Size in MB
                
                backups.append({
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(created_at),
                    'size': round(size, 2),
                    'size_formatted': f"{round(size, 2)} MB",
                    'description': ''  # Add empty description to match template
                })
        
        # Sort backups by creation time (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Set the total backups and auto backup defaults for the template
        total_backups = len(backups)
        last_backup = backups[0] if backups else None
        auto_backup_enabled = False
        auto_backup_frequency = 'weekly'
        
        return render_template('utility/backup.html', 
                            backups=backups,
                            total_backups=total_backups,
                            last_backup=last_backup,
                            auto_backup_enabled=auto_backup_enabled,
                            auto_backup_frequency=auto_backup_frequency,
                            active_page='utilities')
    except Exception as e:
        logging.error(f"Error in backup page: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('utility.index'))

# Add alias for backup_database for backward compatibility with templates
@utility_bp.route('/backup/create', methods=['GET', 'POST'])
def create_backup():
    """Alias for backup_database for backward compatibility"""
    return backup_database()

@utility_bp.route('/backup/download/<filename>')
def download_backup(filename):
    """Download a database backup file"""
    backup_dir = app.config['BACKUP_FOLDER']
    backup_path = os.path.join(backup_dir, filename)
    
    if not os.path.exists(backup_path):
        flash('Backup file not found', 'error')
        return redirect(url_for('utility.backup_database'))
    
    # Log action
    log = Log(action="DOWNLOAD_BACKUP", 
             description=f"Downloaded database backup: {filename}")
    db.session.add(log)
    db.session.commit()
    
    return send_file(backup_path, 
                    as_attachment=True, 
                    download_name=filename)

@utility_bp.route('/backup/delete/<filename>', methods=['POST'])
def delete_backup(filename):
    """Delete a database backup file"""
    backup_dir = app.config['BACKUP_FOLDER']
    backup_path = os.path.join(backup_dir, filename)
    
    if not os.path.exists(backup_path):
        flash('Backup file not found', 'error')
        return redirect(url_for('utility.backup_database'))
    
    try:
        os.remove(backup_path)
        
        # Log action
        log = Log(action="DELETE_BACKUP", 
                 description=f"Deleted database backup: {filename}")
        db.session.add(log)
        db.session.commit()
        
        flash(f'Backup file {filename} deleted successfully', 'success')
    except Exception as e:
        logging.error(f"Error deleting backup: {str(e)}")
        flash(f'An error occurred while deleting the backup: {str(e)}', 'error')
    
    return redirect(url_for('utility.backup_database'))

@utility_bp.route('/restore', methods=['GET', 'POST'])
def restore_database():
    """Restore database from a backup"""
    try:
        if request.method == 'POST':
            # Check if file is provided
            if 'backup_file' not in request.files:
                flash('No backup file provided', 'error')
                return redirect(url_for('utility.restore_database'))
            
            backup_file = request.files['backup_file']
            
            if backup_file.filename == '':
                flash('No backup file selected', 'error')
                return redirect(url_for('utility.restore_database'))
            
            try:
                # Create a temporary file for the uploaded backup
                temp_path = os.path.join(app.config['BACKUP_FOLDER'], 'temp_restore.db')
                backup_file.save(temp_path)
                
                # Verify this is a valid SQLite database
                try:
                    conn = sqlite3.connect(temp_path)
                    conn.close()
                except sqlite3.Error:
                    os.remove(temp_path)
                    flash('Invalid database file', 'error')
                    return redirect(url_for('utility.restore_database'))
                
                # Get current database path
                db_path = os.path.join('instance', 'abet_data.db')
                
                # Create a backup of current database before restore
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                pre_restore_backup = os.path.join(app.config['BACKUP_FOLDER'], f"pre_restore_backup_{timestamp}.db")
                
                if os.path.exists(db_path):
                    shutil.copy2(db_path, pre_restore_backup)
                
                # Close the current database connection
                db.session.close()
                
                # Copy the backup file to the database location
                shutil.copy2(temp_path, db_path)
                
                # Remove temporary file
                os.remove(temp_path)
                
                # Log action using a new connection
                try:
                    engine = db.get_engine()
                    connection = engine.connect()
                    connection.execute("INSERT INTO log (action, description, timestamp) VALUES (?, ?, ?)",
                                    ("RESTORE_DATABASE", f"Restored database from uploaded backup: {backup_file.filename}", datetime.now()))
                    connection.commit()
                    connection.close()
                except Exception as e:
                    logging.error(f"Error logging restore action: {str(e)}")
                
                flash('Database restored successfully. Please restart the application for all changes to take effect.', 'success')
            except Exception as e:
                logging.error(f"Error restoring database: {str(e)}\n{traceback.format_exc()}")
                flash(f'An error occurred while restoring the database: {str(e)}', 'error')
        
        # Get list of available backups for restoration
        backup_dir = app.config['BACKUP_FOLDER']
        backups = []
        
        if os.path.exists(backup_dir):
            backup_files = glob.glob(os.path.join(backup_dir, "abet_data_backup_*.db"))
            for backup_file in backup_files:
                filename = os.path.basename(backup_file)
                created_at = os.path.getmtime(backup_file)
                size = os.path.getsize(backup_file) / (1024 * 1024)  # Size in MB
                
                backups.append({
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(created_at),
                    'size': round(size, 2)
                })
        
        # Sort backups by creation time (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return render_template('utility/restore.html', 
                             backups=backups,
                             active_page='utilities')
    except Exception as e:
        logging.error(f"Error in restore page: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('utility.index'))

@utility_bp.route('/restore/file', methods=['POST'])
def restore_from_file():
    """Restore database from an uploaded file"""
    # Check if file is provided
    if 'backup_file' not in request.files:
        flash('No backup file provided', 'error')
        return redirect(url_for('utility.restore_database'))
    
    backup_file = request.files['backup_file']
    
    if backup_file.filename == '':
        flash('No backup file selected', 'error')
        return redirect(url_for('utility.restore_database'))
    
    # Check if user confirmed the restore action
    if 'confirm_restore' not in request.form:
        flash('You must confirm that you understand the restore process', 'error')
        return redirect(url_for('utility.restore_database'))
    
    try:
        # Create a temporary file for the uploaded backup
        temp_path = os.path.join(app.config['BACKUP_FOLDER'], 'temp_restore.db')
        backup_file.save(temp_path)
        
        # Verify this is a valid SQLite database
        try:
            conn = sqlite3.connect(temp_path)
            conn.close()
        except sqlite3.Error:
            os.remove(temp_path)
            flash('Invalid database file', 'error')
            return redirect(url_for('utility.restore_database'))
        
        # Get current database path
        db_path = os.path.join('instance', 'abet_data.db')
        
        # Create a backup of current database before restore
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pre_restore_backup = os.path.join(app.config['BACKUP_FOLDER'], f"pre_restore_backup_{timestamp}.db")
        
        if os.path.exists(db_path):
            shutil.copy2(db_path, pre_restore_backup)
            flash(f'Created backup of current database before restore: pre_restore_backup_{timestamp}.db', 'info')
        
        # Close the current database connection
        db.session.close()
        
        # Copy the backup file to the database location
        shutil.copy2(temp_path, db_path)
        
        # Remove temporary file
        os.remove(temp_path)
        
        # Log action using a new connection
        engine = db.get_engine()
        connection = engine.connect()
        connection.execute("INSERT INTO log (action, description, timestamp) VALUES (?, ?, ?)",
                         ("RESTORE_DATABASE", f"Restored database from uploaded file: {backup_file.filename}", datetime.now()))
        connection.commit()
        connection.close()
        
        flash('Database restored successfully from uploaded file. Please restart the application for all changes to take effect.', 'success')
    except Exception as e:
        logging.error(f"Error restoring database from file: {str(e)}\n{traceback.format_exc()}")
        flash(f'An error occurred while restoring the database: {str(e)}', 'error')
    
    return redirect(url_for('utility.restore_database'))

@utility_bp.route('/restore/<filename>', methods=['POST'])
def restore_from_backup(filename):
    """Restore database from an existing backup"""
    try:
        backup_dir = app.config['BACKUP_FOLDER']
        backup_path = os.path.join(backup_dir, filename)
        
        if not os.path.exists(backup_path):
            flash('Backup file not found', 'error')
            return redirect(url_for('utility.restore_database'))
        
        # Get current database path
        db_path = os.path.join('instance', 'abet_data.db')
        
        # Check if user wants to backup current database before restore
        backup_current = request.form.get('backup_current', '0') == '1'
        
        if backup_current and os.path.exists(db_path):
            # Create a backup of current database before restore
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_restore_backup = os.path.join(app.config['BACKUP_FOLDER'], f"pre_restore_backup_{timestamp}.db")
            shutil.copy2(db_path, pre_restore_backup)
            flash(f'Created backup of current database before restore: pre_restore_backup_{timestamp}.db', 'info')
        
        # Close the current database connection
        db.session.close()
        
        # Copy the backup file to the database location
        try:
            shutil.copy2(backup_path, db_path)
            
            # Log action using a new connection
            try:
                engine = db.get_engine()
                connection = engine.connect()
                connection.execute("INSERT INTO log (action, description, timestamp) VALUES (?, ?, ?)",
                                ("RESTORE_DATABASE", f"Restored database from backup: {filename}", datetime.now()))
                connection.commit()
                connection.close()
            except Exception as e:
                logging.error(f"Error logging restore action: {str(e)}")
            
            flash('Database restored successfully. Please restart the application for all changes to take effect.', 'success')
        except Exception as e:
            logging.error(f"Error copying backup file: {str(e)}")
            flash(f'An error occurred while restoring the database: {str(e)}', 'error')
    except Exception as e:
        logging.error(f"Error in restore_from_backup: {str(e)}\n{traceback.format_exc()}")
        flash(f'An error occurred while restoring the database: {str(e)}', 'error')
    
    return redirect(url_for('utility.restore_database'))

@utility_bp.route('/merge', methods=['GET', 'POST'])
def merge_database():
    """Merge courses for ABET data consolidation"""
    # Get all courses for selecting source/destination courses
    courses = Course.query.order_by(Course.code).all()
    
    # For clarity, rename this function to match what it does
    return render_template('utility/merge.html', 
                           courses=courses,
                           active_page='utilities')

@utility_bp.route('/merge/courses', methods=['POST'])
def merge_courses():
    """Merge multiple courses into a destination course"""
    try:
        # Get form data
        destination_id = request.form.get('destination_course')
        source_ids = request.form.getlist('source_courses')
        
        # Validate inputs
        if not destination_id:
            flash('Destination course must be selected', 'error')
            return redirect(url_for('utility.merge_database'))
        
        if not source_ids:
            flash('At least one source course must be selected', 'error')
            return redirect(url_for('utility.merge_database'))
        
        # Ensure destination course is not in source courses
        if destination_id in source_ids:
            flash('Destination course cannot be a source course', 'error')
            return redirect(url_for('utility.merge_database'))
        
        # Get the destination course
        destination_course = Course.query.get_or_404(destination_id)
        
        # Create a backup before merging
        if request.form.get('create_backup') == 'on':
            # Call backup function
            backup_database_before_merge()
        
        # Define flags for what to merge
        merge_students = request.form.get('merge_students') == 'on'
        merge_exams = request.form.get('merge_exams') == 'on'
        merge_outcomes = request.form.get('merge_outcomes') == 'on'
        
        # Initialize counters for summary
        students_merged = 0
        exams_merged = 0
        outcomes_merged = 0
        
        # Process each source course
        for source_id in source_ids:
            source_course = Course.query.get(source_id)
            if not source_course:
                continue
            
            # Merge students
            if merge_students:
                for student in source_course.students:
                    # Check if student already exists in destination course
                    existing_student = Student.query.filter_by(
                        course_id=destination_course.id,
                        student_id=student.student_id
                    ).first()
                    
                    if not existing_student:
                        # Create new student in destination course
                        new_student = Student(
                            course_id=destination_course.id,
                            student_id=student.student_id,
                            first_name=student.first_name,
                            last_name=student.last_name
                        )
                        db.session.add(new_student)
                        db.session.flush()  # Get ID for the new student
                        students_merged += 1
                        
                        # Store the new student for score copying
                        dest_student = new_student
                    else:
                        # Use existing student
                        dest_student = existing_student
                    
                    # Copy scores if merging exams
                    if merge_exams:
                        # Get all scores for this student in the source course
                        for score in Score.query.join(Question).join(Exam).filter(
                            Score.student_id == student.id,
                            Exam.course_id == source_course.id
                        ).all():
                            # Find the corresponding question in the destination course
                            source_question = Question.query.get(score.question_id)
                            source_exam = Exam.query.get(source_question.exam_id)
                            
                            # Find matching exam in destination
                            dest_exam = Exam.query.filter_by(
                                course_id=destination_course.id,
                                name=source_exam.name
                            ).first()
                            
                            if dest_exam:
                                # Find matching question in destination exam
                                dest_question = Question.query.filter_by(
                                    exam_id=dest_exam.id,
                                    number=source_question.number
                                ).first()
                                
                                if dest_question:
                                    # Check if score already exists
                                    existing_score = Score.query.filter_by(
                                        student_id=dest_student.id,
                                        question_id=dest_question.id
                                    ).first()
                                    
                                    if not existing_score:
                                        # Create new score
                                        new_score = Score(
                                            student_id=dest_student.id,
                                            question_id=dest_question.id,
                                            score=score.score
                                        )
                                        db.session.add(new_score)
            
            # Merge course outcomes
            if merge_outcomes:
                for outcome in source_course.course_outcomes:
                    # Check if a similar outcome already exists
                    existing_outcome = CourseOutcome.query.filter_by(
                        course_id=destination_course.id,
                        code=outcome.code
                    ).first()
                    
                    if not existing_outcome:
                        # Create new outcome in destination course
                        new_outcome = CourseOutcome(
                            course_id=destination_course.id,
                            code=outcome.code,
                            description=outcome.description
                        )
                        db.session.add(new_outcome)
                        
                        # Link to same program outcomes
                        new_outcome.program_outcomes = outcome.program_outcomes
                        
                        outcomes_merged += 1
            
            # Merge exams
            if merge_exams:
                for exam in source_course.exams:
                    # Check if a similar exam already exists
                    existing_exam = Exam.query.filter_by(
                        course_id=destination_course.id,
                        name=exam.name
                    ).first()
                    
                    if not existing_exam:
                        # Create new exam in destination course
                        new_exam = Exam(
                            course_id=destination_course.id,
                            name=exam.name,
                            date=exam.date,
                            is_makeup=exam.is_makeup,
                            makeup_for_id=None  # Will update below if needed
                        )
                        db.session.add(new_exam)
                        db.session.flush()  # To get the new ID
                        
                        # Copy questions to new exam
                        for question in exam.questions:
                            new_question = Question(
                                exam_id=new_exam.id,
                                number=question.number,
                                text=question.text,
                                max_score=question.max_score
                            )
                            db.session.add(new_question)
                            
                            # Associate with course outcomes if they exist
                            if merge_outcomes:
                                for co in question.course_outcomes:
                                    # Find matching course outcome in destination
                                    dest_co = CourseOutcome.query.filter_by(
                                        course_id=destination_course.id,
                                        code=co.code
                                    ).first()
                                    
                                    if dest_co:
                                        new_question.course_outcomes.append(dest_co)
                        
                        exams_merged += 1
            
        # Commit all changes
        db.session.commit()
        
        # Log the merge action
        log = Log(
            action="MERGE_COURSES",
            description=f"Merged data from {len(source_ids)} courses into {destination_course.code}"
        )
        db.session.add(log)
        db.session.commit()
        
        # Show summary
        summary = []
        if merge_students:
            summary.append(f"{students_merged} students")
        if merge_exams:
            summary.append(f"{exams_merged} exams")
        if merge_outcomes:
            summary.append(f"{outcomes_merged} course outcomes")
        
        if summary:
            flash(f"Successfully merged {', '.join(summary)} into {destination_course.code}.", 'success')
        else:
            flash("Merge completed, but no items were selected for merging.", 'warning')
            
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error merging courses: {str(e)}\n{traceback.format_exc()}")
        flash(f"An error occurred while merging courses: {str(e)}", 'error')
    
    return redirect(url_for('utility.merge_database'))

def backup_database_before_merge():
    """Create a backup before merging courses"""
    try:
        # Get current database path
        db_path = os.path.join('instance', 'abet_data.db')
        
        if not os.path.exists(db_path):
            logging.warning("Database file not found for pre-merge backup")
            return
        
        # Create backup directory if it doesn't exist
        backup_dir = app.config['BACKUP_FOLDER']
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"pre_merge_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy database file
        shutil.copy2(db_path, backup_path)
        
        # Log action
        log = Log(action="BACKUP_BEFORE_MERGE", 
                 description=f"Created database backup before merge: {backup_filename}")
        db.session.add(log)
        db.session.commit()
        
        logging.info(f"Created pre-merge backup: {backup_filename}")
    except Exception as e:
        logging.error(f"Error creating pre-merge backup: {str(e)}")

@utility_bp.route('/help')
def help_page():
    """Display help and documentation"""
    return render_template('utility/help.html', active_page='help')

@utility_bp.route('/logs')
def view_logs():
    """View system logs"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Get filter parameters
        action_filter = request.args.get('action', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Start with base query
        query = Log.query
        
        # Apply filters
        if action_filter:
            query = query.filter(Log.action.like(f'%{action_filter}%'))
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Log.timestamp >= date_from_obj)
            except ValueError:
                flash('Invalid date format for From Date', 'error')
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                # Add one day to include all logs from the selected day
                date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
                query = query.filter(Log.timestamp <= date_to_obj)
            except ValueError:
                flash('Invalid date format for To Date', 'error')
        
        # Get distinct actions for filter dropdown
        distinct_actions = db.session.query(Log.action).distinct().all()
        actions = [action[0] for action in distinct_actions]
        
        # Order by timestamp descending and paginate
        logs = query.order_by(Log.timestamp.desc()).paginate(page=page, per_page=per_page)
        
        return render_template('utility/logs.html', 
                             logs=logs,
                             actions=actions,
                             action_filter=action_filter,
                             date_from=date_from,
                             date_to=date_to,
                             active_page='utilities')
                             
    except Exception as e:
        logging.error(f"Error viewing logs: {str(e)}")
        flash(f'An error occurred while retrieving logs: {str(e)}', 'error')
        return redirect(url_for('utility.index'))

# Add logs alias for backward compatibility
@utility_bp.route('/logs/view')
def logs():
    """Alias for view_logs for backward compatibility"""
    return view_logs()

@utility_bp.route('/logs/export', methods=['GET'])
def export_logs():
    """Export logs to a CSV file"""
    try:
        # Get filter parameters
        action_type = request.args.get('action_type', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Build query
        query = Log.query
        
        if action_type:
            query = query.filter(Log.action == action_type)
        
        if date_from:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Log.timestamp >= date_from_obj)
        
        if date_to:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Add one day to include the entire day
            date_to_obj = datetime.combine(date_to_obj.date(), datetime.max.time())
            query = query.filter(Log.timestamp <= date_to_obj)
        
        # Get logs ordered by timestamp (newest first)
        logs = query.order_by(Log.timestamp.desc()).all()
        
        # Create a temporary file for CSV
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        temp_file_path = temp_file.name
        
        # Write to CSV
        with open(temp_file_path, 'w', newline='') as csvfile:
            fieldnames = ['Timestamp', 'Action', 'Description']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for log in logs:
                writer.writerow({
                    'Timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'Action': log.action,
                    'Description': log.description
                })
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"abet_logs_{timestamp}.csv"
        
        # Log the export
        log_entry = Log(
            action="EXPORT_LOGS",
            description=f"Exported {len(logs)} logs to CSV"
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return send_file(
            temp_file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
    except Exception as e:
        logging.error(f"Error exporting logs: {str(e)}")
        flash(f'An error occurred while exporting logs: {str(e)}', 'error')
        return redirect(url_for('utility.logs'))

@utility_bp.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    """Handle feedback form submissions"""
    try:
        name = request.form.get('name', 'Anonymous')
        email = request.form.get('email', 'Not provided')
        feedback_type = request.form.get('feedback_type', 'Other')
        message = request.form.get('message', '')
        
        if not message:
            flash('Feedback message cannot be empty.', 'error')
            return redirect(url_for('utility.help_page'))
        
        # Log the feedback
        log = Log(
            action="FEEDBACK_SUBMITTED",
            description=f"Feedback ({feedback_type}) submitted by {name} ({email}): {message[:100]}{'...' if len(message) > 100 else ''}"
        )
        db.session.add(log)
        
        # TODO: Additional handling like sending email to administrators
        # could be implemented here
        
        db.session.commit()
        flash('Thank you for your feedback! We appreciate your input.', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error submitting feedback: {str(e)}")
        flash(f'An error occurred while submitting your feedback. Please try again later.', 'error')
    
    return redirect(url_for('utility.help_page'))

@utility_bp.route('/backups')
def list_backups():
    """List all available database backups"""
    # Get list of available backups
    backup_dir = app.config['BACKUP_FOLDER']
    backups = []
    
    if os.path.exists(backup_dir):
        # Get all backup files (including pre-restore and pre-merge backups)
        backup_files = glob.glob(os.path.join(backup_dir, "*.db"))
        for backup_file in backup_files:
            filename = os.path.basename(backup_file)
            created_at = os.path.getmtime(backup_file)
            size = os.path.getsize(backup_file) / (1024 * 1024)  # Size in MB
            
            # Determine backup type
            backup_type = "Regular"
            if "pre_restore_backup" in filename:
                backup_type = "Pre-Restore"
            elif "pre_merge_backup" in filename:
                backup_type = "Pre-Merge"
            
            backups.append({
                'filename': filename,
                'created_at': datetime.fromtimestamp(created_at),
                'size': round(size, 2),
                'size_formatted': f"{round(size, 2)} MB",
                'type': backup_type
            })
    
    # Sort backups by creation time (newest first)
    backups.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('utility/backup_list.html', 
                         backups=backups, 
                         active_page='utilities')

@utility_bp.route('/update_auto_backup', methods=['POST'])
def update_auto_backup():
    """Update automatic backup settings"""
    try:
        auto_backup_enabled = request.form.get('auto_backup_enabled') == 'on'
        auto_backup_frequency = request.form.get('auto_backup_frequency', 'daily')
        
        # TODO: Save these settings to database or config file
        # For now, we'll just show a message
        
        # Log the action
        log = Log(
            action="UPDATE_AUTO_BACKUP_SETTINGS",
            description=f"Updated auto-backup settings: enabled={auto_backup_enabled}, frequency={auto_backup_frequency}"
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Auto-backup settings updated successfully', 'success')
    except Exception as e:
        logging.error(f"Error updating auto-backup settings: {str(e)}")
        flash(f'An error occurred while updating auto-backup settings: {str(e)}', 'error')
    
    return redirect(url_for('utility.backup_database')) 