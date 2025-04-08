from app import create_app
from models import AchievementLevel, db
from decimal import Decimal, ROUND_HALF_UP  # Import Decimal and ROUND_HALF_UP

app = create_app()

with app.app_context():
    course_id_to_check = 3
    levels = AchievementLevel.query.filter_by(course_id=course_id_to_check).order_by(AchievementLevel.min_score.desc()).all()

    if not levels:
        print(f"No achievement levels found for course ID {course_id_to_check}")
    else:
        print(f"Achievement Levels for Course ID {course_id_to_check}:")
        for level in levels:
            # Ensure we are reading as Decimal
            min_score = Decimal(str(level.min_score))
            max_score = Decimal(str(level.max_score))
            print(f"  - Name: {level.name}")
            print(f"    Min Score (DB Type: {type(level.min_score)}, Value: {level.min_score}, As Decimal: {min_score})")
            print(f"    Max Score (DB Type: {type(level.max_score)}, Value: {level.max_score}, As Decimal: {max_score})")
            print(f"    Color: {level.color}")

            # Explicit check for the 'Good' level boundaries
            if level.name == "Good":
                if min_score != Decimal("60.00"):
                    print(f"    *** WARNING: 'Good' min_score is not exactly 60.00! Found: {min_score}")
                if max_score != Decimal("69.99"):
                    print(f"    *** WARNING: 'Good' max_score is not exactly 69.99! Found: {max_score}")
            if level.name == "Need Improvements":
                 if max_score != Decimal("59.99"):
                    print(f"    *** WARNING: 'Need Improvements' max_score is not exactly 59.99! Found: {max_score}")
        
        # Test case for exactly 60.00%
        test_score = Decimal("60.00")
        print(f"\nTesting score exactly at boundary: {test_score}")
        
        # Sort levels properly for the test
        sorted_levels = sorted(levels, key=lambda x: Decimal(str(x.min_score)), reverse=True)
        
        # Check which level 60.00% belongs to using our improved algorithm
        for level in sorted_levels:
            min_score = Decimal(str(level.min_score))
            max_score = Decimal(str(level.max_score))
            if test_score >= min_score and test_score <= max_score:
                print(f"Score {test_score} belongs to level: {level.name} ({min_score}-{max_score})")
                break
        else:
            print(f"Score {test_score} does not match any level!")
            
        # Test UI formatting (simulating Jinja2 template formatting)
        print("\nTesting UI formatting (with 2 decimal places):")
        test_scores = [59.99, 59.995, 60.0, 60.00, 60.01, 69.99, 70.0]
        for score in test_scores:
            formatted = f"{score:.2f}%"  # Using 2 decimal places
            print(f"  Score {score} -> displayed as {formatted} in UI")
            
            # Check how it would be interpreted
            rounded = Decimal(str(score)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            for level in sorted_levels:
                min_score = Decimal(str(level.min_score))
                max_score = Decimal(str(level.max_score))
                if rounded >= min_score and rounded <= max_score:
                    print(f"    Categorized as: {level.name}")
                    break 