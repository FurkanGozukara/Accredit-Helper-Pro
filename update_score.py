from app import create_app
from models import Student, Score, Question, Exam, db
from decimal import Decimal

app = create_app()

def update_pamela_craig_score():
    with app.app_context():
        # Find Pamela Craig in course 3
        student = Student.query.filter_by(course_id=3, first_name="Pamela", last_name="Craig").first()
        
        if not student:
            print("Student Pamela Craig not found")
            return
            
        print(f"Found student: {student.first_name} {student.last_name} (ID: {student.id})")
        
        # Get exams for course 3
        exams = Exam.query.filter_by(course_id=3).all()
        exam_ids = [exam.id for exam in exams]
        
        # Get all scores for this student
        scores = Score.query.filter(
            Score.student_id == student.id,
            Score.exam_id.in_(exam_ids)
        ).all()
        
        if not scores:
            print("No scores found for this student")
            return
            
        print(f"Found {len(scores)} scores")
        
        # Calculate total and get current weighted score
        total_score = 0
        total_max = 0
        
        for score in scores:
            question = Question.query.get(score.question_id)
            total_score += float(score.score)
            total_max += float(question.max_score)
            
        current_percentage = (total_score / total_max) * 100 if total_max > 0 else 0
        print(f"Current calculated score: {current_percentage:.2f}%")
        
        # Update scores to ensure 60.0%
        target_percentage = 60.01  # Slightly higher to ensure "Good" categorization
        target_total = (target_percentage * total_max) / 100
        increase_needed = target_total - total_score
        
        if increase_needed <= 0:
            print("Score is already at or above target. No changes needed.")
            return
            
        print(f"Need to increase total score by {increase_needed:.2f} points")
        
        # Find a single score to update
        score_to_update = scores[0]
        
        # Update the score
        old_score = float(score_to_update.score)
        new_score = old_score + increase_needed
        
        print(f"Updating score ID {score_to_update.id} from {old_score} to {new_score}")
        
        score_to_update.score = Decimal(str(new_score))
        db.session.commit()
        
        print("Score updated successfully. Student should now be categorized as 'Good'")

if __name__ == "__main__":
    update_pamela_craig_score() 