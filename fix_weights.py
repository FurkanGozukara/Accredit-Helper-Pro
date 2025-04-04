from app import create_app
from models import db, ExamWeight, Exam, Course
from decimal import Decimal

def fix_exam_weights():
    app = create_app()
    with app.app_context():
        # Get course ID 3
        course_id = 3
        course = Course.query.get(course_id)
        
        if not course:
            print(f"Course ID {course_id} not found.")
            return
            
        print(f"Fixing weights for course: {course.code} - {course.name}")
        
        # Get all exams for this course
        exams = Exam.query.filter_by(course_id=course_id, is_makeup=False).all()
        if not exams:
            print("No exams found for this course.")
            return
            
        print(f"Found {len(exams)} exams")
        
        # Get existing weights
        weights = ExamWeight.query.filter_by(course_id=course_id).all()
        
        print(f"Found {len(weights)} existing weight records")
        print("Current weights:")
        total_weight = Decimal('0')
        weights_by_exam = {}
        
        for weight in weights:
            exam = Exam.query.get(weight.exam_id)
            exam_name = exam.name if exam else f"Unknown Exam ID {weight.exam_id}"
            print(f"  - {exam_name}: {weight.weight}")
            total_weight += Decimal(str(weight.weight))
            weights_by_exam[weight.exam_id] = weight
            
        print(f"Total current weight: {total_weight}")
        
        # Check if weights are properly set and total 100%
        if abs(total_weight - Decimal('1.0')) <= Decimal('0.01'):
            print("Weights already seem to total 100% (as decimal 1.0). No action needed.")
            return
        
        # Check if values are in percentage form (0-100)
        if total_weight > Decimal('1.5'):  # Likely using percentage format (0-100)
            print("Weights appear to be in percentage format (0-100) instead of decimal (0-1)")
            print("Converting weights to decimal format...")
            
            for weight in weights:
                weight.weight = Decimal(str(weight.weight)) / Decimal('100')
                print(f"  - Converting {weight.exam_id}: {weight.weight * 100}% -> {weight.weight}")
            
            db.session.commit()
            print("Weights converted successfully!")
            return
        
        # If we get here, the weights are likely just not totaling 1.0
        # Let's fix them by distributing them proportionally
        if total_weight > Decimal('0'):
            print("Normalizing weights to total 1.0...")
            
            for weight in weights:
                old_weight = weight.weight
                weight.weight = weight.weight / total_weight
                print(f"  - Adjusting {weight.exam_id}: {old_weight} -> {weight.weight}")
            
            db.session.commit()
            print("Weights normalized successfully!")
        else:
            # If total weight is 0, distribute evenly
            print("Total weight is 0. Distributing weights evenly...")
            weight_value = Decimal('1.0') / Decimal(str(len(exams)))
            
            for exam in exams:
                if exam.id in weights_by_exam:
                    weights_by_exam[exam.id].weight = weight_value
                    print(f"  - Setting {exam.id}: {weight_value}")
                else:
                    new_weight = ExamWeight(exam_id=exam.id, course_id=course_id, weight=weight_value)
                    db.session.add(new_weight)
                    print(f"  - Creating {exam.id}: {weight_value}")
            
            db.session.commit()
            print("Weights distributed evenly!")

if __name__ == "__main__":
    fix_exam_weights()
    print("Done!") 