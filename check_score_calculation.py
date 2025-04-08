from app import create_app
from models import AchievementLevel
from decimal import Decimal

app = create_app()

with app.app_context():
    # Get achievement levels for course ID 3
    achievement_levels = AchievementLevel.query.filter_by(course_id=3).all()
    
    # Exact score to test (60.0%)
    test_score = 60.0
    
    print(f"Testing achievement level calculation for score: {test_score}%")
    print("\nAchievement Levels:")
    for level in achievement_levels:
        min_score = float(level.min_score)
        max_score = float(level.max_score)
        print(f"Level: {level.name}, Range: {min_score}-{max_score}")
    
    # Test with different precision handling methods
    print("\nTesting with different comparison approaches:")
    
    # 1. Direct floating point comparison
    print("\n1. Direct floating point comparison:")
    found = False
    for level in achievement_levels:
        min_score = float(level.min_score)
        max_score = float(level.max_score)
        if min_score <= test_score <= max_score:
            print(f"MATCH: {test_score}% belongs to level: {level.name} ({min_score}-{max_score})")
            found = True
            break
    if not found:
        print(f"NO MATCH: {test_score}% does not match any level")
    
    # 2. Using Decimal for comparison
    print("\n2. Using Decimal for comparison:")
    found = False
    decimal_score = Decimal(str(test_score))
    for level in achievement_levels:
        if level.min_score <= decimal_score <= level.max_score:
            print(f"MATCH: {decimal_score}% belongs to level: {level.name} ({level.min_score}-{level.max_score})")
            found = True
            break
    if not found:
        print(f"NO MATCH: {decimal_score}% does not match any level")
    
    # 3. Using rounding
    print("\n3. Using rounding to 2 decimal places:")
    found = False
    rounded_score = round(test_score, 2)
    for level in achievement_levels:
        min_score = float(level.min_score)
        max_score = float(level.max_score)
        if min_score <= rounded_score <= max_score:
            print(f"MATCH: {rounded_score}% belongs to level: {level.name} ({min_score}-{max_score})")
            found = True
            break
    if not found:
        print(f"NO MATCH: {rounded_score}% does not match any level")
    
    # 4. Using string formatting for precision
    print("\n4. Using string formatting for precision:")
    found = False
    formatted_score = float(f"{test_score:.2f}")
    for level in achievement_levels:
        min_score = float(f"{float(level.min_score):.2f}")
        max_score = float(f"{float(level.max_score):.2f}")
        if min_score <= formatted_score <= max_score:
            print(f"MATCH: {formatted_score}% belongs to level: {level.name} ({min_score}-{max_score})")
            found = True
            break
    if not found:
        print(f"NO MATCH: {formatted_score}% does not match any level")
    
    # Edge case testing with slightly modified values
    print("\nTesting edge cases:")
    edge_values = [59.99, 60.0, 60.01, 69.99, 70.0, 70.01]
    
    for value in edge_values:
        print(f"\nTesting value: {value}")
        found = False
        for level in achievement_levels:
            min_score = float(level.min_score)
            max_score = float(level.max_score)
            if min_score <= value <= max_score:
                print(f"  {value}% belongs to level: {level.name} ({min_score}-{max_score})")
                found = True
                break
        if not found:
            print(f"  {value}% does not match any level") 