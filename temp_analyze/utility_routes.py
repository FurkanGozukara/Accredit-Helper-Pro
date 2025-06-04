from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file, make_response
from flask import current_app, Markup, stream_with_context # Added stream_with_context
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
import urllib.parse

utility_bp = Blueprint('utility', __name__, url_prefix='/utility')

# <<< MODIFIED FUNCTION START >>>
def export_to_excel_csv(data_iterable, filename, headers=None):
    """
    Generic function to export data to Excel-compatible CSV format using streaming.

    Args:
        data_iterable: An iterable (e.g., list, generator) yielding dictionaries or lists
                       containing the data to export.
        filename: The filename for the exported file (without extension)
        headers: Optional list of column headers. If None and the first item yielded
                 is a dict, dict keys will be used as headers. If the first item is
                 a list, it's assumed to be headers if headers=None.

    Returns:
        A Flask response object with the CSV file, streamed.
    """
    try:
        # Use a generator for streaming the response
        def generate_csv():
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';') # Semicolon for Excel

            # Write UTF-8 BOM for Excel compatibility
            yield b'\xef\xbb\xbf'  # UTF-8 BOM
            
            # Write Excel BOM specifier for semicolon separation
            output.write('sep=;\n')
            yield output.getvalue().encode('utf-8')
            output.seek(0)
            output.truncate(0) # Reset buffer

            first_item = None
            is_list_of_dicts = False
            processed_first = False

            # Need to peek at the first item to determine headers/type
            data_iterator = iter(data_iterable)
            try:
                first_item = next(data_iterator)
                processed_first = True
                is_list_of_dicts = isinstance(first_item, dict)
            except StopIteration:
                # Handle empty data iterable - yield nothing more
                pass

            # Determine and write headers
            actual_headers = headers # Use provided headers if they exist
            if not actual_headers:
                if is_list_of_dicts and first_item:
                    actual_headers = list(first_item.keys())
                elif not is_list_of_dicts and first_item: # Assume list of lists, first row is headers
                    actual_headers = first_item
                    # Since first_item was the header, reset processed_first
                    # so we don't write it again as data
                    processed_first = False

            if actual_headers:
                writer.writerow(actual_headers)
                output.seek(0)
                yield output.getvalue().encode('utf-8') # Changed to UTF-8
                output.seek(0)
                output.truncate(0)

            # --- Process data rows ---
            # Write the first item if it wasn't a header row
            if processed_first:
                if is_list_of_dicts:
                     writer.writerow([first_item.get(key, '') for key in actual_headers])
                else: # list of lists
                     writer.writerow(first_item)
                output.seek(0)
                yield output.getvalue().encode('utf-8') # Changed to UTF-8
                output.seek(0)
                output.truncate(0)

            # Process remaining items from the iterator
            for row in data_iterator:
                if is_list_of_dicts:
                    writer.writerow([row.get(key, '') for key in actual_headers])
                else: # list of lists
                    writer.writerow(row)

                output.seek(0)
                yield output.getvalue().encode('utf-8') # Changed to UTF-8
                output.seek(0)
                output.truncate(0) # Reset buffer for next chunk


        # --- Prepare Response ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_filename = f"{filename}_{timestamp}.csv"

        # Log export action (consider logging start and end/size if needed)
        log = Log(action="EXPORT_DATA_STREAM",
                 description=f"Started exporting data stream to: {full_filename}")
        db.session.add(log)
        db.session.commit()

        response = make_response(stream_with_context(generate_csv()))
        
        # Use RFC 5987 encoding for the filename to support international characters
        ascii_filename = full_filename.encode('ascii', 'replace').decode()
        
        # Properly URL encode the filename for RFC 5987
        encoded_filename = urllib.parse.quote(full_filename)
        
        content_disposition = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
        
        response.headers["Content-Disposition"] = content_disposition
        response.headers["Content-type"] = "text/csv; charset=UTF-8" # Changed to UTF-8
        return response

    except Exception as e:
        # Log the error more specifically if possible
        logging.error(f"Error streaming CSV export for {filename}: {str(e)}\n{traceback.format_exc()}") # Added traceback
        # Rollback potential log commit if error happened after logging start
        db.session.rollback()
        flash(f'An error occurred while exporting data: {str(e)}', 'error')
        # Redirect might not be ideal if called from AJAX, but okay for direct download
        # Consider returning an error response instead for API-like usage
        return redirect(url_for('index')) # Or a more relevant error page/redirect
# <<< MODIFIED FUNCTION END >>>

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
    """Delete a backup file"""
    try:
        # Ensure filename is not empty and has .db extension
        if not filename or not filename.endswith('.db'):
            return jsonify({'success': False, 'message': 'Invalid backup filename'})

        # Prevent directory traversal attacks
        if '..' in filename or '/' in filename:
            return jsonify({'success': False, 'message': 'Invalid backup filename'})

        backup_dir = current_app.config['BACKUP_FOLDER']
        backup_path = os.path.join(backup_dir, filename)

        # Check if file exists
        if not os.path.exists(backup_path):
            return jsonify({'success': False, 'message': f'Backup file {filename} not found'})

        # Remove the file
        os.remove(backup_path)

        # Remove from descriptions file if exists
        descriptions_file = os.path.join(backup_dir, 'backup_descriptions.json')
        if os.path.exists(descriptions_file):
            try:
                with open(descriptions_file, 'r') as f:
                    descriptions = json.load(f)

                # Remove the description if it exists
                if filename in descriptions:
                    del descriptions[filename]

                # Write back to the file
                with open(descriptions_file, 'w') as f:
                    json.dump(descriptions, f)
            except Exception as e:
                logging.warning(f"Error updating backup descriptions file: {str(e)}")

        # Log action
        log = Log(action="DELETE_BACKUP", description=f"Deleted backup file: {filename}")
        db.session.add(log)
        db.session.commit()

        return jsonify({'success': True, 'message': f'Backup {filename} deleted successfully'})
    except Exception as e:
        logging.error(f"Error deleting backup: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error deleting backup: {str(e)}'})

@utility_bp.route('/batch_delete_backups', methods=['POST'])
def batch_delete_backups():
    """Delete multiple backup files at once"""
    try:
        # Get the list of filenames from the form
        filenames_json = request.form.get('filenames')
        if not filenames_json:
            return jsonify({'success': False, 'message': 'No backup files specified'})

        try:
            filenames = json.loads(filenames_json)
        except json.JSONDecodeError:
            return jsonify({'success': False, 'message': 'Invalid backup filenames format'})

        if not isinstance(filenames, list) or len(filenames) == 0:
            return jsonify({'success': False, 'message': 'No backup files specified'})

        backup_dir = current_app.config['BACKUP_FOLDER']

        # Load descriptions file
        descriptions_file = os.path.join(backup_dir, 'backup_descriptions.json')
        descriptions = {}
        if os.path.exists(descriptions_file):
            try:
                with open(descriptions_file, 'r') as f:
                    descriptions = json.load(f)
            except Exception:
                descriptions = {}

        # Process each filename
        success_count = 0
        failed_count = 0
        failed_files = []

        for filename in filenames:
            # Ensure filename is not empty and has .db extension
            if not filename or not isinstance(filename, str) or not filename.endswith('.db'):
                failed_count += 1
                failed_files.append(filename)
                continue

            # Prevent directory traversal attacks
            if '..' in filename or '/' in filename:
                failed_count += 1
                failed_files.append(filename)
                continue

            backup_path = os.path.join(backup_dir, filename)

            # Skip if file doesn't exist
            if not os.path.exists(backup_path):
                failed_count += 1
                failed_files.append(filename)
                continue

            try:
                # Remove the file
                os.remove(backup_path)

                # Remove from descriptions if exists
                if filename in descriptions:
                    del descriptions[filename]

                success_count += 1
            except Exception as e:
                logging.error(f"Error deleting backup {filename}: {str(e)}")
                failed_count += 1
                failed_files.append(filename)

        # Update descriptions file
        if descriptions_file and os.path.exists(os.path.dirname(descriptions_file)):
            try:
                with open(descriptions_file, 'w') as f:
                    json.dump(descriptions, f)
            except Exception as e:
                logging.warning(f"Error updating backup descriptions file: {str(e)}")

        # Log action
        log_message = f"Batch deleted {success_count} backup files"
        if failed_count > 0:
            log_message += f", {failed_count} files failed to delete"

        log = Log(action="BATCH_DELETE_BACKUPS", description=log_message)
        db.session.add(log)
        db.session.commit()

        # Prepare response message
        message = f"Successfully deleted {success_count} backup files."
        if failed_count > 0:
            message += f" {failed_count} files could not be deleted."

        return jsonify({
            'success': True,
            'message': message,
            'successful_count': success_count,
            'failed_count': failed_count,
            'failed_files': failed_files
        })
    except Exception as e:
        logging.error(f"Error in batch delete: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error deleting backups: {str(e)}'})

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

@utility_bp.route('/index_status')
def index_status():
    """Show database index status for debugging"""
    from db_index_manager import get_index_status_for_debug
    
    try:
        status = get_index_status_for_debug()
        return render_template('utility/index_status.html', 
                             status=status, 
                             active_page='admin')
    except Exception as e:
        flash(f'Error getting index status: {str(e)}', 'error')
        return redirect(url_for('index'))

@utility_bp.route('/recreate_indexes', methods=['POST'])
def recreate_indexes():
    """Manually recreate missing database indexes"""
    try:
        if hasattr(current_app, 'index_manager'):
            created_count = current_app.index_manager.create_missing_indexes_only()
            if created_count > 0:
                flash(f'Successfully created {created_count} missing database indexes', 'success')
            else:
                flash('All required indexes already exist', 'info')
        else:
            flash('Index manager not available', 'error')
    except Exception as e:
        flash(f'Error recreating indexes: {str(e)}', 'error')
    
    return redirect(url_for('utility.index_status'))

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
    return redirect(url_for('utility.help_page') + '#remote-access')

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
    """
    Import data from an uploaded backup file and merge it with the current database.
    This version uses proper try/except/finally blocks and context managers so that
    database connections are closed before the temporary file is removed.
    Key columns such as max_score, exam weights, course settings, and scores are
    imported, and makeup exam relationships are updated.
    """
    import os, glob, sqlite3, shutil
    from flask import Markup
    temp_path = os.path.join(current_app.config['BACKUP_FOLDER'], 'temp_import.db')

    try:
        # POST branch: process the uploaded backup file.
        if request.method == 'POST':
            # Validate file upload and confirmation.
            if 'backup_file' not in request.files:
                flash('No backup file provided', 'error')
                return redirect(url_for('utility.import_database'))
            backup_file = request.files['backup_file']
            if backup_file.filename.strip() == '':
                flash('No backup file selected', 'error')
                return redirect(url_for('utility.import_database'))
            if 'confirm_import' not in request.form:
                flash('You must confirm that you understand the import process', 'error')
                return redirect(url_for('utility.import_database'))

            # Save the uploaded file.
            backup_file.save(temp_path)

            # Validate the backup file.
            with sqlite3.connect(temp_path) as imp_conn:
                imp_conn.row_factory = sqlite3.Row
                required_tables = ['course', 'exam', 'student', 'question', 'score', 'course_outcome', 'program_outcome']
                existing_tables = [row[0] for row in imp_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()]
                missing_tables = [table for table in required_tables if table not in existing_tables]
                if missing_tables:
                    flash(f"Invalid database: Missing required tables: {', '.join(missing_tables)}", 'error')
                    return redirect(url_for('utility.import_database'))
                # Warn about optional tables.
                for table in ['achievement_level', 'course_settings', 'exam_weight', 'student_exam_attendance']:
                    if table not in existing_tables:
                        flash(f"Optional table '{table}' not found. Related data won't be imported.", 'warning')

            # Create a backup of the current database.
            db_path = os.path.join('instance', 'accredit_data.db')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_import_backup = os.path.join(current_app.config['BACKUP_FOLDER'], f"pre_import_backup_{timestamp}.db")
            if os.path.exists(db_path):
                shutil.copy2(db_path, pre_import_backup)
                flash(f"Created backup of current database before import: pre_import_backup_{timestamp}.db", "info")

            # Get user-selected import options.
            import_courses            = request.form.get('import_courses') == 'on'
            import_students           = request.form.get('import_students') == 'on'
            import_exams              = request.form.get('import_exams') == 'on'
            import_outcomes           = request.form.get('import_outcomes') == 'on'
            import_program_outcomes   = request.form.get('import_program_outcomes') == 'on'
            import_achievement_levels = request.form.get('import_achievement_levels') == 'on'
            import_course_settings    = request.form.get('import_course_settings') == 'on'
            import_exam_weights       = request.form.get('import_exam_weights') == 'on'
            import_attendance         = request.form.get('import_attendance') == 'on'
            import_scores             = request.form.get('import_scores') == 'on'

            # Initialize mapping dictionaries and summary counters.
            import_summary = {
                'courses_imported': 0,
                'outcomes_imported': 0,
                'program_outcomes_imported': 0,
                'achievement_levels_imported': 0,
                'course_settings_imported': 0,
                'students_imported': 0,
                'exams_imported': 0,
                'questions_imported': 0,
                'exam_weights_imported': 0,
                'scores_imported': 0,
                'attendance_imported': 0,
                'co_po_imported': 0,
                'question_co_imported': 0,
                'errors': []  # Track any errors during import
            }
            course_id_map = {}          # backup course id -> current course id
            outcome_id_map = {}         # backup course outcome id -> current course outcome id
            program_outcome_id_map = {} # backup program outcome id -> current program outcome id
            student_id_map = {}         # backup student primary key (id) -> current student id
            exam_id_map = {}            # backup exam id -> current exam id
            question_id_map = {}        # backup question id -> current question id

            # Open both current and backup databases using context managers.
            with sqlite3.connect(db_path) as current_db, sqlite3.connect(temp_path) as import_db:
                current_db.row_factory = sqlite3.Row
                import_db.row_factory = sqlite3.Row

                # Helper function to safely get column value
                def safe_get(row, column, default=None):
                    try:
                        return row[column] if row[column] is not None else default
                    except (IndexError, KeyError):
                        return default

                # Helper function to convert various boolean formats to integer (0 or 1)
                def to_int_bool(value):
                    if value is None:
                        return 0
                    if isinstance(value, bool):
                        return 1 if value else 0
                    if isinstance(value, int):
                        return 1 if value else 0
                    if isinstance(value, str):
                        return 1 if value.lower() in ('true', 't', 'yes', 'y', '1') else 0
                    return 0

                # Begin a transaction.
                current_db.execute("BEGIN TRANSACTION")

                try:
                    # (Optional) Get source database schema info.
                    source_schema = {}
                    for table in existing_tables:
                        source_schema[table] = {
                            column[1]: {'type': column[2], 'notnull': column[3], 'dflt_value': column[4]}
                            for column in import_db.execute(f"PRAGMA table_info({table})").fetchall()
                        }

                    # STEP 1: IMPORT COURSES
                    if import_courses:
                        courses = import_db.execute("SELECT * FROM course").fetchall()
                        for row in courses:
                            if not safe_get(row, 'code') or not safe_get(row, 'name') or not safe_get(row, 'semester'):
                                import_summary['errors'].append("Skipped course with missing required fields")
                                continue

                            existing = current_db.execute(
                                "SELECT id FROM course WHERE code=? AND semester=?",
                                (safe_get(row, 'code'), safe_get(row, 'semester'))
                            ).fetchone()

                            if existing:
                                course_id_map[safe_get(row, 'id')] = existing['id']
                            else:
                                cw = safe_get(row, 'course_weight', 1.0)
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                cur = current_db.execute(
                                    "INSERT INTO course (code, name, semester, course_weight, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                                    (safe_get(row, 'code'), safe_get(row, 'name'), safe_get(row, 'semester'), cw, created, updated)
                                )
                                course_id_map[safe_get(row, 'id')] = cur.lastrowid
                                import_summary['courses_imported'] += 1

                    # STEP 2: IMPORT COURSE OUTCOMES
                    if import_outcomes:
                        outcomes = import_db.execute("SELECT * FROM course_outcome").fetchall()
                        for row in outcomes:
                            if not safe_get(row, 'code') or not safe_get(row, 'course_id'):
                                import_summary['errors'].append("Skipped course outcome with missing required fields")
                                continue
                            if safe_get(row, 'course_id') not in course_id_map:
                                import_summary['errors'].append(f"Skipped course outcome with invalid course_id: {safe_get(row, 'course_id')}")
                                continue
                            curr_course = course_id_map[safe_get(row, 'course_id')]
                            existing = current_db.execute(
                                "SELECT id FROM course_outcome WHERE code=? AND course_id=?",
                                (safe_get(row, 'code'), curr_course)
                            ).fetchone()
                            if existing:
                                outcome_id_map[safe_get(row, 'id')] = existing['id']
                            else:
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                cur = current_db.execute(
                                    "INSERT INTO course_outcome (code, description, course_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                                    (
                                        safe_get(row, 'code'),
                                        safe_get(row, 'description', ''),
                                        curr_course,
                                        created,
                                        updated
                                    )
                                )
                                outcome_id_map[safe_get(row, 'id')] = cur.lastrowid
                                import_summary['outcomes_imported'] += 1

                    # STEP 3: IMPORT PROGRAM OUTCOMES
                    if import_program_outcomes:
                        pos = import_db.execute("SELECT * FROM program_outcome").fetchall()
                        for row in pos:
                            if not safe_get(row, 'code') or not safe_get(row, 'description'):
                                import_summary['errors'].append("Skipped program outcome with missing required fields")
                                continue
                            existing = current_db.execute(
                                "SELECT id FROM program_outcome WHERE code=?",
                                (safe_get(row, 'code'),)
                            ).fetchone()
                            if existing:
                                program_outcome_id_map[safe_get(row, 'id')] = existing['id']
                            else:
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                cur = current_db.execute(
                                    "INSERT INTO program_outcome (code, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
                                    (safe_get(row, 'code'), safe_get(row, 'description'), created, updated)
                                )
                                program_outcome_id_map[safe_get(row, 'id')] = cur.lastrowid
                                import_summary['program_outcomes_imported'] += 1

                    # STEP 4: IMPORT ACHIEVEMENT LEVELS (Optional)
                    if import_achievement_levels:
                        table_exist = import_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='achievement_level'").fetchone()
                        if table_exist:
                            levels = import_db.execute("SELECT * FROM achievement_level").fetchall()
                            for row in levels:
                                if safe_get(row, 'course_id') not in course_id_map:
                                    import_summary['errors'].append(f"Skipped achievement level with invalid course_id: {safe_get(row, 'course_id')}")
                                    continue
                                curr_course = course_id_map[safe_get(row, 'course_id')]
                                existing = current_db.execute(
                                    "SELECT id FROM achievement_level WHERE course_id=? AND name=?",
                                    (curr_course, safe_get(row, 'name', ''))
                                ).fetchone()
                                if existing:
                                    continue
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                name = safe_get(row, 'name', 'Achievement Level')
                                min_score = safe_get(row, 'min_score', 0.0)
                                max_score = safe_get(row, 'max_score', 100.0)
                                color = safe_get(row, 'color', 'primary')
                                current_db.execute(
                                    """
                                    INSERT INTO achievement_level
                                    (course_id, name, min_score, max_score, color, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (curr_course, name, min_score, max_score, color, created, updated)
                                )
                                import_summary['achievement_levels_imported'] += 1

                    # STEP 5: IMPORT COURSE SETTINGS (Optional)
                    if import_course_settings:
                        table_exist = import_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_settings'").fetchone()
                        if table_exist:
                            settings = import_db.execute("SELECT * FROM course_settings").fetchall()
                            for row in settings:
                                if safe_get(row, 'course_id') not in course_id_map:
                                    import_summary['errors'].append(f"Skipped course settings with invalid course_id: {safe_get(row, 'course_id')}")
                                    continue
                                curr_course = course_id_map[safe_get(row, 'course_id')]
                                existing = current_db.execute("SELECT id FROM course_settings WHERE course_id=?", (curr_course,)).fetchone()
                                if existing:
                                    continue
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                success_rate_method = safe_get(row, 'success_rate_method', 'absolute')
                                relative_success_threshold = safe_get(row, 'relative_success_threshold', 60.0)
                                excluded = to_int_bool(safe_get(row, 'excluded', False))
                                current_db.execute(
                                    """
                                    INSERT INTO course_settings
                                    (course_id, success_rate_method, relative_success_threshold, excluded, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    """,
                                    (curr_course, success_rate_method, relative_success_threshold, excluded, created, updated)
                                )
                                import_summary['course_settings_imported'] += 1

                    # STEP 6: IMPORT STUDENTS
                    if import_students:
                        students = import_db.execute("SELECT * FROM student").fetchall()
                        for row in students:
                            if not safe_get(row, 'student_id') or safe_get(row, 'course_id') not in course_id_map:
                                import_summary['errors'].append(f"Skipped student with missing student_id or invalid course_id: {safe_get(row, 'course_id')}")
                                continue
                            curr_course = course_id_map[safe_get(row, 'course_id')]
                            existing = current_db.execute(
                                "SELECT id FROM student WHERE student_id=? AND course_id=?",
                                (safe_get(row, 'student_id'), curr_course)
                            ).fetchone()
                            if existing:
                                student_id_map[safe_get(row, 'id')] = existing['id']
                            else:
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                excluded = to_int_bool(safe_get(row, 'excluded', False))
                                cur = current_db.execute(
                                    """
                                    INSERT INTO student
                                    (student_id, first_name, last_name, course_id, excluded, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        safe_get(row, 'student_id'),
                                        safe_get(row, 'first_name', ''),
                                        safe_get(row, 'last_name', ''),
                                        curr_course,
                                        excluded,
                                        created,
                                        updated
                                    )
                                )
                                student_id_map[safe_get(row, 'id')] = cur.lastrowid
                                import_summary['students_imported'] += 1

                    # STEP 7: IMPORT EXAMS
                    if import_exams:
                        exam_columns = [col[1] for col in import_db.execute("PRAGMA table_info(exam)").fetchall()]
                        exams = import_db.execute("SELECT * FROM exam").fetchall()
                        for row in exams:
                            if safe_get(row, 'course_id') not in course_id_map:
                                import_summary['errors'].append(f"Skipped exam with invalid course_id: {safe_get(row, 'course_id')}")
                                continue
                            curr_course = course_id_map[safe_get(row, 'course_id')]
                            existing = current_db.execute(
                                "SELECT id FROM exam WHERE name=? AND course_id=?",
                                (safe_get(row, 'name', ''), curr_course)
                            ).fetchone()
                            if existing:
                                exam_id_map[safe_get(row, 'id')] = existing['id']
                            else:
                                max_score = safe_get(row, 'max_score', 100.0)
                                exam_date = safe_get(row, 'exam_date', None)
                                is_makeup = to_int_bool(safe_get(row, 'is_makeup', False))
                                is_final = to_int_bool(safe_get(row, 'is_final', False))
                                is_mandatory = to_int_bool(safe_get(row, 'is_mandatory', False))
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                cur = current_db.execute(
                                    """
                                    INSERT INTO exam
                                    (name, max_score, exam_date, course_id, is_makeup, is_final, is_mandatory, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (safe_get(row, 'name', ''), max_score, exam_date, curr_course, is_makeup, is_final, is_mandatory, created, updated)
                                )
                                exam_id_map[safe_get(row, 'id')] = cur.lastrowid
                                import_summary['exams_imported'] += 1

                    # STEP 8: IMPORT QUESTIONS
                    if import_exams:
                        questions = import_db.execute("SELECT * FROM question").fetchall()
                        for row in questions:
                            if safe_get(row, 'exam_id') not in exam_id_map:
                                import_summary['errors'].append(f"Skipped question with invalid exam_id: {safe_get(row, 'exam_id')}")
                                continue
                            curr_exam = exam_id_map[safe_get(row, 'exam_id')]
                            existing = current_db.execute(
                                "SELECT id FROM question WHERE exam_id=? AND number=?",
                                (curr_exam, safe_get(row, 'number', 0))
                            ).fetchone()
                            if existing:
                                question_id_map[safe_get(row, 'id')] = existing['id']
                            else:
                                text = safe_get(row, 'text', '')
                                max_score = safe_get(row, 'max_score', 0.0)
                                number = safe_get(row, 'number', 0)
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                cur = current_db.execute(
                                    """
                                    INSERT INTO question
                                    (text, number, max_score, exam_id, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    """,
                                    (text, number, max_score, curr_exam, created, updated)
                                )
                                question_id_map[safe_get(row, 'id')] = cur.lastrowid
                                import_summary['questions_imported'] += 1

                    # STEP 9: IMPORT EXAM WEIGHTS (Optional)
                    if import_exam_weights:
                        table_exist = import_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='exam_weight'").fetchone()
                        if table_exist:
                            weights = import_db.execute("SELECT * FROM exam_weight").fetchall()
                            for row in weights:
                                backup_exam_id = safe_get(row, 'exam_id')
                                backup_course_id = safe_get(row, 'course_id')
                                if backup_exam_id not in exam_id_map or backup_course_id not in course_id_map:
                                    import_summary['errors'].append(
                                        f"Skipped exam weight with invalid exam_id or course_id: e{backup_exam_id}, c{backup_course_id}"
                                    )
                                    continue
                                curr_exam = exam_id_map[backup_exam_id]
                                curr_course = course_id_map[backup_course_id]
                                weight_value = safe_get(row, 'weight', 0.0)
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                existing = current_db.execute(
                                    "SELECT id FROM exam_weight WHERE exam_id=? AND course_id=?",
                                    (curr_exam, curr_course)
                                ).fetchone()
                                if existing:
                                    current_db.execute(
                                        "UPDATE exam_weight SET weight=?, updated_at=? WHERE id=?",
                                        (weight_value, updated, existing['id'])
                                    )
                                    import_summary['exam_weights_imported'] += 1
                                else:
                                    current_db.execute(
                                        "INSERT INTO exam_weight (exam_id, course_id, weight, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                                        (curr_exam, curr_course, weight_value, created, updated)
                                    )
                                    import_summary['exam_weights_imported'] += 1
                        else:
                            flash("Exam weight table not found in backup.", "warning")

                    # STEP 10: IMPORT SCORES
                    if import_scores:
                        scores = import_db.execute("SELECT * FROM score").fetchall()
                        for row in scores:
                            backup_student_fk = safe_get(row, 'student_id')
                            backup_question_fk = safe_get(row, 'question_id')
                            backup_exam_fk = safe_get(row, 'exam_id')
                            if (backup_student_fk not in student_id_map or
                                backup_question_fk not in question_id_map or
                                backup_exam_fk not in exam_id_map):
                                import_summary['errors'].append(
                                    f"Skipped score with invalid foreign keys: s{backup_student_fk}, q{backup_question_fk}, e{backup_exam_fk}"
                                )
                                continue
                            curr_student = student_id_map[backup_student_fk]
                            curr_question = question_id_map[backup_question_fk]
                            curr_exam = exam_id_map[backup_exam_fk]
                            existing = current_db.execute(
                                "SELECT id FROM score WHERE student_id=? AND question_id=? AND exam_id=?",
                                (curr_student, curr_question, curr_exam)
                            ).fetchone()
                            score_value = safe_get(row, 'score', 0.0)
                            if existing:
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                current_db.execute(
                                    "UPDATE score SET score=?, updated_at=? WHERE id=?",
                                    (score_value, updated, existing['id'])
                                )
                                import_summary['scores_imported'] += 1
                            else:
                                created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                current_db.execute(
                                    "INSERT INTO score (score, student_id, question_id, exam_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                                    (score_value, curr_student, curr_question, curr_exam, created, updated)
                                )
                                import_summary['scores_imported'] += 1

                    # STEP 11: IMPORT STUDENT EXAM ATTENDANCE (Optional)
                    if import_attendance:
                        table_exist = import_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_exam_attendance'").fetchone()
                        if table_exist:
                            attendance_rows = import_db.execute("SELECT * FROM student_exam_attendance").fetchall()
                            for row in attendance_rows:
                                if safe_get(row, 'student_id') not in student_id_map or safe_get(row, 'exam_id') not in exam_id_map:
                                    import_summary['errors'].append(
                                        f"Skipped attendance record with invalid student_id or exam_id: s{safe_get(row, 'student_id')}, e{safe_get(row, 'exam_id')}"
                                    )
                                    continue
                                curr_student = student_id_map[safe_get(row, 'student_id')]
                                curr_exam = exam_id_map[safe_get(row, 'exam_id')]
                                existing = current_db.execute(
                                    "SELECT id FROM student_exam_attendance WHERE student_id=? AND exam_id=?",
                                    (curr_student, curr_exam)
                                ).fetchone()
                                if existing:
                                    attended = to_int_bool(safe_get(row, 'attended', True))
                                    updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                    current_db.execute(
                                        "UPDATE student_exam_attendance SET attended=?, updated_at=? WHERE id=?",
                                        (attended, updated, existing['id'])
                                    )
                                    import_summary['attendance_imported'] += 1
                                else:
                                    attended = to_int_bool(safe_get(row, 'attended', True))
                                    created = safe_get(row, 'created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                    updated = safe_get(row, 'updated_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                    current_db.execute(
                                        """
                                        INSERT INTO student_exam_attendance
                                        (student_id, exam_id, attended, created_at, updated_at)
                                        VALUES (?, ?, ?, ?, ?)
                                        """,
                                        (curr_student, curr_exam, attended, created, updated)
                                    )
                                    import_summary['attendance_imported'] += 1

                    # STEP 12: UPDATE MAKEUP EXAM RELATIONSHIPS
                    for row in import_db.execute("SELECT id, makeup_for FROM exam WHERE makeup_for IS NOT NULL").fetchall():
                        source_exam_id = safe_get(row, 'id')
                        source_makeup_for = safe_get(row, 'makeup_for')
                        if source_exam_id in exam_id_map and source_makeup_for in exam_id_map:
                            dest_exam_id = exam_id_map[source_exam_id]
                            dest_makeup_for = exam_id_map[source_makeup_for]
                            current_db.execute("UPDATE exam SET makeup_for=? WHERE id=?", (dest_makeup_for, dest_exam_id))

                    # STEP 13: IMPORT CO-PO ASSOCIATIONS AND WEIGHTS
                    if import_outcomes and import_program_outcomes:
                        # First check if the table has relative_weight column for older backups
                        has_relative_weight = False
                        try:
                            columns = [col[1] for col in import_db.execute("PRAGMA table_info(course_outcome_program_outcome)").fetchall()]
                            has_relative_weight = 'relative_weight' in columns
                        except:
                            import_summary['errors'].append("Could not determine if course_outcome_program_outcome table has relative_weight column")

                        # Check if destination table has relative_weight column
                        dest_has_relative_weight = False
                        try:
                            dest_columns = [col[1] for col in current_db.execute("PRAGMA table_info(course_outcome_program_outcome)").fetchall()]
                            dest_has_relative_weight = 'relative_weight' in dest_columns
                        except:
                            import_summary['errors'].append("Could not determine if destination course_outcome_program_outcome table has relative_weight column")

                        # Fetch CO-PO associations
                        try:
                            if has_relative_weight:
                                associations = import_db.execute(
                                    "SELECT course_outcome_id, program_outcome_id, relative_weight FROM course_outcome_program_outcome"
                                ).fetchall()
                            else:
                                associations = import_db.execute(
                                    "SELECT course_outcome_id, program_outcome_id FROM course_outcome_program_outcome"
                                ).fetchall()

                            for row in associations:
                                backup_co_id = safe_get(row, 'course_outcome_id')
                                backup_po_id = safe_get(row, 'program_outcome_id')

                                if backup_co_id not in outcome_id_map or backup_po_id not in program_outcome_id_map:
                                    import_summary['errors'].append(
                                        f"Skipped CO-PO association with invalid IDs: co{backup_co_id}, po{backup_po_id}"
                                    )
                                    continue

                                curr_co_id = outcome_id_map[backup_co_id]
                                curr_po_id = program_outcome_id_map[backup_po_id]

                                # Check if association already exists
                                exists = current_db.execute(
                                    "SELECT 1 FROM course_outcome_program_outcome WHERE course_outcome_id=? AND program_outcome_id=?",
                                    (curr_co_id, curr_po_id)
                                ).fetchone()

                                if not exists:
                                    # Check if destination table has relative_weight column
                                    dest_columns = [col[1] for col in current_db.execute("PRAGMA table_info(course_outcome_program_outcome)").fetchall()]
                                    dest_has_relative_weight = 'relative_weight' in dest_columns

                                    if dest_has_relative_weight:
                                        # Get the relative weight with default of 1.0
                                        relative_weight = safe_get(row, 'relative_weight', 1.0)
                                        current_db.execute(
                                            "INSERT INTO course_outcome_program_outcome (course_outcome_id, program_outcome_id, relative_weight) VALUES (?, ?, ?)",
                                            (curr_co_id, curr_po_id, relative_weight)
                                        )
                                    else:
                                        # For older backups without the relative_weight column
                                        current_db.execute(
                                            "INSERT INTO course_outcome_program_outcome (course_outcome_id, program_outcome_id) VALUES (?, ?)",
                                            (curr_co_id, curr_po_id)
                                        )
                                    import_summary['co_po_imported'] += 1
                                elif has_relative_weight and dest_has_relative_weight:
                                    # Update the weight if the association already exists and both tables have relative_weight
                                    relative_weight = safe_get(row, 'relative_weight', 1.0)
                                    try:
                                        current_db.execute(
                                            "UPDATE course_outcome_program_outcome SET relative_weight=? WHERE course_outcome_id=? AND program_outcome_id=?",
                                            (relative_weight, curr_co_id, curr_po_id)
                                        )
                                    except Exception as e:
                                        import_summary['errors'].append(f"Error updating CO-PO weight: {str(e)}")
                        except Exception as e:
                            import_summary['errors'].append(f"Error importing CO-PO associations: {str(e)}")

                    # STEP 14: IMPORT COURSE-OUTCOME QUESTION ASSOCIATIONS
                    if import_outcomes and import_exams:
                        try:
                            # Check if the source database has relative_weight column
                            source_has_relative_weight = False
                            try:
                                columns = [column[1] for column in import_db.execute("PRAGMA table_info(question_course_outcome)").fetchall()]
                                source_has_relative_weight = 'relative_weight' in columns
                            except Exception as ce:
                                import_summary['errors'].append(f"Could not check question_course_outcome columns: {str(ce)}")
                            
                            # Modify query based on whether source has the relative_weight column
                            if source_has_relative_weight:
                                query = "SELECT question_id, course_outcome_id, relative_weight FROM question_course_outcome"
                            else:
                                query = "SELECT question_id, course_outcome_id FROM question_course_outcome"
                                
                            associations = import_db.execute(query).fetchall()
                            for row in associations:
                                backup_q_id = safe_get(row, 'question_id')
                                backup_co_id = safe_get(row, 'course_outcome_id')
                                # Get relative weight if available, otherwise use default 1.0
                                relative_weight = safe_get(row, 'relative_weight', 1.0)

                                if backup_q_id not in question_id_map or backup_co_id not in outcome_id_map:
                                    import_summary['errors'].append(
                                        f"Skipped question-CO association with invalid IDs: q{backup_q_id}, co{backup_co_id}"
                                    )
                                    continue

                                curr_q_id = question_id_map[backup_q_id]
                                curr_co_id = outcome_id_map[backup_co_id]

                                # Check if association already exists
                                exists = current_db.execute(
                                    "SELECT 1 FROM question_course_outcome WHERE question_id=? AND course_outcome_id=?",
                                    (curr_q_id, curr_co_id)
                                ).fetchone()

                                if not exists:
                                    try:
                                        current_db.execute(
                                            "INSERT INTO question_course_outcome (question_id, course_outcome_id, relative_weight) VALUES (?, ?, ?)",
                                            (curr_q_id, curr_co_id, relative_weight)
                                        )
                                        if 'question_co_imported' not in import_summary:
                                            import_summary['question_co_imported'] = 0
                                        import_summary['question_co_imported'] += 1
                                    except Exception as qe:
                                        import_summary['errors'].append(f"Error associating question {curr_q_id} with outcome {curr_co_id}: {str(qe)}")
                        except Exception as e:
                            import_summary['errors'].append(f"Error importing question-CO associations: {str(e)}")

                    current_db.execute("COMMIT")

                    # OPTIONAL: Perform an integrity check.
                    try:
                        integrity_issues = []
                        orphaned_students = current_db.execute(
                            "SELECT COUNT(*) FROM student s LEFT JOIN course c ON s.course_id = c.id WHERE c.id IS NULL"
                        ).fetchone()[0]
                        if orphaned_students > 0:
                            integrity_issues.append(f"Found {orphaned_students} students without valid course references.")
                        orphaned_exams = current_db.execute(
                            "SELECT COUNT(*) FROM exam e LEFT JOIN course c ON e.course_id = c.id WHERE c.id IS NULL"
                        ).fetchone()[0]
                        if orphaned_exams > 0:
                            integrity_issues.append(f"Found {orphaned_exams} exams without valid course references.")
                        orphaned_questions = current_db.execute(
                            "SELECT COUNT(*) FROM question q LEFT JOIN exam e ON q.exam_id = e.id WHERE e.id IS NULL"
                        ).fetchone()[0]
                        if orphaned_questions > 0:
                            integrity_issues.append(f"Found {orphaned_questions} questions without valid exam references.")
                        orphaned_scores = current_db.execute(
                            """
                            SELECT COUNT(*) FROM score s
                            LEFT JOIN question q ON s.question_id = q.id
                            LEFT JOIN student st ON s.student_id = st.id
                            LEFT JOIN exam e ON s.exam_id = e.id
                            WHERE q.id IS NULL OR st.id IS NULL OR e.id IS NULL
                            """
                        ).fetchone()[0]
                        if orphaned_scores > 0:
                            integrity_issues.append(f"Found {orphaned_scores} scores with missing references.")
                        if integrity_issues:
                            msg = "<strong>Database Integrity Check:</strong><br>" + "<br>".join(integrity_issues)
                            flash(Markup(msg), 'warning')
                        else:
                            flash("Database integrity check passed. No issues detected.", "info")
                    except Exception as e:
                        flash(f"Could not complete database integrity check: {str(e)}", "warning")
                        import_summary['errors'].append(f"Integrity check error: {str(e)}")

                except Exception as import_error:
                    current_db.execute("ROLLBACK")
                    error_message = f"Import failed: {str(import_error)}"
                    import_summary['errors'].append(error_message)
                    logging.error(f"Import error: {error_message}\n{traceback.format_exc()}")
                    flash(error_message, "error")

                # Build and flash an import summary message.
                summary_message = "<strong>Import Summary:</strong><br>"
                for key, count in import_summary.items():
                    if key != 'errors' and count:
                        summary_message += f"- {count} {key.replace('_', ' ')}<br>"
                if import_summary.get('errors', []):
                    error_count = len(import_summary['errors'])
                    if error_count > 0:
                        summary_message += f"<br><strong>Warnings/Errors ({error_count}):</strong><br>"
                        for error in import_summary['errors'][:5]:
                            summary_message += f"- {error}<br>"
                        if error_count > 5:
                            summary_message += f"- ... and {error_count - 5} more (see logs for details)<br>"

                log_description = f"Imported data from backup file {backup_file.filename}. "
                if import_summary.get('errors'):
                    log_description += f"Encountered {len(import_summary['errors'])} issues during import."

                try:
                    current_db.execute(
                        "INSERT INTO log (action, description, timestamp) VALUES (?, ?, ?)",
                        ("IMPORT_DATABASE", log_description, datetime.now())
                    )
                    current_db.commit()
                except Exception as log_error:
                    logging.error(f"Could not log import action: {str(log_error)}")

                flash(Markup(summary_message), "success")

        # GET branch: list available backup files.
        backup_dir = current_app.config['BACKUP_FOLDER']
        backups = []
        if os.path.exists(backup_dir):
            for backup_file in glob.glob(os.path.join(backup_dir, "*.db")):
                filename = os.path.basename(backup_file)
                created_at = os.path.getmtime(backup_file)
                size = os.path.getsize(backup_file) / (1024 * 1024)
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
                    'description': backup_type
                })
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        return render_template('utility/import.html', backups=backups, active_page='utilities')

    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", "error")
        logging.error(f"Unexpected error in import: {str(e)}", exc_info=True)
        return redirect(url_for('utility.index'))

    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as file_err:
            logging.error(f"Error deleting temporary file: {file_err}", exc_info=True)

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