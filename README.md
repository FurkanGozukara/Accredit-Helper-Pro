# Accredit Helper Pro

## Overview

Accredit Helper Pro is a comprehensive tool designed to streamline the accreditation process for educational programs, particularly engineering disciplines. This powerful application helps instructors, department chairs, and accreditation coordinators track student achievement of course outcomes and program outcomes with precision and ease.

**Official Download**: [Patreon - SE Courses](https://www.patreon.com/c/SECourses)

## Key Features

### Course Management
- **Flexible Course Creation**: Set up courses with unique codes, names, and semester designations
- **Sorting and Filtering**: Organize courses by code, name, semester, or creation date
- **Search Functionality**: Quickly find specific courses in your database
- **Detailed Course Profiles**: View all associated data in one centralized dashboard

### Outcome Management
- **Program Outcomes (PO)**: Define and customize program-level learning outcomes that align with accreditation standards
- **Course Outcomes (CO)**: Create course-specific learning outcomes with clear, measurable objectives
- **CO-PO Mapping**: Link course outcomes to program outcomes with an intuitive mapping interface
- **Achievement Levels**: Define custom performance categories with color-coding and score ranges

### Exam and Assessment Management
- **Multiple Exam Types**: Create midterms, finals, quizzes, assignments, and projects
- **Flexible Weighting System**: Assign precise weights to different assessment components
- **Makeup Exam Support**: Handle makeup exams with specialized tracking and calculations
- **Final Exam Designation**: Mark specific exams as finals for special handling in calculations
- **Mandatory Exam System**: Flag critical exams as mandatory to exclude non-participating students from outcome calculations

### Question Management
- **Detailed Question Creation**: Add questions with descriptions, maximum scores, and outcome mappings
- **Question-Outcome Alignment**: Link each question to specific course outcomes it assesses
- **Batch Operations**: Add and manage multiple questions efficiently
- **Question Numbering**: Automatic or manual numbering systems

### Student Management
- **Batch Import**: Import student lists from various formats including CSV and plain text
- **Student Records**: Store student IDs, names, and performance data
- **Individual Student Tracking**: Monitor individual student progress across all assessments
- **Student List Management**: Add, edit, or remove students as needed

### Score Tracking
- **Detailed Score Entry**: Record student scores for each question in every exam
- **Auto-Save Functionality**: Save scores in real-time as they're entered
- **Score Visualization**: View score distributions and summaries
- **Data Validation**: Ensure scores fall within acceptable ranges

### Accredit Calculations
- **Automated Achievement Calculations**: Compute achievement levels for course and program outcomes
- **Multiple Calculation Methods**: Choose between absolute and relative achievement calculation models
- **Customizable Success Thresholds**: Set your own thresholds for what constitutes achievement
- **Batch Processing**: Calculate results across multiple courses simultaneously
- **Statistical Analysis**: Generate means, medians, and distributions of achievement metrics

## Recent Updates

### Performance Improvements
- **Optimized All-Courses Analysis**: Significantly reduced calculation time for multi-course analyses through shared core calculation logic
- **Efficient Resource Utilization**: Minimized database queries by calculating each course's results once and reusing them
- **Improved Makeup Exam Handling**: Enhanced consistency in how makeup exam weights are synchronized with their original exams
- **Streamlined Workflow**: Centralized core calculation logic ensures consistency across single-course and all-courses views
- **Consistent Student Exclusion**: Improved handling of student exclusions based on mandatory exam attendance

### Reporting and Exports
- **Excel/CSV Exports**: Export calculation results, student lists, and outcome data
- **Accreditation-Ready Reports**: Generate reports formatted specifically for accreditation submissions
- **Custom Data Filtering**: Export precisely the data you need
- **Visualization Options**: Include charts and graphs in your exports

### Database Management
- **Automated Backups**: Create timestamped backups of your database
- **Backup Descriptions**: Add custom notes to your backups for better organization
- **Restore Functionality**: Easily restore from previous backups
- **Database Merging**: Combine data from multiple database files
- **Pre-Operation Safeguards**: Automatic backups before major operations like merges or restores
- **Export/Import**: Move your data between systems with JSON exports

### Logging and Monitoring
- **Activity Logging**: Track all significant actions within the system
- **Filterable Log Views**: Search logs by date range or action type
- **Log Exports**: Export log data for record-keeping
- **System Monitoring**: Keep track of database growth and performance

### User Interface
- **Responsive Design**: Works on desktops, laptops, and tablets
- **Intuitive Navigation**: Clearly organized menus and breadcrumbs
- **Consistent Layout**: Familiar patterns throughout the application
- **Real-Time Feedback**: Flash messages confirm successful actions
- **Modal Confirmations**: Prevent accidental data deletion
- **Sortable Tables**: Reorder data according to your preferences

## Workflow Guide

### Step 1: Set Up Program Outcomes
1. Navigate to "Program Outcomes" in the main menu
2. Review default outcomes or add custom ones
3. Ensure each outcome has a clear code and description

### Step 2: Create a Course
1. Click "Add Course" on the homepage
2. Enter course code, name, and semester
3. Save to create the course instance

### Step 3: Define Course Outcomes
1. Go to the "Course Outcomes" tab in the course detail page
2. Click "Add Course Outcome"
3. Enter code and description
4. Map each course outcome to relevant program outcomes
5. Repeat for all course outcomes

### Step 4: Create Exams
1. Navigate to the "Exams" tab in the course detail page
2. Click "Add Exam" 
3. Enter exam name, max score, and date
4. Set exam properties (final, mandatory, makeup)
5. Create all necessary exams for the course

### Step 5: Set Exam Weights
1. Click "Manage Weights" in the exams section
2. Assign percentage weights to each exam
3. Ensure weights total 100%

### Step 6: Add Questions to Exams
1. Select an exam to view its details
2. Click "Add Question"
3. Enter question details and maximum score
4. Link each question to relevant course outcomes
5. Repeat for all questions in all exams

### Step 7: Import Students
1. Go to the "Students" tab in the course detail page
2. Click "Import Students"
3. Paste or upload student list in a supported format
4. Confirm student import

### Step 8: Enter Student Scores
1. Navigate to the "Exams" tab
2. Click "Enter Scores" for the relevant exam
3. Enter scores for each student on each question
4. Scores auto-save as they're entered

### Step 9: View Accredit Results
1. Click "View Accredit Results" in the course detail page
2. Review calculated achievements for course and program outcomes
3. Analyze student performance across all measures
4. Export data for accreditation reporting

### Step 10: Back Up Your Data
1. Go to "Utilities" > "Backup Database"
2. Add a description for your backup
3. Create the backup file
4. Download or access later as needed

## Data Management and Security

### Database Backups
- The system automatically creates pre-operation backups before risky operations
- Regular backups can be created through the Utilities menu
- Backups are saved in the `/backups` folder with timestamps
- Custom descriptions can be added to backups for easier identification

### Data Import/Export
- Course data can be exported to JSON format
- Student lists can be imported from various formats
- Calculation results can be exported to Excel/CSV
- Database merging allows combining data from multiple sources

### Security Considerations
- Local database storage ensures your data remains under your control
- File operations include validation to prevent security issues
- Backup files are protected from unauthorized access

## Supported Import Formats

The system can import student lists in the following formats:

```
11220030102  Name1  Surname
11220030126  Name1 Name2  Surname
```

```