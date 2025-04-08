from app import create_app
from models import Student, AchievementLevel, Score, Question, Exam
from decimal import Decimal

app = create_app()

with app.app_context():
    # Find Pamela Craig in Course 3
    student = Student.query.filter_by(course_id=3, first_name="Pamela", last_name="Craig").first()
    
    if student:
        print(f"Found student: {student.first_name} {student.last_name} (ID: {student.id})")
        
        # Get scores for this student
        scores = Score.query.join(Question).join(Exam).filter(
            Score.student_id == student.id,
            Exam.course_id == 3
        ).all()
        
        # Print all scores
        total_score = 0
        total_possible = 0
        
        for score in scores:
            question = Question.query.get(score.question_id)
            exam = Exam.query.get(score.exam_id)
            print(f"Exam: {exam.name}, Question: {question.text[:30]}..., Score: {float(score.score)}/{float(question.max_score)}")
            total_score += float(score.score)
            total_possible += float(question.max_score)
        
        # Calculate percentage
        if total_possible > 0:
            percentage = (total_score / total_possible) * 100
            print(f"\nTotal Score: {total_score}/{total_possible}")
            print(f"Percentage: {percentage}%")
            
            # Check which achievement level this should fall into
            achievement_levels = AchievementLevel.query.filter_by(course_id=3).order_by(AchievementLevel.min_score.desc()).all()
            
            print("\nAchievement Levels Available:")
            for level in achievement_levels:
                print(f"{level.name}: {float(level.min_score)}-{float(level.max_score)} ({level.color})")
                
            print("\nChecking which level the score belongs to...")
            found = False
            for level in achievement_levels:
                min_score = float(level.min_score)
                max_score = float(level.max_score)
                if min_score <= percentage <= max_score:
                    print(f"Score {percentage}% belongs to level: {level.name} ({min_score}-{max_score})")
                    found = True
                    break
            
            if not found:
                print(f"Score {percentage}% does not match any achievement level!")
                # Try with rounded score
                rounded_score = round(percentage, 2)
                print(f"Checking with rounded score {rounded_score}%...")
                for level in achievement_levels:
                    min_score = float(level.min_score)
                    max_score = float(level.max_score)
                    if min_score <= rounded_score <= max_score:
                        print(f"Rounded score {rounded_score}% belongs to level: {level.name} ({min_score}-{max_score})")
                        break
    else:
        print("Student not found.") 