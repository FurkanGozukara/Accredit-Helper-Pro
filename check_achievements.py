from app import create_app
from models import AchievementLevel, db
from decimal import Decimal

app = create_app()

def fix_boundaries():
    with app.app_context():
        # Get achievement levels for course ID 3
        achievement_levels = AchievementLevel.query.filter_by(course_id=3).order_by(AchievementLevel.min_score.desc()).all()
        
        print("Current achievement levels:")
        for level in achievement_levels:
            print(f"{level.name}: {float(level.min_score)}-{float(level.max_score)} ({level.color})")
        
        # Fix the boundaries by slightly adjusting them to ensure no gaps
        for i, level in enumerate(achievement_levels):
            if i < len(achievement_levels) - 1:
                next_level = achievement_levels[i+1]
                # If this level's min is exactly the previous level's max, adjust slightly
                if float(next_level.max_score) == float(level.min_score):
                    print(f"Adjusting boundary between {next_level.name} and {level.name}")
                    # Make the adjustment by 0.01
                    next_level.max_score = float(level.min_score) - 0.01
                    print(f"Changed {next_level.name} max_score to {float(next_level.max_score)}")
        
        # Commit changes
        db.session.commit()
        
        # Verify the changes
        print("\nUpdated achievement levels:")
        achievement_levels = AchievementLevel.query.filter_by(course_id=3).order_by(AchievementLevel.min_score.desc()).all()
        for level in achievement_levels:
            print(f"{level.name}: {float(level.min_score)}-{float(level.max_score)} ({level.color})")

if __name__ == "__main__":
    fix_boundaries() 