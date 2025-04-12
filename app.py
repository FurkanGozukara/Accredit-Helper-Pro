import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
import sqlite3
import csv
import json
import shutil
import webbrowser
import argparse
import subprocess
import sys
import threading
import select
import time

# Import db from models
from models import db, init_db_session
# Import database migration function
from db_migrations import check_and_update_database

def create_app():
    app = Flask(__name__)
    
    # Get the absolute path to the current directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_for_local_use')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(base_dir, "instance", "accredit_data.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['BACKUP_FOLDER'] = os.path.join(base_dir, 'backups')
    
    # Ensure instance and backup folders exist
    os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'instance'), exist_ok=True)
    
    # Initialize extensions with app
    db.init_app(app)
    init_db_session(app)  # Initialize the scoped session
    migrate = Migrate(app, db)
    
    # Setup logging
    logging.basicConfig(
        filename='app.log',
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Import models
    from models import Course, Exam, CourseOutcome, ProgramOutcome, Question, Student, Score, ExamWeight, AchievementLevel
    
    # Register blueprints
    from routes.course_routes import course_bp
    from routes.exam_routes import exam_bp
    from routes.outcome_routes import outcome_bp
    from routes.student_routes import student_bp
    from routes.calculation_routes import calculation_bp
    from routes.utility_routes import utility_bp
    from routes.question_routes import question_bp
    from routes.api_routes import api_bp
    
    app.register_blueprint(course_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(outcome_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(calculation_bp)
    app.register_blueprint(utility_bp)
    app.register_blueprint(question_bp)
    app.register_blueprint(api_bp)
    
    # Create tables if they don't exist - moved after imports
    with app.app_context():
        db.create_all()
        # Run database migrations to update schema for existing installations
        check_and_update_database(app)
        # Initialize default program outcomes if they don't exist
        initialize_program_outcomes()
    
    # Home route
    @app.route('/')
    def index():
        # Get sort parameter from query string, default to 'semester_desc'
        sort = request.args.get('sort', 'semester_desc')
        search = request.args.get('search', '')

        # Start with a base query
        query = Course.query

        # Apply search filter if provided
        if search:
            query = query.filter(
                db.or_(
                    Course.code.ilike(f'%{search}%'),
                    Course.name.ilike(f'%{search}%')
                )
            )

        # Apply sorting
        if sort == 'code_asc':
            query = query.order_by(Course.code.asc())
        elif sort == 'code_desc':
            query = query.order_by(Course.code.desc())
        elif sort == 'name_asc':
            query = query.order_by(Course.name.asc())
        elif sort == 'name_desc':
            query = query.order_by(Course.name.desc())
        elif sort == 'created_asc':
            query = query.order_by(Course.created_at.asc())
        elif sort == 'created_desc':
            query = query.order_by(Course.created_at.desc())
        elif sort == 'updated_asc':
            query = query.order_by(Course.updated_at.asc())
        elif sort == 'updated_desc':
            query = query.order_by(Course.updated_at.desc())
        elif sort == 'semester_asc' or sort == 'semester_desc':
            # Get all courses first to perform custom semester sorting
            courses = query.all()
            
            # Calculate student counts for each course
            student_counts = {}
            for course in courses:
                # Count non-excluded students
                student_counts[course.id] = Student.query.filter_by(course_id=course.id, excluded=False).count()
            
            # Define a function to extract year and term for sorting
            def semester_sort_key(course):
                semester = course.semester or ""
                import re
                
                # Extract year using a more flexible regex pattern
                # Look for any 4-digit number that might represent a year
                year_match = re.search(r'\b(\d{4})\b', semester)
                year = int(year_match.group(1)) if year_match else 0
                
                # Use regex to identify terms more flexibly
                term_priority = 0
                
                # Multi-language support for terms (case insensitive)
                # Spring terms (priority 3)
                if re.search(r'\b(spring|bahar|sp|primavera|frühling|printemps|весна|春|봄|vår|voorjaar|primavera)\b', 
                            semester, re.IGNORECASE):
                    term_priority = 3
                # Fall terms (priority 2)
                elif re.search(r'\b(fall|güz|fa|otoño|herbst|automne|осень|秋|가을|höst|herfst|autunno)\b', 
                              semester, re.IGNORECASE):
                    term_priority = 2
                # Summer terms (priority 1)
                elif re.search(r'\b(summer|yaz|su|verano|sommer|été|лето|夏|여름|sommar|zomer|estate)\b', 
                              semester, re.IGNORECASE):
                    term_priority = 1
                # Winter terms (priority 0)
                elif re.search(r'\b(winter|kış|wi|invierno|冬|겨울|vinter|inverno|hiver|зима)\b', 
                              semester, re.IGNORECASE):
                    term_priority = 0
                # Try to find numeric semester designations (e.g., "1", "2", "3", "4" for quarters)
                elif re.search(r'\b[Ss]emester\s*(\d)\b', semester):
                    num_match = re.search(r'\b[Ss]emester\s*(\d)\b', semester)
                    if num_match:
                        sem_num = int(num_match.group(1))
                        # Map semester numbers to priorities
                        term_priority = min(3, max(0, sem_num - 1))
                
                # Return tuple for sorting (year, term_priority)
                return (year, term_priority)
            
            # Sort the courses
            courses.sort(key=semester_sort_key, reverse=(sort == 'semester_desc'))
            return render_template('index.html', courses=courses, current_sort=sort, search=search, student_counts=student_counts)
        else:  # Default: semester_desc - duplicated here for safety
            # Get all courses for custom sorting
            courses = query.all()
            
            # Calculate student counts for each course
            student_counts = {}
            for course in courses:
                # Count non-excluded students
                student_counts[course.id] = Student.query.filter_by(course_id=course.id, excluded=False).count()
            
            # Define a function to extract year and term for sorting
            def semester_sort_key(course):
                semester = course.semester or ""
                import re
                
                # Extract year using a more flexible regex pattern
                # Look for any 4-digit number that might represent a year
                year_match = re.search(r'\b(\d{4})\b', semester)
                year = int(year_match.group(1)) if year_match else 0
                
                # Use regex to identify terms more flexibly
                term_priority = 0
                
                # Multi-language support for terms (case insensitive)
                # Spring terms (priority 3)
                if re.search(r'\b(spring|bahar|sp|primavera|frühling|printemps|весна|春|봄|vår|voorjaar|primavera)\b', 
                            semester, re.IGNORECASE):
                    term_priority = 3
                # Fall terms (priority 2)
                elif re.search(r'\b(fall|güz|fa|otoño|herbst|automne|осень|秋|가을|höst|herfst|autunno)\b', 
                              semester, re.IGNORECASE):
                    term_priority = 2
                # Summer terms (priority 1)
                elif re.search(r'\b(summer|yaz|su|verano|sommer|été|лето|夏|여름|sommar|zomer|estate)\b', 
                              semester, re.IGNORECASE):
                    term_priority = 1
                # Winter terms (priority 0)
                elif re.search(r'\b(winter|kış|wi|invierno|冬|겨울|vinter|inverno|hiver|зима)\b', 
                              semester, re.IGNORECASE):
                    term_priority = 0
                # Try to find numeric semester designations (e.g., "1", "2", "3", "4" for quarters)
                elif re.search(r'\b[Ss]emester\s*(\d)\b', semester):
                    num_match = re.search(r'\b[Ss]emester\s*(\d)\b', semester)
                    if num_match:
                        sem_num = int(num_match.group(1))
                        # Map semester numbers to priorities
                        term_priority = min(3, max(0, sem_num - 1))
                
                # Return tuple for sorting (year, term_priority)
                return (year, term_priority)
            
            # Sort the courses
            courses.sort(key=semester_sort_key, reverse=True)
            return render_template('index.html', courses=courses, current_sort=sort, search=search, student_counts=student_counts)
            
        # Execute query for non-semester sorts
        courses = query.all()
        
        # Calculate student counts for each course
        student_counts = {}
        for course in courses:
            # Count non-excluded students
            student_counts[course.id] = Student.query.filter_by(course_id=course.id, excluded=False).count()
            
        return render_template('index.html', courses=courses, current_sort=sort, search=search, student_counts=student_counts)
    
    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        # Get detailed error information
        import traceback
        error_traceback = traceback.format_exc()
        error_message = str(e)
        
        # Log the error
        logging.error(f"500 error: {error_message}\n{error_traceback}")
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': error_message,
                'traceback': error_traceback
            }), 500
        
        # For regular requests, pass the error details to the template
        return render_template('errors/500.html', 
                              error_message=error_message,
                              error_traceback=error_traceback), 500

    @app.errorhandler(Exception)
    def handle_uncaught_exception(e):
        # Get detailed error information
        import traceback
        error_traceback = traceback.format_exc()
        error_message = str(e)
        
        # Log the error
        logging.error(f"Uncaught exception: {error_message}\n{error_traceback}")
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': error_message,
                'traceback': error_traceback
            }), 500
        
        # For regular requests, pass the error details to the template
        return render_template('errors/500.html', 
                              error_message=error_message,
                              error_traceback=error_traceback), 500
    
    return app

def initialize_program_outcomes():
    """Initialize default program outcomes if they don't exist"""
    from models import ProgramOutcome
    
    default_outcomes = [
        {"code": "PÇ1", "description": "Matematik, fen bilimleri ve bilgisayar mühendisliği alanlarına özgü konularda yeterli bilgi birikimi; bu alanlardaki kuramsal ve uygulamalı bilgileri, bilgisayar mühendisliği alanındaki karmaşık mühendislik problemlerinin çözümünde kullanabilme becerisi."},
        {"code": "PÇ2", "description": "Bilgisayar mühendisliği alanındaki karmaşık mühendislik problemlerini saptama, tanımlama, formüle etme ve çözme becerisi; bu amaçla uygun analiz, teknik ve modelleme yöntemlerini seçme ve uygulama becerisi."},
        {"code": "PÇ3", "description": "Bilgisayar mühendisliği kapsamındaki karmaşık bir sistemi, süreci, cihazı veya ürünü gerçekçi kısıtlar ve koşullar altında, belirli gereksinimleri karşılayacak şekilde bilgisayar mühendisliği alanındaki modern tasarım yöntemlerini uygulayarak tasarlama becerisi."},
        {"code": "PÇ4", "description": "Bilgisayar mühendisliği uygulamalarında karşılaşılan karmaşık problemlerin analizi ve çözümü için gerekli olan modern teknik ve araçları geliştirme, seçme ve kullanma becerisi; bilişim teknolojilerini etkin bir şekilde kullanma becerisi."},
        {"code": "PÇ5", "description": "Bilgisayar mühendisliği disiplinine özgü karmaşık problemlerin veya araştırma konularının incelenmesi için deney tasarlama, deney yapma, veri toplama, sonuçları analiz etme ve yorumlama becerisi."},
        {"code": "PÇ6", "description": "Disiplin içi ve çok disiplinli takımlarda etkin biçimde çalışabilme becerisi; bireysel çalışma becerisi."},
        {"code": "PÇ7", "description": "Türkçe sözlü ve yazılı etkin iletişim kurma becerisi; en az bir yabancı dil bilgisi; etkin rapor yazma ve yazılı raporları anlama, tasarım ve üretim raporları hazırlayabilme, etkin sunum yapabilme, açık ve anlaşılır talimat verme ve alma becerisi."},
        {"code": "PÇ8", "description": "Yaşam boyu öğrenmenin gerekliliği bilinci; bilgiye erişebilme, bilim ve teknolojideki gelişmeleri izleme ve kendini sürekli yenileme becerisi."},
        {"code": "PÇ9", "description": "Etik ilkelerine uygun davranma, mesleki ve etik sorumluluk bilinci; bilgisayar mühendisliği alanındaki mühendislik uygulamalarında kullanılan standartlar hakkında bilgi."},
        {"code": "PÇ10", "description": "Bilgisayar mühendisliği alanında proje yönetimi, risk yönetimi ve değişiklik yönetimi gibi, iş hayatındaki uygulamalar hakkında bilgi; girişimcilik, yenilikçilik hakkında farkındalık; sürdürülebilir kalkınma hakkında bilgi."},
        {"code": "PÇ11", "description": "Bilgisayar mühendisliği alanındaki mühendislik uygulamalarının evrensel ve toplumsal boyutlarda sağlık, çevre ve güvenlik üzerindeki etkileri ve çağın bilgisayar mühendisliği alanına yansıyan sorunları hakkında bilgi; bilgisayar mühendisliği çözümlerinin hukuksal sonuçları hakkında farkındalık."}
    ]
    
    # Check if program outcomes already exist
    from models import ProgramOutcome
    existing_count = ProgramOutcome.query.count()
    
    if existing_count == 0:
        # Add the default outcomes
        for outcome in default_outcomes:
            program_outcome = ProgramOutcome(
                code=outcome["code"],
                description=outcome["description"]
            )
            db.session.add(program_outcome)
        
        db.session.commit()
        logging.info("Initialized default program outcomes")

def check_cloudflared():
    """Check if cloudflared is installed"""
    try:
        subprocess.run(['cloudflared', 'version'], capture_output=True, text=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def start_cloudflared_tunnel(port):
    """Start a cloudflared tunnel to expose the app publicly"""
    if not check_cloudflared():
        print("=" * 70)
        print("Error: cloudflared is not installed!")
        print("Please install cloudflared from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation")
        print("=" * 70)
        return None
    
    try:
        print("Starting cloudflared tunnel...")
        
        # Start the cloudflared process
        process = subprocess.Popen(
            ['cloudflared', 'tunnel', '--url', f'http://localhost:{port}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Look for the tunnel URL in the output
        import re
        tunnel_url = None
        start_time = time.time()
        timeout = 30  # 30 seconds
        
        while time.time() - start_time < timeout and tunnel_url is None:
            line = process.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
                
            # Look for the box that contains the tunnel URL
            if "Your quick Tunnel has been created!" in line:
                # Read the next line that should contain the URL
                url_line = process.stdout.readline().strip()
                
                # Extract the URL using regex
                match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', url_line)
                if match:
                    tunnel_url = match.group(0)
                    break
            
            # Alternative method: just find any line with a trycloudflare.com URL
            elif "trycloudflare.com" in line:
                match = re.search(r'(https://[a-z0-9-]+\.trycloudflare\.com)', line)
                if match:
                    tunnel_url = match.group(1)
                    break
        
        # Create a thread to silently handle the remaining output
        def silent_reader():
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                # We're not printing output, just consuming it
        
        # Start silent reader thread
        output_thread = threading.Thread(target=silent_reader, daemon=True)
        output_thread.start()
        
        if tunnel_url:
            return {
                'process': process,
                'url': tunnel_url
            }
        else:
            print("=" * 70)
            print("Could not find cloudflared tunnel URL in output.")
            print(f"Please run manually: cloudflared tunnel --url http://localhost:{port}")
            print("=" * 70)
            process.terminate()
            return None
            
    except Exception as e:
        logging.error(f"Error starting cloudflared: {str(e)}")
        print(f"Error starting cloudflared: {str(e)}")
        return None

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Accredit Helper Pro')
    parser.add_argument('port', nargs='?', type=int, default=5000, help='Port to run the application on')
    parser.add_argument('--cloud', action='store_true', help='Expose the application using cloudflared')
    args = parser.parse_args()
    
    app = create_app()
    port = args.port
    
    # Print the local URL
    print("=" * 70)
    print(f"Server started! Access the application at: http://localhost:{port}")
    
    # Start cloudflared if requested
    tunnel_info = None
    if args.cloud and os.environ.get('WERKZEUG_RUN_MAIN') == 'true':  # Check WERKZEUG_RUN_MAIN
        tunnel_info = start_cloudflared_tunnel(port)
        if tunnel_info and tunnel_info.get('url'):
            print("=" * 70)
            print(f"🌎 Remote access URL: {tunnel_info['url']}")
            print("Share this URL to access the application remotely")
            print("=" * 70)
        elif tunnel_info:
            print("Cloudflared tunnel is running but URL was not detected")
        else:
            print("Failed to start cloudflared tunnel")
    
    # Open browser after a slight delay to ensure server is up
    def open_browser_with_port():
        # Check if running in the main Werkzeug process to avoid opening multiple tabs
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            webbrowser.open(f'http://localhost:{port}/')
    
    if not args.cloud:  # Only open browser automatically for local access
        threading.Timer(1.0, open_browser_with_port).start()
    
    # Run the application
    app.run(debug=True, port=port, host="0.0.0.0")  # Allow external connections 