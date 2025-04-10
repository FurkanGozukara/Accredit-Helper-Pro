import os
import sys
import random
import datetime
import json
from faker import Faker
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from flask import Flask
from decimal import Decimal

# Make sure we can import from the current directory
sys.path.append('.')

# Import the models
from models import db, Course, Exam, CourseOutcome, ProgramOutcome, Question, AchievementLevel
from models import Student, Score, ExamWeight, course_outcome_program_outcome, question_course_outcome

# Initialize Faker for generating realistic data
fake = Faker()

# Remove fixed random seed to ensure different random selections each time
# random.seed(42)
# fake.seed_instance(42)

# Global variables
engine = None
Session = None
session = None

def create_database_if_not_exists():
    """Create the database and tables if they don't exist"""
    # Get the absolute path to the current directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Create instance directory if it doesn't exist
    instance_dir = os.path.join(base_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # Create a Flask app to initialize the database
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "accredit_data.db")}'
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
            {"code": "PO1", "description": "Sufficient background in subjects specific to the fields of mathematics, science, and computer engineering; the ability to use theoretical and applied knowledge from these fields in solving complex engineering problems within the computer engineering field."},
            {"code": "PO2", "description": "Ability to identify, define, formulate, and solve complex engineering problems in the field of computer engineering; the ability to select and apply appropriate analysis, techniques, and modeling methods for this purpose."},
            {"code": "PO3", "description": "Ability to design a complex system, process, device, or product within the scope of computer engineering under realistic constraints and conditions to meet specific requirements, by applying modern design methods from the computer engineering field."},
            {"code": "PO4", "description": "Ability to develop, select, and use the modern techniques and tools necessary for the analysis and solution of complex problems encountered in computer engineering applications; the ability to use information technologies effectively."},
            {"code": "PO5", "description": "Ability to design and conduct experiments, collect data, analyze, and interpret results for the investigation of complex problems or research topics specific to the computer engineering discipline."},
            {"code": "PO6", "description": "Ability to work effectively within disciplinary and multi-disciplinary teams; ability to work individually."},
            {"code": "PO7", "description": "Ability to communicate effectively both orally and in writing in Turkish; knowledge of at least one foreign language; ability for effective report writing and understanding written reports, preparing design and production reports, making effective presentations, giving and receiving clear and understandable instructions."},
            {"code": "PO8", "description": "Awareness of the necessity of lifelong learning; the ability to access information, follow developments in science and technology, and continuously renew oneself."},
            {"code": "PO9", "description": "Ability to act in accordance with ethical principles, awareness of professional and ethical responsibility; knowledge about the standards used in engineering applications within the computer engineering field."},
            {"code": "PO10", "description": "Knowledge about business practices such as project management, risk management, and change management in the computer engineering field; awareness of entrepreneurship and innovation; knowledge about sustainable development."},
            {"code": "PO11", "description": "Knowledge about the impacts of engineering applications in the computer engineering field on health, environment, and safety in universal and societal dimensions, and the problems of the era reflected in the computer engineering field; awareness of the legal consequences of computer engineering solutions."}
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
    """Generate three randomly selected courses from a list of 10 potential courses"""
    potential_courses = [
        {
            "code": "CSE101",
            "name": "Introduction to Computer Science",
            "semester": "Fall 2023"
        },
        {
            "code": "CSE301",
            "name": "Database Management Systems",
            "semester": "Spring 2024"
        },
        {
            "code": "CSE201",
            "name": "Data Structures and Algorithms",
            "semester": "Fall 2023"
        },
        {
            "code": "CSE210",
            "name": "Object-Oriented Programming",
            "semester": "Spring 2024"
        },
        {
            "code": "CSE250",
            "name": "Computer Networks",
            "semester": "Fall 2023"
        },
        {
            "code": "CSE310",
            "name": "Software Engineering",
            "semester": "Spring 2024"
        },
        {
            "code": "CSE350",
            "name": "Artificial Intelligence",
            "semester": "Fall 2023"
        },
        {
            "code": "CSE401",
            "name": "Machine Learning",
            "semester": "Spring 2024"
        },
        {
            "code": "CSE410",
            "name": "Computer Graphics",
            "semester": "Fall 2023"
        },
        {
            "code": "CSE450",
            "name": "Operating Systems",
            "semester": "Spring 2024"
        }
    ]
    
    # Randomly select 3 courses from the list
    selected_courses = random.sample(potential_courses, 3)
    
    course_objects = []
    
    for course_data in selected_courses:
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
    print(f"Created {len(course_objects)} randomly selected courses")
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
        "CSE201": [
            {"code": "CSE201-1", "description": "Implement and analyze fundamental data structures"},
            {"code": "CSE201-2", "description": "Design and analyze algorithms for efficiency"},
            {"code": "CSE201-3", "description": "Apply appropriate data structures to solve complex problems"},
            {"code": "CSE201-4", "description": "Evaluate algorithm complexity in time and space"}
        ],
        "CSE210": [
            {"code": "CSE210-1", "description": "Apply object-oriented design principles to software development"},
            {"code": "CSE210-2", "description": "Design and implement class hierarchies and interfaces"},
            {"code": "CSE210-3", "description": "Use inheritance, polymorphism, and encapsulation appropriately"},
            {"code": "CSE210-4", "description": "Implement design patterns to solve common software problems"}
        ],
        "CSE250": [
            {"code": "CSE250-1", "description": "Explain the architecture and protocols of computer networks"},
            {"code": "CSE250-2", "description": "Design and implement network applications"},
            {"code": "CSE250-3", "description": "Analyze network performance and security"},
            {"code": "CSE250-4", "description": "Configure and troubleshoot network components"}
        ],
        "CSE301": [
            {"code": "CSE301-1", "description": "Design and implement relational database schemas"},
            {"code": "CSE301-2", "description": "Develop complex SQL queries for data retrieval and manipulation"},
            {"code": "CSE301-3", "description": "Apply normalization techniques to database designs"},
            {"code": "CSE301-4", "description": "Implement database security and transaction management"}
        ],
        "CSE310": [
            {"code": "CSE310-1", "description": "Apply software engineering principles to software development"},
            {"code": "CSE310-2", "description": "Design, implement, and test software systems"},
            {"code": "CSE310-3", "description": "Manage software development projects effectively"},
            {"code": "CSE310-4", "description": "Work collaboratively in software development teams"}
        ],
        "CSE350": [
            {"code": "CSE350-1", "description": "Explain fundamental AI concepts and algorithms"},
            {"code": "CSE350-2", "description": "Implement search and optimization algorithms"},
            {"code": "CSE350-3", "description": "Design and develop intelligent agent systems"},
            {"code": "CSE350-4", "description": "Apply knowledge representation and reasoning techniques"}
        ],
        "CSE401": [
            {"code": "CSE401-1", "description": "Implement and evaluate machine learning algorithms"},
            {"code": "CSE401-2", "description": "Process and analyze data for machine learning tasks"},
            {"code": "CSE401-3", "description": "Design and train neural networks for various applications"},
            {"code": "CSE401-4", "description": "Evaluate and improve model performance"}
        ],
        "CSE410": [
            {"code": "CSE410-1", "description": "Apply computer graphics principles and algorithms"},
            {"code": "CSE410-2", "description": "Implement 2D and 3D rendering techniques"},
            {"code": "CSE410-3", "description": "Design and develop interactive graphical applications"},
            {"code": "CSE410-4", "description": "Use graphics libraries and APIs effectively"}
        ],
        "CSE450": [
            {"code": "CSE450-1", "description": "Explain operating system concepts and architectures"},
            {"code": "CSE450-2", "description": "Implement process management and scheduling algorithms"},
            {"code": "CSE450-3", "description": "Design and implement memory management systems"},
            {"code": "CSE450-4", "description": "Develop solutions for concurrency and synchronization"}
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
        "CSE201": [
            {"name": "Assignment 1", "max_score": 40, "date_offset": -65},
            {"name": "Quiz 1", "max_score": 20, "date_offset": -55},
            {"name": "Midterm", "max_score": 100, "date_offset": -40},
            {"name": "Assignment 2", "max_score": 40, "date_offset": -25},
            {"name": "Quiz 2", "max_score": 20, "date_offset": -15},
            {"name": "Final Exam", "max_score": 100, "date_offset": -5}
        ],
        "CSE210": [
            {"name": "Quiz 1", "max_score": 20, "date_offset": -70},
            {"name": "Programming Assignment 1", "max_score": 50, "date_offset": -60},
            {"name": "Midterm", "max_score": 100, "date_offset": -45},
            {"name": "Quiz 2", "max_score": 20, "date_offset": -35},
            {"name": "Programming Assignment 2", "max_score": 50, "date_offset": -20},
            {"name": "Final Project", "max_score": 100, "date_offset": -10},
            {"name": "Final Exam", "max_score": 100, "date_offset": -3}
        ],
        "CSE250": [
            {"name": "Lab 1", "max_score": 30, "date_offset": -75},
            {"name": "Lab 2", "max_score": 30, "date_offset": -60},
            {"name": "Midterm", "max_score": 100, "date_offset": -45},
            {"name": "Lab 3", "max_score": 30, "date_offset": -30},
            {"name": "Lab 4", "max_score": 30, "date_offset": -15},
            {"name": "Final Exam", "max_score": 100, "date_offset": -5}
        ],
        "CSE301": [
            {"name": "Homework 1", "max_score": 50, "date_offset": -70},
            {"name": "Midterm 1", "max_score": 100, "date_offset": -55},
            {"name": "Homework 2", "max_score": 50, "date_offset": -40},
            {"name": "Midterm 2", "max_score": 100, "date_offset": -25},
            {"name": "Project", "max_score": 100, "date_offset": -10},
            {"name": "Final Exam", "max_score": 100, "date_offset": -5}
        ],
        "CSE310": [
            {"name": "Requirements Document", "max_score": 50, "date_offset": -70},
            {"name": "Design Document", "max_score": 50, "date_offset": -55},
            {"name": "Midterm", "max_score": 100, "date_offset": -45},
            {"name": "Implementation Phase", "max_score": 100, "date_offset": -25},
            {"name": "Testing Document", "max_score": 50, "date_offset": -15},
            {"name": "Final Project", "max_score": 100, "date_offset": -5}
        ],
        "CSE350": [
            {"name": "Problem Set 1", "max_score": 50, "date_offset": -65},
            {"name": "Problem Set 2", "max_score": 50, "date_offset": -50},
            {"name": "Midterm", "max_score": 100, "date_offset": -40},
            {"name": "Problem Set 3", "max_score": 50, "date_offset": -25},
            {"name": "Project", "max_score": 100, "date_offset": -10},
            {"name": "Final Exam", "max_score": 100, "date_offset": -5}
        ],
        "CSE401": [
            {"name": "Data Analysis Task", "max_score": 50, "date_offset": -65},
            {"name": "Model Implementation", "max_score": 50, "date_offset": -50},
            {"name": "Midterm", "max_score": 100, "date_offset": -40},
            {"name": "Model Evaluation", "max_score": 50, "date_offset": -25},
            {"name": "Final Project", "max_score": 100, "date_offset": -10},
            {"name": "Final Exam", "max_score": 100, "date_offset": -5}
        ],
        "CSE410": [
            {"name": "2D Rendering Assignment", "max_score": 50, "date_offset": -70},
            {"name": "3D Modeling Task", "max_score": 50, "date_offset": -55},
            {"name": "Midterm", "max_score": 100, "date_offset": -45},
            {"name": "Animation Project", "max_score": 50, "date_offset": -30},
            {"name": "Interactive Graphics Project", "max_score": 100, "date_offset": -10},
            {"name": "Final Exam", "max_score": 100, "date_offset": -5}
        ],
        "CSE450": [
            {"name": "Process Scheduling Lab", "max_score": 40, "date_offset": -65},
            {"name": "Memory Management Lab", "max_score": 40, "date_offset": -50},
            {"name": "Midterm", "max_score": 100, "date_offset": -40},
            {"name": "File System Lab", "max_score": 40, "date_offset": -25},
            {"name": "Synchronization Project", "max_score": 80, "date_offset": -10},
            {"name": "Final Exam", "max_score": 100, "date_offset": -5}
        ]
    }
    
    # Define weight distributions per course to ensure total is 100%
    weight_distributions = {
        "CSE101": {
            "Quiz": Decimal('0.1'),       # 10% for each quiz (2 total = 20%)
            "Midterm": Decimal('0.2'),    # 20% for the midterm
            "Project": Decimal('0.2'),    # 20% for the project
            "Final Exam": Decimal('0.4')  # 40% for the final
        },
        "CSE201": {
            "Assignment": Decimal('0.1'),  # 10% for each assignment (2 total = 20%)
            "Quiz": Decimal('0.05'),      # 5% for each quiz (2 total = 10%)
            "Midterm": Decimal('0.3'),    # 30% for the midterm
            "Final Exam": Decimal('0.4')  # 40% for the final
        },
        "CSE210": {
            "Quiz": Decimal('0.05'),      # 5% for each quiz (2 total = 10%)
            "Programming Assignment": Decimal('0.1'),  # 10% for each assignment (2 total = 20%)
            "Midterm": Decimal('0.2'),    # 20% for the midterm
            "Final Project": Decimal('0.2'),  # 20% for the final project
            "Final Exam": Decimal('0.3')  # 30% for the final
        },
        "CSE250": {
            "Lab": Decimal('0.1'),        # 10% for each lab (4 total = 40%)
            "Midterm": Decimal('0.2'),    # 20% for the midterm
            "Final Exam": Decimal('0.4')  # 40% for the final
        },
        "CSE301": {
            "Homework": Decimal('0.05'),  # 5% for each homework (2 total = 10%)
            "Midterm": Decimal('0.15'),   # 15% for each midterm (2 total = 30%)
            "Project": Decimal('0.2'),    # 20% for the project
            "Final Exam": Decimal('0.4')  # 40% for the final
        },
        "CSE310": {
            "Requirements Document": Decimal('0.1'),  # 10% for requirements
            "Design Document": Decimal('0.1'),       # 10% for design
            "Midterm": Decimal('0.2'),              # 20% for midterm
            "Implementation Phase": Decimal('0.2'),  # 20% for implementation
            "Testing Document": Decimal('0.1'),      # 10% for testing
            "Final Project": Decimal('0.3')         # 30% for final project
        },
        "CSE350": {
            "Problem Set": Decimal('0.1'),   # 10% for each problem set (3 total = 30%)
            "Midterm": Decimal('0.2'),      # 20% for midterm
            "Project": Decimal('0.2'),      # 20% for project
            "Final Exam": Decimal('0.3')    # 30% for final
        },
        "CSE401": {
            "Data Analysis Task": Decimal('0.1'),    # 10% for data analysis
            "Model Implementation": Decimal('0.15'), # 15% for model implementation
            "Midterm": Decimal('0.2'),              # 20% for midterm
            "Model Evaluation": Decimal('0.15'),     # 15% for model evaluation
            "Final Project": Decimal('0.2'),         # 20% for final project
            "Final Exam": Decimal('0.2')             # 20% for final exam
        },
        "CSE410": {
            "2D Rendering Assignment": Decimal('0.1'),    # 10% for 2D rendering
            "3D Modeling Task": Decimal('0.1'),          # 10% for 3D modeling
            "Midterm": Decimal('0.2'),                   # 20% for midterm
            "Animation Project": Decimal('0.1'),         # 10% for animation
            "Interactive Graphics Project": Decimal('0.2'), # 20% for interactive graphics
            "Final Exam": Decimal('0.3')                 # 30% for final exam
        },
        "CSE450": {
            "Process Scheduling Lab": Decimal('0.1'),    # 10% for process scheduling
            "Memory Management Lab": Decimal('0.1'),     # 10% for memory management
            "Midterm": Decimal('0.2'),                   # 20% for midterm
            "File System Lab": Decimal('0.1'),           # 10% for file system
            "Synchronization Project": Decimal('0.2'),   # 20% for synchronization project
            "Final Exam": Decimal('0.3')                 # 30% for final exam
        },
        "DEFAULT": {
            "Quiz": Decimal('0.05'),      # Default weight distributions for unknown courses
            "Homework": Decimal('0.05'),
            "Assignment": Decimal('0.1'),
            "Lab": Decimal('0.05'),
            "Midterm": Decimal('0.15'),
            "Project": Decimal('0.2'),
            "Final Exam": Decimal('0.4'),
            "Other": Decimal('0.1')
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
        
        course_exams = []
        for exam_data in exams_data:
            today = datetime.now().date()
            exam_date = today + timedelta(days=exam_data["date_offset"])
            
            # Determine if this exam is a final based on name
            is_final_exam = "Final" in exam_data["name"]
            
            exam = Exam(
                name=exam_data["name"],
                max_score=exam_data["max_score"],
                exam_date=exam_date,
                course_id=course.id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_makeup=False,
                is_final=is_final_exam,
                is_mandatory=is_final_exam  # Final exams are mandatory
            )
            session.add(exam)
            course_exams.append(exam)
            all_exams.append(exam)
        
        # Add makeup exams for final exams and some midterms
        for exam in course_exams:
            if exam.is_final or ("Midterm" in exam.name and random.random() < 0.5):
                makeup_date = exam.exam_date + timedelta(days=random.randint(7, 14))
                makeup_name = f"Makeup {exam.name}"
                
                makeup_exam = Exam(
                    name=makeup_name,
                    max_score=exam.max_score,
                    exam_date=makeup_date,
                    course_id=course.id,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    is_makeup=True,
                    is_final=exam.is_final,
                    is_mandatory=True,  # Makeup exams are also mandatory
                    original_exam=exam  # Properly set the relationship to the original exam
                )
                session.add(makeup_exam)
                all_exams.append(makeup_exam)
    
    # Commit to get exam IDs
    session.commit()
    print(f"Created {len(all_exams)} exams (including makeup exams)")
    
    # Now create the exam weights with valid exam IDs
    for course in courses:
        course_exams = [e for e in all_exams if e.course_id == course.id and not e.is_makeup]
        # Get the course's weight distribution or use default
        weight_dist = weight_distributions.get(course.code, weight_distributions["DEFAULT"])
        
        # Track weights to ensure they sum to 100%
        total_weight = Decimal('0')
        
        for i, exam in enumerate(course_exams):
            # Determine weight based on exam name and course's weight distribution
            weight = Decimal('0')
            # Check each exam type in the weight distribution
            for exam_type, type_weight in weight_dist.items():
                if exam_type in exam.name:
                    weight = type_weight
                    break
            else:
                # If no match found, use "Other" weight or default to 10%
                weight = weight_dist.get("Other", Decimal('0.1'))
            
            # For the last exam, adjust to make total exactly 100%
            if i == len(course_exams) - 1:
                weight = (Decimal('1.0') - total_weight).quantize(Decimal('0.01'))
            else:
                total_weight += weight
            
            # Create weight record for this exam
            exam_weight = ExamWeight(
                exam_id=exam.id,
                course_id=course.id,
                weight=weight,  # Store as decimal (0-1)
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(exam_weight)
            
            # For makeup exams, use the same weight as the original exam
            for makeup_exam in [e for e in all_exams if hasattr(e, 'original_exam') and e.original_exam == exam]:
                makeup_weight = ExamWeight(
                    exam_id=makeup_exam.id,
                    course_id=course.id,
                    weight=weight,  # Same weight as original exam
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(makeup_weight)
    
    session.commit()
    print(f"Created exam weights for all exams (total 100% for each course)")
    
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
        
        total_points = Decimal(str(exam.max_score))
        points_per_question = total_points / Decimal(str(num_questions))
        
        for q_num in range(1, num_questions + 1):
            # Vary the point values a bit
            if q_num == num_questions:
                # Make sure the last question's points make the total exactly max_score
                previous_points_sum = sum(Decimal(str(q.max_score)) for q in all_questions if q.exam_id == exam.id)
                point_value = total_points - previous_points_sum
            else:
                variation = points_per_question * Decimal('0.2')
                # Generate random variation within the range without converting to float
                random_factor = Decimal(str(random.uniform(-1, 1)))
                random_variation = variation * random_factor
                point_value = points_per_question + random_variation
                point_value = point_value.quantize(Decimal('0.1'), rounding='ROUND_HALF_UP')
            
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
        "CSE201": 25,  # Data Structures course
        "CSE210": 25,  # Object-Oriented Programming
        "CSE250": 20,  # Computer Networks
        "CSE301": 20,  # Database Management
        "CSE310": 22,  # Software Engineering
        "CSE350": 18,  # Artificial Intelligence
        "CSE401": 15,  # Machine Learning
        "CSE410": 15,  # Computer Graphics
        "CSE450": 20   # Operating Systems
    }
    
    # Create a dictionary of student IDs per course to ensure uniqueness within each course
    course_student_ids = {course.id: set() for course in courses}
    
    for course in courses:
        num_students = student_counts.get(course.code, 25)  # Default to 25 if course code not in dictionary
        
        for _ in range(num_students):
            # Generate a unique student ID for this course
            while True:
                # Use strings for student IDs with different formats
                id_format = random.choice([
                    lambda: f"S{random.randint(100000, 999999)}",  # Format: S######
                    lambda: f"{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(10000, 99999)}",  # Format: A#####
                    lambda: f"{random.randint(2020, 2024)}{random.randint(1000, 9999)}",  # Format: YYYY####
                    lambda: f"{random.choice(['CS', 'EE', 'ME', 'SE'])}-{random.randint(10000, 99999)}"  # Format: XX-#####
                ])
                
                student_id = id_format()
                if student_id not in course_student_ids[course.id]:
                    course_student_ids[course.id].add(student_id)
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
            # 60% chance for scores 70 and above, 40% chance for scores below 70
            if random.random() < 0.6:
                # Generate a score of 70 or above (0.7 to 1.0)
                student_score_pct = Decimal(str(random.uniform(0.7, 1.0)))
            else:
                # Generate a score below 70 (0.0 to 0.7)
                student_score_pct = Decimal(str(random.uniform(0.0, 0.7)))
            
            # Calculate actual score based on question max score
            max_score = Decimal(str(question.max_score))
            raw_score = student_score_pct * max_score
            
            # Round to one decimal place and ensure it's within bounds
            score_value = max(Decimal('0'), min(max_score, raw_score.quantize(Decimal('0.1'), rounding='ROUND_HALF_UP')))
            
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

def generate_achievement_levels(courses):
    """Generate achievement levels for each course"""
    # Define default achievement levels
    default_levels = [
        {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
        {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
        {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
        {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
        {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"}
    ]
    
    # Check which courses already have achievement levels
    courses_with_levels = set()
    for level in session.query(AchievementLevel).all():
        courses_with_levels.add(level.course_id)
    
    # Filter courses that need achievement levels
    courses_needing_levels = [c for c in courses if c.id not in courses_with_levels]
    
    if not courses_needing_levels:
        print("All courses already have achievement levels.")
        return []
    
    all_levels = []
    
    for course in courses_needing_levels:
        for level_data in default_levels:
            level = AchievementLevel(
                course_id=course.id,
                name=level_data["name"],
                min_score=level_data["min_score"],
                max_score=level_data["max_score"],
                color=level_data["color"],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(level)
            all_levels.append(level)
    
    session.commit()
    print(f"Created {len(all_levels)} achievement levels for {len(courses_needing_levels)} courses")
    return all_levels

def main():
    print("Generating demo data for Accredit Helper Pro...")
    
    # First, create the database if it doesn't exist
    create_database_if_not_exists()
    
    # Now connect to the database for data generation
    base_dir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(base_dir, 'instance')
    db_path = os.path.join(instance_dir, 'accredit_data.db')
    
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
    
    # Generate achievement levels for courses
    print("Generating achievement levels for courses...")
    achievement_levels = generate_achievement_levels(all_courses)
    
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
            
            # 60% chance for scores 70 and above, 40% chance for scores below 70
            if random.random() < 0.6:
                # Generate a score of 70 or above (0.7 to 1.0)
                student_score_pct = Decimal(str(random.uniform(0.7, 1.0)))
            else:
                # Generate a score below 70 (0.0 to 0.7)
                student_score_pct = Decimal(str(random.uniform(0.0, 0.7)))
            
            # Calculate actual score based on question max score
            max_score = Decimal(str(question.max_score))
            raw_score = student_score_pct * max_score
            
            # Round to one decimal place and ensure it's within bounds
            score_value = max(Decimal('0'), min(max_score, raw_score.quantize(Decimal('0.1'), rounding='ROUND_HALF_UP')))
            
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
    achievement_level_count = session.query(AchievementLevel).count()
    
    print(f"Database now contains:")
    print(f"  - {course_count} courses")
    print(f"  - {outcome_count} course outcomes")
    print(f"  - {exam_count} exams")
    print(f"  - {question_count} questions")
    print(f"  - {student_count} students")
    print(f"  - {score_count} scores")
    print(f"  - {achievement_level_count} achievement levels")
    print("\nYou can now use the application to explore and analyze this data.")

if __name__ == "__main__":
    main() 