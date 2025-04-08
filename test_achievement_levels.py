from app import create_app
from models import AchievementLevel
from routes.calculation_routes import get_achievement_level

app = create_app()

def test_achievement_levels():
    """Test the achievement level categorization for boundary cases"""
    with app.app_context():
        # Get achievement levels for course ID 3
        achievement_levels = AchievementLevel.query.filter_by(course_id=3).order_by(AchievementLevel.min_score.desc()).all()
        
        # Test values to check
        test_scores = [
            49.99, 50.0, 50.01,         # Boundary between Failure and Need Improvements
            59.98, 59.99, 60.0, 60.01,  # Boundary between Need Improvements and Good
            69.98, 69.99, 70.0, 70.01,  # Boundary between Good and Better
            89.98, 89.99, 90.0, 90.01   # Boundary between Better and Excellent
        ]
        
        print("Achievement Levels:")
        for level in achievement_levels:
            print(f"  {level.name}: {float(level.min_score)}-{float(level.max_score)}")
        print()
        
        print("Testing boundary values:")
        print(f"{'Score':<8} | {'Achievement Level':<20}")
        print("-" * 35)
        
        for score in test_scores:
            level = get_achievement_level(score, achievement_levels)
            print(f"{score:<8} | {level['name']:<20}")
        
        # Test the specific problem case of 60.0
        print("\nDetailed test for 60.0:")
        result = get_achievement_level(60.0, achievement_levels)
        print(f"60.0 categorized as: {result['name']} (color: {result['color']})")
        
        # Verify if 60.0 is correctly categorized as "Good"
        should_be_good = result['name'] == "Good"
        print(f"Is 60.0 correctly categorized as 'Good'? {'Yes' if should_be_good else 'No - PROBLEM!'}")
        
        # Find the Good level to verify the range
        good_level = next((level for level in achievement_levels if level.name == "Good"), None)
        if good_level:
            print(f"Good level range: {float(good_level.min_score)}-{float(good_level.max_score)}")

if __name__ == "__main__":
    test_achievement_levels() 