from app import create_app
from models import AchievementLevel

app = create_app()

with app.app_context():
    # Get achievement levels for course ID 3
    levels = AchievementLevel.query.filter_by(course_id=3).order_by(AchievementLevel.min_score.desc()).all()
    
    # Print each level with its range
    for level in levels:
        print(f"{level.name}: {float(level.min_score)}-{float(level.max_score)} ({level.color})") 