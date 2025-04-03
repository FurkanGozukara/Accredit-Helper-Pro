import sqlite3
import json
import argparse
import os
import sys

def export_sqlite_to_json(db_path="instance/accredit_data.db", output_path="Exported_Database.json"):
    """
    Export SQLite database to a JSON file
    
    Args:
        db_path (str): Path to the SQLite database file (default: instance/accredit_data.db)
        output_path (str): Path for the output JSON file (default: Exported_Database.json)
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
        # Connect to the database
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)  # Read-only mode
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print(f"Warning: No tables found in the database '{db_path}'")
        
        # Create a dictionary to hold all data
        database = {}
        
        # Export each table
        for table in tables:
            try:
                cursor.execute(f"SELECT * FROM [{table}]")  # Square brackets to handle special characters in table names
                rows = cursor.fetchall()
                
                # Convert rows to list of dictionaries
                table_data = []
                for row in rows:
                    table_data.append({key: row[key] for key in row.keys()})
                
                database[table] = table_data
                print(f"Exported table: {table} ({len(table_data)} rows)")
                
            except sqlite3.Error as e:
                print(f"Error exporting table '{table}': {e}")
        
        # Create directory for output file if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Write to JSON file
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
    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Export SQLite database to JSON format')
    parser.add_argument('-d', '--database', default="instance/accredit_data.db", 
                        help='Path to the SQLite database file (default: instance/accredit_data.db)')
    parser.add_argument('-o', '--output', default="Exported_Database.json", 
                        help='Output JSON file path (default: Exported_Database.json)')
    
    args = parser.parse_args()
    
    # Call the export function
    export_sqlite_to_json(args.database, args.output)