from app import create_app
from models import AchievementLevel, Student
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math

app = create_app()

# Updated Python code from get_achievement_level function in routes/calculation_routes.py
def get_achievement_level_py(score, achievement_levels):
    """Get the achievement level for a given score - Python version with precise decimal handling"""
    try:
        # Ensure score is a Decimal for precision
        if not isinstance(score, Decimal):
            score_decimal = Decimal(str(score))
        else:
            score_decimal = score
            
        # Round to 2 decimal places using ROUND_HALF_UP
        rounded_score = score_decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
    except (InvalidOperation, TypeError, ValueError):
        return {'name': 'Invalid Score', 'color': 'secondary'}
    
    # Sort levels by min_score descending
    try:
        sorted_levels = sorted(achievement_levels, key=lambda x: Decimal(str(x.min_score)), reverse=True)
    except (InvalidOperation, TypeError, ValueError):
        return {'name': 'Config Error', 'color': 'danger'}
    
    for level in sorted_levels:
        try:
            min_score = Decimal(str(level.min_score))
            max_score = Decimal(str(level.max_score))
            
            # Check if score is within the inclusive range
            if rounded_score >= min_score and rounded_score <= max_score:
                return {
                    'name': level.name,
                    'color': level.color
                }
        except (InvalidOperation, TypeError, ValueError):
            continue
            
    return {'name': 'Not Categorized', 'color': 'secondary'}

# JavaScript equivalent from templates/calculation/results.html
def get_achievement_level_js(percentage, achievement_levels):
    """Get the achievement level for a given score - JavaScript equivalent with precise handling"""
    # Convert to float for JavaScript-like behavior
    score = float(percentage)
    
    # Round to 2 decimal places as JavaScript would
    rounded_score = round(score * 100) / 100
    
    # Sort levels by min_score descending
    sorted_levels = sorted(achievement_levels, key=lambda x: float(x.min_score), reverse=True)
    
    for level in sorted_levels:
        min_score = float(level.min_score)
        max_score = float(level.max_score)
        
        # Check if score is within the inclusive range
        if rounded_score >= min_score and rounded_score <= max_score:
            return {
                'name': level.name,
                'color': level.color
            }
    
    return {'name': 'Not Categorized', 'color': 'secondary'}

# Test script
with app.app_context():
    # Get achievement levels for testing
    levels = AchievementLevel.query.filter_by(course_id=3).order_by(AchievementLevel.min_score.desc()).all()
    
    if not levels:
        print("No achievement levels found for testing.")
        exit(1)
        
    # Print actual level definitions from DB
    print("Achievement Level Definitions:")
    for level in levels:
        min_score = Decimal(str(level.min_score))
        max_score = Decimal(str(level.max_score))
        print(f"  {level.name}: {min_score}-{max_score} ({level.color})")
    
    # Test cases - focus on boundaries
    test_cases = [
        "59.99",   # Just below Good
        "59.995",  # Should round to 60.00 and be Good
        "60.00",   # Exact boundary - should be Good
        "60.01",   # Just above boundary - should be Good
        "69.99",   # Upper boundary of Good - should be Good
        "70.00"    # Should be Better
    ]
    
    print("\nTesting boundary cases with Python function:")
    for test in test_cases:
        score = Decimal(test)
        result = get_achievement_level_py(score, levels)
        print(f"Score {test} -> {result['name']} (Python decimal version)")
        
    print("\nTesting boundary cases with JavaScript equivalent:")
    for test in test_cases:
        score = float(test)
        result = get_achievement_level_js(score, levels)
        print(f"Score {test} -> {result['name']} (JavaScript simulation)")
        
    # Test with legacy float conversion to see problem
    print("\nTesting with legacy float conversion (shows issues):")
    for test in test_cases:
        score = float(test) 
        # The problematic way (float conversion)
        if 60.0 <= score <= 69.99:
            print(f"Score {test} -> Good (direct float comparison)")
        else:
            print(f"Score {test} -> Not Good (direct float comparison)")
            # Show binary representation to see why
            print(f"  Binary representation: {score.hex()}")
            
    # Test specific score that might be problematic
    problem_score = "60.00"
    print(f"\nDetailed analysis of problematic score: {problem_score}")
    
    # As float
    float_score = float(problem_score)
    print(f"As float: {float_score}")
    print(f"Float hex: {float_score.hex()}")
    
    # As Decimal
    decimal_score = Decimal(problem_score)
    print(f"As Decimal: {decimal_score}")
    
    # Python decimal comparison
    for level in sorted(levels, key=lambda x: Decimal(str(x.min_score)), reverse=True):
        min_score = Decimal(str(level.min_score))
        max_score = Decimal(str(level.max_score))
        print(f"Checking level {level.name}: {min_score} <= {decimal_score} <= {max_score}")
        print(f"  Min check: {decimal_score >= min_score}")
        print(f"  Max check: {decimal_score <= max_score}")
        print(f"  Combined: {decimal_score >= min_score and decimal_score <= max_score}")

if __name__ == "__main__":
    pass  # No need to call any function as the main code is already in the module level 