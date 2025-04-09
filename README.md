# Accredit Helper Pro

**Accredit Helper Pro** is a comprehensive tool designed for educational institutions to manage course data, track student performance against learning outcomes (POs and COs), and streamline the accreditation assessment process (e.g., ABET, MÜDEK).

## 🛒 Purchase Department License here (all department staff can use): 
https://www.patreon.com/SECourses/shop/accredit-helper-pro-10x-speed-up-your-1440486

## 🏢 Purchase University/Institution-Wide License here (entire university or institution can use): 
https://www.patreon.com/SECourses/shop/accredit-helper-pro-university-wide-1440509

## ♾️ Licenses are lifetime (permanent) and you will receive app updates for life

Click to Go [Table of Contents](#table-of-contents)

## Screenshots of the Accredit Helper Pro

![b0](https://github.com/user-attachments/assets/c9d6dff4-a79e-4892-9958-e08370ee86b0)

![b1](https://github.com/user-attachments/assets/647cdaf1-adca-41a2-afab-145207042643)


---

## Table of Contents

1.  [Overview](#overview-)
2.  [Key Features](#key-features-)
3.  [Installation](#installation-)
4.  [Getting Started: Complete Workflow](#getting-started-complete-workflow-)
    *   [Understanding the Data Hierarchy](#understanding-the-data-hierarchy)
    *   [Step-by-Step Guide](#step-by-step-implementation-guide)
        *   [Step 1: Define Program Outcomes (POs)](#step-1-define-program-outcomes-pos)
        *   [Step 2: Create a Course](#step-2-create-a-course)
        *   [Step 3: Define Course Outcomes (COs)](#step-3-define-course-outcomes-cos)
        *   [Step 4: Add Exams and Set Weights](#step-4-add-exams-and-set-weights)
        *   [Step 5: Add Questions & Link to COs](#step-5-add-questions--link-to-course-outcomes)
        *   [Step 6: Add Students](#step-6-add-students-to-the-course)
        *   [Step 7: Enter Student Scores](#step-7-enter-student-scores)
        *   [Advanced: Mass Association Tool](#advanced-feature-mass-association-tool)
        *   [Step 8: Calculate Results & Generate Reports](#step-8-calculate-results--generate-reports)
        *   [Step 9: Use \\\"All Courses\\\" Analysis](#step-9-use-all-courses-analysis-for-program-wide-assessment)
    *   [Quick Start for Returning Users](#quick-start-for-returning-users)
5.  [Managing Courses](#managing-courses-)
    *   [Creating & Managing Courses](#creating--managing-courses)
    *   [Course Dashboard](#course-dashboard)
    *   [Managing Exam Weights](#managing-exam-weights)
    *   [Course Settings](#course-settings)
    *   [Duplicating a Course](#duplicating-a-course)
    *   [Searching & Exporting Courses](#searching--exporting-courses)
6.  [Managing Outcomes (POs & COs)](#managing-outcomes-pos--cos-)
    *   [Program Outcomes (POs)](#program-outcomes-pos)
    *   [Course Outcomes (COs)](#course-outcomes-cos)
    *   [Outcome Hierarchy](#understanding-the-outcome-hierarchy)
    *   [Outcome Calculation Methods](#outcome-calculation-methods)
7.  [Managing Exams & Questions](#managing-exams--questions-)
    *   [Managing Exams](#managing-exams)
    *   [Mandatory Exams & Makeup Relations](#mandatory-exams--makeup-relations)
    *   [Managing Questions](#managing-questions)
    *   [Batch Question Operations](#batch-question-operations)
    *   [Exporting Exam Data](#exporting-exam-data)
8.  [Managing Students & Scores](#managing-students--scores-)
    *   [Managing Students (Add, Import, Export, Exclude, Batch Delete)](#managing-students)
    *   [Managing Student Attendance](#managing-student-attendance)
    *   [Entering/Editing Scores](#enteringediting-scores)
    *   [Handling Makeup Exam Scores](#handling-make-up-exam-scores)
9.  [Accredit Calculations](#accredit-calculations-)
    *   [Optimized Calculation System](#optimized-calculation-system-)
    *   [Running Calculations & Understanding Results](#running-calculations--understanding-the-results-page)
    *   [Advanced Calculation Features (Makeup, Mandatory, Precision, Debugging)](#advanced-calculation-features)
    *   [Exporting Results](#exporting-results)
    *   [Multi-Course Analysis (\\\"All Courses\\\" View)](#multi-course-analysis-all-courses-view)
10. [Utilities: Data Management & More](#utilities-data-management--more-)
    *   [Remote Access (Cloudflared)](#remote-access-with-cloudflared-)
    *   [API Integration](#api-integration-)
    *   [Backup Database](#backup-database-)
    *   [Restore Database](#restore-database-)
    *   [Import Database](#import-database-)
    *   [Merge Courses](#merge-courses-)
    *   [System Logs](#system-logs-)
    *   [Support & Feedback](#support--feedback-)
11. [Remote Access Guide (Cloudflare Tunnel)](#remote-access-guide-cloudflare-tunnel-)
    *   [About Remote Access](#about-remote-access)
    *   [Installation Guide](#installation-guide)
    *   [Using Remote Access](#using-remote-access)
    *   [Troubleshooting Remote Access](#troubleshooting-remote-access)
12. [Troubleshooting Guide](#troubleshooting-guide-)
    *   [Database & File Issues](#database--file-issues)
    *   [Calculation & Results Issues](#calculation--results-issues)
    *   [Import/Export & Data Transfer Issues](#importexport--data-transfer-issues)
    *   [Performance & Responsiveness Issues](#performance--responsiveness-issues)
    *   [Common Application Issues](#troubleshooting--common-issues)

---

## Overview 🔎

Welcome to **Accredit Helper Pro**, your comprehensive tool for managing course data, tracking student performance against learning outcomes, and streamlining the accreditation assessment process.

> **ℹ️ What is Accreditation?**
> Accreditation is a quality assurance process through which educational institutions demonstrate they meet established standards in providing quality education. This application specifically aids in meeting assessment requirements for accreditation processes (like ABET or MÜDEK) by tracking student achievement of program outcomes.

---

## Key Features ⭐

*   **✅ Program Outcomes (PO):** Define high-level outcomes aligned with accreditation criteria.
*   **✅ Course Outcomes (CO):** Create measurable course-specific outcomes linked to POs.
*   **✅ Exam Management:** Organize assessments with flexible weighting systems.
*   **✅ Question-Outcome Mapping:** Link individual questions to specific learning outcomes.
*   **✅ Student Management:** Import and track individual students across courses.
*   **✅ Score Tracking:** Record and auto-save student performance data via AJAX.
*   **✅ Attendance Tracking:** Record and manage student attendance for exams with automated import/export via AJAX.
*   **✅ Student Exclusion Control:** Manually exclude/include specific students from outcome calculations.
*   **✅ Automated Calculations:** Get precise outcome achievement metrics.
*   **✅ Multiple Calculation Methods:** Choose between absolute (average score) and relative (percent achieving threshold) achievement models.
*   **✅ Custom Achievement Levels:** Define your own performance categories (e.g., Excellent, Good).
*   **✅ Reporting:** Generate accreditation-ready reports and exports (PDF, CSV, Excel).
*   **✅ Data Management:** Backup, restore, merge, and import data seamlessly.
*   **✅ Activity Logging:** Track all significant actions (Add, Edit, Delete, Import, etc.) within the system.
*   **✅ Batch Operations:** Add/manage multiple questions, outcomes, students (including batch deletion), and attendance records efficiently.
*   **✅ Mass Association Tool:** Quickly connect multiple questions to outcomes using simple text syntax.
*   **✅ AJAX-based Interface:** Responsive, real-time updates for score entry and attendance tracking.
*   **✅ Secure Remote Access:** Use Cloudflare Tunnel (`cloudflared`) for accessing the application securely from anywhere.
*   **✅ Advanced Exam Features:** Support for makeup exams, final exam designation, and mandatory exam attendance logic.
*   **✅ Data Visualization:** View interactive charts and graphs for outcome achievements.
*   **✅ Course Duplication:** Quickly set up new courses based on existing templates, copying structure (COs, Exams, Questions, Weights, Settings).
*   **✅ Multi-course Analysis:** Analyze program outcomes across all courses with optimized performance and consistent logic.
*   **✅ Student Score Export:** Export detailed student performance data (grades, outcome achievement).
*   **✅ Detailed Exam Data Exports:** Export comprehensive exam structure, questions, outcome links, and scores for analysis or backup.
*   **✅ API Functionality:** Access data programmatically via REST endpoints (JSON format).
*   **✅ Enhanced Search:** Find specific information across courses (Code, Name, Semester) with dynamic filtering.

### Recent Performance Improvements 🚀

The calculation system has been significantly optimized for:

*   **⚡ Faster Multi-Course Analysis:** Significant speed improvements for program-wide results via centralized calculation and reduced queries.
*   **⚙️ Efficient Resource Usage:** Minimized database queries and optimized data loading for better performance with large datasets.
*   **🔄 Consistent Makeup Exam Handling:** Enhanced synchronization ensures makeup exams correctly inherit weights and scores are used appropriately.
*   **⚖️ Standardized Student Exclusion:** Improved logic consistently handles mandatory exam attendance across calculation methods.
*   **🖱️ Enhanced Attendance Management:** Fast, AJAX-based attendance tracking with bulk import/export capabilities.
*   **☁️ Robust Remote Access:** Improved Cloudflare Tunnel integration for seamless remote usage.

### Who Should Use This Application? 👥

*   Faculty Members
*   Department Chairs
*   Accreditation Coordinators
*   Assessment Committees
*   Program Administrators

### Technical Architecture 🛠️

*   **Backend:** Python Flask framework with SQLAlchemy ORM
*   **Database:** SQLite (portable, file-based)
*   **Frontend:** Bootstrap 5 (responsive design) with AJAX for real-time updates
*   **Security:** Protected file operations, data validation
*   **Remote Access:** Integrated Cloudflare Tunnel support

---

## Installation ⚙️

*(Placeholder - Add your specific installation instructions here)*

1.  **Prerequisites:**
    *   Python 3.8+
    *   `pip` (Python package installer)
2.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/Accredit-Helper-Pro.git
    cd Accredit-Helper-Pro
    ```
3.  **Create and activate a virtual environment:**
    ```bash
    # Windows
    python -m venv venv
    .\\\\venv\\\\Scripts\\\\activate

    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Run the application:**
    ```bash
    python app.py
    ```
6.  Open your web browser and navigate to `http://localhost:5000`.

---

## Getting Started: Complete Workflow 🚀

Follow this comprehensive guide to set up and use Accredit Helper Pro effectively.

### Understanding the Data Hierarchy

Understanding the data organization is crucial:

```mermaid
graph TD
    PO[Program Outcomes (POs) - Program Wide] --> Course[Courses (e.g., CENG301 Fall 2023)]
    Course --> CO[Course Outcomes (COs) - Course Specific]
    Course --> Exam[Exams (Assessments)]
    Course --> Student[Students (Enrolled)]
    CO --> PO
    Exam --> Question[Questions (Assessment Items)]
    Question --> CO
    Student --> Score[Scores (Performance on Questions)]
    Score --> Question
    Score --> Student
```

*   **Program Outcomes (POs):** High-level goals shared across courses.
*   **Courses:** Specific instances (e.g., CENG301 Fall 2023).
*   **Course Outcomes (COs):** Course-specific goals, linked to POs.
*   **Exams:** Assessments (midterms, finals, projects, quizzes).
*   **Questions:** Individual items within exams, linked to COs.
*   **Students:** Enrolled individuals.
*   **Scores:** Student performance on questions.

### Step-by-Step Implementation Guide

#### Step 1: Define Program Outcomes (POs)

POs are the foundation, representing program-level competencies.

1.  Navigate to `Utilities` -> `Program Outcomes`.
2.  Review pre-loaded POs (e.g., MÜDEK-aligned for Turkish engineering programs).
3.  Edit or add POs matching your program's requirements.
4.  Ensure unique codes (e.g., `PO1`) and clear descriptions.

> **✅ Tip:** Align POs with accreditation requirements (e.g., MÜDEK, ABET criteria).

#### Step 2: Create a Course

Each course offering (semester/term) needs its own instance.

1.  From the Homepage, click `Add Course`.
2.  Enter **Course Code** (e.g., `CENG301`).
3.  Enter **Course Name** (e.g., `Software Engineering`).
4.  Specify **Semester** (e.g., `Fall 2023`). Use a consistent format (e.g., \"YYYY Season\") for better sorting.
5.  Click `Save Course`.

> **⚠️ Important:** Create separate instances for each semester (e.g., \"CENG301 Fall 2023\", \"CENG301 Spring 2024\"). This is crucial for accurate tracking over time.

#### Step 3: Define Course Outcomes (COs)

COs are specific, measurable learning objectives linked to POs.

1.  On the Course Detail page, find \"Course Outcomes\" -> `Add Course Outcome`.
2.  Enter **CO Code** (e.g., `CO1`).
3.  Write a clear, measurable **Description**. Use SMART principles (Specific, Measurable, Achievable, Relevant, Time-bound) and start with an action verb (e.g., \"Design...\", \"Analyze...\", \"Implement...\").
4.  **🔥 Critical:** Select the Program Outcome(s) (POs) this CO supports.
5.  Click `Save`. Repeat for all COs (typically 5-10 per course).

> **ℹ️ Example CO-PO Mapping:**
> *   CO1: \"Apply software testing techniques...\" -> maps to PO2, PO3
> *   CO2: \"Communicate technical information...\" -> maps to PO7

> **🔥 Critical:** Every CO *must* link to at least one PO for assessment calculations to work correctly.

#### Step 4: Add Exams and Set Weights

Exams represent all assessed activities (exams, projects, quizzes).

1.  From Course Detail -> \"Exams\" section -> `Add Exam`.
2.  Enter a descriptive **Name** (e.g., `Midterm 1`, `Final Project`).
3.  Set **Max Score** (e.g., `100`). *Note: Individual question max scores are primarily used in calculations.*
4.  Optionally set **Exam Date**.
5.  Check flags if applicable:
    *   `Is Final Exam?`
    *   `Is Mandatory?` (Crucial for student exclusion logic - see below)
    *   `Is Makeup Exam?` (Requires selecting the original exam it replaces)
6.  Save. Repeat for all assessments.

**Setting Exam Weights:**

1.  After adding exams, click `Manage Weights` in the Exams section.
2.  Assign percentage weights (e.g., Midterm 1: 30%, Final: 40%).
3.  **🔥 Important:** Weights must total exactly 100%. If they don't, they will be normalized during calculations, but setting them correctly is best practice.
4.  Click `Save Weights`.

> **⚖️ Note:** Weights determine contribution to grades and outcomes.

**Mandatory Exam Logic:**

*   If one or more exams are marked `Is Mandatory?`.
*   Students who have *zero scores* (or no scores entered) for **ALL** mandatory exams **AND** their corresponding makeup versions (if they exist) will be **excluded** from outcome calculations.
*   This ensures results reflect students who participated in key assessments.
*   If *no* exams are mandatory, only manually excluded students are removed from calculations.

**Managing Makeup Exams:**

1.  Check `Is Makeup Exam?` and select the original exam when creating.
2.  Makeups automatically inherit the weight of the original exam.
3.  Enter scores only for students who took the makeup. Leave blank otherwise.
4.  The system automatically uses the makeup score if available; otherwise, it uses the original score.
5.  Use `Fix Makeup Relations` (Utility available on the `Manage Exams` page accessible from Course Detail -> Exams) if links become inconsistent (e.g., due to naming changes or creation order). This tool automatically tries to re-link makeups to originals based on naming conventions.

#### Step 5: Add Questions & Link to Course Outcomes

Questions are individual assessment items linked to COs.

1.  Go to Course Detail -> Click Exam Name -> Exam Detail page.
2.  Click `Add Question`.
3.  Enter **Question Number** (e.g., `1`, `2a`).
4.  Optionally enter **Question Text** for reference.
5.  Set **Max Score** for this specific question (e.g., `10`, `25`). This score is critical for calculations.
6.  **🔥 Critical:** Select the Course Outcome(s) (COs) this question assesses. A question can assess multiple COs.
7.  Save. Repeat for all questions in all exams.

> **💡 Batch Operations:** Use `Batch Add Questions` or the `Mass Association Tool` (see below) for efficiency when dealing with many questions.

> **🔗 Critical Mapping:** The Question <-> CO link is fundamental. Map carefully.

> **✅ Tip:** For complex assessments like projects or reports, break down the grading rubric into multiple \"questions\", each linked to the specific CO(s) it assesses.

#### Step 6: Add Students to the Course

Enroll students in the course instance.

*   **Manual Entry:** `Add Student` button (for small classes). Enter ID, First Name, Last Name.
*   **Batch Paste (Recommended):**
    1.  Go to Students section -> `Add/Paste Students`.
    2.  Paste list from spreadsheet/text. Supported formats include:
        ```text
        # Format 1: ID<space(s)>Name<space(s)>Surname
        11220030102  Name1  Surname
        11220030126  Name1 Name2  Surname

        # Format 2: ID;Name;Surname
        11220030102;Name1;Surname
        11220030126;Name1 Name2;Surname

        # Format 3: ID<tab>Name<tab>Surname
        11220030102	Name1	Surname
        11220030126	Name1 Name2	Surname
        ```
    3.  Review preview to ensure correct parsing and import.
*   **CSV File Upload:**
    1.  Go to Students section -> `Import Students`.
    2.  Prepare CSV file (e.g., columns: `student_id`, `first_name`, `last_name`). Header row recommended. Use UTF-8 encoding.
    3.  Upload file, map columns if needed, choose import mode (Add new / Add & Update).
    4.  Review preview and import.

**Managing Student Exclusion:**

*   Use the `Exclude/Include` toggle next to a student's name on the Course Detail page (Students list). Excluded students are ignored in calculations.
*   Students might also be auto-excluded based on [Mandatory Exam Logic](#mandatory-exams--makeup-relations).

**Tracking Attendance:**

*   Go to Exam Detail -> `Manage Attendance`. Toggle attendance status per student (saves automatically via AJAX).
*   Bulk actions (All/None) and CSV Import/Export are available. See [Managing Student Attendance](#managing-student-attendance) for details.

> **💾 Student Export:** Use `Export Students` for a CSV list of enrolled students.

#### Step 7: Enter Student Scores

Record performance on each question.

1.  Access score entry grid:
    *   Course Detail -> Students -> `Enter/Edit Scores` (shows all exams for the course).
    *   Exam Detail -> `Enter Scores` (shows only questions for that specific exam).
2.  Grid: Students (rows) x Questions (columns).
3.  Enter scores in the corresponding cells. Scores cannot exceed the Question Max Score (validation applied).
4.  **Scores save automatically (AJAX).** Look for confirmation indicators.

> **⌨️ Efficiency Tip:** Use keyboard navigation for faster entry:
> *   **Tab:** Move to next cell.
> *   **Shift+Tab:** Move to previous cell.
> *   **Arrow Keys:** Navigate between cells.
> *   **Enter:** Save current cell and move down (configurable behavior might vary).

> **⚠️ Makeup Scores:** For makeup exams, enter scores *only* for students who took the makeup. Leave cells blank for students who took the original exam.

#### Advanced Feature: Mass Association Tool

Quickly link multiple questions to outcomes.

1.  Go to Exam Detail -> `Mass Associate Outcomes` button (also available during Batch Add Questions).
2.  Enter associations in the text area using syntax: `q#:oc#:oc#;q#:oc#`
    *   `q#`: Question number (e.g., `q1` for Question 1).
    *   `oc#`: Course Outcome number (e.g., `oc1` for CO1).
    *   Use colon `:` to separate the question number from its outcome(s). Use multiple colons for multiple outcomes per question.
    *   Use semicolon `;` to separate different question associations.
    *   Example: `q1:oc1:oc2;q2:oc3;q3:oc1:oc3:oc4;`
3.  Click `Apply Associations`.

> **✅ Example:** `q1:oc1:oc2;q2:oc3;` maps Q1 to CO1 & CO2, and Q2 to CO3.

> **⚠️ Important:** This tool **replaces** any existing outcome associations for the specified questions. Ensure you include all desired links for a question when using this tool.

#### Step 8: Calculate Results & Generate Reports

Analyze outcome achievement.

1.  Go to Course Detail -> `Calculate Results`.
2.  System processes data using CO-PO links, Q-CO links, student scores, and exam weights.
3.  Review results page: CO/PO achievement percentages, student success rates, detailed breakdowns, and interactive visualizations (charts/graphs).
4.  Export:
    *   **PDF Report:** Formatted summary suitable for accreditation documentation.
    *   **CSV/Excel:** Raw calculation data for further analysis.
    *   **Student Score Export:** Detailed performance data per student vs outcomes.
    *   **Detailed Exam Data Export:** Full structure (exams, questions, outcomes) and scores.

> **⚙️ Optional Config:** Before calculating, customize via Course Detail -> `Settings`:
> *   **Achievement Levels:** Define performance bands (e.g., Excellent: 90-100, Good: 75-89.99...). Used in reports and visualizations.
> *   **Success Rate Method:** Choose how success is defined (affects CO/PO results). See [Outcome Calculation Methods](#outcome-calculation-methods).

> **📊 Calculation Methods:** Choose **Absolute** (achievement = average score) or **Relative** (achievement = % students meeting success threshold). This choice significantly impacts results. Select per course in `Settings` or toggle view globally in the \"All Courses\" analysis.

#### Step 9: Use \\\"All Courses\\\" Analysis for Program-Wide Assessment

Aggregate results across multiple courses for a program-level view.

1.  Navigate to `Calculations` -> `All Courses`.
2.  System aggregates PO results from all courses *not* marked as \"Exclude from Reports\".
3.  Sort courses; toggle between Absolute/Relative calculation views.
4.  View the comprehensive PO achievement table, showing contributions from each course.
5.  Export aggregated results for program assessment and accreditation reports.

> **🚀 Performance:** Utilizes the optimized calculation engine for significantly faster analysis, especially with many courses. Uses weighted averages based on `course_weight`.

### Quick Start for Returning Users

Setting up a new semester for an existing course:

1.  Navigate to the previous semester's course detail page.
2.  Use the `Duplicate Course` feature.
3.  Enter new Semester info, review copied components (COs, Exams, Questions, Weights, Settings).
4.  Import the new student list for the current semester.
5.  Enter scores throughout the term as assessments occur.
6.  Calculate results as needed (e.g., mid-term, end-of-term).

---

## Managing Courses 📚

Courses are the central organizational unit.

### Creating & Managing Courses

*   **Add:** Homepage -> `Add Course` -> Fill Code, Name, Semester, optional Weight -> Save.
*   **Edit:** Course Detail -> Overview -> `Edit` -> Modify properties -> Save.
*   **Delete:** Course Detail -> Overview -> `Delete` -> Confirm.
    > **🔥 Warning:** Deleting a course permanently removes ALL associated data (Exams, Questions, COs, Students, Scores). The application prevents deletion if related items (Exams, Students, Course Outcomes) exist. You must delete these related items first. This action cannot be undone. **Backup your database first!**

### Course Dashboard

The Course Detail page provides access to:

*   **Overview:** Basic info (Code, Name, Semester, Weight), Edit/Delete buttons, Timestamps.
*   **Course Outcomes (COs):** List, Add/Edit/Delete buttons, View PO mappings, Access CO details.
*   **Exams:** List, Add/Edit/Delete buttons, Manage Weights button, Access exam details & score entry, Type indicators (Final, Makeup, Mandatory).
*   **Students:** List, Add/Edit/Delete buttons, Import/Export options, Enter Scores button, Exclusion management toggle.

### Managing Exam Weights

Define assessment contribution (Course Detail -> Exams -> `Manage Weights`):

1.  Enter percentage weight for each non-makeup exam.
2.  **🔥 Sum must be exactly 100%.** (Will be normalized if not, but correct entry is preferred).
3.  Save Weights.
    > **⚖️ Critical:** Essential for accurate calculations. Makeups automatically inherit weight from the original exam.

### Course Settings

Customize calculations and reporting (Course Detail -> `Settings`):

*   **Success Rate Method:** Determines how CO/PO achievement and student success are calculated.
    *   **Absolute:** Achievement based on the average score obtained. Student passes if final weighted score >= threshold (e.g., 60%).
    *   **Relative:** Achievement based on the percentage of students meeting a success threshold. Student passes if score >= absolute threshold OR score >= % of class average (if configured).
*   **Achievement Levels:** Define named performance bands based on score ranges (e.g., Excellent 90-100, Good 75-89.99...). Used in reports and charts.
*   **Exclude Course from Reports:** Checkbox to omit this specific course instance from the aggregated program-level analysis (\"All Courses\" view). Useful for experimental or outdated courses.

### Duplicating a Course

Quickly set up a new instance based on an existing one (Course Detail -> `Duplicate Course`):

1.  Enter New Course Code, Name, Semester, Weight.
2.  Select components to copy:
    *   Course Outcomes (COs)
    *   Exams (structure only)
    *   Questions (linked to copied COs)
    *   Exam Weights
    *   Course Settings (Calculation methods, Achievement levels)
3.  Click `Duplicate`.
    > **⚠️ Important:** Students and Scores are **never** copied. You must import the new student list. Saves significant setup time.

### Searching & Exporting Courses

*   **Search:** Navigate to the `Courses` page. Use the search box at the top to filter by Course Code, Course Name, or Semester. The list updates dynamically.
*   **Export:** On the `Courses` page, click the `Export` button. Downloads a CSV/Excel summary including: Course Code, Name, Semester, Weight, Student Count, Exam Count, CO Count. Useful for reporting and analysis.

---

## Managing Outcomes (POs & COs) 🎯

Outcomes define learning objectives at program and course levels.

### Program Outcomes (POs)

High-level, program-wide competencies (often accreditation-aligned).

*   **Manage:** `Utilities` -> `Program Outcomes`.
*   **View:** List of POs (Code, Description). Click `View` for details, linked COs, and a visual representation of how the PO is supported across courses.
*   **Add/Edit/Delete:** Use buttons on the Program Outcomes page.
    > **⚠️ Deleting PO:** Removes links from COs. COs linked only to the deleted PO become \"orphaned\" and won't contribute to program assessment.
*   **Default POs:** Pre-loaded based on common Turkish engineering criteria (MÜDEK). Modify or replace as needed for your program/accreditation body.

### Course Outcomes (COs)

Specific, measurable objectives for a single course, linked to POs.

*   **Manage:** Course Detail page -> \\\"Course Outcomes\\\" section.
*   **Add:** `Add Course Outcome` -> Enter Code, Description (use action verbs, follow SMART) -> **🔥 Select mapping to PO(s)** -> Save.
*   **View:** List shows Code, Description, linked POs. Click `View` for details & list of assessing questions.
*   **Edit/Delete:** Use buttons next to each CO.
    > **⚠️ Deleting CO:** Removes links from Questions. Questions linked only to the deleted CO become \"orphaned\" and won't contribute to outcome calculations.
*   **Effective COs:** Use SMART principles (Specific, Measurable, Achievable, Relevant, Time-bound). Start with action verbs (e.g., Analyze, Design, Evaluate).

### Understanding the Outcome Hierarchy

```
Exam Questions  -->  Assess -->  Course Outcomes (COs)  --> Support -->  Program Outcomes (POs)
     |                       |                          |
 Assess Specific Skills    Course-Level Objectives    Program-Level Competencies
```

*   **🔥 Critical:** Ensure all connections are correctly made: Question -> CO, CO -> PO. All POs should ideally be covered by COs across the curriculum.
*   **✅ Best Practice:** Define COs and their PO mappings *before* creating exams and questions.
*   **💡 Efficiency:** Use the [Mass Association Tool](#advanced-feature-mass-association-tool) for linking many questions to COs quickly.

### Outcome Calculation Methods

Selected in Course Settings. Affects how outcome achievement percentages are derived.

*   **Absolute Method:** Achievement % = Average score obtained by students on the questions assessing the outcome (weighted by question scores and exam weights).
*   **Relative Method:** Achievement % = Percentage of students who met or exceeded the defined success threshold on the questions assessing the outcome.
    > **✅ Pro Tip:** The Relative method is often preferred for accreditation reports as it directly shows the proportion of students achieving competency.
    > **⚠️ Note:** Student exclusion based on [Mandatory Exam Logic](#mandatory-exams--makeup-relations) applies to both methods.

---

## Managing Exams & Questions 📝

Exams are graded assessments; Questions are the individual items within them.

### Managing Exams

Managed from Course Detail -> \\\"Exams\\\" section.

*   **Add Exam:** `Add Exam` button -> Fill Name, Max Score (informational), Date (optional), Type Flags -> Save.
*   **Type Flags:**
    *   `Is Final Exam?`: Marks the final assessment.
    *   `Is Mandatory?`: Crucial for student exclusion logic (see below).
    *   `Is Makeup Exam?`: Requires selecting the original exam it replaces. Inherits original's weight.
*   **Edit/Delete:** Use buttons next to exam. Deleting removes related questions & scores. **Warning: Deletion is permanent.**

### Mandatory Exams & Makeup Relations

*   **Mandatory Exam Logic Explained:**
    1.  Identify exams marked `Is Mandatory?`.
    2.  For outcome calculations, the system first removes any manually excluded students.
    3.  Then, it checks the remaining students against the mandatory exams. A student is **automatically excluded** if they have *zero scores* (or no score entry) for **ALL** mandatory exams **AND** their corresponding makeup versions (if makeups exist).
    4.  This ensures that outcome statistics reflect only students who participated in the designated key assessments.
    5.  If no exams are marked as mandatory, only manually excluded students are removed.
*   **Multiple Exams Overview Page:** Access via Course Detail -> Exams -> `Manage Exams`. Shows a table view of all exams, types, weights, mandatory status. Useful for overview and consistency checks.
*   **Fix Makeup Relations Utility:** Available on the `Manage Exams` page. Attempts to automatically link makeup exams to their originals based on naming patterns (e.g., \"Midterm 1 Makeup\" links to \"Midterm 1\"). Useful if makeups were created out of order or names were changed.

### Managing Questions

Managed from Exam Detail page (Course Detail -> Click Exam Name).

*   **Add Question:** `Add Question` button -> Fill Number, Text (optional), Max Score (critical for calculations) -> **🔥 Link to Course Outcome(s)** -> Save.
*   **Edit/Delete:** Use buttons on Exam Detail page. Deleting removes associated student scores for that question.
    > **⚠️ Max Scores & Links:** Individual Question Max Scores and the Q -> CO link are fundamental for accurate outcome calculations.

### Batch Question Operations

For efficiency when dealing with many questions (on Exam Detail page):

*   **Batch Add Questions:**
    *   Click `Batch Add Questions`. Specify number of questions.
    *   Fill details (text, max score, CO links) for each question in the form.
    *   Options to \"Distribute Points Equally\" across questions based on Exam Max Score.
    *   Options to \"Mark All Outcomes\" / \"Unmark All Outcomes\" for quick linking.
    *   Use the integrated \"Mass Import Relationships\" text area (same syntax as Mass Association Tool) to define links.
    *   Click `Save All Questions`.
*   **Mass Association Tool:**
    *   Click `Mass Associate Outcomes` button (or use during Batch Add).
    *   Use text syntax (`q#:oc#:oc#;...`) to define links for multiple questions at once.
    *   **Warning:** Replaces existing links for the specified questions.

### Exporting Exam Data

Multiple export options provide flexibility:

*   **Export All Exams (Course Level):** Course Detail -> Exams -> `Export Exams`. Downloads CSV with comprehensive details: exam info, weights, makeup relations, question count, CO summary, achievement levels.
*   **Export Exam Scores (Exam Level):** Exam Detail -> `Export Scores`. Downloads CSV with student IDs, names, scores per question for that specific exam, total scores, and percentages.
*   **Export Questions (Exam Level):** Exam Detail -> `Export Questions`. Downloads CSV listing questions for that exam, their max scores, and linked COs.

---

## Managing Students & Scores 🧑‍🎓

Handle student enrollment and performance data efficiently.

### Managing Students

Managed from Course Detail -> \\\"Students\\\" section.

*   **Add Manually:** `Add Student` -> Enter ID, First Name, Last Name -> Save. (Suitable for small numbers).
*   **Add/Paste Multiple:** `Add/Paste Students` -> Paste list from spreadsheet/text using supported formats (see [Step 6](#step-6-add-students-to-the-course) for format examples: ID Name Surname, ID;Name;Surname, ID\\\\tName\\\\tSurname) -> Review preview -> Save.
*   **Import from CSV:** `Import Students` -> Upload CSV file (UTF-8 recommended, header preferred) -> Map columns (e.g., `student_id`, `first_name`, `last_name`) -> Choose mode (Add new / Add & Update existing) -> Review preview -> Import.
*   **View/Edit/Delete:** Use buttons in the student list. Deleting removes the student and all their scores for *that course*.
*   **Export Students:** `Export Students` -> Downloads a CSV list of students currently enrolled in the course.
*   **Batch Delete:** `Batch Delete` button -> Select students using checkboxes -> `Delete Selected` button -> Confirm. **Warning: Deletes students and their scores for this course.**
*   **Student Exclusion:** Toggle `Exclude/Include` button next to student name. Excluded students are ignored in outcome calculations. Note that students can also be auto-excluded based on [Mandatory Exam Logic](#mandatory-exams--makeup-relations).

### Managing Student Attendance

Track exam participation (Exam Detail -> `Manage Attendance`).

*   **Mark Attendance:** Toggle switch per student (Present/Absent). Changes are saved automatically via AJAX.
*   **Bulk Actions:** Use `All` / `None` buttons to mark all students quickly.
*   **Import/Export:** Upload/download CSV attendance records (typically Student ID and Attendance Status columns).
    > **ℹ️ Note:** Attendance data, combined with scores, is used in the [Mandatory Exam Logic](#mandatory-exams--makeup-relations) for potential student exclusion from calculations.

### Entering/Editing Scores

Record student performance on each question.

1.  **Access Grid:**
    *   Course Detail -> Students -> `Enter/Edit Scores` (All exams combined view).
    *   Exam Detail -> `Enter Scores` (Single exam view).
2.  Enter score in the cell corresponding to the Student (row) and Question (column). Max score validation is applied based on question settings.
3.  **AJAX Auto-Save:** Changes are saved automatically shortly after you move out of a cell. Look for confirmation indicators.
4.  **Navigation:** Use Keyboard (Tab, Shift+Tab, Arrow keys, Enter) for efficient data entry across the grid.
5.  **Mass Import Scores:** Use the `Import Scores` button available on the score entry page to upload scores from a formatted CSV file (typically requires Student ID and Question identifiers).

### Handling Make-up Exam Scores

*   When entering scores for a makeup exam, input scores *only* for those students who took the makeup assessment.
*   Leave the score cell blank for students who took the original exam (or did not take either).
*   The calculation engine automatically prioritizes the makeup score if present; otherwise, it uses the original exam score.

---

## Accredit Calculations 📊

Automated analysis of outcome achievement (COs & POs) based on entered data.

### Optimized Calculation System ⚡

*   **Faster Multi-Course:** Centralized function computes single-course results once and reuses them for efficient \"All Courses\" aggregation.
*   **Efficient:** Reduced database queries and optimized data handling improve performance and lower memory usage, especially for large programs.
*   **Consistent:** Unified logic core ensures consistent results whether viewing a single course or the \"All Courses\" analysis. Handles makeup scores and student exclusions uniformly.

### Running Calculations & Understanding the Results Page

1.  **Prerequisites:** Ensure all data is complete and accurate: Q->CO links, CO->PO links, Exam Weights set (summing to 100% ideally), Student Scores entered.
2.  **Run:** Go to Course Detail -> `Calculate Results`.
3.  **Review Results Page:**
    *   **Course Outcome (CO) Achievement:** Displays % achievement for each CO.
        *   *Absolute Method:* Calculates the average score students achieved on questions linked to the CO (weighted).
        *   *Relative Method:* Calculates the percentage of students who met the success threshold on questions linked to the CO.
        *   May display results using defined [Achievement Levels](#course-settings).
    *   **Program Outcome (PO) Contribution:** Shows how this course contributes to the achievement of linked POs, based on the contributing CO achievements and the selected calculation method.
    *   **Course Success Rate:** Shows the % of students deemed successful based on the method and threshold defined in [Course Settings](#course-settings).
    *   **Student Performance Summary (Optional):** May list individual student grades and outcome achievement details.
    *   **Charts & Visualizations:** Provides graphical representations (e.g., bar charts) of CO and PO achievement.

### Advanced Calculation Features

*   **Makeup Handling:** Automatically uses makeup score if available, otherwise uses original score. Makeups inherit the weight of the original exam.
*   **Mandatory Exams & Exclusion:**
    1.  Manually excluded students are removed first.
    2.  If mandatory exams exist, students missing scores for *all* mandatory exams (and their makeups) are automatically excluded from outcome calculations.
    3.  This ensures results reflect actively participating students.
    4.  Courses can be excluded entirely from program-level aggregation via [Course Settings](#course-settings).
*   **Precision:** Uses Python's `Decimal` type for calculations to avoid floating-point inaccuracies, ensuring reliable results especially around achievement level boundaries.
*   **Debugging:** Click the `Debug Calculations` button (available on the results page) to view detailed step-by-step calculation breakdowns. This includes raw scores, weighted scores, individual CO/PO scores per student, and exclusion status/reason, aiding in troubleshooting unexpected results.

### Exporting Results

From the Calculation Results page, export data for reporting and analysis:

*   **PDF Report:** Formatted summary including tables and charts, suitable for accreditation submissions.
*   **CSV/Excel Export:** Raw calculation data (achievement percentages per outcome) for use in spreadsheets or other tools.
*   **Student Results Export:** Detailed breakdown of individual student performance against outcomes.
*   **Course Exams Export:** Structured export of exam, question, and outcome linkage data (same as Export All Exams from Course Detail).

### Multi-Course Analysis (\\\"All Courses\\\" View)

Gain program-level insights (`Calculations` -> `All Courses`):

*   Aggregates PO achievement results from all courses *not* marked as \"Exclude from Reports\".
*   Calculates program-wide PO achievement using a **weighted average** based on the `course.course_weight` defined for each contributing course.
*   Visualizes how different courses contribute to each PO.
*   Helps identify curriculum strengths, weaknesses, and trends over time.
*   Uses the same optimized, consistent calculation core as single-course analysis.

> **⚖️ Note on Weights:** If exam weights are not set or do not sum to 100% on the `Manage Weights` page, the system will normalize them during calculation (scaling proportionally to sum to 100%) or weight exams equally if no weights are set. However, correctly setting weights to 100% is recommended practice.

---

## Utilities: Data Management & More 🛠️

Tools for data handling, system access, and administration.

### Remote Access with Cloudflared ☁️

*   **Purpose:** Access your locally running Accredit Helper Pro securely from anywhere via the internet.
*   **Features:** Creates a secure public URL using Cloudflare Tunnel, enables easy sharing with colleagues, requires no complex firewall or network configuration.
*   **Setup:** Install the `cloudflared` client software, then run the application with the `--cloud` command-line flag (`python app.py --cloud`).
*   **Guide:** See the detailed [Remote Access Guide](#remote-access-guide-cloudflare-tunnel-) section for installation and usage instructions.

### API Integration 🔌

*   **Purpose:** Allow programmatic access to application data for integration with other systems (e.g., LMS, custom reporting tools).
*   **Format:** Returns data in JSON format.
*   **Endpoints (Examples):**
    *   `/api/exam/{exam_id}/question-outcomes`: Get questions and linked COs for an exam.
    *   `/api/student/{student_id}/abet-scores?course_id={course_id}`: Get a student's CO achievement scores for a course.
    *   `/api/batch-add-questions/{exam_id}`: API endpoint for batch adding questions.
    *   `/api/mass-associate-outcomes`: API endpoint for mass associating outcomes.
    *   `/api/update-question-outcome`: API endpoint for updating Q-CO links.
    *   `/api/course/{course_id}/achievement-levels`: Get achievement level definitions for a course.
    *(Check source or documentation for a complete, up-to-date list)*
*   **Use Cases:** Building custom dashboards, integrating with institutional data warehouses, automating report generation.
    > **⚠️ Security:** These endpoints typically do **not** have built-in authentication. If exposing the application externally (e.g., via Cloudflared or server deployment), ensure appropriate security measures (firewall, authentication layer) are implemented.

### Backup Database 💾

*   **Purpose:** Create safe copies of the entire application database (`accredit_data.db`).
*   **Features:** Add custom descriptions, automatic timestamps, view backup history, download backup files (`.db` format).
*   **When:** Essential before major operations (imports, merges, deletions), at the end of each academic term, and on a regular schedule.
*   **Access:** `Utilities` -> `Backup Database`.

### Restore Database 🔄

*   **Purpose:** Replace the current database with a previously created backup file.
*   **Features:** Lists available backups with descriptions/timestamps, performs an automatic backup of the *current* database before restoring (as a safety net).
*   **When:** To recover from data loss or corruption, to roll back unwanted changes, or to revert to a specific point in time.
*   **Access:** `Utilities` -> `Restore Database`.

### Import Database 📥

*   **Purpose:** Merge data from an existing backup file into the *current* database **without** replacing existing data (additive).
*   **Features:** Allows selection of specific data types to import (e.g., only certain courses, students), previews potential changes/conflicts, performs an auto-backup before import, provides a summary report after import.
*   **When:** Useful for consolidating data from different instances, migrating specific courses from colleagues, or adding historical data selectively.
*   **Access:** `Utilities` -> `Import Database`.

### Merge Courses ➕

*   **Purpose:** Combine data from two or more existing courses within the *current* database into a single target course.
*   **Features:** Merges students, scores, and assessment structures. Provides a preview of the merge operation before execution.
*   **When:** Useful for combining multiple sections of the same course taught in the same term, or consolidating historical data spread across different course entries.
*   **Access:** `Utilities` -> `Merge Courses`.

### System Logs 📜

*   **Purpose:** Track significant actions performed within the application for auditing and troubleshooting.
*   **Features:** View logs chronologically, filter by action type (ADD, EDIT, DELETE, IMPORT, BACKUP/RESTORE, OTHER) and date range, export logs to CSV, color-coded actions for readability.
*   **When:** Essential for understanding who did what and when, troubleshooting errors, auditing changes for compliance.
*   **Access:** `Utilities` -> `System Logs`.

### Support & Feedback 💬

*   **Purpose:** A channel to report issues, request new features, or seek assistance.
*   **Access:** `Utilities` -> `Support & Feedback` or via the main `Help` menu, linking to the [Contact & Support](#contact--support-) section.

---

## Remote Access Guide (Cloudflare Tunnel) ☁️

Access Accredit Helper Pro securely from anywhere using Cloudflare Tunnel (`cloudflared`).

### About Remote Access

Uses Cloudflare's `cloudflared` client to create a secure, encrypted tunnel from your local machine (where the app is running) to Cloudflare's edge network. This generates a temporary, public URL (e.g., `https://random-words.trycloudflare.com`) that you can use to access the app remotely. Benefits include easy setup, no need for firewall changes, and simple sharing.

### Installation Guide

You need to install the `cloudflared` client on the machine running Accredit Helper Pro:

*   **Windows:**
    1.  Download the `.msi` or `.exe` installer from the [Cloudflare Releases page](https://github.com/cloudflare/cloudflared/releases).
    2.  Run the installer.
    3.  Verify by opening Command Prompt and typing `cloudflared --version`.
*   **macOS:**
    1.  Using Homebrew (recommended): `brew install cloudflare/cloudflare/cloudflared`.
    2.  Alternatively, download the package (`.pkg` or `.tar.gz`) from the releases page.
    3.  Verify by opening Terminal and typing `cloudflared --version`.
*   **Linux (Debian/Ubuntu Example):**
    ```bash
    # Download the .deb package (check releases for latest URL/architecture)
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
    # Install the package
    sudo dpkg -i cloudflared.deb
    # Verify installation
    cloudflared --version
    ```
    Check the releases page for instructions for other distributions (e.g., RPM).

> **⚠️ Important:** `cloudflared` needs to be in your system's PATH environment variable for the application to find it automatically. A system restart might be required after installation.

### Using Remote Access

1.  **Start the App with Cloudflare:**
    *   **Windows:** You might use a provided batch file like `Windows_Start_CloudFlare_Public_Url.bat` if available.
    *   **Command Line (All OS):**
        ```bash
        # Navigate to the application directory
        cd path/to/Accredit-Helper-Pro
        # Activate your virtual environment (if used)
        source venv/bin/activate  # Linux/macOS
        # .\\\\venv\\\\Scripts\\\\activate # Windows
        # Run the app with the --cloud flag
        python app.py --cloud
        ```
2.  **Get the Public URL:** The console/terminal window where you started the app will display output from `cloudflared`, including a public URL ending in `.trycloudflare.com`.
3.  **Access and Share:** Copy this URL and paste it into any web browser on any device with internet access. The URL remains active only as long as your local application is running with the `--cloud` flag.

> **🛡️ Security Note:** The generated URL is public. Anyone who has the URL can access your running application instance. Share it carefully and only with trusted colleagues. Close the application (stop the `python app.py --cloud` process) to deactivate the URL immediately.

### Troubleshooting Remote Access

*   **Error: \"cloudflared is not installed or not in PATH\"**:
    *   Verify `cloudflared` is installed (`cloudflared --version`).
    *   Ensure it's in your system PATH. Restart your terminal or PC.
    *   Reinstall `cloudflared`.
*   **No Public URL Displayed in Console**:
    *   Did you use the `--cloud` flag?
    *   Check the console output for specific errors from `cloudflared` or the Python app.
    *   Is an outbound connection to Cloudflare blocked by a firewall?
    *   Test `cloudflared` manually: `cloudflared tunnel --url http://localhost:5000` (assuming app runs on port 5000).
*   **Cannot Connect via Public URL**:
    *   Is the local application still running? Check the console window.
    *   Did you copy the URL correctly?
    *   Does the remote device have internet connectivity? Can it reach other websites?
    *   Try accessing the URL from a different network or browser.
    *   Stop and restart the app with `--cloud` to get a fresh URL.
*   **Slow Performance Remotely**:
    *   Some latency is expected due to internet routing.
    *   Check the upload speed of the internet connection where the app is running.
    *   Avoid very large data operations (like importing huge files) over the remote connection if possible. Use the local interface for heavy tasks.

---

## Troubleshooting Guide 🐛

Common issues and potential solutions.

### Database & File Issues

*   **Backup/Restore Fails:**
    *   **Permissions:** Does the app have write permission in the `instance/backups` directory? Try running with admin/sudo rights (use cautiously).
    *   **Disk Space:** Is there enough free space?
    *   **File Integrity:** Is the backup file corrupted? Try a different backup. Is the current DB file readable?
    *   **Version Compatibility:** Restoring a backup from a very different app version might fail. Ensure versions are compatible or upgrade/migrate carefully.
*   **File System Errors (e.g., Cannot Save Course/Exam):**
    *   **Permissions:** Check write permissions for the `instance` folder and the `accredit_data.db` file within it.
    *   **Disk Space:** Ensure sufficient disk space on the drive.
*   **Database Locked (`OperationalError: database is locked`):**
    *   **Multiple Instances:** Ensure only one copy of `app.py` is running.
    *   **External Tools:** Close any database browser tools (like DB Browser for SQLite) that might be accessing `accredit_data.db`.
    *   **Permissions:** Verify file permissions.
*   **Missing/Unexpected Data:**
    *   **Accidental Deletion:** Check `Utilities` -> `System Logs` for DELETE actions. Restore from backup if necessary.
    *   **Wrong DB File:** Are you sure the application is using the intended `accredit_data.db` file? (Especially if managing multiple copies).
    *   **Import/Merge Issues:** Did the issue appear after an import or merge? Restore the auto-backup created before the operation and try again, checking settings carefully.

### Calculation & Results Issues

*   **Unexpected Results (Percentages too high/low, outcomes wrong):**
    *   **Links:** Triple-check Q->CO and CO->PO links. Are all relevant items linked? Are links correct?
    *   **Weights:** Do Exam Weights sum to 100% in `Manage Weights`? Are they set logically?
    *   **Scores:** Are all student scores entered correctly? Any missing scores? Scores exceeding max points?
    *   **Method:** Check `Course Settings`. Is the correct Success Rate Method (Absolute/Relative) selected? Does the threshold make sense?
    *   **Exclusion:** Check manually excluded students. Review Mandatory Exam settings and student scores/attendance - are students being unexpectedly excluded? Use the `Debug Calculations` tool.
*   **Calculation Errors/Failures (Error message during calculation):**
    *   **Division by Zero:** Check if any Question Max Scores are 0. Check if the course has students with scores.
    *   **Inconsistent Data:** Missing COs, Exams, or other required structure? Orphaned links?
    *   **Timeout:** For extremely large courses, calculations might exceed default timeouts. Try again. If persistent, report as a potential performance issue.
    *   **Use Debug Tool:** The `Debug Calculations` button on the results page is invaluable for diagnosing calculation logic errors.

### Import/Export & Data Transfer Issues

*   **Student Import Problems:**
    *   **Format:** Check data against supported formats (ID Name Surname, ID;Name;Surname, ID\\\\tName\\\\tSurname). Spaces/tabs matter. Use the preview!
    *   **Duplicate IDs:** Ensure student IDs are unique within the import list *and* compared to existing students in the course (if not updating).
    *   **File Encoding:** For CSV, use UTF-8, especially if names contain special characters.
*   **Database Merge/Import Issues:**
    *   **Version Incompatibility:** Merging/importing between significantly different app versions can cause errors. Try updating first.
    *   **ID Conflicts:** Check for potential conflicts in IDs (Course, Exam, Student, etc.) between the source and target data.
    *   **Backup First!** Always backup before merging or importing complex data.
*   **Export Problems:**
    *   **Browser Blocking:** Check if your browser is blocking pop-ups or downloads.
    *   **Permissions:** Can the browser write to your download location?
    *   **No Data:** Are you trying to export from an empty list (e.g., no students in course, no results calculated)? Check filters.

### Performance & Responsiveness Issues

*   **Slow Application (Loading pages, searching):**
    *   **Database Size:** Many years of courses? Consider archiving old data (backup & restore to a separate file, then delete from active DB). Use \"Exclude Course from Reports\" for inactive courses.
    *   **System Resources:** Is the hosting machine low on RAM or CPU? Close other apps.
    *   **Browser:** Clear cache/cookies. Try Chrome or Firefox. Disable interfering extensions.
*   **Slow Score Entry Grid:**
    *   **View:** Use the exam-specific score entry (`Exam Detail -> Enter Scores`) instead of the all-exams view (`Course Detail -> Enter/Edit Scores`) for large classes.
    *   **Input Method:** Enter scores in batches rather than extremely rapidly, allowing AJAX saves to complete. Keyboard navigation is usually faster than mouse clicks.
    *   **Browser:** Chrome often handles large, dynamic tables better.

### Troubleshooting & Common Issues

*   **Application Won't Start:**
    *   **Dependencies:** Run `pip install -r requirements.txt` again in your activated virtual environment. Check console for Python errors.
    *   **DB Corruption:** Temporarily move/rename `instance/accredit_data.db`. If it starts, the DB was corrupt; restore from backup into the new file or start fresh.
    *   **Port Conflict:** Is another service using port 5000? Try `python app.py --port 5001`.
*   **Charts Not Displaying:**
    *   **Browser:** Ensure JavaScript is enabled. Try a different browser. Clear cache.
    *   **Data:** Are there calculated results to display? Need scores and links first.
    *   **Network:** If remote, check connection. Check browser's Developer Console (F12) for JavaScript errors.
*   **Unexpected Error Messages:**
    *   **Bug:** Could be a software bug. Note the steps to reproduce, take a screenshot, check System Logs, and report it.
    *   **Data Format:** Did you enter data in an unexpected format (e.g., text where numbers expected)?
    *   **Version:** Are you using the latest version? Check for updates.

