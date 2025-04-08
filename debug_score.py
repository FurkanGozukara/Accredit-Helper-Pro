from app import create_app
from models import AchievementLevel, Student
from decimal import Decimal
import math

app = create_app()

# Python code from get_achievement_level function in routes/calculation_routes.py
def get_achievement_level_py(score, achievement_levels):
    """Get the achievement level for a given score - Python version"""
    # Round to 2 decimal places (0.01 precision) to ensure proper categorization
    rounded_score = round(float(score), 2)
    for level in achievement_levels:
        if level.min_score <= rounded_score <= level.max_score:
            return {
                'name': level.name,
                'color': level.color
            }
    return {
        'name': 'Not Categorized',
        'color': 'secondary'
    }

# JavaScript equivalent from templates/calculation/results.html
def get_achievement_level_js(percentage, achievement_levels):
    """Get the achievement level for a given score - JavaScript version"""
    # Round to 2 decimal places (0.01 precision) to ensure proper categorization
    percentage = round(float(percentage) * 100) / 100
    
    for level in achievement_levels:
        min_score = float(level.min_score)
        max_score = float(level.max_score)
        if percentage >= min_score and percentage <= max_score:
            return {
                'name': level.name,
                'color': level.color
            }
    
    return {
        'name': 'N/A', 
        'color': 'secondary'
    }

# Test scores to try
test_scores = [
    59.98, 59.99, 60.0, 60.00, 60.01, 60.1,
    69.98, 69.99, 70.0, 70.00, 70.01, 70.1
]

def test_score_precision():
    with app.app_context():
        # Get achievement levels for course ID 3
        achievement_levels = AchievementLevel.query.filter_by(course_id=3).all()
        
        print("Achievement Levels in database:")
        for level in achievement_levels:
            print(f"  {level.name}: {float(level.min_score)}-{float(level.max_score)} ({level.color})")
            print(f"    min_score type: {type(level.min_score)}, value: {level.min_score}")
            print(f"    max_score type: {type(level.max_score)}, value: {level.max_score}")
        
        print("\nTesting various scores:")
        print(f"{'Score':<10} | {'Python Method':<20} | {'JavaScript Method':<20}")
        print("-" * 60)
        
        for score in test_scores:
            py_result = get_achievement_level_py(score, achievement_levels)
            js_result = get_achievement_level_js(score, achievement_levels)
            
            # Show the exact math calculations being done for score 60.0
            if score == 60.0:
                print("\nDetailed calculations for score 60.0:")
                for level in achievement_levels:
                    min_score = float(level.min_score)
                    max_score = float(level.max_score)
                    print(f"Comparing with {level.name}: {min_score} <= 60.0 <= {max_score}")
                    print(f"  min comparison: {min_score} <= 60.0 = {min_score <= 60.0}")
                    print(f"  max comparison: 60.0 <= {max_score} = {60.0 <= max_score}")
                    print(f"  combined: {min_score <= 60.0 and 60.0 <= max_score}")
                print()
            
            print(f"{score:<10} | {py_result['name']:<20} | {js_result['name']:<20}")
        
        # Try to find the student with score exactly 60.0
        print("\nLooking for student with score 60.0 in the database:")
        from routes.calculation_routes import calculate_single_course_results
        
        # Get course calculation results
        results = calculate_single_course_results(3)
        
        # Check student scores
        for student_id, student_data in results.get('student_results', {}).items():
            overall_score = student_data.get('weighted_score', 0)
            if 59.9 <= float(overall_score) <= 60.1:
                student = Student.query.get(student_id)
                py_result = get_achievement_level_py(overall_score, achievement_levels)
                js_result = get_achievement_level_js(overall_score, achievement_levels)
                print(f"Student {student.first_name} {student.last_name}: Score {float(overall_score)}")
                print(f"  Python result: {py_result['name']}")
                print(f"  JavaScript result: {js_result['name']}")
                print(f"  Score type: {type(overall_score)}")
                print(f"  Decimal representation: {overall_score}")
                print(f"  Float representation: {float(overall_score)}")
                print(f"  Repr: {repr(overall_score)}")
                print(f"  Rounded 2 decimals: {round(float(overall_score), 2)}")

if __name__ == "__main__":
    test_score_precision() 