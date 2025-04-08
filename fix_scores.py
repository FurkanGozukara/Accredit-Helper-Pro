from app import create_app
from models import Student, AchievementLevel, db
from routes.calculation_routes import get_achievement_level, calculate_single_course_results

app = create_app()

def fix_pamela_craig_score():
    with app.app_context():
        # Get Pamela Craig from course id 3
        student = Student.query.filter_by(course_id=3, first_name="Pamela", last_name="Craig").first()
        if not student:
            print("Student Pamela Craig not found in course 3.")
            return
        
        print(f"Found student: {student.first_name} {student.last_name} (ID: {student.id})")
        
        # Get the achievement levels for course 3
        achievement_levels = AchievementLevel.query.filter_by(course_id=3).order_by(AchievementLevel.min_score.desc()).all()
        
        print("\nAchievement levels:")
        for level in achievement_levels:
            print(f"  {level.name}: {float(level.min_score)}-{float(level.max_score)}")
        
        # Get Pamela's score data from the calculation
        results = calculate_single_course_results(3)
        
        if student.id not in results.get('student_results', {}):
            print(f"No calculation results found for student ID {student.id}")
            return
        
        student_data = results['student_results'][student.id]
        overall_score = student_data.get('weighted_score', 0)
        
        print(f"\nCurrent score: {float(overall_score)}")
        print(f"Score type: {type(overall_score)}")
        
        # Test categorization with the updated get_achievement_level function
        level = get_achievement_level(overall_score, achievement_levels)
        print(f"Categorized as: {level['name']} (color: {level['color']})")
        
        # If the score is 60.0, we need to ensure it's categorized as "Good"
        if abs(float(overall_score) - 60.0) < 0.01:
            print("\nScore is 60.0, should be categorized as 'Good'")
            
            # Directly test the function that does categorization
            for level in achievement_levels:
                min_score = float(level.min_score)
                max_score = float(level.max_score)
                test_score = float(overall_score)
                
                print(f"Testing level {level.name}: {min_score} <= {test_score} <= {max_score}")
                print(f"  {min_score} <= {test_score} = {min_score <= test_score}")
                print(f"  {test_score} <= {max_score} = {test_score <= max_score}")
                print(f"  Combined: {min_score <= test_score and test_score <= max_score}")
                print(f"  {test_score} == {min_score} = {test_score == min_score}")
        
        print("\nRestarting the server is needed to apply the changes to the get_achievement_level function.")
        print("Make sure to view the page again after restarting the server.")

if __name__ == "__main__":
    fix_pamela_craig_score() 