import sqlite3
import json
import argparse
import os
import sys

def export_sqlite_to_json(db_path="instance/accredit_data.db", output_path="Exported_Database.json", course_id=0):
    """
    Export SQLite database to a JSON file.
    
    If course_id is provided and is not 0, export only the records related to that course
    and its relations. Otherwise, export every table of the database.
    
    Args:
        db_path (str): Path to the SQLite database file (default: instance/accredit_data.db)
        output_path (str): Path for the output JSON file (default: Exported_Database.json)
        course_id (int): Specific course id to filter export. If 0, export entire database (default: 0)
    """
    # Get absolute paths
    db_path = os.path.abspath(os.path.expanduser(db_path))
    output_path = os.path.abspath(os.path.expanduser(output_path))
    
    # Validate database file exists
    if not os.path.isfile(db_path):
        print(f"Error: Database file not found at '{db_path}'")
        print("Please check the path and try again.")
        print("Current working directory is:", os.getcwd())
        sys.exit(1)
    
    conn = None
    try:
        # Connect to the database in read-only mode and set row_factory for dict-like access
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        database = {}
        
        if course_id and course_id != 0:
            print(f"Exporting data for course_id = {course_id}")
            # Define the filter conditions for each table that is related to a course.
            # These conditions ensure that only records connected to the given course_id are exported.
            filter_conditions = {
                "course": ("WHERE id = ?", (course_id,)),
                "exam": ("WHERE course_id = ?", (course_id,)),
                "exam_weight": ("WHERE course_id = ?", (course_id,)),
                "course_outcome": ("WHERE course_id = ?", (course_id,)),
                "course_settings": ("WHERE course_id = ?", (course_id,)),
                "achievement_level": ("WHERE course_id = ?", (course_id,)),
                "student": ("WHERE course_id = ?", (course_id,)),
                "question": ("WHERE exam_id IN (SELECT id FROM exam WHERE course_id = ?)", (course_id,)),
                "score": ("WHERE exam_id IN (SELECT id FROM exam WHERE course_id = ?)", (course_id,)),
                "student_exam_attendance": ("WHERE exam_id IN (SELECT id FROM exam WHERE course_id = ?)", (course_id,)),
                "question_course_outcome": (
                    "WHERE question_id IN (SELECT id FROM question WHERE exam_id IN (SELECT id FROM exam WHERE course_id = ?))",
                    (course_id,)
                ),
                "course_outcome_program_outcome": (
                    "WHERE course_outcome_id IN (SELECT id FROM course_outcome WHERE course_id = ?)",
                    (course_id,)
                ),
                "program_outcome": (
                    "WHERE id IN (SELECT program_outcome_id FROM course_outcome_program_outcome WHERE course_outcome_id IN (SELECT id FROM course_outcome WHERE course_id = ?))",
                    (course_id,)
                )
            }
            
            # Only export the tables specified above (i.e. the ones related to course data)
            for table, (condition, params) in filter_conditions.items():
                query = f"SELECT * FROM [{table}] {condition}"
                try:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    table_data = [dict(row) for row in rows]
                    database[table] = table_data
                    print(f"Exported table: {table} ({len(table_data)} rows)")
                except sqlite3.Error as e:
                    print(f"Error exporting table '{table}': {e}")
                    
        else:
            # Export all tables if course_id is 0 or not provided.
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            if not tables:
                print(f"Warning: No tables found in the database '{db_path}'")
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT * FROM [{table}]")
                    rows = cursor.fetchall()
                    table_data = [dict(row) for row in rows]
                    database[table] = table_data
                    print(f"Exported table: {table} ({len(table_data)} rows)")
                except sqlite3.Error as e:
                    print(f"Error exporting table '{table}': {e}")
        
        # Create directory for output file if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Write the dictionary as a JSON file
        with open(output_path, 'w') as json_file:
            json.dump(database, json_file, indent=2)
            
        print(f"Database successfully exported to {output_path}")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Set up command line arguments including the optional course_id parameter.
    parser = argparse.ArgumentParser(
        description='Export SQLite database to JSON format with optional course filtering'
    )
    parser.add_argument(
        '-d', '--database', default="instance/accredit_data.db", 
        help='Path to the SQLite database file (default: instance/accredit_data.db)'
    )
    parser.add_argument(
        '-o', '--output', default="Exported_Database.json", 
        help='Output JSON file path (default: Exported_Database.json)'
    )
    parser.add_argument(
        '--course_id', type=int, default=0, 
        help='If set to a non-zero value, export only records related to that course id and its relations (default: 0 means export all)'
    )
    
    args = parser.parse_args()
    
    export_sqlite_to_json(args.database, args.output, args.course_id)