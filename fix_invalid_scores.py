#!/usr/bin/env python3
"""
Fix invalid scores that exceed the maximum possible score for questions
"""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Question, Score
from decimal import Decimal
import logging

def find_and_fix_invalid_scores():
    """Find and fix scores that exceed the maximum possible score"""
    
    app = create_app()
    
    with app.app_context():
        print("=== FINDING AND FIXING INVALID SCORES ===")
        print()
        
        # Find all scores that exceed their question's max_score
        invalid_scores = db.session.query(Score, Question).join(
            Question, Score.question_id == Question.id
        ).filter(
            Score.score > Question.max_score
        ).all()
        
        print(f"Found {len(invalid_scores)} invalid scores")
        
        if len(invalid_scores) == 0:
            print("No invalid scores found!")
            return
        
        # Group by course to understand the scope
        course_groups = {}
        for score, question in invalid_scores:
            course_id = question.exam.course_id
            if course_id not in course_groups:
                course_groups[course_id] = []
            course_groups[course_id].append((score, question))
        
        print(f"Invalid scores found in {len(course_groups)} courses:")
        
        for course_id, scores_questions in course_groups.items():
            from models import Course
            course = Course.query.get(course_id)
            print(f"\nCourse: {course.code} - {course.name}")
            print(f"  {len(scores_questions)} invalid scores")
            
            # Show some examples
            for i, (score, question) in enumerate(scores_questions[:5]):  # Show first 5
                print(f"    Score {score.score} > Max {question.max_score} (Q{question.number}, Exam: {question.exam.name})")
            
            if len(scores_questions) > 5:
                print(f"    ... and {len(scores_questions) - 5} more")
        
        # Ask for confirmation to fix
        print(f"\n=== FIXING INVALID SCORES ===")
        print("Options:")
        print("1. Cap scores to max_score (recommended)")
        print("2. Set scores to 0")
        print("3. Delete invalid scores")
        print("4. Cancel (don't fix)")
        
        choice = input("Enter your choice (1-4): ").strip()
        
        if choice == "1":
            # Cap scores to max_score
            fixed_count = 0
            for score, question in invalid_scores:
                old_score = score.score
                score.score = question.max_score
                print(f"Fixed: Score {old_score} -> {question.max_score} for Q{question.number}")
                fixed_count += 1
            
            db.session.commit()
            print(f"\n✓ Fixed {fixed_count} scores by capping to max_score")
            
        elif choice == "2":
            # Set scores to 0
            fixed_count = 0
            for score, question in invalid_scores:
                old_score = score.score
                score.score = Decimal('0')
                print(f"Fixed: Score {old_score} -> 0 for Q{question.number}")
                fixed_count += 1
            
            db.session.commit()
            print(f"\n✓ Fixed {fixed_count} scores by setting to 0")
            
        elif choice == "3":
            # Delete invalid scores
            fixed_count = 0
            for score, question in invalid_scores:
                print(f"Deleted: Score {score.score} for Q{question.number}")
                db.session.delete(score)
                fixed_count += 1
            
            db.session.commit()
            print(f"\n✓ Deleted {fixed_count} invalid scores")
            
        elif choice == "4":
            print("Operation cancelled")
            return
        else:
            print("Invalid choice, operation cancelled")
            return
        
        # Log the fix
        from models import Log
        log = Log(
            action="FIX_INVALID_SCORES",
            description=f"Fixed {len(invalid_scores)} invalid scores that exceeded question max_score"
        )
        db.session.add(log)
        db.session.commit()
        
        print("\n=== VERIFICATION ===")
        # Verify no more invalid scores exist
        remaining_invalid = db.session.query(Score, Question).join(
            Question, Score.question_id == Question.id
        ).filter(
            Score.score > Question.max_score
        ).count()
        
        if remaining_invalid == 0:
            print("✓ All invalid scores have been fixed!")
        else:
            print(f"⚠️  {remaining_invalid} invalid scores still remain")

def analyze_score_distribution():
    """Analyze score distribution to understand the data better"""
    app = create_app()
    
    with app.app_context():
        print("\n=== SCORE DISTRIBUTION ANALYSIS ===")
        
        # Get some statistics
        total_scores = Score.query.count()
        print(f"Total scores in database: {total_scores}")
        
        # Find questions with unusually high scores
        high_score_questions = db.session.query(Question).join(
            Score, Question.id == Score.question_id
        ).filter(
            Score.score > Question.max_score * Decimal('0.9')  # Scores > 90% of max
        ).distinct().all()
        
        print(f"Questions with high scores (>90% max): {len(high_score_questions)}")
        
        # Check for questions where ALL scores exceed max_score
        completely_broken_questions = []
        for question in Question.query.all():
            scores = Score.query.filter_by(question_id=question.id).all()
            if scores and all(score.score > question.max_score for score in scores):
                completely_broken_questions.append(question)
        
        print(f"Questions where ALL scores exceed max: {len(completely_broken_questions)}")
        
        if completely_broken_questions:
            print("Completely broken questions:")
            for question in completely_broken_questions[:5]:
                print(f"  Q{question.number} (Max: {question.max_score}, Exam: {question.exam.name})")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Analyze first
    analyze_score_distribution()
    
    # Then fix
    find_and_fix_invalid_scores() 