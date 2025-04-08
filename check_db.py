import sqlite3

# Connect to the database
conn = sqlite3.connect('instance/accredit_data.db')
cursor = conn.cursor()

# Check exam count
cursor.execute('SELECT COUNT(*) FROM exam')
print(f'Exam count: {cursor.fetchone()[0]}')

# Check course count
cursor.execute('SELECT COUNT(*) FROM course')
print(f'Course count: {cursor.fetchone()[0]}')

# Get all courses
cursor.execute('SELECT id, code, name FROM course')
courses = cursor.fetchall()
print("\nAll courses:")
for course in courses:
    print(f"Course ID: {course[0]}, Code: {course[1]}, Name: {course[2]}")
    
    # Get exams for this course
    cursor.execute('SELECT id, name, max_score FROM exam WHERE course_id = ?', (course[0],))
    exams = cursor.fetchall()
    
    if exams:
        print(f"  Exams for course {course[1]}:")
        for exam in exams:
            print(f"    Exam ID: {exam[0]}, Name: {exam[1]}, Max Score: {exam[2]}")
    else:
        print(f"  No exams found for course {course[1]}")
    print()

# Close the connection
conn.close() 