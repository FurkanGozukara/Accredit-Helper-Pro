import os
import sys
from flask import Flask
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import exists

# Add project root to sys.path to allow importing models
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from models import (
        db, init_db_session, Course, Exam, ExamWeight, CourseOutcome,
        ProgramOutcome, Question, Student, Score, CourseSettings,
        AchievementLevel, StudentExamAttendance,
        course_outcome_program_outcome, question_course_outcome
    )
except ImportError as e:
    print(f"Error importing models: {e}")
    print("Ensure this script is run from the project root directory or adjust sys.path.")
    sys.exit(1)

def create_check_app():
    """Creates a minimal Flask app for the integrity check."""
    app = Flask(__name__)
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, "instance", "accredit_data.db")

    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        print("Please ensure the database exists and the script is run from the correct directory.")
        sys.exit(1)

    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    init_db_session(app) # Initialize scoped session
    return app

def check_foreign_key(session, model, fk_column_name, related_model):
    """Checks for orphaned records for a specific foreign key."""
    orphaned_count = 0
    # Get the actual Column object
    fk_column = getattr(model, fk_column_name)
    # Find IDs present in the child table's FK column
    child_ids = session.query(fk_column).filter(fk_column.isnot(None)).distinct().all()
    child_ids_set = {id_tuple[0] for id_tuple in child_ids} # Extract IDs

    if not child_ids_set:
        # print(f"  No non-null foreign key values found for {model.__tablename__}.{fk_column_name}. Skipping check.")
        return 0 # No FKs to check

    # Find existing parent IDs
    parent_ids = session.query(related_model.id).all()
    parent_ids_set = {id_tuple[0] for id_tuple in parent_ids}

    # Find orphaned IDs (present in child FK, but not in parent PK)
    orphaned_ids = child_ids_set - parent_ids_set

    if orphaned_ids:
        print(f"  Found {len(orphaned_ids)} orphaned records in '{model.__tablename__}' referencing '{related_model.__tablename__}' via '{fk_column_name}':")
        # Retrieve and print details of the first few orphaned records for context
        orphaned_records = session.query(model).filter(fk_column.in_(orphaned_ids)).limit(5).all()
        for record in orphaned_records:
            print(f"    - {model.__name__} ID: {record.id}, Missing {related_model.__name__} ID: {getattr(record, fk_column_name)}")
        if len(orphaned_ids) > 5:
            print(f"    - ... and {len(orphaned_ids) - 5} more.")
        orphaned_count = len(orphaned_ids)

    return orphaned_count

def check_association_table(session, association_table, fk1_name, model1, fk2_name, model2):
    """Checks an association table for orphaned records."""
    orphaned_count = 0
    print(f"Checking association table: {association_table.name}")

    # Check first foreign key
    fk1_col = association_table.columns[fk1_name]
    child1_ids = session.query(fk1_col).distinct().all()
    child1_ids_set = {id_tuple[0] for id_tuple in child1_ids}
    if child1_ids_set:
        parent1_ids = session.query(model1.id).all()
        parent1_ids_set = {id_tuple[0] for id_tuple in parent1_ids}
        orphaned1_ids = child1_ids_set - parent1_ids_set
        if orphaned1_ids:
            print(f"  Found {len(orphaned1_ids)} orphaned entries referencing '{model1.__tablename__}' via '{fk1_name}'. Example missing IDs: {list(orphaned1_ids)[:5]}")
            orphaned_count += len(orphaned1_ids)

    # Check second foreign key
    fk2_col = association_table.columns[fk2_name]
    child2_ids = session.query(fk2_col).distinct().all()
    child2_ids_set = {id_tuple[0] for id_tuple in child2_ids}
    if child2_ids_set:
        parent2_ids = session.query(model2.id).all()
        parent2_ids_set = {id_tuple[0] for id_tuple in parent2_ids}
        orphaned2_ids = child2_ids_set - parent2_ids_set
        if orphaned2_ids:
            print(f"  Found {len(orphaned2_ids)} orphaned entries referencing '{model2.__tablename__}' via '{fk2_name}'. Example missing IDs: {list(orphaned2_ids)[:5]}")
            orphaned_count += len(orphaned2_ids)

    return orphaned_count


def run_integrity_check():
    """Runs the database integrity checks."""
    app = create_check_app()
    total_orphaned = 0

    with app.app_context():
        session = db.session
        print("Starting database integrity check...")

        # --- Check Models with Foreign Keys ---
        print("\nChecking Model Foreign Keys:")

        # Exam -> Course
        total_orphaned += check_foreign_key(session, Exam, 'course_id', Course)
        # Exam -> Exam (makeup_for)
        total_orphaned += check_foreign_key(session, Exam, 'makeup_for', Exam) # Checks nullable FK

        # ExamWeight -> Exam & Course
        total_orphaned += check_foreign_key(session, ExamWeight, 'exam_id', Exam)
        total_orphaned += check_foreign_key(session, ExamWeight, 'course_id', Course)

        # CourseOutcome -> Course
        total_orphaned += check_foreign_key(session, CourseOutcome, 'course_id', Course)

        # Question -> Exam
        total_orphaned += check_foreign_key(session, Question, 'exam_id', Exam)

        # Student -> Course
        total_orphaned += check_foreign_key(session, Student, 'course_id', Course)

        # Score -> Student, Question, Exam
        total_orphaned += check_foreign_key(session, Score, 'student_id', Student)
        total_orphaned += check_foreign_key(session, Score, 'question_id', Question)
        total_orphaned += check_foreign_key(session, Score, 'exam_id', Exam)

        # CourseSettings -> Course
        total_orphaned += check_foreign_key(session, CourseSettings, 'course_id', Course)

        # AchievementLevel -> Course
        total_orphaned += check_foreign_key(session, AchievementLevel, 'course_id', Course)

        # StudentExamAttendance -> Student & Exam
        total_orphaned += check_foreign_key(session, StudentExamAttendance, 'student_id', Student)
        total_orphaned += check_foreign_key(session, StudentExamAttendance, 'exam_id', Exam)

        # --- Check Association Tables ---
        print("\nChecking Association Tables:")
        total_orphaned += check_association_table(
            session, course_outcome_program_outcome,
            'course_outcome_id', CourseOutcome,
            'program_outcome_id', ProgramOutcome
        )
        total_orphaned += check_association_table(
            session, question_course_outcome,
            'question_id', Question,
            'course_outcome_id', CourseOutcome
        )

        # --- Summary ---
        print("\nIntegrity Check Complete.")
        if total_orphaned == 0:
            print("No orphaned records found. Database integrity looks good!")
        else:
            print(f"Found a total of {total_orphaned} potential orphaned records or references.")
            print("Review the output above for details.")

        session.remove() # Clean up the session

if __name__ == "__main__":
    run_integrity_check() 