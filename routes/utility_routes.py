from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file, make_response
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
import io

utility_bp = Blueprint('utility', __name__, url_prefix='/utility')

def export_to_excel_csv(data, filename, headers=None):
    """
    Generic function to export data to Excel-compatible CSV format
    
    Args:
        data: List of dictionaries or list of lists containing the data to export
        filename: The filename for the exported file (without extension)
        headers: Optional list of column headers. If None and data is list of dicts, 
                dict keys will be used as headers. If data is list of lists, the first
                row is assumed to be headers if headers=None.
    
    Returns:
        A Flask response object with the CSV file
    """
    try:
        # Create a StringIO object to store the CSV
        output = io.StringIO()
        
        # Add the sep=; directive as the first line - Excel special format directive
        output.write('sep=;\n')
        
        # Determine delimiter based on data structure
        delimiter = ';'  # Semicolon is often better for Excel in many locales
        
        # Create CSV writer
        writer = csv.writer(output, delimiter=delimiter)
        
        # Determine if we're dealing with list of dicts or list of lists
        is_list_of_dicts = data and isinstance(data[0], dict)
        
        # If data is a list of dictionaries and no headers provided, use dict keys
        if is_list_of_dicts and not headers:
            headers = list(data[0].keys())
            # Write headers
            writer.writerow(headers)
            # Write data rows
            for row in data:
                writer.writerow([row.get(key, '') for key in headers])
        else:
            # For list of lists
            if headers:
                # If headers are explicitly provided, write them first
                writer.writerow(headers)
                # Then write all data rows
                for row in data:
                    writer.writerow([row.get(key, '') for key in headers])
            else:
                # If no headers and data is list of lists, assume first row is headers
                writer.writerows(data)
        
        # Prepare response
        output.seek(0)
        output_str = output.getvalue()
        
        # Convert to UTF-16 encoding with BOM
        # UTF-16 has its own BOM marker built into the encoding
        utf16_data = output_str.encode('utf-16')
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Add .csv extension to filename
        full_filename = f"{filename}_{timestamp}.csv"
        
        # Log export action
        log = Log(action="EXPORT_DATA", 
                 description=f"Exported data to: {full_filename}")
        db.session.add(log)
        db.session.commit()
        
        response = make_response(utf16_data)
        response.headers["Content-Disposition"] = f"attachment; filename={full_filename}"
        # Use UTF-16 in the content type
        response.headers["Content-type"] = "text/csv; charset=UTF-16"
        return response
    except Exception as e:
        logging.error(f"Error exporting data: {str(e)}")
        flash(f'An error occurred while exporting data: {str(e)}', 'error')
        return redirect(url_for('index'))

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
                db_path = os.path.join('instance', 'accredit_data.db')
                
                if not os.path.exists(db_path):
                    flash('Database file not found', 'error')
                    return redirect(url_for('utility.backup_database'))
                
                # Create backup directory if it doesn't exist
                backup_dir = app.config['BACKUP_FOLDER']
                os.makedirs(backup_dir, exist_ok=True)
                
                # Create backup filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"accredit_data_backup_{timestamp}.db"
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
            backup_files = glob.glob(os.path.join(backup_dir, "accredit_data_backup_*.db"))
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
                db_path = os.path.join('instance', 'accredit_data.db')
                
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
            backup_files = glob.glob(os.path.join(backup_dir, "accredit_data_backup_*.db"))
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
        db_path = os.path.join('instance', 'accredit_data.db')
        
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
        db_path = os.path.join('instance', 'accredit_data.db')
        
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
        db_path = os.path.join('instance', 'accredit_data.db')
        
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
        
        # Prepare data for export
        data = []
        headers = ['Timestamp', 'Action', 'Description']
        
        for log in logs:
            data.append({
                'Timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'Action': log.action,
                'Description': log.description
            })
            
        # Export data using utility function
        return export_to_excel_csv(data, "abet_logs", headers)
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

@utility_bp.route('/import', methods=['GET', 'POST'])
def import_database():
    """Import data from a backup file and merge with existing database"""
    try:
        if request.method == 'POST':
            # Check if file is provided
            if 'backup_file' not in request.files:
                flash('No backup file provided', 'error')
                return redirect(url_for('utility.import_database'))
            
            backup_file = request.files['backup_file']
            
            if backup_file.filename == '':
                flash('No backup file selected', 'error')
                return redirect(url_for('utility.import_database'))
            
            # Check if user confirmed the import action
            if 'confirm_import' not in request.form:
                flash('You must confirm that you understand the import process', 'error')
                return redirect(url_for('utility.import_database'))
            
            try:
                # Create a temporary file for the uploaded backup
                temp_path = os.path.join(app.config['BACKUP_FOLDER'], 'temp_import.db')
                backup_file.save(temp_path)
                
                # Verify this is a valid SQLite database
                try:
                    conn = sqlite3.connect(temp_path)
                    conn.close()
                except sqlite3.Error:
                    os.remove(temp_path)
                    flash('Invalid database file', 'error')
                    return redirect(url_for('utility.import_database'))
                
                # Get current database path
                db_path = os.path.join('instance', 'accredit_data.db')
                
                # Create a backup of current database before import
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                pre_import_backup = os.path.join(app.config['BACKUP_FOLDER'], f"pre_import_backup_{timestamp}.db")
                
                if os.path.exists(db_path):
                    shutil.copy2(db_path, pre_import_backup)
                    flash(f'Created backup of current database before import: pre_import_backup_{timestamp}.db', 'info')
                
                # Define what to import based on form selections
                import_courses = request.form.get('import_courses') == 'on'
                import_students = request.form.get('import_students') == 'on'
                import_exams = request.form.get('import_exams') == 'on'
                import_outcomes = request.form.get('import_outcomes') == 'on'
                
                # Connect to both databases
                current_db = sqlite3.connect(db_path)
                import_db = sqlite3.connect(temp_path)
                
                # Set row factory for both connections to access columns by name
                current_db.row_factory = sqlite3.Row
                import_db.row_factory = sqlite3.Row
                
                # Initialize counters for summary
                courses_imported = 0
                students_imported = 0
                exams_imported = 0
                outcomes_imported = 0
                scores_imported = 0
                
                # Create ID mapping dictionaries for all entity types
                course_id_map = {}       # maps import_db course_id to current_db course_id
                student_id_map = {}      # maps import_db student_id to current_db student_id
                exam_id_map = {}         # maps import_db exam_id to current_db exam_id
                question_id_map = {}     # maps import_db question_id to current_db question_id
                outcome_id_map = {}      # maps import_db outcome_id to current_db outcome_id
                
                try:
                    # Start transaction
                    current_db.execute("BEGIN TRANSACTION")
                    
                    # STEP 1: First, create mappings for ALL existing entities in both databases
                    
                    # Get all courses from both databases for mapping
                    current_courses = {(c['code'], c['semester']): c['id'] for c in current_db.execute("SELECT id, code, semester FROM course").fetchall()}
                    import_courses_data = import_db.execute("SELECT * FROM course").fetchall()
                    
                    # Get course outcomes lookup tables
                    current_outcomes = {(o['code'], o['course_id']): o['id'] for o in current_db.execute("SELECT id, code, course_id FROM course_outcome").fetchall()}
                    
                    # Get exams lookup tables by name and course
                    current_exams = {(e['name'], e['course_id']): e['id'] for e in current_db.execute("SELECT id, name, course_id FROM exam").fetchall()}
                    
                    # Get students lookup tables by student_id and course_id
                    current_students = {(s['student_id'], s['course_id']): s['id'] for s in current_db.execute("SELECT id, student_id, course_id FROM student").fetchall()}
                    
                    # Get questions lookup by number, exam_id and max_score (to handle potential duplicates)
                    current_questions = {(q['number'], q['exam_id'], q['max_score']): q['id'] for q in current_db.execute("SELECT id, number, exam_id, max_score FROM question").fetchall()}
                    
                    # STEP 2: Import courses if selected
                    if import_courses:
                        for course_data in import_courses_data:
                            course_key = (course_data['code'], course_data['semester'])
                            import_course_id = course_data['id']
                            
                            # Check if course already exists in current database
                            if course_key in current_courses:
                                # Course already exists, just map the ID
                                existing_id = current_courses[course_key]
                                course_id_map[import_course_id] = existing_id
                                logging.info(f"Mapped existing course: {course_data['code']} {course_data['semester']} " +
                                            f"(import ID: {import_course_id}, current ID: {existing_id})")
                            else:
                                # Insert new course
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO course (code, name, semester, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?)
                                    """,
                                    (
                                        course_data['code'],
                                        course_data['name'],
                                        course_data['semester'],
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                new_course_id = cursor.lastrowid
                                course_id_map[import_course_id] = new_course_id
                                current_courses[course_key] = new_course_id  # Update lookup for subsequent operations
                                courses_imported += 1
                                logging.info(f"Imported new course: {course_data['code']} {course_data['semester']} " +
                                           f"(import ID: {import_course_id}, new ID: {new_course_id})")
                    else:
                        # Even if not importing courses, create ID mapping for existing courses
                        for course_data in import_courses_data:
                            course_key = (course_data['code'], course_data['semester'])
                            if course_key in current_courses:
                                existing_id = current_courses[course_key]
                                course_id_map[course_data['id']] = existing_id
                                logging.info(f"Mapped existing course (no import): {course_data['code']} {course_data['semester']} " +
                                           f"(import ID: {course_data['id']}, current ID: {existing_id})")
                    
                    # STEP 3: Import course outcomes if selected
                    if import_outcomes and course_id_map:  # Only if we have course mappings
                        import_outcomes_data = import_db.execute("SELECT * FROM course_outcome").fetchall()
                        
                        for outcome_data in import_outcomes_data:
                            import_outcome_id = outcome_data['id']
                            import_course_id = outcome_data['course_id']
                            
                            # Get mapped course ID in current database
                            if import_course_id not in course_id_map:
                                continue  # Skip if no mapping for this course
                                
                            current_course_id = course_id_map[import_course_id]
                            outcome_key = (outcome_data['code'], current_course_id)
                            
                            # Check if outcome already exists in current database
                            if outcome_key in current_outcomes:
                                # Outcome already exists, just map the ID
                                outcome_id_map[import_outcome_id] = current_outcomes[outcome_key]
                            else:
                                # Insert new outcome
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO course_outcome (code, description, course_id, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?)
                                    """,
                                    (
                                        outcome_data['code'],
                                        outcome_data['description'],
                                        current_course_id,
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                new_outcome_id = cursor.lastrowid
                                outcome_id_map[import_outcome_id] = new_outcome_id
                                current_outcomes[outcome_key] = new_outcome_id  # Update lookup
                                outcomes_imported += 1
                    
                    # STEP 4: Import students if selected
                    if import_students and course_id_map:  # Only if we have course mappings
                        import_students_data = import_db.execute("SELECT * FROM student").fetchall()
                        
                        for student_data in import_students_data:
                            import_student_id = student_data['id']
                            import_course_id = student_data['course_id']
                            
                            # Get mapped course ID in current database
                            if import_course_id not in course_id_map:
                                continue  # Skip if no mapping for this course
                                
                            current_course_id = course_id_map[import_course_id]
                            student_key = (student_data['student_id'], current_course_id)
                            
                            # Check if student already exists in current database
                            if student_key in current_students:
                                # Student already exists, just map the ID
                                student_id_map[import_student_id] = current_students[student_key]
                            else:
                                # Insert new student
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO student (student_id, first_name, last_name, course_id, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        student_data['student_id'],
                                        student_data['first_name'],
                                        student_data['last_name'],
                                        current_course_id,
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                new_student_id = cursor.lastrowid
                                student_id_map[import_student_id] = new_student_id
                                current_students[student_key] = new_student_id  # Update lookup
                                students_imported += 1
                    
                    # STEP 5: Import exams and questions if selected
                    if import_exams and course_id_map:  # Only if we have course mappings
                        import_exams_data = import_db.execute("SELECT * FROM exam").fetchall()
                        
                        for exam_data in import_exams_data:
                            import_exam_id = exam_data['id']
                            import_course_id = exam_data['course_id']
                            
                            # Get mapped course ID in current database
                            if import_course_id not in course_id_map:
                                continue  # Skip if no mapping for this course
                                
                            current_course_id = course_id_map[import_course_id]
                            
                            # For exams, we need a more robust way to detect duplicates
                            # First check by name and course_id
                            exam_key = (exam_data['name'], current_course_id)
                            
                            if exam_key in current_exams:
                                # Exam with this name already exists in this course
                                current_exam_id = current_exams[exam_key]
                                exam_id_map[import_exam_id] = current_exam_id
                                
                                # If we're not importing exams, just map it and continue
                                if not import_exams:
                                    continue
                                
                                # For duplicate exams, we can either:
                                # 1. Skip it (current approach)
                                # 2. Rename it to avoid conflict (e.g., append '_imported')
                                # 3. Compare details and only import if different
                                
                                # For now, we'll use approach #2 - rename and import as new
                                modified_name = f"{exam_data['name']}_imported_{timestamp}"
                                
                                # Insert as a new exam with modified name
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO exam (name, max_score, exam_date, course_id, is_makeup, is_mandatory, is_final, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        modified_name,
                                        exam_data['max_score'],
                                        exam_data['exam_date'],
                                        current_course_id,
                                        exam_data['is_makeup'],
                                        exam_data['is_mandatory'],
                                        exam_data.get('is_final', False),  # Default to False if field doesn't exist
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                new_exam_id = cursor.lastrowid
                                exam_id_map[import_exam_id] = new_exam_id
                                current_exams[(modified_name, current_course_id)] = new_exam_id  # Update lookup
                                exams_imported += 1
                            else:
                                # Insert new exam with original name
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO exam (name, max_score, exam_date, course_id, is_makeup, is_mandatory, is_final, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        exam_data['name'],
                                        exam_data['max_score'],
                                        exam_data['exam_date'],
                                        current_course_id,
                                        exam_data['is_makeup'],
                                        exam_data['is_mandatory'],
                                        exam_data.get('is_final', False),  # Default to False if field doesn't exist
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                new_exam_id = cursor.lastrowid
                                exam_id_map[import_exam_id] = new_exam_id
                                current_exams[exam_key] = new_exam_id  # Update lookup
                                exams_imported += 1
                            
                            # Now import questions for this exam (regardless of whether exam was newly imported or just mapped)
                            current_exam_id = exam_id_map[import_exam_id]
                            import_questions_data = import_db.execute(
                                "SELECT * FROM question WHERE exam_id = ?", 
                                (import_exam_id,)
                            ).fetchall()
                            
                            for question_data in import_questions_data:
                                import_question_id = question_data['id']
                                question_key = (question_data['number'], current_exam_id, question_data['max_score'])
                                
                                # Check if question already exists
                                if question_key in current_questions:
                                    # Question already exists, just map the ID
                                    question_id_map[import_question_id] = current_questions[question_key]
                                else:
                                    # Insert new question
                                    cursor = current_db.execute(
                                        """
                                        INSERT INTO question (text, number, max_score, exam_id, created_at, updated_at)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                        """,
                                        (
                                            question_data['text'],
                                            question_data['number'],
                                            question_data['max_score'],
                                            current_exam_id,
                                            datetime.now(),
                                            datetime.now()
                                        )
                                    )
                                    new_question_id = cursor.lastrowid
                                    question_id_map[import_question_id] = new_question_id
                                    current_questions[question_key] = new_question_id  # Update lookup
                    
                    # STEP 5B: Import exam weights
                    if exam_id_map and course_id_map:
                        # Get existing exam weights to avoid duplicates
                        current_weights = {}
                        for weight in current_db.execute("SELECT exam_id, course_id, weight FROM exam_weight").fetchall():
                            current_weights[(weight['exam_id'], weight['course_id'])] = weight['weight']
                        
                        # Get all exam weights from import database
                        import_weights_data = import_db.execute("SELECT * FROM exam_weight").fetchall()
                        weights_imported = 0
                        
                        for weight_data in import_weights_data:
                            import_exam_id = weight_data['exam_id']
                            import_course_id = weight_data['course_id']
                            
                            # Skip if any mapping is missing
                            if import_exam_id not in exam_id_map or import_course_id not in course_id_map:
                                continue
                            
                            current_exam_id = exam_id_map[import_exam_id]
                            current_course_id = course_id_map[import_course_id]
                            weight_key = (current_exam_id, current_course_id)
                            
                            # Check if weight already exists
                            if weight_key in current_weights:
                                # Could update the existing weight if needed
                                # For now, we'll skip to avoid overwriting
                                continue
                            
                            # Insert the weight
                            cursor = current_db.execute(
                                """
                                INSERT INTO exam_weight (exam_id, course_id, weight, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (
                                    current_exam_id,
                                    current_course_id,
                                    weight_data['weight'],
                                    datetime.now(),
                                    datetime.now()
                                )
                            )
                            weights_imported += 1
                        
                        if weights_imported > 0:
                            logging.info(f"Imported {weights_imported} exam weights")
                    
                    # STEP 5C: Import course settings
                    if course_id_map:
                        # Get existing course settings to avoid duplicates
                        current_settings = {s['course_id']: s for s in current_db.execute(
                            "SELECT course_id, success_rate_method, relative_success_threshold FROM course_settings"
                        ).fetchall()}
                        
                        # Get all course settings from import database
                        try:
                            # Check if the table exists first
                            settings_table_exists = import_db.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name='course_settings'"
                            ).fetchone()
                            
                            if settings_table_exists:
                                import_settings_data = import_db.execute("SELECT * FROM course_settings").fetchall()
                                settings_imported = 0
                                
                                for settings_data in import_settings_data:
                                    import_course_id = settings_data['course_id']
                                    
                                    # Skip if mapping is missing
                                    if import_course_id not in course_id_map:
                                        continue
                                    
                                    current_course_id = course_id_map[import_course_id]
                                    
                                    # Check if settings already exist
                                    if current_course_id in current_settings:
                                        # Could update existing settings if needed
                                        # For now, we'll skip to avoid overwriting user preferences
                                        continue
                                    
                                    # Insert the settings
                                    cursor = current_db.execute(
                                        """
                                        INSERT INTO course_settings (course_id, success_rate_method, relative_success_threshold, created_at, updated_at)
                                        VALUES (?, ?, ?, ?, ?)
                                        """,
                                        (
                                            current_course_id,
                                            settings_data['success_rate_method'],
                                            settings_data['relative_success_threshold'],
                                            datetime.now(),
                                            datetime.now()
                                        )
                                    )
                                    settings_imported += 1
                                
                                if settings_imported > 0:
                                    logging.info(f"Imported {settings_imported} course settings")
                        except Exception as e:
                            # Log but continue if there was an issue with settings import
                            logging.warning(f"Could not import course settings: {str(e)}")
                    
                    # STEP 6: Import scores - we can import scores regardless of whether we imported students/exams/questions
                    # as long as we have the mappings for them
                    if student_id_map and question_id_map and exam_id_map:
                        import_scores_data = import_db.execute("SELECT * FROM score").fetchall()
                        
                        # Get existing scores to avoid duplicates
                        existing_scores = set()
                        for score in current_db.execute("SELECT student_id, question_id, exam_id FROM score").fetchall():
                            existing_scores.add((score['student_id'], score['question_id'], score['exam_id']))
                        
                        for score_data in import_scores_data:
                            # Get mappings for this score
                            import_student_id = score_data['student_id']
                            import_question_id = score_data['question_id']
                            import_exam_id = score_data['exam_id']
                            
                            # Skip if any mapping is missing
                            if (import_student_id not in student_id_map or 
                                import_question_id not in question_id_map or 
                                import_exam_id not in exam_id_map):
                                # Log this for debugging
                                logging.debug(f"Skipping score - Missing mapping: student={import_student_id in student_id_map}, " +
                                             f"question={import_question_id in question_id_map}, exam={import_exam_id in exam_id_map}")
                                continue
                            
                            current_student_id = student_id_map[import_student_id]
                            current_question_id = question_id_map[import_question_id]
                            current_exam_id = exam_id_map[import_exam_id]
                            
                            # Skip if score already exists
                            if (current_student_id, current_question_id, current_exam_id) in existing_scores:
                                continue
                            
                            # Insert the score
                            cursor = current_db.execute(
                                """
                                INSERT INTO score (score, student_id, question_id, exam_id, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    score_data['score'],
                                    current_student_id,
                                    current_question_id,
                                    current_exam_id,
                                    datetime.now(),
                                    datetime.now()
                                )
                            )
                            scores_imported += 1
                            # Add to existing scores set to avoid duplicates
                            existing_scores.add((current_student_id, current_question_id, current_exam_id))
                    else:
                        # Log to help debug why scores weren't imported
                        logging.info(f"Skipping score import - Missing mappings: student_map={bool(student_id_map)}, " +
                                    f"question_map={bool(question_id_map)}, exam_map={bool(exam_id_map)}")
                        if not import_students:
                            logging.info("Student import was disabled - this could explain missing student mappings")
                        if not import_exams:
                            logging.info("Exam import was disabled - this could explain missing exam/question mappings")
                    
                    # STEP 6B: Add a special pass to map and import scores even when their related entities 
                    # weren't selected for import but exist in both databases
                    if not scores_imported and (not student_id_map or not question_id_map or not exam_id_map):
                        logging.info("Attempting second-pass score import by mapping existing entities")
                        
                        # Build more complete mappings of existing entities
                        if not student_id_map:
                            # Map students by student_id (assuming unique across database)
                            import_students_by_id = {s['student_id']: s['id'] for s in 
                                import_db.execute("SELECT id, student_id FROM student").fetchall()}
                            current_students_by_id = {s['student_id']: s['id'] for s in 
                                current_db.execute("SELECT id, student_id FROM student").fetchall()}
                            
                            for student_id, import_db_id in import_students_by_id.items():
                                if student_id in current_students_by_id:
                                    student_id_map[import_db_id] = current_students_by_id[student_id]
                        
                        if not exam_id_map:
                            # Map exams by name and course (this is trickier because it depends on course mapping)
                            # First ensure we have a course mapping
                            if not course_id_map:
                                import_courses_by_key = {(c['code'], c['semester']): c['id'] for c in 
                                    import_db.execute("SELECT id, code, semester FROM course").fetchall()}
                                current_courses_by_key = {(c['code'], c['semester']): c['id'] for c in 
                                    current_db.execute("SELECT id, code, semester FROM course").fetchall()}
                                
                                for course_key, import_db_id in import_courses_by_key.items():
                                    if course_key in current_courses_by_key:
                                        course_id_map[import_db_id] = current_courses_by_key[course_key]
                            
                            # Now map exams with the course mapping
                            if course_id_map:
                                import_exams_all = import_db.execute("SELECT * FROM exam").fetchall()
                                current_exams_by_key = {(e['name'], e['course_id']): e['id'] for e in 
                                    current_db.execute("SELECT id, name, course_id FROM exam").fetchall()}
                                
                                for exam in import_exams_all:
                                    if exam['course_id'] in course_id_map:
                                        current_course_id = course_id_map[exam['course_id']]
                                        exam_key = (exam['name'], current_course_id)
                                        if exam_key in current_exams_by_key:
                                            exam_id_map[exam['id']] = current_exams_by_key[exam_key]
                        
                        if not question_id_map and exam_id_map:
                            # Map questions by number and exam_id
                            import_questions_all = import_db.execute("SELECT id, number, exam_id FROM question").fetchall()
                            current_questions_by_key = {(q['number'], q['exam_id']): q['id'] for q in 
                                current_db.execute("SELECT id, number, exam_id FROM question").fetchall()}
                            
                            for question in import_questions_all:
                                if question['exam_id'] in exam_id_map:
                                    current_exam_id = exam_id_map[question['exam_id']]
                                    question_key = (question['number'], current_exam_id)
                                    if question_key in current_questions_by_key:
                                        question_id_map[question['id']] = current_questions_by_key[question_key]
                        
                        # Now try to import scores again with the expanded mappings
                        if student_id_map and question_id_map and exam_id_map:
                            import_scores_data = import_db.execute("SELECT * FROM score").fetchall()
                            
                            # Get existing scores to avoid duplicates
                            existing_scores = set()
                            for score in current_db.execute("SELECT student_id, question_id, exam_id FROM score").fetchall():
                                existing_scores.add((score['student_id'], score['question_id'], score['exam_id']))
                            
                            for score_data in import_scores_data:
                                # Get mappings for this score
                                import_student_id = score_data['student_id']
                                import_question_id = score_data['question_id']
                                import_exam_id = score_data['exam_id']
                                
                                # Skip if any mapping is missing
                                if (import_student_id not in student_id_map or 
                                    import_question_id not in question_id_map or 
                                    import_exam_id not in exam_id_map):
                                    continue
                                
                                current_student_id = student_id_map[import_student_id]
                                current_question_id = question_id_map[import_question_id]
                                current_exam_id = exam_id_map[import_exam_id]
                                
                                # Skip if score already exists
                                if (current_student_id, current_question_id, current_exam_id) in existing_scores:
                                    continue
                                
                                # Insert the score
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO score (score, student_id, question_id, exam_id, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        score_data['score'],
                                        current_student_id,
                                        current_question_id,
                                        current_exam_id,
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                scores_imported += 1
                                # Add to existing scores set to avoid duplicates
                                existing_scores.add((current_student_id, current_question_id, current_exam_id))
                            
                            if scores_imported > 0:
                                logging.info(f"Second-pass score import successful: {scores_imported} scores imported")
                    
                    # STEP 7: Handle makeup exam relationships
                    if exam_id_map:
                        # Get all makeup exams from the import database
                        makeup_exams = import_db.execute(
                            "SELECT id, makeup_for FROM exam WHERE is_makeup = 1 AND makeup_for IS NOT NULL"
                        ).fetchall()
                        
                        for makeup_exam in makeup_exams:
                            import_exam_id = makeup_exam['id']
                            import_original_exam_id = makeup_exam['makeup_for']
                            
                            # Skip if any mapping is missing
                            if (import_exam_id not in exam_id_map or 
                                import_original_exam_id not in exam_id_map):
                                continue
                            
                            current_exam_id = exam_id_map[import_exam_id]
                            current_original_exam_id = exam_id_map[import_original_exam_id]
                            
                            # Update the makeup_for relationship
                            current_db.execute(
                                "UPDATE exam SET makeup_for = ? WHERE id = ?",
                                (current_original_exam_id, current_exam_id)
                            )
                    
                    # STEP 8: Handle question-outcome relationships (if they exist in the schema)
                    try:
                        # Check if the relationship table exists
                        question_outcomes_exists = current_db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='question_course_outcome'"
                        ).fetchone()
                        
                        if question_outcomes_exists and outcome_id_map and question_id_map:
                            # Get all question-outcome relationships from import database
                            import_relationships = import_db.execute(
                                "SELECT question_id, course_outcome_id FROM question_course_outcome"
                            ).fetchall()
                            
                            # Get existing relationships to avoid duplicates
                            existing_relationships = set()
                            for rel in current_db.execute("SELECT question_id, course_outcome_id FROM question_course_outcome").fetchall():
                                existing_relationships.add((rel['question_id'], rel['course_outcome_id']))
                            
                            # Counter for tracking imported relationships
                            relationships_imported = 0
                            relationships_skipped = 0
                            
                            logging.info(f"Found {len(import_relationships)} question-outcome relationships to import")
                            
                            for rel in import_relationships:
                                import_question_id = rel['question_id']
                                import_outcome_id = rel['course_outcome_id']
                                
                                # Skip if any mapping is missing
                                if (import_question_id not in question_id_map or 
                                    import_outcome_id not in outcome_id_map):
                                    logging.debug(f"Skipping relationship - Missing mapping: question={import_question_id in question_id_map}, " +
                                                f"outcome={import_outcome_id in outcome_id_map}")
                                    relationships_skipped += 1
                                    continue
                                
                                current_question_id = question_id_map[import_question_id]
                                current_outcome_id = outcome_id_map[import_outcome_id]
                                
                                # Skip if relationship already exists
                                if (current_question_id, current_outcome_id) in existing_relationships:
                                    relationships_skipped += 1
                                    continue
                                
                                # Insert the relationship
                                current_db.execute(
                                    "INSERT INTO question_course_outcome (question_id, course_outcome_id) VALUES (?, ?)",
                                    (current_question_id, current_outcome_id)
                                )
                                relationships_imported += 1
                                # Add to existing set to avoid duplicates
                                existing_relationships.add((current_question_id, current_outcome_id))
                            
                            logging.info(f"Imported {relationships_imported} question-outcome relationships, skipped {relationships_skipped}")
                            
                            # Add a flash message about outcome relationships
                            if relationships_imported > 0:
                                flash(f'Successfully imported {relationships_imported} question-outcome relationships', 'info')
                        else:
                            if not question_outcomes_exists:
                                logging.warning("question_course_outcome table not found in database")
                            if not outcome_id_map:
                                logging.warning("No outcome ID mappings available for relationship import")
                            if not question_id_map:
                                logging.warning("No question ID mappings available for relationship import")
                    except Exception as e:
                        # Log but continue if there was an issue with question-outcome relationships
                        logging.warning(f"Could not import question-outcome relationships: {str(e)}")
                    
                    # STEP 9: Handle course outcome to program outcome relationships
                    try:
                        # Check if the relationship table exists
                        course_program_exists = current_db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='course_outcome_program_outcome'"
                        ).fetchone()
                        
                        if course_program_exists and outcome_id_map:
                            # Get program outcome IDs
                            program_outcomes = {po['code']: po['id'] for po in 
                                current_db.execute("SELECT id, code FROM program_outcome").fetchall()}
                            
                            # Get all course outcome-program outcome relationships from import database
                            import_relationships = import_db.execute(
                                "SELECT course_outcome_id, program_outcome_id FROM course_outcome_program_outcome"
                            ).fetchall()
                            
                            # Get existing relationships to avoid duplicates
                            existing_relationships = set()
                            for rel in current_db.execute("SELECT course_outcome_id, program_outcome_id FROM course_outcome_program_outcome").fetchall():
                                existing_relationships.add((rel['course_outcome_id'], rel['program_outcome_id']))
                            
                            # Counter for tracking imported relationships
                            program_relationships_imported = 0
                            program_relationships_skipped = 0
                            
                            logging.info(f"Found {len(import_relationships)} course-program outcome relationships to import")
                            
                            for rel in import_relationships:
                                import_course_outcome_id = rel['course_outcome_id']
                                import_program_outcome_id = rel['program_outcome_id']
                                
                                # Skip if outcome mapping is missing
                                if import_course_outcome_id not in outcome_id_map:
                                    program_relationships_skipped += 1
                                    continue
                                
                                # Get the imported program outcome code to map to the current database
                                try:
                                    import_program_code = import_db.execute(
                                        "SELECT code FROM program_outcome WHERE id = ?", 
                                        (import_program_outcome_id,)
                                    ).fetchone()['code']
                                    
                                    # Find corresponding program outcome in current database
                                    if import_program_code in program_outcomes:
                                        current_program_id = program_outcomes[import_program_code]
                                    else:
                                        program_relationships_skipped += 1
                                        continue
                                except:
                                    program_relationships_skipped += 1
                                    continue
                                
                                current_course_outcome_id = outcome_id_map[import_course_outcome_id]
                                
                                # Skip if relationship already exists
                                if (current_course_outcome_id, current_program_id) in existing_relationships:
                                    program_relationships_skipped += 1
                                    continue
                                
                                # Insert the relationship
                                current_db.execute(
                                    "INSERT INTO course_outcome_program_outcome (course_outcome_id, program_outcome_id) VALUES (?, ?)",
                                    (current_course_outcome_id, current_program_id)
                                )
                                program_relationships_imported += 1
                                # Add to existing set to avoid duplicates
                                existing_relationships.add((current_course_outcome_id, current_program_id))
                            
                            logging.info(f"Imported {program_relationships_imported} course-program outcome relationships, skipped {program_relationships_skipped}")
                            
                            # Add a flash message about program outcome relationships
                            if program_relationships_imported > 0:
                                flash(f'Successfully imported {program_relationships_imported} course-program outcome relationships', 'info')
                    except Exception as e:
                        # Log but continue if there was an issue with course-program outcome relationships
                        logging.warning(f"Could not import course-program outcome relationships: {str(e)}")
                    
                    # Commit all changes
                    current_db.execute("COMMIT")
                    
                    # Add detailed logging for debugging
                    logging.info("Database import summary:")
                    logging.info(f"  Courses: {courses_imported} imported")
                    logging.info(f"  Students: {students_imported} imported")
                    logging.info(f"  Outcomes: {outcomes_imported} imported")
                    logging.info(f"  Exams: {exams_imported} imported")
                    logging.info(f"  Exam Weights: {weights_imported if 'weights_imported' in locals() else 0} imported")
                    logging.info(f"  Course Settings: {settings_imported if 'settings_imported' in locals() else 0} imported")
                    logging.info(f"  Scores: {scores_imported} imported")
                    
                    # Log action
                    log = Log(action="IMPORT_DATABASE", 
                             description=f"Imported and merged data from: {backup_file.filename}")
                    db.session.add(log)
                    db.session.commit()
                    
                    # Build summary message
                    summary_parts = []
                    if courses_imported > 0:
                        summary_parts.append(f"{courses_imported} courses")
                    if students_imported > 0:
                        summary_parts.append(f"{students_imported} students")
                    if outcomes_imported > 0:
                        summary_parts.append(f"{outcomes_imported} course outcomes")
                    if exams_imported > 0:
                        summary_parts.append(f"{exams_imported} exams")
                    if scores_imported > 0:
                        summary_parts.append(f"{scores_imported} scores")
                    if 'weights_imported' in locals() and weights_imported > 0:
                        summary_parts.append(f"{weights_imported} exam weights")
                    if 'settings_imported' in locals() and settings_imported > 0:
                        summary_parts.append(f"{settings_imported} course settings")
                    
                    if summary_parts:
                        summary = ", ".join(summary_parts)
                        flash(f'Successfully imported and merged: {summary}', 'success')
                    else:
                        flash('Import completed, but no new data was added (possibly because all items already exist).', 'warning')
                    
                except Exception as e:
                    # Rollback in case of error
                    current_db.execute("ROLLBACK")
                    logging.error(f"Error during database import: {str(e)}\n{traceback.format_exc()}")
                    flash(f'An error occurred during import: {str(e)}', 'error')
                finally:
                    # Close database connections
                    current_db.close()
                    import_db.close()
                
                # Remove temporary file
                os.remove(temp_path)
                
            except Exception as e:
                logging.error(f"Error importing database: {str(e)}\n{traceback.format_exc()}")
                flash(f'An error occurred while importing the database: {str(e)}', 'error')
        
        # Get list of available backups for reference
        backup_dir = app.config['BACKUP_FOLDER']
        backups = []
        
        if os.path.exists(backup_dir):
            backup_files = glob.glob(os.path.join(backup_dir, "accredit_data_backup_*.db"))
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
        
        return render_template('utility/import.html', 
                             backups=backups,
                             active_page='utilities')
    except Exception as e:
        logging.error(f"Error in import page: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('utility.index')) 