#!/usr/bin/env python3
"""
Test script to verify that chart colors are working correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import GlobalAchievementLevel
from routes.calculation_routes import get_achievement_level

def test_achievement_levels():
    """Test the get_achievement_level function with various scores"""
    with app.app_context():
        # Get achievement levels from database
        achievement_levels = GlobalAchievementLevel.query.order_by(GlobalAchievementLevel.min_score.desc()).all()
        
        if not achievement_levels:
            print("No achievement levels found in database")
            return
        
        # Display achievement levels
        print("Achievement Levels Configuration:")
        print("=" * 50)
        for level in achievement_levels:
            print(f"{level.name}: {level.min_score}% - {level.max_score}% (Color: {level.color})")
        
        print("\nTesting score to color mapping:")
        print("=" * 50)
        
        # Test various scores
        test_scores = [95.5, 85.2, 75.8, 65.3, 55.7, 45.1, 30.5, 0.0]
        
        for score in test_scores:
            level = get_achievement_level(score, achievement_levels)
            print(f"Score: {score:5.1f}% -> Level: {level['name']:18} (Color: {level['color']})")
        
        print("\nChart color mapping (RGBA):")
        print("=" * 50)
        
        color_map = {
            'primary': 'rgba(13, 110, 253, 0.7)',    # Blue
            'secondary': 'rgba(108, 117, 125, 0.7)', # Gray
            'success': 'rgba(25, 135, 84, 0.7)',     # Green
            'danger': 'rgba(220, 53, 69, 0.7)',      # Red
            'warning': 'rgba(255, 193, 7, 0.7)',     # Yellow
            'info': 'rgba(13, 202, 240, 0.7)',       # Cyan
            'dark': 'rgba(33, 37, 41, 0.7)',         # Dark gray
            'light': 'rgba(248, 249, 250, 0.7)'      # Light gray/white
        }
        
        for score in test_scores:
            level = get_achievement_level(score, achievement_levels)
            rgba_color = color_map.get(level['color'], 'rgba(108, 117, 125, 0.7)')
            print(f"Score: {score:5.1f}% -> {level['name']:18} -> {rgba_color}")

if __name__ == '__main__':
    test_achievement_levels() 