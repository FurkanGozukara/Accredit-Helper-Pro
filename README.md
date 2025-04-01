# ABET Helper Pro

A comprehensive tool for teachers to calculate and track achievement of course outcomes for ABET (Accreditation Board for Engineering and Technology) requirements.
Please purchase from here to use : https://www.patreon.com/c/SECourses


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

The application comes with a Windows installer to set up a virtual environment. The installer will create a Python virtual environment and install all necessary dependencies.

### Prerequisites

- Python 3.8 or higher
- Git

### Installation Steps

1. Run the `Windows_Install.bat` file by double-clicking it
2. Wait for the installation to complete
3. Run the application using the provided shortcut or by running `python app.py` in the command prompt

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

## License

This software is provided for educational purposes only. Use at your own risk. 