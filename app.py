import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from werkzeug.utils import secure_filename
import sqlite3
import csv
import json
import shutil
import webbrowser

# Import db from models
from models import db

def create_app():
    app = Flask(__name__)
    
    # Get the absolute path to the current directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_for_local_use')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(base_dir, "instance", "abet_data.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['BACKUP_FOLDER'] = os.path.join(base_dir, 'backups')
    
    # Ensure instance and backup folders exist
    os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'instance'), exist_ok=True)
    
    # Initialize extensions with app
    db.init_app(app)
    
    # Setup logging
    logging.basicConfig(
        filename='app.log',
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Import models
    from models import Course, Exam, CourseOutcome, ProgramOutcome, Question, Student, Score, ExamWeight
    
    # Register blueprints
    from routes.course_routes import course_bp
    from routes.exam_routes import exam_bp
    from routes.outcome_routes import outcome_bp
    from routes.student_routes import student_bp
    from routes.calculation_routes import calculation_bp
    from routes.utility_routes import utility_bp
    from routes.question_routes import question_bp
    
    app.register_blueprint(course_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(outcome_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(calculation_bp)
    app.register_blueprint(utility_bp)
    app.register_blueprint(question_bp)
    
    # Create tables if they don't exist - moved after imports
    with app.app_context():
        db.create_all()
        # Initialize default program outcomes if they don't exist
        initialize_program_outcomes()
    
    # Home route
    @app.route('/')
    def index():
        courses = Course.query.all()
        return render_template('index.html', courses=courses)
    
    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500
    
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

def open_browser():
    """Open browser to the app URL"""
    webbrowser.open('http://localhost:5000/')

if __name__ == '__main__':
    app = create_app()
    # Print the URL
    print("=" * 70)
    print("Server started! Access the application at: http://localhost:5000")
    print("=" * 70)
    # Open browser after a slight delay to ensure server is up
    import threading
    threading.Timer(1.0, open_browser).start()
    app.run(debug=True) 