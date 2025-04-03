from app import create_app, db
from models import Exam
import re

def fix_makeup_relationships():
    """Fix makeup exam relationships by matching exam names."""
    app = create_app()
    
    with app.app_context():
        # Get all courses
        all_courses = db.session.query(db.distinct(Exam.course_id)).all()
        total_fixed = 0
        
        for course_id, in all_courses:
            print(f"\nProcessing course ID: {course_id}")
            
            # Get all exams for this course
            exams = Exam.query.filter_by(course_id=course_id).all()
            
            # First, print all exams
            print("\nExams for this course:")
            for exam in exams:
                print(f"ID: {exam.id}, Name: {exam.name}, is_makeup: {exam.is_makeup}, makeup_for: {exam.makeup_for}")
            
            # Find makeup exams with no makeup_for value
            makeup_exams = [exam for exam in exams if exam.is_makeup and exam.makeup_for is None]
            
            if not makeup_exams:
                print("No makeup exams to fix in this course.")
                continue
            
            # For each makeup exam, find its original exam
            for makeup_exam in makeup_exams:
                name = makeup_exam.name.lower()
                
                # Try to extract the original exam name
                # Method 1: Check if it starts with "Makeup" followed by another exam name
                if name.startswith("makeup"):
                    base_name = name[6:].strip()  # Remove "Makeup" and any spaces
                    
                    # Find a matching exam
                    original_exam = None
                    for exam in exams:
                        if not exam.is_makeup and exam.name.lower() == base_name:
                            original_exam = exam
                            break
                    
                    # If exact match not found, try fuzzy matching
                    if not original_exam:
                        for exam in exams:
                            if not exam.is_makeup and base_name in exam.name.lower():
                                original_exam = exam
                                break
                    
                    if original_exam:
                        print(f"Matching '{makeup_exam.name}' with '{original_exam.name}'")
                        makeup_exam.makeup_for = original_exam.id
                        total_fixed += 1
                        db.session.commit()
                        print(f"Updated makeup_for to {original_exam.id}")
                    else:
                        print(f"Could not find original exam for '{makeup_exam.name}'")
            
            # Verify fixes
            print("\nVerifying fixes:")
            for exam in Exam.query.filter_by(course_id=course_id, is_makeup=True).all():
                if exam.makeup_for:
                    original = Exam.query.get(exam.makeup_for)
                    original_name = original.name if original else "Unknown"
                    print(f"ID: {exam.id}, Name: {exam.name}, makeup_for: {exam.makeup_for} ({original_name})")
                else:
                    print(f"ID: {exam.id}, Name: {exam.name}, makeup_for: None")
        
        print(f"\nTotal makeup exams fixed: {total_fixed}")

if __name__ == "__main__":
    fix_makeup_relationships() 