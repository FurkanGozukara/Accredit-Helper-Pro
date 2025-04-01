import os
import sys
import random
import datetime
import json
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from flask import Flask

# Make sure we can import from the current directory
sys.path.append('.')

# Import the models
from models import db, Course, Exam, CourseOutcome, ProgramOutcome, Question
from models import Student, Score, ExamWeight, course_outcome_program_outcome, question_course_outcome

# Initialize Faker for generating realistic data
fake = Faker()

# Configure random seed for reproducibility
random.seed(42)
fake.seed_instance(42)

def create_database_if_not_exists():
    """Create the database and tables if they don't exist"""
    # Get the absolute path to the current directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Create instance directory if it doesn't exist
    instance_dir = os.path.join(base_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # Create a Flask app to initialize the database
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "abet_data.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize db with app
    db.init_app(app)
    
    # Create all tables within app context
    with app.app_context():
        db.create_all()
        # Initialize default program outcomes
        initialize_program_outcomes()
    
    print("Database structure created successfully")

def initialize_program_outcomes():
    """Initialize default program outcomes if they don't exist"""
    # Check if program outcomes already exist
    existing_count = ProgramOutcome.query.count()
    
    if existing_count == 0:
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
        
        # Add the default outcomes
        for outcome in default_outcomes:
            program_outcome = ProgramOutcome(
                code=outcome["code"],
                description=outcome["description"],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.session.add(program_outcome)
        
        db.session.commit()
        print("Initialized default program outcomes")

def generate_courses():
    """Generate two courses with different characteristics"""
    courses = [
        {
            "code": "CSE101",
            "name": "Introduction to Computer Science",
            "semester": "Fall 2023"
        },
        {
            "code": "CSE301",
            "name": "Database Management Systems",
            "semester": "Spring 2024"
        }
    ]
    
    course_objects = []
    
    for course_data in courses:
        course = Course(
            code=course_data["code"],
            name=course_data["name"],
            semester=course_data["semester"],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        session.add(course)
        course_objects.append(course)
    
    session.commit()
    print(f"Created {len(course_objects)} courses")
    return course_objects

def generate_program_outcomes():
    """Get existing program outcomes from the database"""
    program_outcomes = session.query(ProgramOutcome).all()
    if not program_outcomes:
        print("Warning: No program outcomes found in the database.")
        print("This shouldn't happen as we've initialized them.")
        sys.exit(1)
    
    return program_outcomes

def generate_course_outcomes(courses, program_outcomes):
    """Generate course outcomes for each course and link to program outcomes"""
    course_outcomes_data = {
        "CSE101": [
            {"code": "CSE101-1", "description": "Understand fundamental concepts in computer science"},
            {"code": "CSE101-2", "description": "Apply basic programming principles to solve simple problems"},
            {"code": "CSE101-3", "description": "Analyze algorithms for efficiency and correctness"},
            {"code": "CSE101-4", "description": "Implement data structures to organize and manipulate data"}
        ],
        "CSE301": [
            {"code": "CSE301-1", "description": "Design and implement relational database schemas"},
            {"code": "CSE301-2", "description": "Develop complex SQL queries for data retrieval and manipulation"},
            {"code": "CSE301-3", "description": "Apply normalization techniques to database designs"},
            {"code": "CSE301-4", "description": "Implement database security and transaction management"}
        ]
    }
    
    # Default course outcomes for any course that doesn't have predefined ones
    default_outcomes = [
        {"code": "CO-1", "description": "Understand and apply fundamental principles in this field"},
        {"code": "CO-2", "description": "Analyze and solve complex problems using appropriate techniques"},
        {"code": "CO-3", "description": "Design and implement effective solutions to real-world problems"},
        {"code": "CO-4", "description": "Evaluate the quality and effectiveness of various approaches"}
    ]
    
    all_course_outcomes = []
    
    for course in courses:
        # Get course-specific outcomes or use defaults if none defined
        course_data = course_outcomes_data.get(course.code, [])
        
        # If no predefined outcomes for this course, use the defaults with proper code prefix
        if not course_data:
            course_data = []
            for i, outcome in enumerate(default_outcomes, 1):
                course_data.append({
                    "code": f"{course.code}-{i}",
                    "description": outcome["description"]
                })
        
        for co_data in course_data:
            course_outcome = CourseOutcome(
                code=co_data["code"],
                description=co_data["description"],
                course_id=course.id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Associate with 2-3 random program outcomes
            selected_pos = random.sample(program_outcomes, random.randint(2, 3))
            course_outcome.program_outcomes = selected_pos
            
            session.add(course_outcome)
            all_course_outcomes.append(course_outcome)
    
    session.commit()
    print(f"Created {len(all_course_outcomes)} course outcomes")
    return all_course_outcomes

def generate_exams(courses):
    """Generate exams for each course"""
    exam_types = {
        "CSE101": [
            {"name": "Quiz 1", "max_score": 20, "date_offset": -60},
            {"name": "Midterm", "max_score": 100, "date_offset": -45},
            {"name": "Quiz 2", "max_score": 20, "date_offset": -30},
            {"name": "Project", "max_score": 100, "date_offset": -15},
            {"name": "Final Exam", "max_score": 100, "date_offset": -7}
        ],
        "CSE301": [
            {"name": "Homework 1", "max_score": 50, "date_offset": -70},
            {"name": "Midterm 1", "max_score": 100, "date_offset": -55},
            {"name": "Homework 2", "max_score": 50, "date_offset": -40},
            {"name": "Midterm 2", "max_score": 100, "date_offset": -25},
            {"name": "Project", "max_score": 100, "date_offset": -10},
            {"name": "Final Exam", "max_score": 100, "date_offset": -5}
        ]
    }
    
    # Define weight distributions per course to ensure total is 100%
    weight_distributions = {
        "CSE101": {
            "Quiz": 0.1,       # 10% for each quiz (2 total = 20%)
            "Midterm": 0.2,    # 20% for the midterm
            "Project": 0.2,    # 20% for the project
            "Final Exam": 0.4  # 40% for the final
        },
        "CSE301": {
            "Homework": 0.05,  # 5% for each homework (2 total = 10%)
            "Midterm": 0.15,   # 15% for each midterm (2 total = 30%)
            "Project": 0.2,    # 20% for the project
            "Final Exam": 0.4  # 40% for the final
        },
        "DEFAULT": {
            "Quiz": 0.05,      # Default weight distributions for unknown courses
            "Homework": 0.05,
            "Midterm": 0.15,
            "Project": 0.2,
            "Final Exam": 0.4,
            "Other": 0.1
        }
    }
    
    all_exams = []
    
    # First, create all exams
    for course in courses:
        exams_data = exam_types.get(course.code, [])
        # If no predefined exams, create some default ones
        if not exams_data:
            exams_data = [
                {"name": "Midterm", "max_score": 100, "date_offset": -45},
                {"name": "Final Exam", "max_score": 100, "date_offset": -7}
            ]
            
        for exam_data in exams_data:
            today = datetime.now().date()
            exam_date = today + timedelta(days=exam_data["date_offset"])
            
            exam = Exam(
                name=exam_data["name"],
                max_score=exam_data["max_score"],
                exam_date=exam_date,
                course_id=course.id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_makeup=False
            )
            session.add(exam)
            all_exams.append(exam)
    
    # Commit to get exam IDs
    session.commit()
    print(f"Created {len(all_exams)} exams")
    
    # Now create the exam weights with valid exam IDs
    for course in courses:
        course_exams = [e for e in all_exams if e.course_id == course.id]
        # Get the course's weight distribution or use default
        weight_dist = weight_distributions.get(course.code, weight_distributions["DEFAULT"])
        
        # Track weights to ensure they sum to 100%
        total_weight = 0
        
        for i, exam in enumerate(course_exams):
            # Determine weight based on exam name and course's weight distribution
            weight = 0
            # Check each exam type in the weight distribution
            for exam_type, type_weight in weight_dist.items():
                if exam_type in exam.name:
                    weight = type_weight
                    break
            else:
                # If no match found, use "Other" weight or default to 10%
                weight = weight_dist.get("Other", 0.1)
            
            # For the last exam, adjust to make total exactly 100%
            if i == len(course_exams) - 1:
                weight = round(1.0 - total_weight, 2)
            else:
                total_weight += weight
            
            exam_weight = ExamWeight(
                exam_id=exam.id,
                course_id=course.id,
                weight=weight,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(exam_weight)
    
    session.commit()
    print(f"Created {len(all_exams)} exam weights (total 100% for each course)")
    
    return all_exams

def generate_questions(exams, course_outcomes):
    """Generate questions for each exam and link them to course outcomes"""
    all_questions = []
    
    for exam in exams:
        # Get course outcomes for this exam's course
        relevant_outcomes = [co for co in course_outcomes if co.course_id == exam.course_id]
        
        # Determine number of questions based on exam type
        if "Quiz" in exam.name or "Homework" in exam.name:
            num_questions = random.randint(5, 10)
        elif "Midterm" in exam.name:
            num_questions = random.randint(1, 10)
        elif "Final" in exam.name:
            num_questions = random.randint(40, 40)
        elif "Project" in exam.name:
            num_questions = random.randint(3, 6)
        else:
            num_questions = random.randint(5, 15)
        
        total_points = exam.max_score
        points_per_question = total_points / num_questions
        
        for q_num in range(1, num_questions + 1):
            # Vary the point values a bit
            if q_num == num_questions:
                # Make sure the last question's points make the total exactly max_score
                previous_points_sum = sum(q.max_score for q in all_questions if q.exam_id == exam.id)
                point_value = total_points - previous_points_sum
            else:
                variation = points_per_question * 0.2
                point_value = points_per_question + random.uniform(-variation, variation)
                point_value = round(point_value, 1)
            
            question = Question(
                text=f"Question {q_num}: {fake.sentence()}",
                number=q_num,
                max_score=point_value,
                exam_id=exam.id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Associate with 1-2 random course outcomes
            if relevant_outcomes:
                num_outcomes = min(len(relevant_outcomes), random.randint(1, 2))
                selected_cos = random.sample(relevant_outcomes, num_outcomes)
                question.course_outcomes = selected_cos
            
            session.add(question)
            all_questions.append(question)
    
    session.commit()
    print(f"Created {len(all_questions)} questions")
    return all_questions

def generate_students(courses):
    """Generate students for each course"""
    all_students = []
    
    # Number of students per course
    student_counts = {
        "CSE101": 30,  # Intro course has more students
        "CSE301": 20   # Advanced course has fewer students
    }
    
    # Create a set of student IDs to ensure uniqueness
    student_ids = set()
    
    for course in courses:
        num_students = student_counts.get(course.code, 25)
        
        for _ in range(num_students):
            # Generate a unique student ID
            while True:
                student_id = f"{random.randint(1, 9)}{random.randint(100000, 999999)}"
                if student_id not in student_ids:
                    student_ids.add(student_id)
                    break
            
            student = Student(
                student_id=student_id,
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                course_id=course.id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(student)
            all_students.append(student)
    
    session.commit()
    print(f"Created {len(all_students)} students")
    return all_students

def generate_scores(questions, students):
    """Generate scores for each student on each question"""
    all_scores = []
    
    for student in students:
        # Get all questions for exams in this student's course
        relevant_questions = [q for q in questions if q.exam.course_id == student.course_id]
        
        for question in relevant_questions:
            # Generate a score following a normal distribution
            # Mean score of 75% of max with standard deviation of 15%
            mean_score_pct = 0.75
            std_dev_pct = 0.15
            
            # Add some randomness to the student's overall performance level (±15%)
            student_performance_modifier = random.uniform(-0.15, 0.15)
            student_mean_score_pct = mean_score_pct + student_performance_modifier
            
            # Ensure the percentage stays in a valid range
            student_mean_score_pct = max(0.05, min(0.95, student_mean_score_pct))
            
            # Calculate the actual score
            max_score = question.max_score
            raw_score = random.normalvariate(student_mean_score_pct * max_score, std_dev_pct * max_score)
            score_value = max(0, min(max_score, round(raw_score, 1)))
            
            score = Score(
                score=score_value,
                student_id=student.id,
                question_id=question.id,
                exam_id=question.exam_id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(score)
            all_scores.append(score)
    
    session.commit()
    print(f"Created {len(all_scores)} scores")
    return all_scores

def main():
    print("Generating demo data for ABET Helper Pro...")
    
    # First, create the database if it doesn't exist
    create_database_if_not_exists()
    
    # Now connect to the database for data generation
    base_dir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(base_dir, 'instance')
    db_path = os.path.join(instance_dir, 'abet_data.db')
    
    # Connect to the database
    global engine, Session, session
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Get existing courses in the database
    existing_courses = session.query(Course).all()
    existing_course_count = len(existing_courses)
    
    if existing_course_count > 0:
        print(f"Found {existing_course_count} existing courses in the database.")
        response = input(f"Do you want to generate demo data for these existing courses? (y/n): ")
        if response.lower() != 'y':
            print("Will only generate data for new courses.")
            existing_courses = []
        else:
            print(f"Will generate data for existing courses as well.")
    
    # Ask if user wants to add new courses
    response = input(f"Do you want to add new demo courses to the database? (y/n): ")
    if response.lower() == 'y':
        # Generate new courses
        new_courses = generate_courses()
        # Combine with existing courses if any
        all_courses = existing_courses + new_courses
    else:
        all_courses = existing_courses
        print("Will not add new courses.")
    
    if not all_courses:
        print("No courses to generate data for. Exiting.")
        return
    
    # Generate the data in the correct order to maintain relationships
    program_outcomes = generate_program_outcomes()
    
    # First, check which courses already have course outcomes
    courses_with_outcomes = set()
    for co in session.query(CourseOutcome).all():
        courses_with_outcomes.add(co.course_id)
    
    # Filter courses that need outcomes
    courses_needing_outcomes = [c for c in all_courses if c.id not in courses_with_outcomes]
    
    if courses_needing_outcomes:
        print(f"Generating course outcomes for {len(courses_needing_outcomes)} courses...")
        course_outcomes = generate_course_outcomes(courses_needing_outcomes, program_outcomes)
    else:
        print("All courses already have course outcomes.")
        course_outcomes = session.query(CourseOutcome).all()
    
    # Get all course outcomes after generation
    all_course_outcomes = session.query(CourseOutcome).all()
    
    # Similarly, check which courses need exams
    courses_with_exams = set()
    for exam in session.query(Exam).all():
        courses_with_exams.add(exam.course_id)
    
    courses_needing_exams = [c for c in all_courses if c.id not in courses_with_exams]
    
    if courses_needing_exams:
        print(f"Generating exams for {len(courses_needing_exams)} courses...")
        exams = generate_exams(courses_needing_exams)
    else:
        print("All courses already have exams.")
        exams = session.query(Exam).all()
    
    # Get all exams after generation
    all_exams = session.query(Exam).all()
    
    # Check for courses that already have questions
    courses_with_questions = set()
    for question in session.query(Question).all():
        exam = session.query(Exam).get(question.exam_id)
        if exam:
            courses_with_questions.add(exam.course_id)
    
    # Filter exams that need questions based on their course
    exams_needing_questions = [e for e in all_exams if e.course_id not in courses_with_questions]
    
    if exams_needing_questions:
        print(f"Generating questions for {len(exams_needing_questions)} exams...")
        questions = generate_questions(exams_needing_questions, all_course_outcomes)
    else:
        print("All courses already have questions for their exams.")
        questions = session.query(Question).all()
    
    # Get all questions after generation
    all_questions = session.query(Question).all()
    
    # Similarly, check which courses need students
    courses_with_students = set()
    for student in session.query(Student).all():
        courses_with_students.add(student.course_id)
    
    courses_needing_students = [c for c in all_courses if c.id not in courses_with_students]
    
    if courses_needing_students:
        print(f"Generating students for {len(courses_needing_students)} courses...")
        students = generate_students(courses_needing_students)
    else:
        print("All courses already have students.")
        students = session.query(Student).all()
    
    # Get all students after generation
    all_students = session.query(Student).all()
    
    # Finally, generate scores for all students on all questions
    # First, let's get all existing scores to avoid duplicates
    existing_scores = set()
    for score in session.query(Score).all():
        existing_scores.add((score.student_id, score.question_id))
    
    # Now generate scores for student-question pairs that don't have scores yet
    print("Generating scores for students...")
    new_scores = []
    total_scores_needed = 0
    
    for student in all_students:
        # Get all questions for exams in this student's course
        course_questions = [q for q in all_questions if q.exam.course_id == student.course_id]
        total_scores_needed += len(course_questions)
        
        for question in course_questions:
            # Skip if score already exists
            if (student.id, question.id) in existing_scores:
                continue
                
            # Generate score as before
            mean_score_pct = 0.75
            std_dev_pct = 0.15
            student_performance_modifier = random.uniform(-0.15, 0.15)
            student_mean_score_pct = max(0.05, min(0.95, mean_score_pct + student_performance_modifier))
            
            max_score = question.max_score
            raw_score = random.normalvariate(student_mean_score_pct * max_score, std_dev_pct * max_score)
            score_value = max(0, min(max_score, round(raw_score, 1)))
            
            score = Score(
                score=score_value,
                student_id=student.id,
                question_id=question.id,
                exam_id=question.exam_id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(score)
            new_scores.append(score)
            
            # Commit in batches to avoid memory issues
            if len(new_scores) % 1000 == 0:
                session.commit()
                print(f"Generated {len(new_scores)} scores so far...")
    
    session.commit()
    print(f"Generated {len(new_scores)} new scores out of {total_scores_needed} possible scores")
    
    print("\nDemo data generation complete!")
    course_count = session.query(Course).count()
    outcome_count = session.query(CourseOutcome).count()
    exam_count = session.query(Exam).count()
    question_count = session.query(Question).count()
    student_count = session.query(Student).count()
    score_count = session.query(Score).count()
    
    print(f"Database now contains:")
    print(f"  - {course_count} courses")
    print(f"  - {outcome_count} course outcomes")
    print(f"  - {exam_count} exams")
    print(f"  - {question_count} questions")
    print(f"  - {student_count} students")
    print(f"  - {score_count} scores")
    print("\nYou can now use the application to explore and analyze this data.")

if __name__ == "__main__":
    main() 