"""
Migration script to add the AchievementLevel table to the database.
"""

from app import db
from models import AchievementLevel, Course, Log
from datetime import datetime

def upgrade():
    """Add the achievement_level table to the database schema"""
    # Define default achievement levels for existing courses
    default_levels = [
        {"name": "Excellent", "min_score": 90, "max_score": 100, "color": "success"},
        {"name": "Better", "min_score": 70, "max_score": 89, "color": "info"},
        {"name": "Good", "min_score": 60, "max_score": 69, "color": "primary"},
        {"name": "Need Improvements", "min_score": 50, "max_score": 59, "color": "warning"},
        {"name": "Failure", "min_score": 1, "max_score": 49, "color": "danger"}
    ]
    
    # Create the table
    try:
        db.engine.execute("""
        CREATE TABLE achievement_level (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            name VARCHAR(50) NOT NULL,
            min_score NUMERIC(10, 2) NOT NULL,
            max_score NUMERIC(10, 2) NOT NULL,
            color VARCHAR(20) NOT NULL DEFAULT 'primary',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES course (id) ON DELETE CASCADE
        );
        CREATE INDEX idx_achievement_level_course ON achievement_level (course_id);
        """)
        
        # Add default levels for each existing course
        courses = Course.query.all()
        for course in courses:
            for level_data in default_levels:
                level = AchievementLevel(
                    course_id=course.id,
                    name=level_data["name"],
                    min_score=level_data["min_score"],
                    max_score=level_data["max_score"],
                    color=level_data["color"]
                )
                db.session.add(level)
        
        # Log the migration
        log = Log(action="DB_MIGRATION", description="Added achievement level table and default levels")
        db.session.add(log)
        db.session.commit()
        
        print("✅ Successfully added achievement_level table and default levels for existing courses.")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error adding achievement_level table: {str(e)}")
        return False

def downgrade():
    """Remove the achievement_level table from the database schema"""
    try:
        db.engine.execute("DROP TABLE IF EXISTS achievement_level;")
        
        # Log the migration
        log = Log(action="DB_MIGRATION", description="Removed achievement level table")
        db.session.add(log)
        db.session.commit()
        
        print("✅ Successfully removed achievement_level table.")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error removing achievement_level table: {str(e)}")
        return False

if __name__ == "__main__":
    print("Running migration: Add achievement_level table")
    upgrade() 