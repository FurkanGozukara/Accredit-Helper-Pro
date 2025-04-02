# ABET Helper Pro

A comprehensive tool for teachers to calculate and track achievement of course outcomes for ABET (Accreditation Board for Engineering and Technology) requirements.

**Official Download**: [Patreon - SE Courses](https://www.patreon.com/c/SECourses)

## Features

- **Course Management**: Add, edit, and delete courses with semesters
- **Exam Management**: Create exams, add questions, and assign weights
- **Outcome Tracking**: Define course outcomes and link them to program outcomes
- **Student Data**: Import student lists in various formats
- **Score Management**: Enter and auto-save student scores for exam questions
- **ABET Calculations**: Automatically calculate course outcome achievements
- **Reporting**: Export results for ABET verification
- **Database Management**: Backup, restore, and merge database files

## Installation

### Prerequisites

- Python 3.8 or higher
- Git

### Installation Methods

#### Option 1: Windows Installer (Recommended)

1. Run the `Windows_Install.bat` file by double-clicking it
2. Wait for the installation to complete
3. Run the application using the provided shortcut or by running `python app.py` in the command prompt

#### Option 2: Manual Installation

1. Clone the repository or download the source code
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`

## Running the Application

### Using the PowerShell Script (Recommended)

1. Right-click on `run_app.ps1` and select "Run with PowerShell" or
2. Open PowerShell and run: `powershell -ExecutionPolicy Bypass -File run_app.ps1`
3. Access the application in your browser at: `http://localhost:5000`

### Alternative Method

1. Activate the virtual environment (if not already activated)
2. Run `python app.py`
3. Access the application in your browser at: `http://localhost:5000`

## Usage

### First Run

On first launch, the application will:
- Check if a database exists and create one if needed
- Initialize default program outcomes

### Basic Workflow

1. **Create a Course**
   - Click "Add Course" on the main page
   - Enter course code, name, and semester

2. **Define Course Outcomes**
   - In the course detail page, go to the "Course Outcomes" tab
   - Click "Add Course Outcome"
   - Associate each course outcome with program outcomes

3. **Add Exams**
   - In the course detail page, go to the "Exams" tab
   - Click "Add Exam"
   - Set exam weights by clicking "Manage Weights"

4. **Add Questions to Exams**
   - Click on an exam to view its details
   - Add questions and associate them with course outcomes
   - Set scores for each question

5. **Import Students**
   - In the course detail page, go to the "Students" tab
   - Click "Import Students"
   - Paste or upload a student list in one of the supported formats

6. **Enter Scores**
   - Click on the "Enter Scores" button for an exam
   - Enter student scores for each question

7. **View ABET Results**
   - Click "View ABET Results" on the course detail page
   - See calculated achievements for each course and program outcome
   - Export results if needed

## Data Backup and Management

The application offers several utilities:

- **Backup Database**: Create a backup of your database
- **Restore Database**: Restore from a previous backup
- **Merge Databases**: Combine data from multiple database files

## Supported Student Import Formats

The system can import student lists in the following formats:

```
11220030102  Name1  Surname
11220030126  Name1 Name2  Surname
```

```
11220030102;Name1;Surname
11220030126;Name1 Name2;Surname
```

```
11220030102	Name1	Surname
11220030126	Name1 Name2	Surname
```

## Troubleshooting

- **Application won't start**: Ensure Python is installed correctly and added to PATH
- **Database errors**: Check file permissions in the application directory
- **Import issues**: Verify that student data matches one of the supported formats

## License

This software is provided for educational purposes only. Use at your own risk. 