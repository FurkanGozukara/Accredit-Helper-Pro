from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file, make_response
from flask import current_app, Markup
from app import db
from models import Log, Course, Student, Exam, CourseOutcome, Question, Score, ExamWeight, StudentExamAttendance, ProgramOutcome
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
import json
from sqlalchemy import text
from sqlalchemy.orm import Session
import time
from sqlalchemy.orm import scoped_session, sessionmaker

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
                if is_list_of_dicts:
                    for row in data:
                        writer.writerow([row.get(key, '') for key in headers])
                else:
                    # If data is list of lists, just write the data directly
                    for row in data:
                        writer.writerow(row)
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
                backup_dir = current_app.config['BACKUP_FOLDER']
                os.makedirs(backup_dir, exist_ok=True)
                
                # Create backup filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"accredit_data_backup_{timestamp}.db"
                backup_path = os.path.join(backup_dir, backup_filename)
                
                # Copy database file
                shutil.copy2(db_path, backup_path)
                
                # Get and save the custom description
                description = request.form.get('description', '').strip()
                
                # Load existing backup descriptions or create new if not exists
                descriptions_file = os.path.join(backup_dir, 'backup_descriptions.json')
                descriptions = {}
                if os.path.exists(descriptions_file):
                    try:
                        with open(descriptions_file, 'r') as f:
                            descriptions = json.load(f)
                    except json.JSONDecodeError:
                        # Handle case where file exists but is invalid JSON
                        descriptions = {}
                
                # Save the description for this backup
                descriptions[backup_filename] = description
                
                # Write back to the file
                with open(descriptions_file, 'w') as f:
                    json.dump(descriptions, f)
                
                # Log action
                log = Log(action="BACKUP_DATABASE", 
                        description=f"Created database backup: {backup_filename}" + 
                        (f" with description: {description}" if description else ""))
                db.session.add(log)
                db.session.commit()
                
                flash(f'Database backup created successfully: {backup_filename}', 'success')
            except Exception as e:
                logging.error(f"Error creating backup: {str(e)}")
                flash(f'An error occurred while creating the backup: {str(e)}', 'error')
        
        # Get list of available backups
        backup_dir = current_app.config['BACKUP_FOLDER']
        backups = []
        
        # Load backup descriptions
        descriptions_file = os.path.join(backup_dir, 'backup_descriptions.json')
        descriptions = {}
        if os.path.exists(descriptions_file):
            try:
                with open(descriptions_file, 'r') as f:
                    descriptions = json.load(f)
            except json.JSONDecodeError:
                # Handle corrupt JSON file
                descriptions = {}
        
        if os.path.exists(backup_dir):
            backup_files = glob.glob(os.path.join(backup_dir, "*.db"))
            for backup_file in backup_files:
                filename = os.path.basename(backup_file)
                created_at = os.path.getmtime(backup_file)
                size = os.path.getsize(backup_file) / (1024 * 1024)  # Size in MB
                
                # Add backup type information
                backup_type = "Regular"
                if "pre_import_backup" in filename:
                    backup_type = "Pre-Import"
                elif "pre_restore_backup" in filename:
                    backup_type = "Pre-Restore"
                elif "pre_merge_backup" in filename:
                    backup_type = "Pre-Merge"
                
                # Get custom description if available, otherwise use backup type
                custom_description = descriptions.get(filename, '')
                display_description = custom_description if custom_description else backup_type
                
                backups.append({
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(created_at),
                    'size': round(size, 2),
                    'size_formatted': f"{round(size, 2)} MB",
                    'type': backup_type,  # Keep type for color coding
                    'description': display_description  # Use custom description if available
                })
        
        # Sort backups by creation time (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Set the total backups and last backup for the template
        total_backups = len(backups)
        last_backup = backups[0] if backups else None
        
        return render_template('utility/backup.html', 
                            backups=backups,
                            total_backups=total_backups,
                            last_backup=last_backup,
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

@utility_bp.route('/backup/download/<filename>', methods=['GET'])
def download_backup(filename):
    """Download a backup file"""
    try:
        backup_dir = current_app.config['BACKUP_FOLDER']
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
    except Exception as e:
        logging.error(f"Error downloading backup: {str(e)}")
        flash(f'An error occurred while downloading the backup: {str(e)}', 'error')
        return redirect(url_for('utility.backup_database'))

@utility_bp.route('/backup/delete/<filename>', methods=['POST'])
def delete_backup(filename):
    """Delete a database backup"""
    try:
        backup_dir = current_app.config['BACKUP_FOLDER']
        backup_path = os.path.join(backup_dir, filename)
        
        if not os.path.exists(backup_path):
            flash('Backup file not found', 'error')
            return redirect(url_for('utility.backup_database'))
        
        # Delete backup file
        os.remove(backup_path)
        
        # Also remove the entry from descriptions if it exists
        descriptions_file = os.path.join(backup_dir, 'backup_descriptions.json')
        if os.path.exists(descriptions_file):
            try:
                with open(descriptions_file, 'r') as f:
                    descriptions = json.load(f)
                
                # Remove the description for this backup if it exists
                if filename in descriptions:
                    del descriptions[filename]
                
                # Write back to the file
                with open(descriptions_file, 'w') as f:
                    json.dump(descriptions, f)
            except Exception as e:
                logging.error(f"Error updating backup descriptions: {str(e)}")
        
        # Log action
        log = Log(action="DELETE_BACKUP", description=f"Deleted backup: {filename}")
        db.session.add(log)
        db.session.commit()
        
        flash(f'Backup file {filename} deleted successfully', 'success')
    except Exception as e:
        logging.error(f"Error deleting backup: {str(e)}")
        flash(f'An error occurred while deleting the backup: {str(e)}', 'error')
    
    return redirect(url_for('utility.backup_database'))

def refresh_database_session():
    """Refresh the database session after a database restore"""
    try:
        logging.info("Refreshing database session after restore")
        
        # Close any existing connections
        db.session.close()
        
        # Get the engine and dispose of it to close all connections
        try:
            engine = db.get_engine()
            engine.dispose()
        except Exception as e:
            logging.warning(f"Error disposing engine, continuing with refresh: {str(e)}")
        
        # Create a new scoped session
        try:
            from sqlalchemy.orm import scoped_session, sessionmaker
            engine = db.get_engine(app=current_app)
            session_factory = sessionmaker(bind=engine)
            db.session = scoped_session(session_factory)
            
            # Test if it worked
            if db.session.execute(text("SELECT 1")).scalar() == 1:
                logging.info("Database session successfully refreshed")
                return True
            else:
                logging.error("Failed to execute test query after session refresh")
                return False
        except Exception as e:
            logging.error(f"Error refreshing database session: {str(e)}\n{traceback.format_exc()}")
            return False
    except Exception as e:
        logging.error(f"Error refreshing database session: {str(e)}\n{traceback.format_exc()}")
        return False

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
                temp_path = os.path.join(current_app.config['BACKUP_FOLDER'], 'temp_restore.db')
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
                pre_restore_backup = os.path.join(current_app.config['BACKUP_FOLDER'], f"pre_restore_backup_{timestamp}.db")
                
                if os.path.exists(db_path):
                    shutil.copy2(db_path, pre_restore_backup)
                
                # Close the current database connection
                db.session.close()
                
                # Copy the backup file to the database location
                shutil.copy2(temp_path, db_path)
                
                # Remove temporary file
                os.remove(temp_path)
                
                # Refresh the database session
                if refresh_database_session():
                    # Log action using the refreshed session
                    log = Log(
                        action="RESTORE_DATABASE", 
                        description=f"Restored database from uploaded backup: {backup_file.filename}",
                        timestamp=datetime.now()
                    )
                    db.session.add(log)
                    db.session.commit()
                    
                    flash('Database restored successfully. The database session has been refreshed.', 'success')
                else:
                    # Still log the action, but with a different connection since refresh failed
                    engine = db.get_engine()
                    connection = engine.connect()
                    connection.execute(text("INSERT INTO log (action, description, timestamp) VALUES (:action, :description, :timestamp)"), 
                                    {"action": "RESTORE_DATABASE", 
                                     "description": f"Restored database from uploaded backup: {backup_file.filename}. Session refresh failed.", 
                                     "timestamp": datetime.now()})
                    connection.commit()
                    connection.close()
                    
                    flash('Database restored successfully, but session refresh failed. Please restart the application.', 'warning')
            except Exception as e:
                logging.error(f"Error restoring database: {str(e)}\n{traceback.format_exc()}")
                flash(f'An error occurred while restoring the database: {str(e)}', 'error')
        
        # Get list of available backups for restoration
        backup_dir = current_app.config['BACKUP_FOLDER']
        backups = []
        
        # Load backup descriptions
        descriptions_file = os.path.join(backup_dir, 'backup_descriptions.json')
        descriptions = {}
        if os.path.exists(descriptions_file):
            try:
                with open(descriptions_file, 'r') as f:
                    descriptions = json.load(f)
            except json.JSONDecodeError:
                # Handle corrupt JSON file
                descriptions = {}
        
        if os.path.exists(backup_dir):
            backup_files = glob.glob(os.path.join(backup_dir, "accredit_data_backup_*.db"))
            # Add pre-restore and pre-import backups to the list
            backup_files.extend(glob.glob(os.path.join(backup_dir, "pre_restore_backup_*.db")))
            backup_files.extend(glob.glob(os.path.join(backup_dir, "pre_import_backup_*.db")))
            for backup_file in backup_files:
                filename = os.path.basename(backup_file)
                created_at = os.path.getmtime(backup_file)
                size = os.path.getsize(backup_file) / (1024 * 1024)  # Size in MB
                
                # Add backup type information
                backup_type = "Regular"
                if "pre_import_backup" in filename:
                    backup_type = "Pre-Import"
                elif "pre_restore_backup" in filename:
                    backup_type = "Pre-Restore"
                
                backups.append({
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(created_at),
                    'size': round(size, 2),
                    'size_formatted': f"{round(size, 2)} MB",
                    'type': backup_type,
                    'description': descriptions.get(filename, backup_type)
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
        temp_path = os.path.join(current_app.config['BACKUP_FOLDER'], 'temp_restore.db')
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
        pre_restore_backup = os.path.join(current_app.config['BACKUP_FOLDER'], f"pre_restore_backup_{timestamp}.db")
        
        if os.path.exists(db_path):
            shutil.copy2(db_path, pre_restore_backup)
            flash(f'Created backup of current database before restore: pre_restore_backup_{timestamp}.db', 'info')
        
        # Close all existing database connections to ensure clean restore
        db.session.close()
        engine = db.get_engine()
        engine.dispose()
        
        # Copy the backup file to the database location
        try:
            # Use direct file copy for better performance
            shutil.copy2(temp_path, db_path)
            
            # Remove temporary file
            os.remove(temp_path)
            
            # Refresh the database session
            if refresh_database_session():
                # Log action using the refreshed session
                log = Log(
                    action="RESTORE_DATABASE", 
                    description=f"Restored database from uploaded file: {backup_file.filename}",
                    timestamp=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
                
                # Reload all models to ensure they reflect the restored database schema
                from importlib import reload
                import models
                reload(models)
                
                # Return JSON response for frontend to handle refresh
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'message': 'Database restored successfully. Please wait while the application refreshes.',
                        'refresh': True,
                        'force_reload': True
                    })
                
                flash('Database restored successfully. The database session has been refreshed.', 'success')
                # Add JavaScript to force page refresh after a short delay
                return render_template('utility/restore_success.html', 
                                      message='Database restored successfully. The page will refresh automatically.',
                                      redirect_url=url_for('index'))
            else:
                # Still log the action, but with a different connection since refresh failed
                engine = db.get_engine()
                connection = engine.connect()
                connection.execute(text("INSERT INTO log (action, description, timestamp) VALUES (:action, :description, :timestamp)"), 
                                {"action": "RESTORE_DATABASE", 
                                 "description": f"Restored database from uploaded file: {backup_file.filename}. Session refresh failed.", 
                                 "timestamp": datetime.now()})
                connection.commit()
                connection.close()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'message': 'Database restored successfully, but session refresh failed. The application will now restart.',
                        'refresh': True,
                        'force_reload': True
                    })
                
                flash('Database restored successfully, but session refresh failed. Please restart the application.', 'warning')
        except Exception as e:
            logging.error(f"Error copying backup file: {str(e)}")
            flash(f'An error occurred while restoring the database: {str(e)}', 'error')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': f'An error occurred while restoring the database: {str(e)}'
                })
    except Exception as e:
        logging.error(f"Error restoring database from file: {str(e)}\n{traceback.format_exc()}")
        flash(f'An error occurred while restoring the database: {str(e)}', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': f'An error occurred while restoring the database: {str(e)}'
            })
    
    return redirect(url_for('utility.restore_database'))

@utility_bp.route('/restore/<filename>', methods=['POST'])
def restore_from_backup(filename):
    """Restore database from an existing backup"""
    try:
        backup_dir = current_app.config['BACKUP_FOLDER']
        backup_path = os.path.join(backup_dir, filename)
        
        if not os.path.exists(backup_path):
            flash('Backup file not found', 'error')
            return redirect(url_for('utility.restore_database'))
        
        # Get current database path
        db_path = os.path.join('instance', 'accredit_data.db')
        
        # Always create a backup of current database before restore
        if os.path.exists(db_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_restore_backup = os.path.join(current_app.config['BACKUP_FOLDER'], f"pre_restore_backup_{timestamp}.db")
            shutil.copy2(db_path, pre_restore_backup)
            flash(f'Created automatic backup of current database before restore: pre_restore_backup_{timestamp}.db', 'info')
        
        # Close all existing database connections to ensure clean restore
        db.session.close()
        engine = db.get_engine()
        engine.dispose()
        
        # Copy the backup file to the database location
        try:
            # Use direct file copy for better performance
            shutil.copy2(backup_path, db_path)
            
            # Refresh the database session
            if refresh_database_session():
                # Log action using the refreshed session
                log = Log(
                    action="RESTORE_DATABASE", 
                    description=f"Restored database from backup: {filename}",
                    timestamp=datetime.now()
                )
                db.session.add(log)
                db.session.commit()
                
                # Reload all models to ensure they reflect the restored database schema
                from importlib import reload
                import models
                reload(models)
                
                # Return JSON response for frontend to handle refresh
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'message': 'Database restored successfully. Please wait while the application refreshes.',
                        'refresh': True,
                        'force_reload': True
                    })
                
                flash('Database restored successfully. The database session has been refreshed.', 'success')
                # Add JavaScript to force page refresh after a short delay
                return render_template('utility/restore_success.html', 
                                      message='Database restored successfully. The page will refresh automatically.',
                                      redirect_url=url_for('index'))
            else:
                # Still log the action, but with a different connection since refresh failed
                engine = db.get_engine()
                connection = engine.connect()
                connection.execute(text("INSERT INTO log (action, description, timestamp) VALUES (:action, :description, :timestamp)"), 
                                {"action": "RESTORE_DATABASE", 
                                 "description": f"Restored database from backup: {filename}. Session refresh failed.", 
                                 "timestamp": datetime.now()})
                connection.commit()
                connection.close()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'message': 'Database restored successfully, but session refresh failed. The application will now restart.',
                        'refresh': True,
                        'force_reload': True
                    })
                
                flash('Database restored successfully, but session refresh failed. Please restart the application.', 'warning')
        except Exception as e:
            logging.error(f"Error copying backup file: {str(e)}")
            flash(f'An error occurred while restoring the database: {str(e)}', 'error')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': f'An error occurred while restoring the database: {str(e)}'
                })
    except Exception as e:
        logging.error(f"Error in restore_from_backup: {str(e)}\n{traceback.format_exc()}")
        flash(f'An error occurred while restoring the database: {str(e)}', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': f'An error occurred while restoring the database: {str(e)}'
            })
    
    return redirect(url_for('utility.restore_database'))

@utility_bp.route('/merge', methods=['GET', 'POST'])
def merge_database():
    """Merge courses for Accredit data consolidation"""
    # Get all courses for selecting source/destination courses
    courses = Course.query.order_by(Course.code).all()
    
    # For clarity, rename this function to match what it does
    return render_template('utility/merge.html', 
                           courses=courses,
                           active_page='utilities')

@utility_bp.route('/merge/courses', methods=['POST'])
def merge_courses():
    """Merge multiple courses into a destination course"""
    # Initialize db session - don't start nested transaction yet
    transaction_savepoint = None
    
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
        
        # Always create a backup before merging, regardless of checkbox
        # (but keep the checkbox for UI consistency)
        backup_result = backup_database_before_merge()
        if not backup_result['success']:
            flash(f"Warning: Failed to create backup before merge: {backup_result['error']}. Proceeding with merge.", 'warning')
        
        # Define flags for what to merge
        merge_students = request.form.get('merge_students') == 'on'
        merge_exams = request.form.get('merge_exams') == 'on'
        merge_outcomes = request.form.get('merge_outcomes') == 'on'
        
        # Initialize counters and tracking for summary
        stats = {
            'students_merged': 0,
            'exams_merged': 0,
            'outcomes_merged': 0,
            'scores_merged': 0,
            'weights_merged': 0,
            'attendances_merged': 0,
            'conflicts': []  # To track any conflicts/warnings
        }
        
        # Pre-load existing items in destination course for faster lookups
        dest_students_map = {student.student_id: student for student in destination_course.students}
        dest_exams_map = {exam.name: exam for exam in destination_course.exams}
        dest_outcomes_map = {outcome.code: outcome for outcome in destination_course.course_outcomes}
        
        # Mapping of source exam IDs to destination exam IDs (for makeup relationships)
        exam_id_mapping = {}
        
        # Now start a transaction savepoint before actual changes
        # Using session begin_nested() to create a SAVEPOINT
        transaction_savepoint = db.session.begin_nested()
        
        # Process each source course
        for source_id in source_ids:
            source_course = Course.query.get(source_id)
            if not source_course:
                stats['conflicts'].append(f"Source course ID {source_id} not found, skipping")
                continue
            
            # Merge outcomes first (needed for exam/question associations)
            if merge_outcomes:
                merge_course_outcomes(source_course, destination_course, dest_outcomes_map, stats)
            
            # Merge exams next (needed for student score associations)
            if merge_exams:
                merge_course_exams(source_course, destination_course, dest_exams_map, dest_outcomes_map, exam_id_mapping, stats)
            
            # Finally merge students (and their scores if applicable)
            if merge_students:
                merge_course_students(source_course, destination_course, dest_students_map, dest_exams_map, exam_id_mapping, merge_exams, stats)
        
        # Fix makeup exam relationships now that all exams are merged
        if merge_exams:
            fix_makeup_relationships(exam_id_mapping, stats)
        
        # Commit all changes
        transaction_savepoint.commit()
        db.session.commit()
        
        # Log the merge action with detailed information
        log_description = f"Merged data from {len(source_ids)} courses into {destination_course.code}. "
        if stats['conflicts']:
            log_description += f"Conflicts: {', '.join(stats['conflicts'][:3])}"
            if len(stats['conflicts']) > 3:
                log_description += f" and {len(stats['conflicts']) - 3} more"
        
        log = Log(
            action="MERGE_COURSES",
            description=log_description
        )
        db.session.add(log)
        db.session.commit()
        
        # Show summary
        summary = []
        if merge_students:
            summary.append(f"{stats['students_merged']} students, {stats['scores_merged']} scores")
            if stats.get('attendances_merged', 0) > 0:
                summary.append(f"{stats['attendances_merged']} attendance records")
        if merge_exams:
            summary.append(f"{stats['exams_merged']} exams")
            if stats.get('weights_merged', 0) > 0:
                summary.append(f"{stats['weights_merged']} exam weights")
        if merge_outcomes:
            summary.append(f"{stats['outcomes_merged']} course outcomes")
        
        if summary:
            flash(f"Successfully merged {', '.join(summary)} into {destination_course.code}.", 'success')
            
            # Show conflicts as warnings if any
            if stats['conflicts']:
                conflict_msg = f"{len(stats['conflicts'])} conflicts were detected during merge. Check logs for details."
                flash(conflict_msg, 'warning')
        else:
            flash("Merge completed, but no items were selected for merging.", 'warning')
            
    except Exception as e:
        # Roll back to savepoint in case of exception, but only if it was created successfully
        if transaction_savepoint is not None and transaction_savepoint.is_active:
            try:
                transaction_savepoint.rollback()
            except Exception as rollback_error:
                logging.error(f"Error rolling back transaction: {str(rollback_error)}")
        
        # Always do a session rollback to ensure we're in a clean state
        db.session.rollback()
        
        # Log detailed error information
        error_details = traceback.format_exc()
        logging.error(f"Error merging courses: {str(e)}\n{error_details}")
        flash(f"An error occurred while merging courses: {str(e)}", 'error')
    
    return redirect(url_for('utility.merge_database'))

def merge_course_outcomes(source_course, destination_course, dest_outcomes_map, stats):
    """Helper function to merge course outcomes from source to destination"""
    # Track outcomes that need program outcomes relationships
    outcomes_to_link = []
    
    for outcome in source_course.course_outcomes:
        try:
            # Check if a similar outcome already exists
            if outcome.code in dest_outcomes_map:
                # Outcome already exists, check if descriptions match
                existing = dest_outcomes_map[outcome.code]
                if existing.description != outcome.description:
                    stats['conflicts'].append(
                        f"Outcome {outcome.code} has different descriptions in source and destination: "
                        f"'{outcome.description[:50]}...' vs '{existing.description[:50]}...'"
                    )
                
                # Check if program outcome relationships are complete
                # Get program outcomes associated with source and destination outcomes
                source_po_ids = {po.id for po in outcome.program_outcomes}
                dest_po_ids = {po.id for po in existing.program_outcomes}
                
                # Find missing program outcomes in destination
                missing_pos = source_po_ids - dest_po_ids
                if missing_pos:
                    # Get the program outcomes to add
                    pos_to_add = [po for po in outcome.program_outcomes if po.id in missing_pos]
                    if pos_to_add:
                        # Add the missing program outcomes to the existing outcome
                        for po in pos_to_add:
                            existing.program_outcomes.append(po)
                        stats['conflicts'].append(
                            f"Added {len(pos_to_add)} missing program outcome links to existing outcome {outcome.code}"
                        )
                
                continue
            
            # Create new outcome in destination course
            new_outcome = CourseOutcome(
                course_id=destination_course.id,
                code=outcome.code,
                description=outcome.description
            )
            db.session.add(new_outcome)
            db.session.flush()  # Get ID for new outcome
            
            # Store outcome to link program outcomes after basic creation
            outcomes_to_link.append((new_outcome, outcome.program_outcomes))
            
            # Update the lookup map
            dest_outcomes_map[outcome.code] = new_outcome
            stats['outcomes_merged'] += 1
            
        except Exception as e:
            stats['conflicts'].append(f"Error merging outcome {outcome.code}: {str(e)}")
            logging.error(f"Error in merge_course_outcomes: {str(e)}\n{traceback.format_exc()}")
    
    # Link program outcomes in a separate step to avoid potential ORM issues
    for new_outcome, program_outcomes in outcomes_to_link:
        try:
            # Link to same program outcomes
            for po in program_outcomes:
                new_outcome.program_outcomes.append(po)
            
            db.session.flush()  # Flush to ensure relationships are saved
        except Exception as e:
            stats['conflicts'].append(
                f"Error linking program outcomes for outcome {new_outcome.code}: {str(e)}"
            )
            logging.error(f"Error linking program outcomes: {str(e)}\n{traceback.format_exc()}")
    
    # Final flush to ensure all changes are persisted
    db.session.flush()

def merge_course_exams(source_course, destination_course, dest_exams_map, dest_outcomes_map, exam_id_mapping, stats):
    """Helper function to merge exams from source to destination"""
    for exam in source_course.exams:
        # Check if a similar exam already exists
        if exam.name in dest_exams_map:
            existing_exam = dest_exams_map[exam.name]
            # Store mapping even for existing exams (needed for makeup relationships)
            exam_id_mapping[exam.id] = existing_exam.id
            stats['conflicts'].append(f"Exam '{exam.name}' already exists in destination course, skipping")
            continue
        
        # Create new exam in destination course - don't set makeup_for yet
        new_exam = Exam(
            course_id=destination_course.id,
            name=exam.name,
            exam_date=exam.exam_date,
            max_score=exam.max_score,
            is_makeup=exam.is_makeup,
            is_final=exam.is_final,
            is_mandatory=exam.is_mandatory
            # makeup_for will be set later to avoid potential reference issues
        )
        db.session.add(new_exam)
        db.session.flush()  # To get the new ID
        
        # Store mapping for fixing makeup relationships later
        exam_id_mapping[exam.id] = new_exam.id
        
        # Copy questions to new exam
        for question in exam.questions:
            new_question = Question(
                exam_id=new_exam.id,
                number=question.number,
                text=question.text,
                max_score=question.max_score
            )
            db.session.add(new_question)
            db.session.flush()  # Add flush to ensure question is saved before linking to course outcomes
            
            # Associate with course outcomes if they exist
            for co in question.course_outcomes:
                # Find matching course outcome in destination
                dest_co = dest_outcomes_map.get(co.code)
                if dest_co:
                    new_question.course_outcomes.append(dest_co)
        
        # Copy exam weights if they exist
        merge_exam_weights(exam.id, new_exam.id, destination_course.id, stats)
        
        # Update the lookup map
        dest_exams_map[exam.name] = new_exam
        stats['exams_merged'] += 1

def merge_exam_weights(source_exam_id, dest_exam_id, dest_course_id, stats):
    """Helper function to merge exam weights"""
    try:
        # Check if source exam has weights
        source_weight = ExamWeight.query.filter_by(exam_id=source_exam_id).first()
        if not source_weight:
            # No weight to merge
            return
        
        # Check if destination exam already has weights
        dest_weight = ExamWeight.query.filter_by(exam_id=dest_exam_id).first()
        if dest_weight:
            # Weight already exists - check for conflicts
            if float(dest_weight.weight) != float(source_weight.weight):
                weight_diff = abs(float(dest_weight.weight) - float(source_weight.weight))
                stats['conflicts'].append(
                    f"Exam weight for exam ID {dest_exam_id} differs from source exam ID {source_exam_id}: "
                    f"{dest_weight.weight} vs {source_weight.weight} (diff: {weight_diff:.4f})"
                )
        else:
            # Create new weight for destination exam
            new_weight = ExamWeight(
                exam_id=dest_exam_id,
                course_id=dest_course_id,
                weight=source_weight.weight
            )
            db.session.add(new_weight)
            db.session.flush()  # Ensure weight is committed
            stats['weights_merged'] = stats.get('weights_merged', 0) + 1
            
    except Exception as e:
        stats['conflicts'].append(f"Error merging exam weight for exam {dest_exam_id}: {str(e)}")
        logging.error(f"Error in merge_exam_weights: {str(e)}\n{traceback.format_exc()}")

def merge_course_students(source_course, destination_course, dest_students_map, dest_exams_map, exam_id_mapping, merge_exams, stats):
    """Helper function to merge students and their scores"""
    # Batch size for bulk inserts
    BATCH_SIZE = 100
    
    # Prepare lists for batched operations
    new_students = []
    new_scores = []
    new_attendances = []
    
    # Build a mapping of destination exam question numbers to question objects
    # This avoids needing to query for each question individually
    dest_question_mapping = {}  # {(exam_id, question_number): question_object}
    
    # Only build the question mapping if we're merging exams and scores
    if merge_exams:
        # Get all destination exam questions in a single query
        dest_questions = Question.query.join(Exam).filter(Exam.course_id == destination_course.id).all()
        for q in dest_questions:
            dest_question_mapping[(q.exam_id, q.number)] = q
    
    # Process students in batches
    for student in source_course.students:
        try:
            # Check if student already exists in destination course
            if student.student_id in dest_students_map:
                # Use existing student
                dest_student = dest_students_map[student.student_id]
                
                # Check for name conflicts and log them
                if (dest_student.first_name != student.first_name or 
                    dest_student.last_name != student.last_name):
                    stats['conflicts'].append(
                        f"Student ID {student.student_id} has different names in source and destination: "
                        f"{student.first_name} {student.last_name} vs {dest_student.first_name} {dest_student.last_name}"
                    )
            else:
                # Create new student in destination course
                new_student = Student(
                    course_id=destination_course.id,
                    student_id=student.student_id,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    excluded=student.excluded
                )
                new_students.append(new_student)
                db.session.add(new_student)
                db.session.flush()  # Get ID for the new student
                
                # Update student map
                dest_students_map[student.student_id] = new_student
                dest_student = new_student
                stats['students_merged'] += 1
            
            # Merge scores and attendance records if merging exams
            if merge_exams:
                # Process scores
                process_student_scores(student, dest_student, source_course, 
                                     dest_exams_map, dest_question_mapping, 
                                     new_scores, stats)
                
                # Process attendance records
                process_student_attendance(student, dest_student, exam_id_mapping, 
                                         new_attendances, stats)
            
            # Flush after each batch to optimize performance
            if len(new_students) >= BATCH_SIZE or len(new_scores) >= BATCH_SIZE or len(new_attendances) >= BATCH_SIZE:
                db.session.flush()
                # Clear the lists after flush
                new_students = []
                new_scores = []
                new_attendances = []
                
        except Exception as e:
            stats['conflicts'].append(f"Error processing student {student.student_id}: {str(e)}")
            logging.error(f"Error in merge_course_students: {str(e)}\n{traceback.format_exc()}")
    
    # Final flush for any remaining records
    if new_students or new_scores or new_attendances:
        db.session.flush()

def process_student_scores(source_student, dest_student, source_course, dest_exams_map, dest_question_mapping, new_scores, stats):
    """Process and merge scores for a student"""
    # Get all scores for this student in the source course (optimized query)
    scores = Score.query.join(Question).join(Exam).filter(
        Score.student_id == source_student.id,
        Exam.course_id == source_course.id
    ).all()
    
    # Track existing scores to avoid conflicts
    existing_score_keys = set()
    
    # Get all existing scores for the destination student
    existing_scores = Score.query.filter_by(student_id=dest_student.id).all()
    for existing_score in existing_scores:
        # Store (question_id, exam_id) as key
        existing_score_keys.add((existing_score.question_id, existing_score.exam_id))
    
    for score in scores:
        try:
            # Find the corresponding question in the destination course
            source_question = Question.query.get(score.question_id)
            if not source_question:
                stats['conflicts'].append(f"Source question ID {score.question_id} not found")
                continue
                
            source_exam = Exam.query.get(source_question.exam_id)
            if not source_exam:
                stats['conflicts'].append(f"Source exam for question ID {score.question_id} not found")
                continue
            
            # Skip if exam wasn't merged
            dest_exam = dest_exams_map.get(source_exam.name)
            if not dest_exam:
                continue
            
            # Find matching question in destination exam using mapping
            dest_question = dest_question_mapping.get((dest_exam.id, source_question.number))
            
            if dest_question:
                # Verify question compatibility
                if float(dest_question.max_score) != float(source_question.max_score):
                    stats['conflicts'].append(
                        f"Question {dest_question.number} in exam {dest_exam.name} has different max_score: "
                        f"{dest_question.max_score} vs {source_question.max_score}"
                    )
                
                # Check if score already exists
                if (dest_question.id, dest_exam.id) in existing_score_keys:
                    # Score exists - could add logic to handle conflicts if needed
                    continue
                
                # Create new score
                new_score = Score(
                    student_id=dest_student.id,
                    question_id=dest_question.id,
                    exam_id=dest_exam.id,
                    score=score.score
                )
                new_scores.append(new_score)
                stats['scores_merged'] += 1
                
                # Mark as existing to avoid duplicates
                existing_score_keys.add((dest_question.id, dest_exam.id))
                
        except Exception as e:
            stats['conflicts'].append(f"Error merging score for student {source_student.student_id}, " 
                                    f"question {score.question_id}: {str(e)}")
            logging.error(f"Error in process_student_scores: {str(e)}")

def process_student_attendance(source_student, dest_student, exam_id_mapping, new_attendances, stats):
    """Process and merge attendance records for a student"""
    # Get all attendance records for this student
    attendances = StudentExamAttendance.query.filter_by(student_id=source_student.id).all()
    
    # Track existing attendance records
    existing_attendance_keys = set()
    
    # Get all existing attendance records for the destination student
    existing_attendances = StudentExamAttendance.query.filter_by(student_id=dest_student.id).all()
    for existing_attendance in existing_attendances:
        existing_attendance_keys.add(existing_attendance.exam_id)
    
    for attendance in attendances:
        try:
            # Skip if the exam wasn't merged
            if attendance.exam_id not in exam_id_mapping:
                continue
            
            # Get corresponding destination exam
            dest_exam_id = exam_id_mapping[attendance.exam_id]
            
            # Skip if attendance record already exists
            if dest_exam_id in existing_attendance_keys:
                continue
            
            # Create new attendance record
            new_attendance = StudentExamAttendance(
                student_id=dest_student.id,
                exam_id=dest_exam_id,
                attended=attendance.attended
            )
            new_attendances.append(new_attendance)
            stats['attendances_merged'] = stats.get('attendances_merged', 0) + 1
            
            # Mark as existing to avoid duplicates
            existing_attendance_keys.add(dest_exam_id)
            
        except Exception as e:
            stats['conflicts'].append(f"Error merging attendance for student {source_student.student_id}, " 
                                    f"exam {attendance.exam_id}: {str(e)}")
            logging.error(f"Error in process_student_attendance: {str(e)}")

def fix_makeup_relationships(exam_id_mapping, stats):
    """Fix makeup exam relationships after all exams are merged"""
    # Get all source exams that have makeup relationships
    source_makeup_exams = Exam.query.filter(Exam.id.in_(exam_id_mapping.keys())).filter(Exam.makeup_for.isnot(None)).all()
    
    for exam in source_makeup_exams:
        try:
            # We need both the exam and its makeup_for exam to have been merged
            if exam.id in exam_id_mapping:
                dest_exam_id = exam_id_mapping[exam.id]
                dest_exam = Exam.query.get(dest_exam_id)
                
                if not dest_exam:
                    stats['conflicts'].append(f"Destination exam ID {dest_exam_id} not found for makeup relationship")
                    continue
                
                # Check if the original exam it's a makeup for was also merged
                if exam.makeup_for in exam_id_mapping:
                    dest_makeup_for_id = exam_id_mapping[exam.makeup_for]
                    
                    # Verify the destination makeup_for exam exists
                    dest_makeup_for_exam = Exam.query.get(dest_makeup_for_id)
                    if dest_makeup_for_exam:
                        # Update the makeup relationship
                        dest_exam.makeup_for = dest_makeup_for_id
                        db.session.add(dest_exam)
                        logging.info(f"Fixed makeup relationship: Exam ID {dest_exam_id} is makeup for {dest_makeup_for_id}")
                    else:
                        stats['conflicts'].append(f"Destination makeup exam ID {dest_makeup_for_id} not found")
                else:
                    # The original exam wasn't merged, so we can't establish the relationship
                    stats['conflicts'].append(f"Makeup relationship broken: original exam {exam.makeup_for} was not merged")
                    
                    # Get makeup_for exam details for better logging
                    original_makeup_for = Exam.query.get(exam.makeup_for)
                    if original_makeup_for:
                        logging.warning(f"Could not establish makeup relationship for {dest_exam.name}. " 
                                        f"Original makeup_for exam '{original_makeup_for.name}' was not merged.")
        except Exception as e:
            stats['conflicts'].append(f"Error fixing makeup relationship for exam ID {exam.id}: {str(e)}")
            logging.error(f"Error in fix_makeup_relationships: {str(e)}\n{traceback.format_exc()}")
    
    # Commit these changes before continuing
    db.session.flush()

def backup_database_before_merge():
    """Create a backup before merging courses
    
    Returns:
        dict: A dictionary with 'success' boolean and 'error' message if failed
    """
    result = {"success": False, "error": None}
    
    try:
        # Get current database path
        db_path = os.path.join('instance', 'accredit_data.db')
        
        if not os.path.exists(db_path):
            result["error"] = "Database file not found for pre-merge backup"
            logging.warning(result["error"])
            return result
        
        # Create backup directory if it doesn't exist
        backup_dir = current_app.config['BACKUP_FOLDER']
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
        result["success"] = True
        result["backup_filename"] = backup_filename
        return result
    except Exception as e:
        error_msg = f"Error creating pre-merge backup: {str(e)}"
        logging.error(error_msg)
        result["error"] = error_msg
        return result

@utility_bp.route('/help')
def help_page():
    """Display help and documentation"""
    return render_template('utility/help.html', active_page='help')

@utility_bp.route('/cloud-help')
def cloud_help_page():
    """Display cloudflared remote access help"""
    return render_template('utility/cloud_help.html', active_page='utilities')

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
    backup_dir = current_app.config['BACKUP_FOLDER']
    backups = []
    
    # Load backup descriptions
    descriptions_file = os.path.join(backup_dir, 'backup_descriptions.json')
    descriptions = {}
    if os.path.exists(descriptions_file):
        try:
            with open(descriptions_file, 'r') as f:
                descriptions = json.load(f)
        except json.JSONDecodeError:
            # Handle corrupt JSON file
            descriptions = {}
    
    if os.path.exists(backup_dir):
        # Get all backup files (including pre-restore and pre-merge backups)
        backup_files = glob.glob(os.path.join(backup_dir, "*.db"))
        for backup_file in backup_files:
            filename = os.path.basename(backup_file)
            created_at = os.path.getmtime(backup_file)
            size = os.path.getsize(backup_file) / (1024 * 1024)  # Size in MB
            
            # Add backup type information
            backup_type = "Regular"
            if "pre_import_backup" in filename:
                backup_type = "Pre-Import"
            elif "pre_restore_backup" in filename:
                backup_type = "Pre-Restore"
            elif "pre_merge_backup" in filename:
                backup_type = "Pre-Merge"
            
            # Get custom description if available, otherwise use backup type
            custom_description = descriptions.get(filename, '')
            display_description = custom_description if custom_description else backup_type
            
            backups.append({
                'filename': filename,
                'created_at': datetime.fromtimestamp(created_at),
                'size': round(size, 2),
                'size_formatted': f"{round(size, 2)} MB",
                'type': backup_type,  # Use type for display in the badge
                'description': display_description  # Use custom description if available
            })
    
    # Sort backups by creation time (newest first)
    backups.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('utility/backup_list.html', 
                         backups=backups, 
                         active_page='utilities')

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
                temp_path = os.path.join(current_app.config['BACKUP_FOLDER'], 'temp_import.db')
                backup_file.save(temp_path)
                
                # Verify this is a valid SQLite database
                try:
                    conn = sqlite3.connect(temp_path)
                    
                    # Validate that this is a proper ABET Helper database
                    required_tables = ['course', 'exam', 'student', 'question', 'score', 'course_outcome', 'program_outcome']
                    existing_tables = [row[0] for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()]
                    
                    missing_tables = [table for table in required_tables if table not in existing_tables]
                    if missing_tables:
                        conn.close()
                        os.remove(temp_path)
                        flash(f'Invalid database: Missing required tables: {", ".join(missing_tables)}', 'error')
                        return redirect(url_for('utility.import_database'))
                    
                    # Check for optional tables (like achievement_level) - these aren't required but we'll note if they exist
                    optional_tables = ['achievement_level', 'student_exam_attendance', 'course_settings', 'exam_weight']
                    
                    for optional_table in optional_tables:
                        if optional_table not in existing_tables:
                            schema_warnings.append(f"Optional table '{optional_table}' not found in import database. Related data won't be imported.")
                    
                    # Verify schema compatibility - check essential columns exist
                    schema_validation_errors = []
                    schema_warnings = []
                    
                    # Check course table
                    course_cols = [col[1] for col in conn.execute("PRAGMA table_info(course)").fetchall()]
                    required_course_cols = ['id', 'code', 'name', 'semester']
                    missing_course_cols = [col for col in required_course_cols if col not in course_cols]
                    if missing_course_cols:
                        schema_validation_errors.append(f"Course table missing columns: {', '.join(missing_course_cols)}")
                    
                    # Check for course_weight column (optional but important)
                    if 'course_weight' not in course_cols:
                        schema_warnings.append("Course table missing 'course_weight' column. Default value of 1.0 will be used.")
                    
                    # Check student table
                    student_cols = [col[1] for col in conn.execute("PRAGMA table_info(student)").fetchall()]
                    required_student_cols = ['id', 'student_id', 'first_name', 'last_name', 'course_id']
                    missing_student_cols = [col for col in required_student_cols if col not in student_cols]
                    if missing_student_cols:
                        schema_validation_errors.append(f"Student table missing columns: {', '.join(missing_student_cols)}")
                    
                    # Check program_outcome table
                    po_cols = [col[1] for col in conn.execute("PRAGMA table_info(program_outcome)").fetchall()]
                    required_po_cols = ['id', 'code', 'description']
                    missing_po_cols = [col for col in required_po_cols if col not in po_cols]
                    if missing_po_cols:
                        schema_validation_errors.append(f"Program Outcome table missing columns: {', '.join(missing_po_cols)}")
                    
                    # Check course_outcome table
                    co_cols = [col[1] for col in conn.execute("PRAGMA table_info(course_outcome)").fetchall()]
                    required_co_cols = ['id', 'code', 'description', 'course_id']
                    missing_co_cols = [col for col in required_co_cols if col not in co_cols]
                    if missing_co_cols:
                        schema_validation_errors.append(f"Course Outcome table missing columns: {', '.join(missing_co_cols)}")
                    
                    # Check exam table
                    exam_cols = [col[1] for col in conn.execute("PRAGMA table_info(exam)").fetchall()]
                    required_exam_cols = ['id', 'name', 'course_id']
                    missing_exam_cols = [col for col in required_exam_cols if col not in exam_cols]
                    if missing_exam_cols:
                        schema_validation_errors.append(f"Exam table missing columns: {', '.join(missing_exam_cols)}")
                    
                    # Check achievement_level table if it exists in the database
                    if 'achievement_level' in existing_tables:
                        achievement_level_cols = [col[1] for col in conn.execute("PRAGMA table_info(achievement_level)").fetchall()]
                        required_achievement_level_cols = ['id', 'course_id', 'name', 'min_score', 'max_score', 'color']
                        missing_achievement_level_cols = [col for col in required_achievement_level_cols if col not in achievement_level_cols]
                        if missing_achievement_level_cols:
                            schema_validation_errors.append(f"Achievement Level table missing columns: {', '.join(missing_achievement_level_cols)}")
                    
                    # Validate data consistency
                    data_validation_errors = []
                    
                    # Verify course data integrity
                    invalid_courses = conn.execute(
                        "SELECT COUNT(*) FROM course WHERE code IS NULL OR code = '' OR name IS NULL OR name = '' OR semester IS NULL OR semester = ''"
                    ).fetchone()[0]
                    if invalid_courses > 0:
                        data_validation_errors.append(f"Found {invalid_courses} courses with missing or invalid required data")
                    
                    # Verify student data integrity
                    invalid_students = conn.execute(
                        "SELECT COUNT(*) FROM student WHERE student_id IS NULL OR student_id = '' OR course_id IS NULL"
                    ).fetchone()[0]
                    if invalid_students > 0:
                        data_validation_errors.append(f"Found {invalid_students} students with missing or invalid required data")
                    
                    # Verify exam data integrity
                    invalid_exams = conn.execute(
                        "SELECT COUNT(*) FROM exam WHERE name IS NULL OR name = '' OR course_id IS NULL"
                    ).fetchone()[0]
                    if invalid_exams > 0:
                        data_validation_errors.append(f"Found {invalid_exams} exams with missing or invalid required data")
                    
                    # Verify course outcome data integrity
                    invalid_outcomes = conn.execute(
                        "SELECT COUNT(*) FROM course_outcome WHERE code IS NULL OR code = '' OR course_id IS NULL"
                    ).fetchone()[0]
                    if invalid_outcomes > 0:
                        data_validation_errors.append(f"Found {invalid_outcomes} course outcomes with missing or invalid required data")
                    
                    # Verify achievement level data integrity if the table exists
                    if 'achievement_level' in existing_tables:
                        invalid_achievement_levels = conn.execute(
                            """
                            SELECT COUNT(*) FROM achievement_level 
                            WHERE name IS NULL OR name = '' OR course_id IS NULL 
                            OR min_score IS NULL OR max_score IS NULL OR min_score > max_score
                            """
                        ).fetchone()[0]
                        if invalid_achievement_levels > 0:
                            data_validation_errors.append(f"Found {invalid_achievement_levels} achievement levels with missing or invalid required data")
                    
                    conn.close()
                    
                    if schema_validation_errors:
                        os.remove(temp_path)
                        flash('Schema compatibility errors:', 'error')
                        for error in schema_validation_errors:
                            flash(error, 'error')
                        return redirect(url_for('utility.import_database'))
                    
                    if data_validation_errors:
                        os.remove(temp_path)
                        flash('Data validation errors:', 'error')
                        for error in data_validation_errors:
                            flash(error, 'error')
                        return redirect(url_for('utility.import_database'))
                    
                    if schema_warnings:
                        for warning in schema_warnings:
                            flash(warning, 'warning')
                    
                except sqlite3.Error as e:
                    os.remove(temp_path)
                    flash(f'Invalid database file: {str(e)}', 'error')
                    return redirect(url_for('utility.import_database'))
                
                # Get current database path
                db_path = os.path.join('instance', 'accredit_data.db')
                
                # Create a backup of current database before import
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                pre_import_backup = os.path.join(current_app.config['BACKUP_FOLDER'], f"pre_import_backup_{timestamp}.db")
                
                if os.path.exists(db_path):
                    shutil.copy2(db_path, pre_import_backup)
                    flash(f'Created backup of current database before import: pre_import_backup_{timestamp}.db', 'info')
                
                # Define what to import based on form selections
                import_courses = request.form.get('import_courses') == 'on'
                import_students = request.form.get('import_students') == 'on'
                import_exams = request.form.get('import_exams') == 'on'
                import_outcomes = request.form.get('import_outcomes') == 'on'
                import_program_outcomes = request.form.get('import_program_outcomes') == 'on'
                import_achievement_levels = request.form.get('import_achievement_levels') == 'on'
                
                # Connect to both databases
                current_db = sqlite3.connect(db_path)
                import_db = sqlite3.connect(temp_path)
                
                # Set row factory for both connections to access columns by name
                current_db.row_factory = sqlite3.Row
                import_db.row_factory = sqlite3.Row
                
                # Initialize counters for summary
                import_summary = {
                    'courses_imported': 0,
                    'students_imported': 0,
                    'exams_imported': 0,
                    'outcomes_imported': 0,
                    'program_outcomes_imported': 0,
                    'scores_imported': 0,
                    'attendance_records_imported': 0,
                    'weights_imported': 0,
                    'settings_imported': 0,
                    'achievement_levels_imported': 0,
                    'co_po_relationships_imported': 0,
                    'question_co_relationships_imported': 0
                }
                
                # Initialize error tracking collections
                import_errors = {
                    'courses': 0,
                    'students': 0,
                    'exams': 0,
                    'outcomes': 0,
                    'program_outcomes': 0,
                    'questions': 0,
                    'scores': 0,
                    'weights': 0,
                    'settings': 0,
                    'achievement_levels': 0,
                    'attendance': 0,
                    'relationships': 0
                }
                
                # Create ID mapping dictionaries for all entity types
                course_id_map = {}       # maps import_db course_id to current_db course_id
                student_id_map = {}      # maps import_db student_id to current_db student_id
                exam_id_map = {}         # maps import_db exam_id to current_db exam_id
                question_id_map = {}     # maps import_db question_id to current_db question_id
                outcome_id_map = {}      # maps import_db outcome_id to current_db outcome_id
                
                try:
                    # Start transaction
                    current_db.execute("BEGIN TRANSACTION")
                    
                    # Record savepoints for each major section to allow partial recovery
                    def create_savepoint(name):
                        current_db.execute(f"SAVEPOINT {name}")
                        logging.info(f"Created savepoint {name}")
                    
                    def rollback_to_savepoint(name):
                        current_db.execute(f"ROLLBACK TO SAVEPOINT {name}")
                        logging.info(f"Rolled back to savepoint {name}")
                    
                    def release_savepoint(name):
                        current_db.execute(f"RELEASE SAVEPOINT {name}")
                        logging.info(f"Released savepoint {name}")
                    
                    # STEP 1: First, create mappings for ALL existing entities in both databases
                    create_savepoint("init_mappings")
                    
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
                    
                    release_savepoint("init_mappings")
                    
                    # STEP 2: Import courses if selected
                    if import_courses:
                        create_savepoint("courses")
                        # Create a set to track courses that already exist and should be skipped
                        existing_course_ids = set()
                        
                        for course_data in import_courses_data:
                            course_key = (course_data['code'], course_data['semester'])
                            import_course_id = course_data['id']
                            
                            # Debug - log the keys available in course_data
                            try:
                                logging.info(f"Course data keys: {dict(course_data).keys()}")
                                logging.info(f"Course data full: {dict(course_data)}")
                            except:
                                logging.info("Failed to convert course_data to dict")
                            
                            # Validate course data
                            if not course_data['code'] or not course_data['name'] or not course_data['semester']:
                                logging.warning(f"Skipping course with invalid data: {course_data['code']}")
                                import_errors['courses'] += 1
                                continue
                            
                            # Check if course already exists in current database
                            if course_key in current_courses:
                                # Course already exists, just map the ID
                                existing_id = current_courses[course_key]
                                course_id_map[import_course_id] = existing_id
                                # Add to set of existing course IDs to skip related data import
                                existing_course_ids.add(import_course_id)
                                logging.info(f"Mapped existing course: {course_data['code']} {course_data['semester']} " +
                                            f"(import ID: {import_course_id}, current ID: {existing_id})")
                            else:
                                # Fetch the column names for the course table in the import database
                                course_columns = [column[1] for column in 
                                                 import_db.execute("PRAGMA table_info(course)").fetchall()]
                                
                                # Check if course_weight is in the columns, otherwise it will be defaulted to 1.0
                                has_course_weight = 'course_weight' in course_columns
                                if not has_course_weight:
                                    logging.warning("course_weight column not found in import database, will use default 1.0")
                                
                                # Debug the course data to see what we're getting
                                try:
                                    # Get the actual course_weight value and convert it explicitly
                                    course_weight_value = 1.0  # Default
                                    if has_course_weight:
                                        # Try to access it directly from course_data dictionary
                                        if 'course_weight' in course_data:
                                            try:
                                                # Log the raw value for debugging
                                                raw_weight = course_data['course_weight']
                                                logging.info(f"Raw course weight value: {raw_weight}, type: {type(raw_weight)}")
                                                
                                                # Convert to float regardless of type
                                                if raw_weight is not None:
                                                    course_weight_value = float(raw_weight)
                                            except (ValueError, TypeError) as e:
                                                logging.warning(f"Error converting course_weight: {e}, using default 1.0")
                                        else:
                                            # Fallback to a direct query for this specific course
                                            weight_row = import_db.execute(
                                                "SELECT course_weight FROM course WHERE id = ?", 
                                                (import_course_id,)
                                            ).fetchone()
                                            if weight_row and weight_row[0] is not None:
                                                course_weight_value = float(weight_row[0])
                                                logging.info(f"Retrieved course weight from direct query: {course_weight_value}")
                                except Exception as e:
                                    logging.error(f"Error processing course_weight: {e}")
                                    course_weight_value = 1.0  # Default on error
                                
                                # Insert new course
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO course (code, name, semester, course_weight, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        course_data['code'],
                                        course_data['name'],
                                        course_data['semester'],
                                        course_weight_value,  # Use our explicitly converted value
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                new_course_id = cursor.lastrowid
                                course_id_map[import_course_id] = new_course_id
                                current_courses[course_key] = new_course_id  # Update lookup for subsequent operations
                                import_summary['courses_imported'] += 1
                                logging.info(f"Imported new course: {course_data['code']} {course_data['semester']} " +
                                           f"(import ID: {import_course_id}, new ID: {new_course_id}, " +
                                           f"weight: {course_weight_value})")
                        release_savepoint("courses")
                    else:
                        # Even if not importing courses, create ID mapping for existing courses
                        # Create a set to track courses that already exist and should be skipped
                        existing_course_ids = set()
                        
                        for course_data in import_courses_data:
                            course_key = (course_data['code'], course_data['semester'])
                            if course_key in current_courses:
                                existing_id = current_courses[course_key]
                                course_id_map[course_data['id']] = existing_id
                                # Add to set of existing course IDs to skip related data import
                                existing_course_ids.add(course_data['id'])
                                logging.info(f"Mapped existing course (no import): {course_data['code']} {course_data['semester']} " +
                                           f"(import ID: {course_data['id']}, current ID: {existing_id})")
                    
                    # STEP 3: Import course outcomes if selected
                    if import_outcomes and course_id_map:  # Only if we have course mappings
                        create_savepoint("outcomes")
                        import_outcomes_data = import_db.execute("SELECT * FROM course_outcome").fetchall()
                        
                        for outcome_data in import_outcomes_data:
                            import_outcome_id = outcome_data['id']
                            import_course_id = outcome_data['course_id']
                            
                            # Validate outcome data
                            if not outcome_data['code'] or outcome_data['course_id'] is None:
                                logging.warning(f"Skipping outcome with invalid data: {outcome_data['code']}")
                                import_errors['outcomes'] += 1
                                continue
                            
                            # Get mapped course ID in current database
                            if import_course_id not in course_id_map:
                                continue  # Skip if no mapping for this course
                            
                            # Skip importing outcomes for existing courses
                            if import_course_id in existing_course_ids:
                                continue
                                
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
                                import_summary['outcomes_imported'] += 1
                        release_savepoint("outcomes")
                    
                    # STEP 3.5: Import program outcomes if selected
                    if import_program_outcomes:
                        create_savepoint("program_outcomes")
                        # Get all existing program outcomes
                        current_program_outcomes = {po['code']: po['id'] for po in 
                                                  current_db.execute("SELECT id, code FROM program_outcome").fetchall()}
                        
                        # Get all program outcomes from import database
                        import_program_outcomes = import_db.execute("SELECT * FROM program_outcome").fetchall()
                        program_outcome_id_map = {}  # maps import_db po_id to current_db po_id
                        
                        for po_data in import_program_outcomes:
                            import_po_id = po_data['id']
                            
                            # Validate PO data
                            if not po_data['code'] or not po_data['description']:
                                logging.warning(f"Skipping program outcome with invalid data: {po_data['code']}")
                                import_errors['program_outcomes'] += 1
                                continue
                            
                            # Check if PO already exists in current database
                            if po_data['code'] in current_program_outcomes:
                                # PO already exists, just map the ID
                                program_outcome_id_map[import_po_id] = current_program_outcomes[po_data['code']]
                            else:
                                # Insert new program outcome
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO program_outcome (code, description, created_at, updated_at)
                                    VALUES (?, ?, ?, ?)
                                    """,
                                    (
                                        po_data['code'],
                                        po_data['description'],
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                new_po_id = cursor.lastrowid
                                program_outcome_id_map[import_po_id] = new_po_id
                                current_program_outcomes[po_data['code']] = new_po_id  # Update lookup
                                import_summary['program_outcomes_imported'] += 1
                        release_savepoint("program_outcomes")
                    else:
                        # Even if not importing program outcomes, create ID mapping for existing ones
                        current_program_outcomes = {po['code']: po['id'] for po in 
                                                  current_db.execute("SELECT id, code FROM program_outcome").fetchall()}
                        
                        import_program_outcomes = import_db.execute("SELECT * FROM program_outcome").fetchall()
                        program_outcome_id_map = {}  # maps import_db po_id to current_db po_id
                        
                        for po_data in import_program_outcomes:
                            if po_data['code'] in current_program_outcomes:
                                program_outcome_id_map[po_data['id']] = current_program_outcomes[po_data['code']]
                    
                    # STEP 4: Import achievement levels if selected
                    if import_achievement_levels and import_courses and course_id_map:
                        create_savepoint("achievement_levels")
                        
                        # Check if achievement_level table exists in the import database
                        table_exists = import_db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='achievement_level'"
                        ).fetchone()
                        
                        if table_exists:
                            # Get all achievement levels from the import database
                            import_achievement_level_data = import_db.execute(
                                "SELECT * FROM achievement_level"
                            ).fetchall()
                            
                            for level_data in import_achievement_level_data:
                                import_course_id = level_data['course_id']
                                
                                # Skip if course mapping is missing
                                if import_course_id not in course_id_map:
                                    continue
                                
                                # Skip achievement levels for existing courses
                                if import_course_id in existing_course_ids:
                                    continue
                                
                                current_course_id = course_id_map[import_course_id]
                                
                                # Check if this achievement level already exists in current database
                                # (matching on course_id, name, and min/max scores)
                                existing_level = current_db.execute(
                                    """
                                    SELECT id FROM achievement_level 
                                    WHERE course_id = ? AND name = ? AND min_score = ? AND max_score = ?
                                    """, 
                                    (
                                        current_course_id,
                                        level_data['name'],
                                        level_data['min_score'],
                                        level_data['max_score']
                                    )
                                ).fetchone()
                                
                                if existing_level:
                                    # Level already exists, skip
                                    continue
                                
                                # Insert new achievement level
                                try:
                                    current_db.execute(
                                        """
                                        INSERT INTO achievement_level 
                                        (course_id, name, min_score, max_score, color, created_at, updated_at)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                        """,
                                        (
                                            current_course_id,
                                            level_data['name'],
                                            level_data['min_score'],
                                            level_data['max_score'],
                                            level_data['color'],
                                            datetime.now(),
                                            datetime.now()
                                        )
                                    )
                                    import_summary['achievement_levels_imported'] += 1
                                except Exception as e:
                                    import_errors['achievement_levels'] += 1
                                    logging.error(f"Error importing achievement level: {str(e)}")
                        release_savepoint("achievement_levels")
                    
                    # STEP 5a: Import students if selected
                    if import_students and course_id_map:
                        create_savepoint("students")
                        
                        # Get all students from import database
                        import_students_data = import_db.execute("SELECT * FROM student").fetchall()
                        
                        for student_data in import_students_data:
                            import_student_id = student_data['id']
                            import_course_id = student_data['course_id']
                            
                            # Validate student data
                            if not student_data['student_id'] or student_data['course_id'] is None:
                                logging.warning(f"Skipping student with invalid data: {student_data['student_id']}")
                                import_errors['students'] += 1
                                continue
                            
                            # Skip if no mapping for this course
                            if import_course_id not in course_id_map:
                                continue  
                            
                            # Skip students for existing courses
                            if import_course_id in existing_course_ids:
                                continue
                            
                            current_course_id = course_id_map[import_course_id]
                            student_key = (student_data['student_id'], current_course_id)
                            
                            # Check if student already exists
                            if student_key in current_students:
                                # Student already exists, just map the ID
                                student_id_map[import_student_id] = current_students[student_key]
                                continue
                            
                            # Insert new student
                            try:
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO student 
                                    (student_id, first_name, last_name, course_id, excluded, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        student_data['student_id'],
                                        student_data['first_name'],
                                        student_data['last_name'],
                                        current_course_id,
                                        student_data['excluded'] if 'excluded' in student_data else False,
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                
                                new_student_id = cursor.lastrowid
                                student_id_map[import_student_id] = new_student_id
                                current_students[student_key] = new_student_id  # Update lookup
                                import_summary['students_imported'] += 1
                            except Exception as e:
                                import_errors['students'] += 1
                                logging.error(f"Error importing student: {str(e)}")
                        
                        release_savepoint("students")
                    
                    # STEP 5b: Import exams and questions if selected
                    if import_exams and course_id_map:
                        create_savepoint("exams")
                        
                        # Get all exams from import database
                        import_exams_data = import_db.execute("SELECT * FROM exam").fetchall()
                        
                        for exam_data in import_exams_data:
                            import_exam_id = exam_data['id']
                            import_course_id = exam_data['course_id']
                            
                            # Validate exam data
                            if not exam_data['name'] or exam_data['course_id'] is None:
                                logging.warning(f"Skipping exam with invalid data: {exam_data['name']}")
                                import_errors['exams'] += 1
                                continue
                            
                            # Skip if no mapping for this course
                            if import_course_id not in course_id_map:
                                continue
                            
                            # Skip exams for existing courses
                            if import_course_id in existing_course_ids:
                                continue
                            
                            current_course_id = course_id_map[import_course_id]
                            exam_key = (exam_data['name'], current_course_id)
                            
                            # Check if exam already exists
                            if exam_key in current_exams:
                                # Exam already exists, just map the ID
                                existing_exam_id = current_exams[exam_key]
                                exam_id_map[import_exam_id] = existing_exam_id
                                continue
                            
                            # Insert new exam
                            try:
                                cursor = current_db.execute(
                                    """
                                    INSERT INTO exam
                                    (name, max_score, exam_date, course_id, is_makeup, is_final, is_mandatory, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        exam_data['name'],
                                        exam_data['max_score'],
                                        exam_data['exam_date'],
                                        current_course_id,
                                        exam_data['is_makeup'] if 'is_makeup' in exam_data else False,
                                        exam_data['is_final'] if 'is_final' in exam_data else False,
                                        exam_data['is_mandatory'] if 'is_mandatory' in exam_data else False,
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                
                                new_exam_id = cursor.lastrowid
                                exam_id_map[import_exam_id] = new_exam_id
                                current_exams[exam_key] = new_exam_id  # Update lookup
                                import_summary['exams_imported'] += 1
                                
                                # Import questions for this exam
                                import_questions_data = import_db.execute(
                                    "SELECT * FROM question WHERE exam_id = ?", 
                                    (import_exam_id,)
                                ).fetchall()
                                
                                for question_data in import_questions_data:
                                    import_question_id = question_data['id']
                                    question_key = (question_data['number'], new_exam_id, question_data['max_score'])
                                    
                                    # Check if question already exists
                                    if question_key in current_questions:
                                        # Question already exists, just map the ID
                                        question_id_map[import_question_id] = current_questions[question_key]
                                        continue
                                    
                                    # Insert new question
                                    try:
                                        cursor = current_db.execute(
                                            """
                                            INSERT INTO question
                                            (text, number, max_score, exam_id, created_at, updated_at)
                                            VALUES (?, ?, ?, ?, ?, ?)
                                            """,
                                            (
                                                question_data['text'],
                                                question_data['number'],
                                                question_data['max_score'],
                                                new_exam_id,
                                                datetime.now(),
                                                datetime.now()
                                            )
                                        )
                                        
                                        new_question_id = cursor.lastrowid
                                        question_id_map[import_question_id] = new_question_id
                                        current_questions[question_key] = new_question_id  # Update lookup
                                    except Exception as e:
                                        import_errors['questions'] += 1
                                        logging.error(f"Error importing question: {str(e)}")
                                        
                                # Import exam weights if they exist
                                try:
                                    # First check if the table exists
                                    weight_table_exists = import_db.execute(
                                        "SELECT name FROM sqlite_master WHERE type='table' AND name='exam_weight'"
                                    ).fetchone()
                                    
                                    if weight_table_exists:
                                        # Get weights for this exam
                                        weight_data = import_db.execute(
                                            "SELECT * FROM exam_weight WHERE exam_id = ?",
                                            (import_exam_id,)
                                        ).fetchone()
                                        
                                        if weight_data:
                                            current_db.execute(
                                                """
                                                INSERT INTO exam_weight
                                                (exam_id, course_id, weight, created_at, updated_at)
                                                VALUES (?, ?, ?, ?, ?)
                                                """,
                                                (
                                                    new_exam_id,
                                                    current_course_id,
                                                    weight_data['weight'],
                                                    datetime.now(),
                                                    datetime.now()
                                                )
                                            )
                                            import_summary['weights_imported'] += 1
                                except Exception as e:
                                    import_errors['weights'] += 1
                                    logging.error(f"Error importing exam weight: {str(e)}")
                            except Exception as e:
                                import_errors['exams'] += 1
                                logging.error(f"Error importing exam: {str(e)}")
                        
                        # Import scores if we have students and questions
                        if student_id_map and question_id_map:
                            try:
                                # Get all scores from import database
                                import_scores_data = import_db.execute("SELECT * FROM score").fetchall()
                                
                                for score_data in import_scores_data:
                                    import_student_id = score_data['student_id']
                                    import_question_id = score_data['question_id']
                                    import_exam_id = score_data['exam_id']
                                    
                                    # Skip if any mapping is missing
                                    if (import_student_id not in student_id_map or
                                        import_question_id not in question_id_map or
                                        import_exam_id not in exam_id_map):
                                        continue
                                    
                                    # Get mapped IDs
                                    current_student_id = student_id_map[import_student_id]
                                    current_question_id = question_id_map[import_question_id]
                                    current_exam_id = exam_id_map[import_exam_id]
                                    
                                    # Check if score already exists
                                    existing_score = current_db.execute(
                                        """
                                        SELECT id FROM score
                                        WHERE student_id = ? AND question_id = ?
                                        """,
                                        (current_student_id, current_question_id)
                                    ).fetchone()
                                    
                                    if existing_score:
                                        # Score already exists, skip
                                        continue
                                    
                                    # Insert new score
                                    current_db.execute(
                                        """
                                        INSERT INTO score
                                        (score, student_id, question_id, exam_id, created_at, updated_at)
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
                                    import_summary['scores_imported'] += 1
                            except Exception as e:
                                import_errors['scores'] += 1
                                logging.error(f"Error importing scores: {str(e)}")
                        
                        release_savepoint("exams")
                    
                    # STEP 5c: Import course settings if available
                    if import_courses and course_id_map:
                        create_savepoint("course_settings")
                        
                        # Check if course_settings table exists in the import database
                        settings_table_exists = import_db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='course_settings'"
                        ).fetchone()
                        
                        if settings_table_exists:
                            # Get all course settings from import database
                            import_settings_data = import_db.execute("SELECT * FROM course_settings").fetchall()
                            
                            for settings_data in import_settings_data:
                                import_course_id = settings_data['course_id']
                                
                                # Skip if course mapping is missing
                                if import_course_id not in course_id_map:
                                    continue
                                
                                # Skip settings for existing courses
                                if import_course_id in existing_course_ids:
                                    continue
                                
                                current_course_id = course_id_map[import_course_id]
                                
                                # Check if settings already exist for this course
                                existing_settings = current_db.execute(
                                    "SELECT id FROM course_settings WHERE course_id = ?", 
                                    (current_course_id,)
                                ).fetchone()
                                
                                if existing_settings:
                                    # Settings already exist, skip
                                    continue
                                
                                # Insert new course settings
                                try:
                                    current_db.execute(
                                        """
                                        INSERT INTO course_settings
                                        (course_id, success_rate_method, relative_success_threshold, excluded, created_at, updated_at)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                        """,
                                        (
                                            current_course_id,
                                            settings_data['success_rate_method'],
                                            settings_data['relative_success_threshold'],
                                            settings_data['excluded'] if 'excluded' in settings_data else False,
                                            datetime.now(),
                                            datetime.now()
                                        )
                                    )
                                    import_summary['settings_imported'] += 1
                                except Exception as e:
                                    import_errors['settings'] += 1
                                    logging.error(f"Error importing course settings: {str(e)}")
                        
                        release_savepoint("course_settings")
                    
                    # STEP 6: Import student exam attendance records if selected
                    if import_students and import_exams and student_id_map and exam_id_map:
                        create_savepoint("attendance")
                        import_attendance_data = import_db.execute(
                            "SELECT * FROM student_exam_attendance"
                        ).fetchall()
                        
                        for attendance_data in import_attendance_data:
                            import_student_id = attendance_data['student_id']
                            import_exam_id = attendance_data['exam_id']
                            
                            # Skip if any mapping is missing
                            if (import_student_id not in student_id_map or 
                                import_exam_id not in exam_id_map):
                                continue
                            
                            # Get mapped IDs
                            current_student_id = student_id_map[import_student_id]
                            current_exam_id = exam_id_map[import_exam_id]
                            
                            # Check if attendance record already exists in current database
                            existing_attendance = current_db.execute(
                                """
                                SELECT id FROM student_exam_attendance 
                                WHERE student_id = ? AND exam_id = ?
                                """, 
                                (current_student_id, current_exam_id)
                            ).fetchone()
                            
                            if existing_attendance:
                                # Attendance record already exists, skip
                                continue
                            
                            # Insert new attendance record
                            try:
                                current_db.execute(
                                    """
                                    INSERT INTO student_exam_attendance 
                                    (student_id, exam_id, attended, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?)
                                    """,
                                    (
                                        current_student_id,
                                        current_exam_id,
                                        attendance_data['attended'],
                                        datetime.now(),
                                        datetime.now()
                                    )
                                )
                                import_summary['attendance_records_imported'] += 1
                            except Exception as e:
                                import_errors['attendance'] += 1
                                logging.error(f"Error importing attendance record: {str(e)}")
                        release_savepoint("attendance")
                    
                    # STEP 7: Handle makeup exam relationships with improved circular reference detection
                    if exam_id_map:
                        create_savepoint("makeup_relationships")
                        # Get all makeup exams from the import database
                        makeup_exams = import_db.execute(
                            "SELECT id, makeup_for FROM exam WHERE is_makeup = 1 AND makeup_for IS NOT NULL"
                        ).fetchall()
                        
                        # Detect circular references in makeup exams
                        makeup_graph = {}
                        for makeup_exam in makeup_exams:
                            if makeup_exam['id'] not in makeup_graph:
                                makeup_graph[makeup_exam['id']] = set()
                            makeup_graph[makeup_exam['id']].add(makeup_exam['makeup_for'])
                        
                        # Check for cycles
                        def has_cycle(node, visited, path):
                            visited.add(node)
                            path.add(node)
                            
                            if node in makeup_graph:
                                for neighbor in makeup_graph[node]:
                                    if neighbor not in visited:
                                        if has_cycle(neighbor, visited, path):
                                            return True
                                    elif neighbor in path:
                                        return True
                            
                            path.remove(node)
                            return False
                        
                        circular_refs = set()
                        for node in makeup_graph:
                            if node not in circular_refs:  # Skip nodes already identified in cycles
                                visited = set()
                                path = set()
                                if has_cycle(node, visited, path):
                                    circular_refs.update(path)
                        
                        if circular_refs:
                            logging.warning(f"Detected circular references in makeup exams: {circular_refs}")
                            flash("Detected circular references in makeup exams. These relationships will be skipped.", "warning")
                        
                        for makeup_exam in makeup_exams:
                            import_exam_id = makeup_exam['id']
                            import_original_exam_id = makeup_exam['makeup_for']
                            
                            # Skip circular references
                            if import_exam_id in circular_refs or import_original_exam_id in circular_refs:
                                import_errors['exams'] += 1
                                continue
                            
                            # Skip if any mapping is missing
                            if (import_exam_id not in exam_id_map or 
                                import_original_exam_id not in exam_id_map):
                                continue
                            
                            # Skip relationships for exams from existing courses
                            try:
                                # Check if either exam is from an existing course
                                exam_data = import_db.execute("SELECT course_id FROM exam WHERE id = ?", 
                                                           (import_exam_id,)).fetchone()
                                if exam_data and exam_data['course_id'] in existing_course_ids:
                                    continue
                                
                                original_exam_data = import_db.execute("SELECT course_id FROM exam WHERE id = ?", 
                                                                     (import_original_exam_id,)).fetchone()
                                if original_exam_data and original_exam_data['course_id'] in existing_course_ids:
                                    continue
                            except Exception as e:
                                logging.debug(f"Error checking makeup exam source course: {str(e)}")
                            
                            current_exam_id = exam_id_map[import_exam_id]
                            current_original_exam_id = exam_id_map[import_original_exam_id]
                            
                            # Update the makeup_for relationship
                            current_db.execute(
                                "UPDATE exam SET makeup_for = ? WHERE id = ?",
                                (current_original_exam_id, current_exam_id)
                            )
                        release_savepoint("makeup_relationships")
                    
                    # STEP 8: Handle question-outcome relationships (if they exist in the schema)
                    # ... existing code ...
                    
                    # STEP 10: Handle CO-PO and Question-CO relationships
                    create_savepoint("relationships")
                    
                    # Handle CO-PO relationships if both outcomes are imported
                    if (import_outcomes or import_program_outcomes) and outcome_id_map and program_outcome_id_map:
                        try:
                            # Check if course_outcome_program_outcome table exists
                            table_exists = import_db.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name='course_outcome_program_outcome'"
                            ).fetchone()
                            
                            if table_exists:
                                # Get all CO-PO relationships from import database
                                import_co_po_data = import_db.execute(
                                    "SELECT * FROM course_outcome_program_outcome"
                                ).fetchall()
                                
                                for co_po_data in import_co_po_data:
                                    import_co_id = co_po_data['course_outcome_id']
                                    import_po_id = co_po_data['program_outcome_id']
                                    
                                    # Skip if any mapping is missing
                                    if (import_co_id not in outcome_id_map or 
                                        import_po_id not in program_outcome_id_map):
                                        continue
                                    
                                    # Get mapped IDs
                                    current_co_id = outcome_id_map[import_co_id]
                                    current_po_id = program_outcome_id_map[import_po_id]
                                    
                                    # Skip relationships for outcomes from existing courses
                                    try:
                                        # Check if the course outcome is from an existing course
                                        co_data = import_db.execute("SELECT course_id FROM course_outcome WHERE id = ?", 
                                                                   (import_co_id,)).fetchone()
                                        if co_data and co_data['course_id'] in existing_course_ids:
                                            continue
                                    except Exception as e:
                                        logging.debug(f"Error checking CO-PO relationship source: {str(e)}")
                                    
                                    # Check if relationship already exists
                                    existing_relationship = current_db.execute(
                                        """
                                        SELECT * FROM course_outcome_program_outcome 
                                        WHERE course_outcome_id = ? AND program_outcome_id = ?
                                        """, 
                                        (current_co_id, current_po_id)
                                    ).fetchone()
                                    
                                    if existing_relationship:
                                        # Relationship already exists, skip
                                        continue
                                    
                                    # Insert new relationship
                                    current_db.execute(
                                        """
                                        INSERT INTO course_outcome_program_outcome 
                                        (course_outcome_id, program_outcome_id)
                                        VALUES (?, ?)
                                        """,
                                        (current_co_id, current_po_id)
                                    )
                                    import_summary['co_po_relationships_imported'] += 1
                        except Exception as e:
                            import_errors['relationships'] += 1
                            logging.error(f"Error importing CO-PO relationships: {str(e)}")
                    
                    # Handle Question-CO relationships if both questions and outcomes are imported
                    if import_exams and import_outcomes and question_id_map and outcome_id_map:
                        try:
                            # Check if question_course_outcome table exists
                            table_exists = import_db.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name='question_course_outcome'"
                            ).fetchone()
                            
                            if table_exists:
                                # Get all Question-CO relationships from import database
                                import_q_co_data = import_db.execute(
                                    "SELECT * FROM question_course_outcome"
                                ).fetchall()
                                
                                for q_co_data in import_q_co_data:
                                    import_q_id = q_co_data['question_id']
                                    import_co_id = q_co_data['course_outcome_id']
                                    
                                    # Skip if any mapping is missing
                                    if (import_q_id not in question_id_map or 
                                        import_co_id not in outcome_id_map):
                                        continue
                                    
                                    # Skip relationships for questions from existing courses
                                    try:
                                        # First get the exam ID for this question
                                        q_data = import_db.execute("SELECT exam_id FROM question WHERE id = ?", 
                                                                  (import_q_id,)).fetchone()
                                        if q_data:
                                            # Now get the course ID for this exam
                                            exam_data = import_db.execute("SELECT course_id FROM exam WHERE id = ?", 
                                                                        (q_data['exam_id'],)).fetchone()
                                            if exam_data and exam_data['course_id'] in existing_course_ids:
                                                continue
                                    except Exception as e:
                                        logging.debug(f"Error checking Question-CO relationship source: {str(e)}")
                                    
                                    # Get mapped IDs
                                    current_q_id = question_id_map[import_q_id]
                                    current_co_id = outcome_id_map[import_co_id]
                                    
                                    # Check if relationship already exists
                                    existing_relationship = current_db.execute(
                                        """
                                        SELECT * FROM question_course_outcome 
                                        WHERE question_id = ? AND course_outcome_id = ?
                                        """, 
                                        (current_q_id, current_co_id)
                                    ).fetchone()
                                    
                                    if existing_relationship:
                                        # Relationship already exists, skip
                                        continue
                                    
                                    # Insert new relationship
                                    current_db.execute(
                                        """
                                        INSERT INTO question_course_outcome 
                                        (question_id, course_outcome_id)
                                        VALUES (?, ?)
                                        """,
                                        (current_q_id, current_co_id)
                                    )
                                    import_summary['question_co_relationships_imported'] += 1
                        except Exception as e:
                            import_errors['relationships'] += 1
                            logging.error(f"Error importing Question-CO relationships: {str(e)}")
                    
                    release_savepoint("relationships")
                    
                    # FINAL STEP: Commit and display summary
                    current_db.execute("COMMIT")
                    
                    # Verify database integrity after import
                    try:
                        integrity_issues = []
                        
                        # Check for orphaned records
                        # Check students without valid courses
                        orphaned_students = current_db.execute(
                            """
                            SELECT COUNT(*) FROM student s
                            LEFT JOIN course c ON s.course_id = c.id
                            WHERE c.id IS NULL
                            """
                        ).fetchone()[0]
                        
                        if orphaned_students > 0:
                            integrity_issues.append(f"Found {orphaned_students} students without valid course references")
                        
                        # Check exams without valid courses
                        orphaned_exams = current_db.execute(
                            """
                            SELECT COUNT(*) FROM exam e
                            LEFT JOIN course c ON e.course_id = c.id
                            WHERE c.id IS NULL
                            """
                        ).fetchone()[0]
                        
                        if orphaned_exams > 0:
                            integrity_issues.append(f"Found {orphaned_exams} exams without valid course references")
                        
                        # Check questions without valid exams
                        orphaned_questions = current_db.execute(
                            """
                            SELECT COUNT(*) FROM question q
                            LEFT JOIN exam e ON q.exam_id = e.id
                            WHERE e.id IS NULL
                            """
                        ).fetchone()[0]
                        
                        if orphaned_questions > 0:
                            integrity_issues.append(f"Found {orphaned_questions} questions without valid exam references")
                        
                        # Check course outcomes without valid courses
                        orphaned_outcomes = current_db.execute(
                            """
                            SELECT COUNT(*) FROM course_outcome co
                            LEFT JOIN course c ON co.course_id = c.id
                            WHERE c.id IS NULL
                            """
                        ).fetchone()[0]
                        
                        if orphaned_outcomes > 0:
                            integrity_issues.append(f"Found {orphaned_outcomes} course outcomes without valid course references")
                        
                        # Check achievement levels without valid courses
                        try:
                            # First check if the table exists
                            table_exists = current_db.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name='achievement_level'"
                            ).fetchone()
                            
                            if table_exists:
                                orphaned_achievement_levels = current_db.execute(
                                    """
                                    SELECT COUNT(*) FROM achievement_level al
                                    LEFT JOIN course c ON al.course_id = c.id
                                    WHERE c.id IS NULL
                                    """
                                ).fetchone()[0]
                                
                                if orphaned_achievement_levels > 0:
                                    integrity_issues.append(f"Found {orphaned_achievement_levels} achievement levels without valid course references")
                        except Exception as e:
                            logging.error(f"Error checking achievement level integrity: {str(e)}")
                        
                        # If integrity issues were found, notify the user
                        if integrity_issues:
                            integrity_message = "<strong>Database Integrity Check:</strong><br>The following issues were detected after import:<br>"
                            for issue in integrity_issues:
                                integrity_message += f"- {issue}<br>"
                            integrity_message += "<br>It's recommended to review your data and fix these issues."
                            flash(integrity_message, 'warning')
                        else:
                            flash("Database integrity check passed. No issues detected.", 'info')
                            
                    except Exception as e:
                        logging.error(f"Error during database integrity check: {str(e)}")
                        flash("Could not complete database integrity check after import.", 'warning')
                    
                    # Display import summary
                    summary_message = "<strong>Import Summary:</strong><br>"
                    if import_summary['courses_imported'] > 0:
                        summary_message += f"- {import_summary['courses_imported']} courses imported<br>"
                    if import_summary['outcomes_imported'] > 0:
                        summary_message += f"- {import_summary['outcomes_imported']} course outcomes imported<br>"
                    if import_summary['program_outcomes_imported'] > 0:
                        summary_message += f"- {import_summary['program_outcomes_imported']} program outcomes imported<br>"
                    if import_summary['students_imported'] > 0:
                        summary_message += f"- {import_summary['students_imported']} students imported<br>"
                    if import_summary['exams_imported'] > 0:
                        summary_message += f"- {import_summary['exams_imported']} exams imported<br>"
                    if import_summary['scores_imported'] > 0:
                        summary_message += f"- {import_summary['scores_imported']} scores imported<br>"
                    if import_summary['attendance_records_imported'] > 0:
                        summary_message += f"- {import_summary['attendance_records_imported']} attendance records imported<br>"
                    if import_summary['weights_imported'] > 0:
                        summary_message += f"- {import_summary['weights_imported']} exam weights imported<br>"
                    if import_summary['settings_imported'] > 0:
                        summary_message += f"- {import_summary['settings_imported']} course settings imported<br>"
                    if import_summary['achievement_levels_imported'] > 0:
                        summary_message += f"- {import_summary['achievement_levels_imported']} achievement levels imported<br>"
                    if import_summary['co_po_relationships_imported'] > 0:
                        summary_message += f"- {import_summary['co_po_relationships_imported']} CO-PO relationships imported<br>"
                    if import_summary['question_co_relationships_imported'] > 0:
                        summary_message += f"- {import_summary['question_co_relationships_imported']} Question-CO relationships imported<br>"
                    
                    # Add note about skipped existing courses if any were found
                    if existing_course_ids:
                        existing_count = len(existing_course_ids)
                        existing_courses_info = [f"{c['code']} {c['semester']}" for c in 
                                               import_db.execute("SELECT code, semester FROM course WHERE id IN (" + 
                                                              ",".join(["?" for _ in existing_course_ids]) + ")",
                                                            tuple(existing_course_ids)).fetchall()]
                        
                        summary_message += f"<br><strong>Skipped {existing_count} existing courses:</strong><br>"
                        # Limit the number of courses shown to avoid huge messages
                        max_courses_to_show = 10
                        if len(existing_courses_info) > max_courses_to_show:
                            for course in existing_courses_info[:max_courses_to_show]:
                                summary_message += f"- {course}<br>"
                            summary_message += f"- ... and {len(existing_courses_info) - max_courses_to_show} more<br>"
                        else:
                            for course in existing_courses_info:
                                summary_message += f"- {course}<br>"
                    
                    flash(Markup(summary_message), 'success')
                    
                    # Display error summary if any occurred
                    error_count = sum(import_errors.values())
                    if error_count > 0:
                        error_entity_count = sum(1 for count in import_errors.values() if count > 0)
                        error_message = f"<strong>Import completed with {error_count} issues in {error_entity_count} data categories:</strong><br>"
                        for entity, count in import_errors.items():
                            if count > 0:
                                error_message += f"- {count} {entity} errors<br>"
                        flash(Markup(error_message), 'warning')
                    
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
        backup_dir = current_app.config['BACKUP_FOLDER']
        backups = []
        
        if os.path.exists(backup_dir):
            # Change this line to include all .db files, not just accredit_data_backup_*.db
            backup_files = glob.glob(os.path.join(backup_dir, "*.db"))
            for backup_file in backup_files:
                filename = os.path.basename(backup_file)
                created_at = os.path.getmtime(backup_file)
                size = os.path.getsize(backup_file) / (1024 * 1024)  # Size in MB
                
                # Add backup type information
                backup_type = "Regular"
                if "pre_import_backup" in filename:
                    backup_type = "Pre-Import"
                elif "pre_restore_backup" in filename:
                    backup_type = "Pre-Restore"
                
                backups.append({
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(created_at),
                    'size': round(size, 2),
                    'size_formatted': f"{round(size, 2)} MB",
                    'description': backup_type  # Use description field to show backup type
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

@utility_bp.route('/merge/preview', methods=['POST'])
def preview_merge():
    """Preview what would be merged between courses without performing the actual merge"""
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Extract parameters
        destination_id = data.get('destination_course')
        source_ids = data.get('source_courses', [])
        merge_students = data.get('merge_students', False)
        merge_exams = data.get('merge_exams', False)
        merge_outcomes = data.get('merge_outcomes', False)
        
        # Validate inputs
        if not destination_id:
            return jsonify({
                'success': False,
                'message': 'Destination course must be selected'
            }), 400
        
        if not source_ids:
            return jsonify({
                'success': False,
                'message': 'At least one source course must be selected'
            }), 400
        
        # Ensure destination course is not in source courses
        if destination_id in source_ids:
            return jsonify({
                'success': False,
                'message': 'Destination course cannot be a source course'
            }), 400
        
        # Get the destination and source courses
        destination_course = Course.query.get(destination_id)
        if not destination_course:
            return jsonify({
                'success': False,
                'message': 'Destination course not found'
            }), 404
        
        source_courses = []
        for source_id in source_ids:
            source_course = Course.query.get(source_id)
            if source_course:
                source_courses.append(source_course)
        
        if not source_courses:
            return jsonify({
                'success': False,
                'message': 'No valid source courses found'
            }), 404
        
        # Initialize preview data
        preview = {
            'destination': {
                'id': destination_course.id,
                'code': destination_course.code,
                'name': destination_course.name,
                'term': destination_course.semester,
                'students_count': len(destination_course.students),
                'exams_count': len(destination_course.exams),
                'outcomes_count': len(destination_course.course_outcomes)
            },
            'sources': [],
            'merge_preview': {
                'students': {
                    'total': 0,
                    'new': 0,
                    'existing': 0,
                    'conflicts': [],
                    'warnings': []
                },
                'exams': {
                    'total': 0,
                    'new': 0,
                    'existing': 0,
                    'conflicts': [],
                    'warnings': [],
                    'makeup_issues': []
                },
                'outcomes': {
                    'total': 0,
                    'new': 0,
                    'existing': 0,
                    'conflicts': [],
                    'warnings': []
                },
                'weights': {
                    'total': 0,
                    'new': 0,
                    'existing': 0,
                    'conflicts': [],
                    'warnings': []
                },
                'attendances': {
                    'total': 0,
                    'new': 0,
                    'warnings': []
                }
            }
        }
        
        # Build lookup maps for destination items
        dest_students = {student.student_id: student for student in destination_course.students}
        dest_exams = {exam.name: exam for exam in destination_course.exams}
        dest_outcomes = {outcome.code: outcome for outcome in destination_course.course_outcomes}
        
        # Track potential makeup relationship issues
        makeup_mapping = {}  # {source_exam_id: (exam_name, makeup_for_id, makeup_for_name)}
        
        # Analyze each source course
        for source_course in source_courses:
            source_info = {
                'id': source_course.id,
                'code': source_course.code,
                'name': source_course.name,
                'term': source_course.semester,
                'students_count': len(source_course.students),
                'exams_count': len(source_course.exams),
                'outcomes_count': len(source_course.course_outcomes)
            }
            preview['sources'].append(source_info)
            
            # Analyze students
            if merge_students:
                preview['merge_preview']['students']['total'] += len(source_course.students)
                
                # Check for students with incomplete attendance records
                if merge_exams:
                    for student in source_course.students:
                        # Get all exams for this course
                        course_exams = Exam.query.filter_by(course_id=source_course.id).all()
                        course_exam_ids = [exam.id for exam in course_exams]
                        
                        # Get attendance records for this student
                        attendance_exam_ids = [
                            a.exam_id for a in StudentExamAttendance.query.filter_by(student_id=student.id).all()
                        ]
                        
                        # Find exams without attendance records
                        missing_attendance = set(course_exam_ids) - set(attendance_exam_ids)
                        if missing_attendance and len(missing_attendance) > 0:
                            preview['merge_preview']['attendances']['warnings'].append({
                                'student_id': student.student_id,
                                'missing_attendance': len(missing_attendance),
                                'course': source_course.code
                            })
                
                for student in source_course.students:
                    if student.student_id in dest_students:
                        preview['merge_preview']['students']['existing'] += 1
                        # Check for conflicts
                        dest_student = dest_students[student.student_id]
                        if (dest_student.first_name != student.first_name or 
                            dest_student.last_name != student.last_name):
                            preview['merge_preview']['students']['conflicts'].append({
                                'student_id': student.student_id,
                                'source_name': f"{student.first_name} {student.last_name}",
                                'dest_name': f"{dest_student.first_name} {dest_student.last_name}",
                                'course': source_course.code
                            })
                    else:
                        preview['merge_preview']['students']['new'] += 1
            
            # Analyze exams
            if merge_exams:
                preview['merge_preview']['exams']['total'] += len(source_course.exams)
                
                # Check for makeup exam relationships
                for exam in source_course.exams:
                    if exam.is_makeup and exam.makeup_for:
                        # Store this makeup relationship
                        makeup_exam = Exam.query.get(exam.makeup_for)
                        makeup_for_name = makeup_exam.name if makeup_exam else "Unknown"
                        
                        makeup_mapping[exam.id] = (exam.name, exam.makeup_for, makeup_for_name)
                
                # Analyze exam weights as well
                weights_count = 0
                exam_weights = {}  # {exam_name: weight}
                
                # Get all weights in one query for efficiency
                all_weights = ExamWeight.query.join(Exam).filter(
                    Exam.course_id == source_course.id
                ).all()
                
                for weight in all_weights:
                    weights_count += 1
                    exam = Exam.query.get(weight.exam_id)
                    if exam:
                        exam_weights[exam.name] = weight.weight
                
                preview['merge_preview']['weights']['total'] += weights_count
                
                # Check for missing weights
                for exam in source_course.exams:
                    if exam.name not in exam_weights:
                        preview['merge_preview']['weights']['warnings'].append({
                            'exam_name': exam.name,
                            'issue': "Missing weight",
                            'course': source_course.code
                        })
                
                # Check weights against destination
                for exam_name, weight_value in exam_weights.items():
                    # Check if destination has this exam
                    if exam_name in dest_exams:
                        dest_exam = dest_exams[exam_name]
                        dest_weight = ExamWeight.query.filter_by(exam_id=dest_exam.id).first()
                        
                        if dest_weight:
                            preview['merge_preview']['weights']['existing'] += 1
                            # Check for weight conflicts
                            if float(dest_weight.weight) != float(weight_value):
                                preview['merge_preview']['weights']['conflicts'].append({
                                    'exam_name': exam_name,
                                    'source_weight': float(weight_value),
                                    'dest_weight': float(dest_weight.weight),
                                    'course': source_course.code
                                })
                        else:
                            preview['merge_preview']['weights']['new'] += 1
                    else:
                        # New exam, weight will be new
                        preview['merge_preview']['weights']['new'] += 1
                
                # Analyze attendance records
                attendance_count = StudentExamAttendance.query.join(Student).filter(
                    Student.course_id == source_course.id
                ).count()
                
                preview['merge_preview']['attendances']['total'] += attendance_count
                
                # Analyze exams and questions
                for exam in source_course.exams:
                    if exam.name in dest_exams:
                        preview['merge_preview']['exams']['existing'] += 1
                        # Check for potential conflicts
                        dest_exam = dest_exams[exam.name]
                        
                        # Check exam properties for significant differences
                        if exam.is_final != dest_exam.is_final:
                            preview['merge_preview']['exams']['conflicts'].append({
                                'exam_name': exam.name,
                                'issue': 'is_final flag mismatch',
                                'source_value': exam.is_final,
                                'dest_value': dest_exam.is_final,
                                'course': source_course.code
                            })
                        
                        if exam.is_mandatory != dest_exam.is_mandatory:
                            preview['merge_preview']['exams']['conflicts'].append({
                                'exam_name': exam.name,
                                'issue': 'is_mandatory flag mismatch',
                                'source_value': exam.is_mandatory,
                                'dest_value': dest_exam.is_mandatory,
                                'course': source_course.code
                            })
                        
                        # Check if questions are compatible
                        source_questions = {q.number: q for q in exam.questions}
                        dest_questions = {q.number: q for q in dest_exam.questions}
                        
                        # Check for missing questions in either direction
                        source_question_nums = set(source_questions.keys())
                        dest_question_nums = set(dest_questions.keys())
                        
                        missing_in_dest = source_question_nums - dest_question_nums
                        if missing_in_dest:
                            preview['merge_preview']['exams']['warnings'].append({
                                'exam_name': exam.name,
                                'issue': f"Destination missing questions: {', '.join(map(str, missing_in_dest))}",
                                'course': source_course.code
                            })
                        
                        missing_in_source = dest_question_nums - source_question_nums
                        if missing_in_source:
                            preview['merge_preview']['exams']['warnings'].append({
                                'exam_name': exam.name,
                                'issue': f"Source missing questions: {', '.join(map(str, missing_in_source))}",
                                'course': source_course.code
                            })
                        
                        # Check for score mismatches in common questions
                        for q_num in source_question_nums & dest_question_nums:
                            source_q = source_questions[q_num]
                            dest_q = dest_questions[q_num]
                            if float(dest_q.max_score) != float(source_q.max_score):
                                preview['merge_preview']['exams']['conflicts'].append({
                                    'exam_name': exam.name,
                                    'question_number': q_num,
                                    'source_max_score': float(source_q.max_score),
                                    'dest_max_score': float(dest_q.max_score),
                                    'course': source_course.code
                                })
                    else:
                        preview['merge_preview']['exams']['new'] += 1
            
            # Analyze outcomes
            if merge_outcomes:
                preview['merge_preview']['outcomes']['total'] += len(source_course.course_outcomes)
                
                # Check for outcomes with missing program outcome links
                for outcome in source_course.course_outcomes:
                    if not outcome.program_outcomes:
                        preview['merge_preview']['outcomes']['warnings'].append({
                            'code': outcome.code,
                            'issue': 'No program outcomes linked',
                            'course': source_course.code
                        })
                    
                    if outcome.code in dest_outcomes:
                        preview['merge_preview']['outcomes']['existing'] += 1
                        # Check for description conflicts
                        dest_outcome = dest_outcomes[outcome.code]
                        if dest_outcome.description != outcome.description:
                            preview['merge_preview']['outcomes']['conflicts'].append({
                                'code': outcome.code,
                                'source_description': outcome.description,
                                'dest_description': dest_outcome.description,
                                'course': source_course.code
                            })
                        
                        # Check for program outcome mapping differences
                        source_po_ids = {po.id for po in outcome.program_outcomes}
                        dest_po_ids = {po.id for po in dest_outcome.program_outcomes}
                        
                        missing_po_ids = source_po_ids - dest_po_ids
                        if missing_po_ids:
                            missing_pos = ProgramOutcome.query.filter(ProgramOutcome.id.in_(missing_po_ids)).all()
                            missing_po_codes = [po.code for po in missing_pos]
                            preview['merge_preview']['outcomes']['warnings'].append({
                                'code': outcome.code,
                                'issue': f"Missing program outcome links: {', '.join(missing_po_codes)}",
                                'course': source_course.code
                            })
                    else:
                        preview['merge_preview']['outcomes']['new'] += 1
        
        # Analyze makeup relationships for potential issues
        if merge_exams:
            # Build a mapping of which source exams will be merged vs skipped
            will_merge = {}  # {source_exam_id: will_merge_boolean}
            for source_course in source_courses:
                for exam in source_course.exams:
                    will_merge[exam.id] = not (exam.name in dest_exams)
            
            # Check for broken makeup relationships
            for exam_id, (exam_name, makeup_for, makeup_for_name) in makeup_mapping.items():
                if will_merge.get(exam_id, False) and not will_merge.get(makeup_for, False):
                    # The makeup exam will be merged but its original won't be
                    preview['merge_preview']['exams']['makeup_issues'].append({
                        'exam_name': exam_name,
                        'issue': f"Makeup exam will be merged but its original exam '{makeup_for_name}' already exists in destination",
                        'severity': 'warning'
                    })
                
                if not will_merge.get(exam_id, False) and will_merge.get(makeup_for, True):
                    # The original exam will be merged but its makeup won't be
                    preview['merge_preview']['exams']['makeup_issues'].append({
                        'exam_name': makeup_for_name,
                        'issue': f"Original exam will be merged but its makeup '{exam_name}' already exists in destination",
                        'severity': 'warning'
                    })
        
        return jsonify({
            'success': True,
            'preview': preview
        })
        
    except Exception as e:
        logging.error(f"Error generating merge preview: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f"Error generating preview: {str(e)}"
        }), 500

@utility_bp.route('/validate-backup', methods=['POST'])
def validate_backup_file():
    """Validate a backup file before importing"""
    try:
        # Check if file is provided
        if 'backup_file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No backup file provided'
            })
        
        backup_file = request.files['backup_file']
        
        if backup_file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No backup file selected'
            })
        
        # Create a temporary file for the uploaded backup
        temp_path = os.path.join(current_app.config['BACKUP_FOLDER'], 'temp_validate.db')
        backup_file.save(temp_path)
        
        validation_errors = []
        db_stats = {}
        
        # Verify this is a valid SQLite database
        try:
            conn = sqlite3.connect(temp_path)
            conn.row_factory = sqlite3.Row
            
            # Validate that this is a proper ABET Helper database
            required_tables = ['course', 'exam', 'student', 'question', 'score', 'course_outcome', 'program_outcome']
            existing_tables = [row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            
            missing_tables = [table for table in required_tables if table not in existing_tables]
            if missing_tables:
                validation_errors.append(f"Missing required tables: {', '.join(missing_tables)}")
            
            # Collect database statistics
            if 'course' in existing_tables:
                db_stats['courses'] = conn.execute("SELECT COUNT(*) FROM course").fetchone()[0]
            
            if 'student' in existing_tables:
                db_stats['students'] = conn.execute("SELECT COUNT(*) FROM student").fetchone()[0]
            
            if 'exam' in existing_tables:
                db_stats['exams'] = conn.execute("SELECT COUNT(*) FROM exam").fetchone()[0]
            
            if 'question' in existing_tables:
                db_stats['questions'] = conn.execute("SELECT COUNT(*) FROM question").fetchone()[0]
            
            if 'course_outcome' in existing_tables:
                db_stats['course_outcomes'] = conn.execute("SELECT COUNT(*) FROM course_outcome").fetchone()[0]
            
            if 'program_outcome' in existing_tables:
                db_stats['program_outcomes'] = conn.execute("SELECT COUNT(*) FROM program_outcome").fetchone()[0]
            
            if 'score' in existing_tables:
                db_stats['scores'] = conn.execute("SELECT COUNT(*) FROM score").fetchone()[0]
            
            # Verify schema compatibility - check essential columns exist
            if 'course' in existing_tables:
                course_cols = [col[1] for col in conn.execute("PRAGMA table_info(course)").fetchall()]
                required_course_cols = ['id', 'code', 'name', 'semester']
                missing_course_cols = [col for col in required_course_cols if col not in course_cols]
                if missing_course_cols:
                    validation_errors.append(f"Course table missing columns: {', '.join(missing_course_cols)}")
            
            if 'student' in existing_tables:
                student_cols = [col[1] for col in conn.execute("PRAGMA table_info(student)").fetchall()]
                required_student_cols = ['id', 'student_id', 'first_name', 'last_name', 'course_id']
                missing_student_cols = [col for col in required_student_cols if col not in student_cols]
                if missing_student_cols:
                    validation_errors.append(f"Student table missing columns: {', '.join(missing_student_cols)}")
            
            # Check data integrity issues
            data_issues = []
            
            # Check for orphaned records
            if all(table in existing_tables for table in ['student', 'course']):
                orphaned_students = conn.execute(
                    """
                    SELECT COUNT(*) FROM student s
                    LEFT JOIN course c ON s.course_id = c.id
                    WHERE c.id IS NULL
                    """
                ).fetchone()[0]
                
                if orphaned_students > 0:
                    data_issues.append(f"Found {orphaned_students} students without valid course references")
            
            if all(table in existing_tables for table in ['exam', 'course']):
                orphaned_exams = conn.execute(
                    """
                    SELECT COUNT(*) FROM exam e
                    LEFT JOIN course c ON e.course_id = c.id
                    WHERE c.id IS NULL
                    """
                ).fetchone()[0]
                
                if orphaned_exams > 0:
                    data_issues.append(f"Found {orphaned_exams} exams without valid course references")
            
            # Find invalid data entries
            if 'course' in existing_tables:
                invalid_courses = conn.execute(
                    "SELECT COUNT(*) FROM course WHERE code IS NULL OR code = '' OR name IS NULL OR name = '' OR semester IS NULL OR semester = ''"
                ).fetchone()[0]
                
                if invalid_courses > 0:
                    data_issues.append(f"Found {invalid_courses} courses with missing required data")
            
            # Add data issues to validation errors
            validation_errors.extend(data_issues)
            
            conn.close()
            
        except sqlite3.Error as e:
            validation_errors.append(f"Invalid database file: {str(e)}")
        
        # Remove temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Database validation failed',
                'errors': validation_errors,
                'stats': db_stats
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Database file is valid and ready for import',
                'stats': db_stats
            })
            
    except Exception as e:
        logging.error(f"Error validating backup file: {str(e)}\n{traceback.format_exc()}")
        
        # Clean up temp file if it exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
            
        return jsonify({
            'success': False,
            'message': f'An error occurred while validating the file: {str(e)}'
        })