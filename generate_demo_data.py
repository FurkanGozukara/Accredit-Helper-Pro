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
from decimal import Decimal, ROUND_HALF_UP

# Make sure we can import from the current directory
sys.path.append('.')

# Import the models
from models import db, Course, Exam, CourseOutcome, ProgramOutcome, Question, AchievementLevel, GlobalAchievementLevel
from models import Student, Score, ExamWeight, course_outcome_program_outcome, question_course_outcome

# Initialize Faker for generating realistic data
fake = Faker()

# Remove fixed random seed to ensure different random selections each time
# random.seed(42) # Commented out for variability
# fake.seed_instance(42) # Commented out for variability

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
        # Initialize default global achievement levels
        initialize_global_achievement_levels()

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

def initialize_global_achievement_levels():
    """Initialize default global achievement levels if they don't exist"""
    # Check if global achievement levels already exist
    existing_count = GlobalAchievementLevel.query.count()

    if existing_count == 0:
        default_levels = [
            {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
            {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
            {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
            {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
            {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"} # Changed min_score from 0.00 to 0.01
        ]

        # Add the default global achievement levels
        for level in default_levels:
            global_level = GlobalAchievementLevel(
                name=level["name"],
                min_score=level["min_score"],
                max_score=level["max_score"],
                color=level["color"],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.session.add(global_level)

        db.session.commit()
        print("Initialized default global achievement levels")

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

    # Get existing semester+code combinations from database
    existing_combinations = set()
    for course in session.query(Course).all():
        existing_combinations.add((course.semester, course.code))

    # Filter out potential courses that already exist in the database
    filtered_courses = [
        course for course in potential_courses
        if (course["semester"], course["code"]) not in existing_combinations
    ]

    if not filtered_courses:
        print("All potential courses already exist in the database. No new courses created.")
        return []

    # Randomly select up to 3 courses from the filtered list
    num_to_select = min(3, len(filtered_courses))
    selected_courses = random.sample(filtered_courses, num_to_select)

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

    try:
        session.commit()
        print(f"Created {len(course_objects)} randomly selected courses")
    except Exception as e:
        session.rollback()
        print(f"Error creating courses: {e}")
        return []
    return course_objects

def generate_program_outcomes():
    """Get existing program outcomes from the database"""
    program_outcomes = session.query(ProgramOutcome).all()
    if not program_outcomes:
        # This case should not happen due to initialization logic
        print("Warning: No program outcomes found in the database.")
        # Attempt to initialize again just in case
        try:
            app = Flask(__name__) # Need app context for initialization
            app.config['SQLALCHEMY_DATABASE_URI'] = engine.url # Use existing engine URL
            db.init_app(app)
            with app.app_context():
                initialize_program_outcomes()
            program_outcomes = session.query(ProgramOutcome).all() # Query again
            if not program_outcomes:
                 print("Error: Failed to initialize or find program outcomes. Exiting.")
                 sys.exit(1)
        except Exception as init_e:
            print(f"Error during re-initialization attempt: {init_e}")
            sys.exit(1)

    return program_outcomes

def generate_course_outcomes(courses, program_outcomes):
    """Generate course outcomes for each course and link to program outcomes"""
    # Original course-specific outcomes data
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

    # Pool of shared/common outcomes that can appear across different courses
    shared_outcomes = [
        {"description": "Apply critical thinking to solve complex problems", "variants": [
            "Apply critical thinking to solve complex problems in the field",
            "Use critical thinking techniques to solve complex problems",
            "Apply critical thinking and analysis to solve domain problems"
        ]},
        {"description": "Implement effective software solutions", "variants": [
            "Design and implement effective software solutions",
            "Implement effective and efficient software solutions",
            "Create effective software solutions for practical problems"
        ]},
        {"description": "Analyze and evaluate different algorithms and approaches", "variants": [
            "Evaluate and analyze different approaches to problem solving",
            "Analyze and compare different algorithms for effectiveness",
            "Analyze the efficiency of different algorithmic approaches"
        ]},
        {"description": "Communicate technical concepts effectively", "variants": [
            "Effectively communicate technical concepts to diverse audiences",
            "Communicate technical ideas and designs effectively",
            "Effectively present and document technical information"
        ]},
        {"description": "Work collaboratively in team environments", "variants": [
            "Collaborate effectively in team-based development projects",
            "Work effectively in collaborative team environments",
            "Participate constructively in collaborative technical teams"
        ]},
        {"description": "Apply ethical principles to technological solutions", "variants": [
            "Consider ethical implications when developing technical solutions",
            "Apply professional ethics to technology development",
            "Integrate ethical considerations into solution development"
        ]}
    ]

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

        # Randomly determine the number of outcomes (between 2 and 6)
        num_outcomes = random.randint(2, 6)
        
        # Create a list to hold the selected outcomes for this course
        selected_outcomes = []
        
        # Keep track of descriptions to avoid exact duplicates within the same course
        course_descriptions = set()

        # For each outcome slot
        for i in range(1, num_outcomes + 1):
            # Decide whether to use a shared outcome (30% chance) or course-specific one
            use_shared = random.random() < 0.3
            
            if use_shared and shared_outcomes:
                # Select a random shared outcome
                shared = random.choice(shared_outcomes)
                # Decide whether to use the main description or a variant
                if random.random() < 0.6:  # 60% chance to use a variant
                    if shared["variants"]:
                        description = random.choice(shared["variants"])
                    else:
                        description = shared["description"]
                else:
                    description = shared["description"]
                
                # Create a code for this outcome
                code = f"{course.code}-{i}"
                
            else:
                # Use course-specific outcome if available, otherwise use default
                if i <= len(course_data):
                    code = course_data[i-1]["code"]
                    description = course_data[i-1]["description"]
                else:
                    # If we need more outcomes than are defined, create generic ones
                    code = f"{course.code}-{i}"
                    # Try to use a shared outcome as a fallback
                    if shared_outcomes:
                        random_shared = random.choice(shared_outcomes)
                        description = random_shared["description"]
                    else:
                        # Use a default if no shared outcomes available
                        description = f"Outcome {i} for {course.code}"
            
            # Check if this exact description is already used for this course
            if description not in course_descriptions:
                selected_outcomes.append({
                    "code": code,
                    "description": description
                })
                course_descriptions.add(description)
            else:
                # If duplicate, try to find a non-duplicate
                attempts = 0
                while attempts < 5 and description in course_descriptions:
                    # Try to find a unique description
                    if shared_outcomes:
                        random_shared = random.choice(shared_outcomes)
                        if random.random() < 0.6 and random_shared["variants"]:
                            description = random.choice(random_shared["variants"])
                        else:
                            description = random_shared["description"]
                    else:
                        description = f"Unique outcome {i} for {course.code} (attempt {attempts})"
                    attempts += 1
                
                # Add the outcome (even if still duplicate after attempts, at least we tried)
                selected_outcomes.append({
                    "code": code,
                    "description": description
                })
                course_descriptions.add(description)

        # Now create the course outcomes from our selected list
        for co_data in selected_outcomes:
            course_outcome = CourseOutcome(
                code=co_data["code"],
                description=co_data["description"],
                course_id=course.id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            # Associate with 2-3 random program outcomes
            if program_outcomes: # Ensure program_outcomes is not empty
                num_to_link = min(len(program_outcomes), random.randint(2, 3))
                selected_pos = random.sample(program_outcomes, num_to_link)
                
                # Generate relative weights for CO-PO relationships (between 0.5 and 2.0)
                for po in selected_pos:
                    # Check if the association table has a 'relative_weight' column
                    # We need to handle both old and new database schemas
                    try:
                        from sqlalchemy import inspect
                        inspector = inspect(engine)
                        columns = [c['name'] for c in inspector.get_columns('course_outcome_program_outcome')]
                        
                        if 'relative_weight' in columns:
                            # Generate a random weight between 0.5 and 2.0 with 0.01 precision
                            relative_weight = round(random.uniform(0.5, 2.0), 2)
                            
                            # Add the PO to the CO with the relative weight using SQL expression
                            stmt = course_outcome_program_outcome.insert().values(
                                course_outcome_id=course_outcome.id,
                                program_outcome_id=po.id,
                                relative_weight=relative_weight
                            )
                            # We need to defer this execution until after the course_outcome is committed
                            # So we'll add the PO to the course_outcome normally and update the weight after commit
                            course_outcome.program_outcomes.append(po)
                        else:
                            # For older installations without the relative_weight column
                            course_outcome.program_outcomes.append(po)
                    except Exception as e:
                        print(f"Warning: Could not inspect database schema or add relative weights: {e}")
                        # Fallback to simple association
                        course_outcome.program_outcomes.append(po)
            else:
                print(f"Warning: No program outcomes available to associate with {course_outcome.code}")

            session.add(course_outcome)
            all_course_outcomes.append(course_outcome)

    try:
        session.commit()
        
        # Now update the relative weights for the associations
        # This is needed because we need the course_outcome.id which is only available after commit
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(engine)
            columns = [c['name'] for c in inspector.get_columns('course_outcome_program_outcome')]
            
            if 'relative_weight' in columns:
                for course_outcome in all_course_outcomes:
                    for po in course_outcome.program_outcomes:
                        # Generate a random weight between 0.5 and 2.0 with 0.01 precision
                        relative_weight = round(random.uniform(0.5, 2.0), 2)
                        
                        # Update the relative_weight directly using SQL
                        stmt = text("""
                            UPDATE course_outcome_program_outcome 
                            SET relative_weight = :weight 
                            WHERE course_outcome_id = :co_id AND program_outcome_id = :po_id
                        """)
                        session.execute(stmt, {"weight": relative_weight, "co_id": course_outcome.id, "po_id": po.id})
                
                session.commit()
        except Exception as e:
            print(f"Warning: Could not update relative weights: {e}")
            session.rollback()
            
        print(f"Created {len(all_course_outcomes)} course outcomes")
    except Exception as e:
        session.rollback()
        print(f"Error creating course outcomes: {e}")
        return [] # Return empty list on failure
    return all_course_outcomes

def generate_exams(courses):
    """Generate exams for each course, including makeups and weights"""
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
        "DEFAULT": { # Default weights if course code not found
            "Quiz": Decimal('0.1'),
            "Assignment": Decimal('0.15'),
            "Midterm": Decimal('0.25'),
            "Project": Decimal('0.1'),
            "Final Exam": Decimal('0.4'),
            "Other": Decimal('0.0') # Handle unknown types gracefully
        }
    }

    all_regular_exams = []
    makeup_exam_info_list = [] # Store dicts: {'makeup': makeup_exam_obj, 'original': original_exam_obj}

    # --- Step 1: Create Regular Exams ---
    for course in courses:
        exams_data = exam_types.get(course.code, [])
        if not exams_data: # Use default if none defined
            exams_data = [
                {"name": "Midterm", "max_score": 100, "date_offset": -45},
                {"name": "Final Exam", "max_score": 100, "date_offset": -7}
            ]

        course_regular_exams = []
        for exam_data in exams_data:
            today = datetime.now().date()
            exam_date = today + timedelta(days=exam_data["date_offset"])
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
                is_mandatory=is_final_exam
            )
            session.add(exam)
            course_regular_exams.append(exam)
            all_regular_exams.append(exam)

        # --- Step 2: Create Makeup Exam Objects (without linking yet) ---
        for regular_exam in course_regular_exams:
            if regular_exam.is_final or ("Midterm" in regular_exam.name and random.random() < 0.5):
                makeup_date = regular_exam.exam_date + timedelta(days=random.randint(7, 14))
                makeup_name = f"Makeup {regular_exam.name}"

                makeup_exam = Exam(
                    name=makeup_name,
                    max_score=regular_exam.max_score,
                    exam_date=makeup_date,
                    course_id=regular_exam.course_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    is_makeup=True,
                    is_final=regular_exam.is_final,
                    is_mandatory=True,
                    # makeup_for FK will be set AFTER original exam has an ID
                )
                session.add(makeup_exam)
                # Store objects for linking after commit
                makeup_exam_info_list.append({'makeup': makeup_exam, 'original': regular_exam})

    # --- Step 3: Commit Regular Exams to get IDs ---
    try:
        session.commit()
        print(f"Created {len(all_regular_exams)} regular exams.")
    except Exception as e:
        session.rollback()
        print(f"Error creating regular exams: {e}")
        return [] # Can't proceed without regular exams

    # --- Step 4: Link Makeup Exams using makeup_for FK ---
    successfully_linked_makeups = []
    for info in makeup_exam_info_list:
        makeup_exam = info['makeup']
        original_exam = info['original']
        # The original_exam object should now have its ID populated from the previous commit
        if original_exam.id:
            makeup_exam.makeup_for = original_exam.id # Set the foreign key
            session.add(makeup_exam) # Add again to stage the update
            successfully_linked_makeups.append(makeup_exam)
        else:
            # This case should be rare if the first commit succeeded
            print(f"Warning: Original exam {original_exam.name} for course {original_exam.course_id} has no ID after commit. Cannot link makeup exam {makeup_exam.name}.")

    # --- Step 5: Commit Makeup Exam Links ---
    if successfully_linked_makeups:
        try:
            session.commit()
            print(f"Created and linked {len(successfully_linked_makeups)} makeup exams.")
        except Exception as e:
            session.rollback()
            print(f"Error linking makeup exams: {e}")
            # Decide if you want to continue without linked makeups or stop
            # For now, we'll proceed but they won't have weights

    # --- Step 6: Assign Weights ---
    combined_exams = all_regular_exams + successfully_linked_makeups # All exams that exist in DB

    for course in courses:
        # Filter exams relevant to this course that exist in DB
        course_exams_for_weights = [e for e in combined_exams if e.course_id == course.id]
        weight_dist = weight_distributions.get(course.code, weight_distributions["DEFAULT"])

        regular_course_exams = [e for e in course_exams_for_weights if not e.is_makeup]
        total_weight = Decimal('0')
        exam_weights_map = {} # Map: {original_exam_id: weight}

        # Assign weights to regular exams first
        for i, exam in enumerate(regular_course_exams):
            assigned_weight = Decimal('0')
            matched_key = None
            # Prioritize longer keys first if names overlap (e.g., "Final Exam" before "Exam")
            sorted_keys = sorted(weight_dist.keys(), key=len, reverse=True)
            for exam_type in sorted_keys:
                if exam_type in exam.name:
                    # Basic check to avoid partial matches like 'Assign' in 'Assignment'
                    if exam.name.startswith(exam_type):
                         matched_key = exam_type
                         break
                    # Allow matches like "Quiz 1", "Midterm 2"
                    if exam.name.startswith(exam_type + " "):
                         matched_key = exam_type
                         break


            if matched_key:
                assigned_weight = weight_dist[matched_key]
            else:
                assigned_weight = weight_dist.get("Other", Decimal('0.0'))
                if assigned_weight == Decimal('0.0'): # Only warn if the fallback is also zero
                    print(f"Warning: No specific or 'Other' weight > 0 found for '{exam.name}' in course {course.code}. Assigning weight 0.")

            # Adjust last exam's weight to make total 1.0
            if i == len(regular_course_exams) - 1:
                remaining_weight = (Decimal('1.0') - total_weight).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if remaining_weight < 0:
                   print(f"Warning: Calculated remaining weight is negative ({remaining_weight}) for course {course.code}. Adjusting weight for {exam.name} to 0.")
                   remaining_weight = Decimal('0.0')
                assigned_weight = remaining_weight
            # Prevent cumulative weight exceeding 1.0 before the last item
            elif total_weight + assigned_weight > Decimal('1.01'):
                 print(f"Warning: Cumulative weight ({total_weight + assigned_weight}) exceeding 1.0 for course {course.code} before last exam. Clamping weight for {exam.name}.")
                 assigned_weight = max(Decimal('0.0'), (Decimal('1.0') - total_weight).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

            # Ensure non-negative weight
            assigned_weight = max(Decimal('0.0'), assigned_weight)

            exam_weight = ExamWeight(
                exam_id=exam.id,
                course_id=course.id,
                weight=assigned_weight,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(exam_weight)
            exam_weights_map[exam.id] = assigned_weight
            total_weight += assigned_weight

        # Verify final total weight for regular exams
        if not (Decimal('0.99') <= total_weight <= Decimal('1.01')):
             print(f"Warning: Final total weight for course {course.code} ({course.id}) is {total_weight}. Check weight distribution.")

        # Assign weights to linked makeup exams
        makeup_course_exams = [e for e in course_exams_for_weights if e.is_makeup and e.makeup_for is not None]
        for makeup_exam in makeup_course_exams:
            original_exam_id = makeup_exam.makeup_for # Use the FK value

            if original_exam_id in exam_weights_map:
                makeup_weight_value = exam_weights_map[original_exam_id]
                makeup_weight = ExamWeight(
                    exam_id=makeup_exam.id,
                    course_id=course.id,
                    weight=makeup_weight_value,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(makeup_weight)
            else:
                # This might happen if the original exam somehow didn't get a weight assigned
                print(f"Warning: Could not find weight in map for original exam ID {original_exam_id} (for makeup {makeup_exam.name}, ID: {makeup_exam.id}). Skipping makeup weight assignment.")

    # --- Step 7: Commit Weights ---
    try:
        session.commit()
        print(f"Created exam weights for relevant exams.")
    except Exception as e:
        session.rollback()
        print(f"Error creating exam weights: {e}")

    return combined_exams # Return all exams that were successfully added/linked

def generate_questions(exams, course_outcomes):
    """Generate questions for each exam and link them to course outcomes"""
    all_questions = []

    for exam in exams:
        # Get course outcomes for this exam's course
        relevant_outcomes = [co for co in course_outcomes if co.course_id == exam.course_id]

        # Determine number of questions based on exam type
        if "Quiz" in exam.name or "Homework" in exam.name or "Lab" in exam.name or "Assignment" in exam.name:
            num_questions = random.randint(3, 8)
        elif "Midterm" in exam.name:
            num_questions = random.randint(5, 15)
        elif "Final Exam" in exam.name: # Regular or Makeup Final
            num_questions = random.randint(8, 20)
        elif "Project" in exam.name:
            num_questions = random.randint(2, 5) # Projects usually have fewer, higher-value parts
        else: # Default for unknown types
            num_questions = random.randint(4, 10)

        if num_questions == 0: # Ensure at least one question
             num_questions = 1

        total_points = Decimal(str(exam.max_score))

        # Distribute points among questions - allow more variance
        points = []
        if num_questions > 0 and total_points > 0 :
            # Generate random weights for each question
            raw_weights = [random.uniform(0.1, 1.0) for _ in range(num_questions)] # Ensure non-zero weight
            total_raw_weight = sum(raw_weights)

            # Normalize weights and calculate points, ensuring sum matches exam max_score
            current_sum = Decimal('0')
            for i in range(num_questions):
                # Calculate proportional points
                point_value = (Decimal(str(raw_weights[i])) / Decimal(str(total_raw_weight)) * total_points)

                # Round intelligently: round down for all but last, adjust last one
                if i < num_questions - 1:
                     # Round down to 1 decimal place
                    point_value = (point_value * 10).to_integral_value() / Decimal(10)
                    # Ensure at least 0.1 points if total points > 0
                    point_value = max(Decimal('0.1'), point_value)
                    points.append(point_value)
                    current_sum += point_value
                else:
                    # Assign remaining points to the last question
                    last_point_value = (total_points - current_sum).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                    # Ensure last point value is non-negative and at least 0.1 if possible
                    last_point_value = max(Decimal('0.0'), last_point_value)
                    if total_points > 0 and last_point_value == 0 and current_sum < total_points:
                        last_point_value = Decimal('0.1')
                    # Prevent total exceeding max_score due to rounding up last item
                    if current_sum + last_point_value > total_points:
                         last_point_value = total_points - current_sum # Recalculate precisely
                         last_point_value = max(Decimal('0.0'), last_point_value) # Ensure non-negative

                    points.append(last_point_value)
                    current_sum += last_point_value # Update final sum


            # Shuffle points to avoid pattern where last question always has adjusted points
            random.shuffle(points)

            # Final check: If sum is slightly off due to rounding, adjust the largest item
            final_sum_check = sum(points)
            if abs(final_sum_check - total_points) > Decimal('0.01'):
                difference = total_points - final_sum_check
                if points: # Ensure points list is not empty
                    points.sort(reverse=True) # Find largest element
                    points[0] += difference # Add difference to the largest element
                    # Ensure it's not negative after adjustment
                    points[0] = max(Decimal('0.0'), points[0].quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
                    random.shuffle(points) # Shuffle again

        elif num_questions > 0 and total_points <= 0:
             # If max_score is 0, assign 0 points to all questions
             points = [Decimal('0.0')] * num_questions


        for q_num in range(1, num_questions + 1):
            point_value = points[q_num-1] if points and q_num <= len(points) else Decimal('0')

            question = Question(
                text=f"Question {q_num}: {fake.sentence(nb_words=random.randint(6, 15))}", # More variable question text
                number=q_num,
                max_score=point_value,
                exam_id=exam.id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            # Associate with 1-2 random course outcomes, if available
            if relevant_outcomes:
                num_outcomes_to_link = min(len(relevant_outcomes), random.randint(1, 2))
                selected_cos = random.sample(relevant_outcomes, num_outcomes_to_link)
                question.course_outcomes = selected_cos

            session.add(question)
            all_questions.append(question)

    try:
        session.commit()
        print(f"Created {len(all_questions)} questions")
    except Exception as e:
        session.rollback()
        print(f"Error creating questions: {e}")
        return []
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
    students_to_add = []

    for course in courses:
        num_students = student_counts.get(course.code, 25)  # Default to 25 if course code not in dictionary

        for _ in range(num_students):
            # Generate a unique student ID for this course
            attempts = 0
            while attempts < 100: # Prevent infinite loop
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
                    student = Student(
                        student_id=student_id,
                        first_name=fake.first_name(),
                        last_name=fake.last_name(),
                        course_id=course.id,
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    students_to_add.append(student)
                    break # Found unique ID
                attempts += 1
            if attempts >= 100:
                print(f"Warning: Could not generate unique student ID for course {course.code} after 100 attempts. Skipping one student.")


    session.add_all(students_to_add)
    try:
        session.commit()
        print(f"Created {len(students_to_add)} students")
    except Exception as e:
        session.rollback()
        print(f"Error creating students: {e}")
        # Query existing students for the affected courses to return what was created
        student_ids_added = [s.id for s in students_to_add if s.id] # Get IDs if commit partially worked
        all_students = session.query(Student).filter(Student.id.in_(student_ids_added)).all()
        return all_students

    # Query students again after successful commit to get their IDs
    all_students = session.query(Student).filter(Student.course_id.in_([c.id for c in courses])).all()
    return all_students


def generate_achievement_levels(courses):
    """Generate achievement levels for each course if they don't exist"""
    # Define default achievement levels
    default_levels = [
        {"name": "Excellent", "min_score": 90.00, "max_score": 100.00, "color": "success"},
        {"name": "Better", "min_score": 70.00, "max_score": 89.99, "color": "info"},
        {"name": "Good", "min_score": 60.00, "max_score": 69.99, "color": "primary"},
        {"name": "Need Improvements", "min_score": 50.00, "max_score": 59.99, "color": "warning"},
        {"name": "Failure", "min_score": 0.01, "max_score": 49.99, "color": "danger"} # Min score 0.01
    ]

    # Check which courses already have achievement levels
    courses_with_levels = set(level.course_id for level in session.query(AchievementLevel.course_id).distinct())

    # Filter courses that need achievement levels
    courses_needing_levels = [c for c in courses if c.id not in courses_with_levels]

    if not courses_needing_levels:
        print("All relevant courses already have achievement levels.")
        return []

    all_levels = []
    levels_to_add = []
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
            levels_to_add.append(level)
            all_levels.append(level) # Keep track even before commit for return value

    session.add_all(levels_to_add)
    try:
        session.commit()
        print(f"Created {len(levels_to_add)} achievement levels for {len(courses_needing_levels)} courses")
    except Exception as e:
        session.rollback()
        print(f"Error creating achievement levels: {e}")
        return [] # Return empty on failure

    return all_levels

def main():
    print("Generating demo data for Accredit Helper Pro...")

    # --- Initialization ---
    try:
        create_database_if_not_exists()
    except Exception as e:
        print(f"Fatal Error during database initialization: {e}")
        sys.exit(1)

    # Now connect to the database for data generation
    base_dir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(base_dir, 'instance')
    db_path = os.path.join(instance_dir, 'accredit_data.db')

    # Connect to the database
    global engine, Session, session
    try:
        engine = create_engine(f'sqlite:///{db_path}')
        Session = sessionmaker(bind=engine)
        session = Session()
    except Exception as e:
        print(f"Fatal Error connecting to database: {e}")
        sys.exit(1)

    # --- Course Selection ---
    existing_courses = session.query(Course).all()
    existing_course_count = len(existing_courses)
    courses_to_process = [] # List of courses for which we will generate data

    if existing_course_count > 0:
        print(f"\nFound {existing_course_count} existing courses in the database.")
        try:
            response = input(f"Generate NEW demo data (students, exams, scores etc.) for these existing courses? (y/n): ")
        except EOFError: # Handle running in non-interactive environment
             print("Non-interactive mode detected, generating data for existing courses.")
             response = 'y'

        if response.lower() == 'y':
            print(f"Will generate NEW data for {existing_course_count} existing courses.")
            courses_to_process.extend(existing_courses)
        else:
            print("Will only generate data for newly created courses (if any).")

    # Generate new courses (up to 3 if possible)
    new_courses = generate_courses()
    courses_to_process.extend(new_courses)

    if not courses_to_process:
        print("\nNo courses selected or created for data generation. Exiting.")
        session.close()
        return

    print(f"\nWill generate data for the following {len(courses_to_process)} courses:")
    for c in courses_to_process:
        print(f" - {c.code} ({c.semester}) - ID: {c.id}")

    # Map course IDs to indices for score generation logic BEFORE filtering
    all_target_course_ids = sorted(list(set(c.id for c in courses_to_process)))
    course_index_map = {course_id: idx for idx, course_id in enumerate(all_target_course_ids)}
    num_target_courses = len(all_target_course_ids)
    print(f"Course ID to Index mapping for scoring: {course_index_map}")


    # --- Data Generation Steps (with checks for existing data) ---

    program_outcomes = generate_program_outcomes() # Get or initialize POs

    # --- Course Outcomes ---
    print("\n--- Generating Course Outcomes ---")
    # Check which of the *selected* courses already have outcomes
    existing_co_course_ids = set(co.course_id for co in session.query(CourseOutcome.course_id)
                                  .filter(CourseOutcome.course_id.in_(all_target_course_ids)).distinct())
    courses_needing_outcomes = [c for c in courses_to_process if c.id not in existing_co_course_ids]
    if courses_needing_outcomes:
        print(f"Generating outcomes for {len(courses_needing_outcomes)} courses...")
        generate_course_outcomes(courses_needing_outcomes, program_outcomes)
    else:
        print("All selected courses already have course outcomes.")
    # Get all outcomes for the courses we are processing
    all_course_outcomes = session.query(CourseOutcome).filter(CourseOutcome.course_id.in_(all_target_course_ids)).all()


    # --- Exams & Weights ---
    print("\n--- Generating Exams & Weights ---")
    existing_exam_course_ids = set(exam.course_id for exam in session.query(Exam.course_id)
                                   .filter(Exam.course_id.in_(all_target_course_ids)).distinct())
    courses_needing_exams = [c for c in courses_to_process if c.id not in existing_exam_course_ids]
    if courses_needing_exams:
        print(f"Generating exams and weights for {len(courses_needing_exams)} courses...")
        generate_exams(courses_needing_exams) # generate_exams now handles weights too
    else:
        print("All selected courses already appear to have exams.")
    # Get all exams for the courses we are processing
    all_exams = session.query(Exam).filter(Exam.course_id.in_(all_target_course_ids)).all()
    all_exam_ids = [e.id for e in all_exams]


    # --- Questions ---
    print("\n--- Generating Questions ---")
    existing_question_exam_ids = set(q.exam_id for q in session.query(Question.exam_id)
                                     .filter(Question.exam_id.in_(all_exam_ids)).distinct())
    exams_needing_questions = [e for e in all_exams if e.id not in existing_question_exam_ids]
    if exams_needing_questions:
        print(f"Generating questions for {len(exams_needing_questions)} exams...")
        generate_questions(exams_needing_questions, all_course_outcomes)
    else:
        print("All exams for selected courses already appear to have questions.")
    # Get all questions for the relevant exams
    all_questions = session.query(Question).filter(Question.exam_id.in_(all_exam_ids)).all()


    # --- Students ---
    print("\n--- Generating Students ---")
    existing_student_course_ids = set(s.course_id for s in session.query(Student.course_id)
                                      .filter(Student.course_id.in_(all_target_course_ids)).distinct())
    courses_needing_students = [c for c in courses_to_process if c.id not in existing_student_course_ids]
    if courses_needing_students:
        print(f"Generating students for {len(courses_needing_students)} courses...")
        generate_students(courses_needing_students)
    else:
        print("All selected courses already appear to have students.")
    # Get all students for the courses we are processing
    all_students = session.query(Student).filter(Student.course_id.in_(all_target_course_ids)).all()


    # --- Achievement Levels ---
    print("\n--- Generating Achievement Levels ---")
    generate_achievement_levels(courses_to_process)


    # --- Scores (Using Normal Distribution Logic) ---
    print("\n--- Generating Scores ---")
    # Get existing scores ONLY for the students and questions we are processing to avoid re-generating
    relevant_student_ids = [s.id for s in all_students]
    relevant_question_ids = [q.id for q in all_questions]
    existing_scores = set((score.student_id, score.question_id)
                          for score in session.query(Score.student_id, Score.question_id)
                          .filter(Score.student_id.in_(relevant_student_ids))
                          .filter(Score.question_id.in_(relevant_question_ids))
                          .all())
    print(f"Found {len(existing_scores)} existing relevant score entries. Skipping generation for these.")

    new_scores_to_add = []
    total_scores_possible = 0

    student_progress_counter = 0
    student_total = len(all_students)

    # Pre-filter questions by course_id for efficiency
    questions_by_course = {}
    for q in all_questions:
        course_id = q.exam.course_id # Access course_id via exam relationship
        if course_id not in questions_by_course:
            questions_by_course[course_id] = []
        questions_by_course[course_id].append(q)


    for student in all_students:
        student_progress_counter += 1
        if student_progress_counter % 50 == 0: # Print progress update
             print(f"  Generating scores for student {student_progress_counter}/{student_total} (ID: {student.student_id})...")

        student_course_id = student.course_id
        # Get pre-filtered questions for this student's course
        course_questions = questions_by_course.get(student_course_id, [])
        total_scores_possible += len(course_questions)

        # Determine score distribution parameters based on the course's mapped index
        # Use modulo num_target_courses as a fallback if index is out of expected range (0, 1, 2)
        course_idx = course_index_map.get(student_course_id, 0) % max(1, num_target_courses) # Avoid modulo by zero

        mean_pct = 0.6 # Default mean if index is unexpected
        std_dev = 0.20 # Standard deviation for score spread

        # Apply the requested score distributions based on course index
        if course_idx == 0:
            # First course: Target average 40-50% -> Mean 0.45, High Variance
            mean_pct = 0.45
            std_dev = 0.22
        elif course_idx == 1:
            # Second course: Target average 50-70% -> Mean 0.60, High Variance
            mean_pct = 0.60
            std_dev = 0.20
        elif course_idx == 2:
             # Third course: Target average 70-100% -> Mean 0.85, High Variance
            mean_pct = 0.85
            std_dev = 0.18
        # Add more elif conditions here if processing more than 3 courses with specific distributions

        for question in course_questions:
            # Skip if score already exists or max_score is invalid/zero
            if (student.id, question.id) in existing_scores:
                continue
            max_score = Decimal(str(question.max_score))
            if max_score <= 0:
                 continue

            # Generate a raw percentage score using a normal distribution
            raw_pct = random.normalvariate(mean_pct, std_dev)
            # Clamp the percentage between 0.0 and 1.0
            clamped_pct = max(0.0, min(1.0, raw_pct))
            student_score_pct = Decimal(str(clamped_pct))

            # Calculate actual score
            raw_score = student_score_pct * max_score
            # Round to one decimal place and ensure bounds [0, max_score]
            score_value = max(Decimal('0'), min(max_score, raw_score.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)))

            score = Score(
                score=score_value,
                student_id=student.id,
                question_id=question.id,
                exam_id=question.exam_id, # Store exam_id directly on score for easier querying
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            new_scores_to_add.append(score)

            # Add & Commit in batches for memory efficiency
            if len(new_scores_to_add) >= 2000:
                session.add_all(new_scores_to_add)
                try:
                    session.commit()
                    print(f"    ... committed batch of {len(new_scores_to_add)} scores ...")
                    new_scores_to_add = [] # Reset batch
                except Exception as e:
                    print(f"Error committing score batch: {e}")
                    session.rollback()
                    # Optionally: break or try smaller batches
                    new_scores_to_add = [] # Discard failing batch for now


    # Add & Commit any remaining scores
    if new_scores_to_add:
        session.add_all(new_scores_to_add)
        try:
            session.commit()
            print(f"    ... committed final batch of {len(new_scores_to_add)} scores.")
        except Exception as e:
            print(f"Error committing final score batch: {e}")
            session.rollback()

    print(f"\nAttempted to generate scores. {len(existing_scores)} skipped, aiming for {total_scores_possible - len(existing_scores)} new entries.")


    # --- Final Summary ---
    print("\n--- Demo Data Generation Summary ---")
    # Recount everything after all operations
    final_course_count = session.query(Course).count()
    final_po_count = session.query(ProgramOutcome).count()
    final_co_count = session.query(CourseOutcome).count()
    final_exam_count = session.query(Exam).count()
    final_question_count = session.query(Question).count()
    final_student_count = session.query(Student).count()
    final_score_count = session.query(Score).count()
    final_ach_level_count = session.query(AchievementLevel).count()
    final_global_ach_level_count = session.query(GlobalAchievementLevel).count()

    print(f"\nDatabase now contains:")
    print(f"  - {final_course_count} total courses")
    print(f"  - {final_po_count} program outcomes")
    print(f"  - {final_co_count} course outcomes")
    print(f"  - {final_exam_count} exams (including makeups)")
    print(f"  - {final_question_count} questions")
    print(f"  - {final_student_count} student enrollments")
    print(f"  - {final_score_count} scores")
    print(f"  - {final_ach_level_count} course-specific achievement levels")
    print(f"  - {final_global_ach_level_count} global achievement levels")
    print("\nDemo data generation process complete.")

    session.close()
    print("Database session closed.")


if __name__ == "__main__":
    main()