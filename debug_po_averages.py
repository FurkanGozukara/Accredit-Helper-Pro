#!/usr/bin/env python3
"""
Debug script to analyze Program Outcome average calculation issues
This script examines individual course scores to identify why some PO averages exceed 100%
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Course, ProgramOutcome, CourseSettings
from routes.calculation_routes import calculate_course_results_from_bulk_data_v2_optimized, bulk_load_course_data
from decimal import Decimal
import json

# Create app instance
app = create_app()

def debug_po_averages():
    """Debug the program outcome average calculation"""
    with app.app_context():
        print("=== DEBUG: Program Outcome Average Calculation ===\n")
        
        print("1. Loading all courses and program outcomes...")
        courses = Course.query.all()
        program_outcomes = ProgramOutcome.query.all()
        
        print(f"Found {len(courses)} courses and {len(program_outcomes)} program outcomes\n")
        
        # Load bulk data
        course_ids = [course.id for course in courses]
        display_method = 'absolute'
        bulk_data = bulk_load_course_data(course_ids, display_method)
        
        # Track scores for each program outcome
        po_data = {}
        for po in program_outcomes:
            po_data[po.code] = {
                'id': po.id,
                'description': po.description,
                'course_scores': [],
                'problematic_courses': []
            }
        
        print("2. Calculating individual course scores...")
        valid_courses = 0
        
        for course in courses:
            # Check if course is excluded
            is_excluded = course.settings and course.settings.excluded
            if is_excluded:
                print(f"   EXCLUDED: {course.code} - {course.name}")
                continue
            
            # Skip courses with no outcomes or exams
            if not hasattr(course, 'course_outcomes') or not course.course_outcomes:
                continue
            if not hasattr(course, 'exams') or not course.exams:
                continue
            
            # Calculate course results
            result = calculate_course_results_from_bulk_data_v2_optimized(course.id, bulk_data, display_method)
            
            if not result['is_valid_for_aggregation']:
                continue
                
            valid_courses += 1
            course_weight = Decimal(str(course.course_weight))
            
            print(f"   {course.code} (Weight: {course_weight}): ", end="")
            course_po_scores = []
            
            for po in program_outcomes:
                po_score = result['program_outcome_scores'].get(po.id)
                contributes = po.id in result['contributing_po_ids']
                
                if contributes and po_score is not None:
                    po_data[po.code]['course_scores'].append((po_score, course_weight, course.code))
                    course_po_scores.append(f"{po.code}:{po_score:.2f}%")
                    
                    # Flag problematic scores
                    if po_score > 100:
                        po_data[po.code]['problematic_courses'].append({
                            'code': course.code,
                            'name': course.name,
                            'score': po_score,
                            'weight': course_weight
                        })
            
            if course_po_scores:
                print(", ".join(course_po_scores[:3]) + ("..." if len(course_po_scores) > 3 else ""))
            else:
                print("No contributing PO scores")
        
        print(f"\n3. Found {valid_courses} valid courses contributing to PO averages\n")
        
        print("4. Analyzing Program Outcome Averages:")
        print("="*80)
        
        for po_code, data in po_data.items():
            if not data['course_scores']:
                continue
                
            print(f"\n{po_code}: {data['description']}")
            print("-" * (len(po_code) + len(data['description']) + 2))
            
            # Calculate weighted average
            weighted_scores = data['course_scores']
            sum_weighted_scores = sum(Decimal(str(score)) * weight for score, weight, _ in weighted_scores)
            sum_weights = sum(weight for _, weight, _ in weighted_scores)
            
            if sum_weights > 0:
                weighted_avg = sum_weighted_scores / sum_weights
                print(f"Weighted Average: {weighted_avg:.2f}%")
            else:
                weighted_avg = 0
                print(f"Weighted Average: 0.00% (no valid scores)")
            
            # Show contributing courses
            print(f"Contributing courses ({len(weighted_scores)}):")
            for score, weight, course_code in sorted(weighted_scores, key=lambda x: x[0], reverse=True):
                print(f"  {course_code}: {score:.2f}% (weight: {weight})")
            
            # Highlight problematic courses
            if data['problematic_courses']:
                print(f"\n🔴 PROBLEMATIC COURSES (>100%):")
                for course_info in sorted(data['problematic_courses'], key=lambda x: x['score'], reverse=True):
                    print(f"  {course_info['code']}: {course_info['score']:.2f}% (weight: {course_info['weight']})")
                    print(f"     {course_info['name']}")
            
            # Show simple average for comparison
            simple_avg = sum(score for score, _, _ in weighted_scores) / len(weighted_scores)
            print(f"Simple Average (unweighted): {simple_avg:.2f}%")
            
            if weighted_avg > 100:
                print(f"⚠️  WARNING: Average exceeds 100%!")
            
            print()
        
        print("\n5. Summary of Issues:")
        print("="*50)
        
        total_problematic = 0
        for po_code, data in po_data.items():
            if data['problematic_courses']:
                total_problematic += len(data['problematic_courses'])
                print(f"{po_code}: {len(data['problematic_courses'])} courses with scores >100%")
        
        if total_problematic == 0:
            print("✅ No courses found with scores >100%")
        else:
            print(f"\n🔴 Total problematic course-PO combinations: {total_problematic}")
            print("These courses are causing the impossible averages!")

def debug_specific_po(po_code):
    """Debug a specific program outcome in detail"""
    with app.app_context():
        po = ProgramOutcome.query.filter_by(code=po_code).first()
        if not po:
            print(f"Program Outcome {po_code} not found!")
            return
        
        print(f"=== DETAILED DEBUG: {po_code} ===")
        print(f"Description: {po.description}\n")
        
        courses = Course.query.all()
        course_ids = [course.id for course in courses]
        bulk_data = bulk_load_course_data(course_ids, 'absolute')
        
        contributing_courses = []
        
        for course in courses:
            if course.settings and course.settings.excluded:
                continue
            
            result = calculate_course_results_from_bulk_data_v2_optimized(course.id, bulk_data, 'absolute')
            
            if not result['is_valid_for_aggregation']:
                continue
            
            if po.id in result['contributing_po_ids']:
                po_score = result['program_outcome_scores'].get(po.id)
                if po_score is not None:
                    contributing_courses.append({
                        'code': course.code,
                        'name': course.name,
                        'score': po_score,
                        'weight': course.course_weight,
                        'student_count': result['student_count_used']
                    })
        
        # Sort by score descending
        contributing_courses.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"Contributing courses: {len(contributing_courses)}")
        print("-" * 50)
        
        for course_info in contributing_courses:
            print(f"{course_info['code']}: {course_info['score']:.2f}% "
                  f"(weight: {course_info['weight']}, students: {course_info['student_count']})")
            if course_info['score'] > 100:
                print(f"  ⚠️  {course_info['name']} - PROBLEMATIC SCORE")
        
        # Calculate weighted average
        if contributing_courses:
            weighted_sum = sum(Decimal(str(c['score'])) * Decimal(str(c['weight'])) 
                             for c in contributing_courses)
            weight_sum = sum(Decimal(str(c['weight'])) for c in contributing_courses)
            
            weighted_avg = weighted_sum / weight_sum if weight_sum > 0 else 0
            print(f"\nWeighted Average: {weighted_avg:.2f}%")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Debug specific PO
        debug_specific_po(sys.argv[1])
    else:
        # Debug all POs
        debug_po_averages() 