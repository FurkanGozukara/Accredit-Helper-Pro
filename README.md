# Accredit Helper Pro

**Accredit Helper Pro** is a comprehensive tool designed for educational institutions to manage course data, track student performance against learning outcomes (POs and COs), and streamline the accreditation assessment process (e.g., ABET, MÜDEK).

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
        *   [Step 9: Use \"All Courses\" Analysis](#step-9-use-all-courses-analysis-for-program-wide-assessment)
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
    *   [Multi-Course Analysis (\"All Courses\" View)](#multi-course-analysis-all-courses-view)
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
13. [Privacy Policy](#privacy-policy-)
14. [Terms of Use](#terms-of-use-)
15. [Contact & Support](#contact--support-)
16. [Contributing](#contributing-)
17. [License](#license-)

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
*   **✅ Attendance Tracking:** Record and manage student attendance for exams with automated import/export.
*   **✅ Student Exclusion Control:** Manually exclude/include specific students from outcome calculations.
*   **✅ Automated Calculations:** Get precise outcome achievement metrics.
*   **✅ Multiple Calculation Methods:** Choose between absolute and relative achievement models.
*   **✅ Custom Achievement Levels:** Define your own performance categories.
*   **✅ Reporting:** Generate accreditation-ready reports and exports (PDF, CSV, Excel).
*   **✅ Data Management:** Backup, restore, merge, and import data seamlessly.
*   **✅ Activity Logging:** Track all significant actions within the system.
*   **✅ Batch Operations:** Add/manage multiple questions, outcomes, students (incl. deletion), attendance.
*   **✅ Mass Association Tool:** Quickly connect multiple questions to outcomes using simple syntax.
*   **✅ AJAX-based Interface:** Responsive, real-time updates for score entry and attendance.
*   **✅ Secure Remote Access:** Use Cloudflare Tunnel for accessing the application from anywhere.
*   **✅ Advanced Exam Features:** Support for makeup exams, final exam designation, and mandatory exam attendance.
*   **✅ Data Visualization:** View interactive charts and graphs for outcome achievements.
*   **✅ Course Duplication:** Quickly set up new courses based on existing templates.
*   **✅ Multi-course Analysis:** Analyze program outcomes across all courses with optimized performance.
*   **✅ Student Score Export:** Export detailed student performance data.
*   **✅ Detailed Exam Data Exports:** Export exam structure, questions, outcomes, and scores.
*   **✅ API Functionality:** Access data programmatically via REST endpoints.
*   **✅ Enhanced Search:** Find specific information across courses with the built-in search.

### Recent Performance Improvements 🚀

The calculation system has been significantly optimized for:

*   **⚡ Faster Multi-Course Analysis:** Significant speed improvements for program-wide results.
*   **⚙️ Efficient Resource Usage:** Minimized database queries for better performance with large datasets.
*   **🔄 Consistent Makeup Exam Handling:** Enhanced synchronization of makeup exam weights.
*   **⚖️ Standardized Student Exclusion:** Improved logic for handling mandatory exam attendance.
*   **🖱️ Enhanced Attendance Management:** AJAX-based attendance tracking with bulk import/export.
*   **☁️ Robust Remote Access:** Improved Cloudflare Tunnel integration.

### Who Should Use This Application? 👥

*   Faculty Members
*   Department Chairs
*   Accreditation Coordinators
*   Assessment Committees
*   Program Administrators

### Technical Architecture 🛠️

*   **Backend:** Python Flask framework with SQLAlchemy ORM
*   **Database:** SQLite (portable, file-based)
*   **Frontend:** Bootstrap 5 (responsive design)
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
    .\\venv\\Scripts\\activate

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
4.  Specify **Semester** (e.g., `Fall 2023`).
5.  Click `Save Course`.

> **⚠️ Important:** Create separate instances for each semester (e.g., \"CENG301 Fall 2023\", \"CENG301 Spring 2024\").

#### Step 3: Define Course Outcomes (COs)

COs are specific, measurable learning objectives linked to POs.

1.  On the Course Detail page, find \"Course Outcomes\" -> `Add Course Outcome`.
2.  Enter **CO Code** (e.g., `CO1`).
3.  Write a clear, measurable **Description** (start with an action verb, e.g., \"Design...\").
4.  **🔥 Critical:** Select the Program Outcome(s) (POs) this CO supports.
5.  Click `Save`. Repeat for all COs (typically 5-10 per course).

> **ℹ️ Example CO-PO Mapping:**
> *   CO1: \"Apply software testing techniques...\" -> maps to PO2, PO3
> *   CO2: \"Communicate technical information...\" -> maps to PO7

> **🔥 Critical:** Every CO *must* link to at least one PO for assessment.

#### Step 4: Add Exams and Set Weights

Exams represent all assessed activities (exams, projects, quizzes).

1.  From Course Detail -> \"Exams\" section -> `Add Exam`.
2.  Enter a descriptive **Name** (e.g., `Midterm 1`, `Final Project`).
3.  Set **Max Score** (e.g., `100`).
4.  Optionally set **Exam Date**.
5.  Check flags if applicable:
    *   `Is Final Exam?`
    *   `Is Mandatory?` (See [Mandatory Exam Logic](#mandatory-exams--makeup-relations))
    *   `Is Makeup Exam?` (Select original exam it replaces)
6.  Save. Repeat for all assessments.

**Setting Exam Weights:**

1.  After adding exams, click `Manage Weights` in the Exams section.
2.  Assign percentage weights (e.g., Midterm 1: 30%, Final: 40%).
3.  **🔥 Important:** Weights must total exactly 100%.
4.  Click `Save Weights`.

> **⚖️ Note:** Weights determine contribution to grades and outcomes. Makeups inherit weight.

**Managing Makeup Exams:**

1.  Check `Is Makeup Exam?` and select the original exam when creating.
2.  Enter scores only for students who took the makeup.
3.  The system automatically uses the correct score (makeup > original).
4.  Use `Fix Makeup Relations` (in Exams section) if links become inconsistent.

#### Step 5: Add Questions & Link to Course Outcomes

Questions are individual assessment items linked to COs.

1.  Go to Course Detail -> Click Exam Name -> Exam Detail page.
2.  Click `Add Question`.
3.  Enter **Question Number** (e.g., `1`, `2a`).
4.  Optionally enter **Question Text**.
5.  Set **Max Score** for this question (e.g., `10`, `25`).
6.  **🔥 Critical:** Select the Course Outcome(s) (COs) this question assesses.
7.  Save. Repeat for all questions in all exams.

> **💡 Batch Operations:** Use `Batch Add Questions` or the `Mass Association Tool` (see below) for efficiency.

> **🔗 Critical Mapping:** The Question <-> CO link is fundamental. Map carefully. A question can assess multiple COs.

> **✅ Tip:** For projects, break down the rubric into \"questions\" assessing different COs.

#### Step 6: Add Students to the Course

Enroll students in the course instance.

*   **Manual Entry:** `Add Student` button (for small classes).
*   **Batch Import (Recommended):**
    1.  Go to Students section -> `Import Students`.
    2.  Paste list from spreadsheet/text (formats supported: ID Name Surname, ID;Name;Surname, ID\\tName\\tSurname).
    ```text
    # Example formats
    11220030102  Name1  Surname
    11220030126  Name1 Name2  Surname

    11220030102;Name1;Surname

    11220030102	Name1	Surname
    ```
    3.  Review preview and import.
*   **CSV File Upload:** Prepare CSV (ID, First Name, Last Name), upload, map columns, import.

**Managing Student Exclusion:**

*   Use the `Exclude/Include` toggle next to a student's name on the Course Detail page (Students list). Excluded students are ignored in calculations.
*   Students might also be auto-excluded based on [Mandatory Exam Logic](#mandatory-exams--makeup-relations).

**Tracking Attendance:**

*   Go to Exam Detail -> `Manage Attendance`. Toggle attendance (saves automatically).
*   Batch import/export available. See [Student Attendance](#managing-student-attendance).

> **💾 Student Export:** Use `Export Students` for a CSV list.

#### Step 7: Enter Student Scores

Record performance on each question.

1.  Access score entry:
    *   Course Detail -> Students -> `Enter/Edit Scores` (all exams)
    *   Exam Detail -> `Enter Scores` (single exam)
2.  Grid: Students (rows) x Questions (columns).
3.  Enter scores (cannot exceed Question Max Score).
4.  **Scores save automatically (AJAX).**

> **⌨️ Efficiency Tip:** Use Tab, Shift+Tab, Arrow keys, Enter for navigation.

> **⚠️ Makeup Scores:** Enter scores *only* for students who took the makeup. Leave blank otherwise.

#### Advanced Feature: Mass Association Tool

Quickly link multiple questions to outcomes.

1.  Go to Exam Detail -> `Mass Associate Outcomes`.
2.  Enter associations in the text area using syntax: `q#:oc#:oc#;q#:oc#`
    *   `q#`: Question number (e.g., `q1`)
    *   `oc#`: Course Outcome number (e.g., `oc1` for CO1)
    *   `:` separates question from outcomes / multiple outcomes.
    *   `;` separates different question associations.
    *   Example: `q1:oc1:oc2;q2:oc3;q3:oc1:oc3:oc4;`
3.  Click `Apply Associations`.

> **✅ Example:** `q1:oc1:oc2;q2:oc3;` maps Q1 to CO1 & CO2, and Q2 to CO3.

> **⚠️ Important:** Replaces existing associations for specified questions. Include all desired links.

#### Step 8: Calculate Results & Generate Reports

Analyze outcome achievement.

1.  Go to Course Detail -> `Calculate Results`.
2.  System processes data (CO-PO links, Q-CO links, scores, weights).
3.  Review results: CO/PO achievement, success rates, visualizations.
4.  Export:
    *   **PDF Report:** Formatted summary.
    *   **CSV/Excel:** Raw calculation data.
    *   **Student Score Export:** Detailed performance per student.
    *   **Detailed Exam Data Export:** Full structure and scores.

> **⚙️ Optional Config:** Customize before calculating (Course Detail -> `Settings`):
> *   Achievement Levels (e.g., Excellent: 90-100%).
> *   Success Rate Method (Absolute vs. Relative).

> **📊 Multiple Methods:** Choose **Absolute** (avg score) or **Relative** (% students above threshold) in Course Settings or globally (\"All Courses\" view).

#### Step 9: Use \"All Courses\" Analysis for Program-Wide Assessment

Aggregate results across courses for program-level view.

1.  Navigate to `Calculations` -> `All Courses`.
2.  System aggregates PO results from all *non-excluded* courses.
3.  Sort courses; toggle Absolute/Relative view.
4.  View comprehensive PO achievement table.
5.  Export for accreditation reports.

> **🚀 Performance:** Optimized engine significantly speeds up multi-course analysis.

### Quick Start for Returning Users

Setting up a new semester for an existing course:

1.  Use `Duplicate Course` feature (Course Detail page).
2.  Update Semester, review copied components (COs, Exams, Qs, Weights, Settings).
3.  Import new student list.
4.  Enter scores throughout the term.
5.  Calculate results.

---

## Managing Courses 📚

Courses are the central organizational unit.

### Creating & Managing Courses

*   **Add:** Homepage -> `Add Course` -> Fill Code, Name, Semester, optional Weight -> Save.
*   **Edit:** Course Detail -> Overview -> `Edit` -> Modify properties -> Save.
*   **Delete:** Course Detail -> Overview -> `Delete` -> Confirm.
    > **🔥 Warning:** Deleting removes ALL related data (Exams, Questions, COs, Students, Scores). Cannot be undone unless related items are deleted first. Backup first!

### Course Dashboard

The Course Detail page provides access to:

*   **Overview:** Basic info, Edit/Delete buttons.
*   **Course Outcomes (COs):** List, Add/Edit/Delete, View PO mappings.
*   **Exams:** List, Add/Edit/Delete, Manage Weights, Access score entry, Type indicators.
*   **Students:** List, Add/Edit/Delete, Import/Export, Enter Scores, Exclusion management.

### Managing Exam Weights

Define assessment contribution (Course Detail -> Exams -> `Manage Weights`):

1.  Enter percentage weight for each non-makeup exam.
2.  **🔥 Sum must be exactly 100%.**
3.  Save Weights.
    > **⚖️ Critical:** Essential for accurate calculations. Makeups inherit weight.

### Course Settings

Customize calculations (Course Detail -> `Settings`):

*   **Success Rate Method:**
    *   **Absolute:** Average score approach. Passing based on fixed threshold (e.g., 60%). CO achievement = average student score.
    *   **Relative:** Percentage of students meeting threshold. Passing based on absolute threshold OR % of class average. CO achievement = % students passing threshold.
*   **Achievement Levels:** Define performance bands (e.g., Excellent 90-100, Good 75-89.99...). Used in reports.
*   **Exclude Course from Reports:** Check to omit this course from program-level (\"All Courses\") analysis.

### Duplicating a Course

Quickly set up a new instance based on an existing one (Course Detail -> `Duplicate Course`):

1.  Enter New Course Code, Name, Semester, Weight.
2.  Select components to copy (COs, Exams, Questions, Weights, Settings).
3.  Click `Duplicate`.
    > **⚠️ Important:** Students and Scores are **never** copied.

### Searching & Exporting Courses

*   **Search:** `Courses` page -> Use search box (Code, Name, Semester). Filters dynamically.
*   **Export:** `Courses` page -> `Export` button -> Downloads CSV/Excel summary (Code, Name, Semester, Weight, Counts).

---

## Managing Outcomes (POs & COs) 🎯

Outcomes define learning objectives.

### Program Outcomes (POs)

High-level, program-wide competencies (often accreditation-aligned).

*   **Manage:** `Utilities` -> `Program Outcomes`.
*   **View:** List of POs (Code, Description). Click `View` for details & CO mappings.
*   **Add/Edit/Delete:** Use buttons on the Program Outcomes page.
    > **⚠️ Deleting PO:** Removes links to COs. Orphaned COs affect calculations.
*   **Default POs:** Pre-loaded based on common Turkish engineering criteria (MÜDEK). Modify as needed.

### Course Outcomes (COs)

Specific, measurable objectives for a single course, linked to POs.

*   **Manage:** Course Detail page -> \"Course Outcomes\" section.
*   **Add:** `Add Course Outcome` -> Enter Code, Description -> **🔥 Select mapping to PO(s)** -> Save.
*   **View:** List shows Code, Description, linked POs. Click `View` for details & assessing questions.
*   **Edit/Delete:** Use buttons next to each CO.
    > **⚠️ Deleting CO:** Removes links to Questions. Orphaned questions affect calculations.
*   **Effective COs:** Use SMART principles (Specific, Measurable, Achievable, Relevant, Time-bound). Start with action verbs.

### Understanding the Outcome Hierarchy

```
Exam Questions  -->  Assess -->  Course Outcomes (COs)  --> Support -->  Program Outcomes (POs)
     |                       |                          |
 Assess Specific Skills    Course-Level Objectives    Program-Level Competencies
```

*   **🔥 Critical:** Ensure all connections: Q -> CO, CO -> PO. All POs should be covered across the curriculum.
*   **✅ Best Practice:** Define COs and PO mappings *before* creating exams/questions.
*   **💡 Efficiency:** Use the [Mass Association Tool](#advanced-feature-mass-association-tool) for linking many questions.

### Outcome Calculation Methods

Selected in Course Settings. Affects how achievement % is derived.

*   **Absolute:** Achievement = Average score on related questions.
*   **Relative:** Achievement = % of students meeting success threshold on related questions.
    > **✅ Pro Tip:** Relative method often preferred for accreditation reports (shows % achieving competency).
    > **⚠️ Note:** Students missing all mandatory exams are excluded. See [Mandatory Exam Logic](#mandatory-exams--makeup-relations).

---

## Managing Exams & Questions 📝

Exams are graded assessments; Questions are items within them.

### Managing Exams

Managed from Course Detail -> \"Exams\" section.

*   **Add Exam:** `Add Exam` button -> Fill Name, Max Score, Date, Type Flags -> Save.
*   **Type Flags:**
    *   `Is Final Exam?`
    *   `Is Mandatory?` (Crucial for student exclusion logic - see below)
    *   `Is Makeup Exam?` (Requires selecting original exam)
*   **Edit/Delete:** Use buttons next to exam. Deleting removes questions & scores.

### Mandatory Exams & Makeup Relations

*   **Mandatory Exam Logic:**
    1.  If an exam (or multiple exams) are marked `Is Mandatory?`.
    2.  Students who have *zero scores* (or no scores entered) for **ALL** mandatory exams **AND** their makeup versions (if they exist) will be *excluded* from outcome calculations.
    3.  This ensures results reflect students who participated in key assessments.
    4.  If *no* exams are mandatory, only manually excluded students are removed.
*   **Multiple Exams Overview:** `Manage Exams` page (from Course Detail) shows all exams, types, weights, mandatory status.
*   **Fix Makeup Relations:** Utility on `Manage Exams` page to auto-link makeups to originals based on name (e.g., \"Midterm 1 Makeup\" to \"Midterm 1\"). Useful if created out of order or names changed.

### Managing Questions

Managed from Exam Detail page (Course Detail -> Click Exam Name).

*   **Add Question:** `Add Question` button -> Fill Number, Text (optional), Max Score -> **🔥 Link to Course Outcome(s)** -> Save.
*   **Edit/Delete:** Use buttons on Exam Detail page. Deleting removes associated scores.
    > **⚠️ Max Scores:** Individual Question Max Scores drive calculations. Linking Q -> CO is essential.

### Batch Question Operations

For efficiency (on Exam Detail page):

*   **Batch Add Questions:** Create multiple questions at once. Specify number, fill details (text, max score, CO links) per question. Options to distribute points equally, mass mark/unmark outcomes.
*   **Mass Association Tool:** Use text syntax (`q#:oc#:oc#;...`) to link many questions to COs quickly. Available during Batch Add or via `Mass Associate Outcomes` button. Replaces existing links.

### Exporting Exam Data

*   **Export All Exams (Course Level):** Course Detail -> Exams -> `Export Exams`. CSV with exam details, weights, makeups, CO summary.
*   **Export Exam Scores (Exam Level):** Exam Detail -> `Export Scores`. CSV with student scores for that exam.
*   **Export Questions (Exam Level):** Exam Detail -> `Export Questions`. CSV with question details and CO links.

---

## Managing Students & Scores 🧑‍🎓

Handle student enrollment and performance data.

### Managing Students

Managed from Course Detail -> \"Students\" section.

*   **Add Manually:** `Add Student` -> Enter ID, Name -> Save.
*   **Add/Paste Multiple:** `Add/Paste Students` -> Paste list -> Preview -> Save.
*   **Import from CSV:** `Import Students` -> Upload CSV -> Map columns -> Choose mode (Add new / Add & Update) -> Import.
*   **View/Edit/Delete:** Use list view buttons. Deleting removes student's scores for that course.
*   **Export Students:** `Export Students` -> Download CSV list.
*   **Batch Delete:** `Batch Delete` -> Checkboxes -> `Delete Selected`.
*   **Student Exclusion:** Toggle `Exclude/Include` button. Excluded students ignored in calculations. Auto-exclusion may occur based on [Mandatory Exam Logic](#mandatory-exams--makeup-relations).

### Managing Student Attendance

Track exam attendance (Exam Detail -> `Manage Attendance`).

*   **Mark Attendance:** Toggle switch per student (AJAX auto-save).
*   **Bulk Actions:** `All` / `None` buttons.
*   **Import/Export:** Upload/download CSV attendance records.
    > **ℹ️ Note:** Attendance data + scores are used in the mandatory exam logic for student exclusion.

### Entering/Editing Scores

Record scores per question.

1.  **Access Grid:**
    *   Course Detail -> Students -> `Enter/Edit Scores` (All exams for course)
    *   Exam Detail -> `Enter Scores` (Single exam)
2.  Enter score in cell (Student row x Question column). Max score validation applied.
3.  **AJAX Auto-Save:** Changes saved automatically.
4.  **Navigation:** Use Keyboard (Tab, Arrows, Enter).
5.  **Mass Import Scores:** `Import Scores` button on score entry page (upload CSV).

### Handling Make-up Exam Scores

*   Enter scores *only* for students who took the makeup.
*   Leave blank for students who took the original.
*   Calculation engine uses makeup score if present, otherwise original score.

---

## Accredit Calculations 📊

Automated analysis of outcome achievement (COs & POs).

### Optimized Calculation System ⚡

*   **Faster Multi-Course:** Centralized function reuses single-course results.
*   **Efficient:** Reduced DB queries, better memory usage.
*   **Consistent:** Unified logic, improved makeup/exclusion handling.

### Running Calculations & Understanding the Results Page

1.  Ensure data is complete (Links: Q->CO, CO->PO; Weights set; Scores entered).
2.  Go to Course Detail -> `Calculate Results`.
3.  Results page shows:
    *   **Course Outcome (CO) Achievement:** % achievement per CO. Uses selected [Calculation Method](#outcome-calculation-methods). May show Achievement Levels.
    *   **Program Outcome (PO) Contribution:** How this course contributes to linked POs.
    *   **Course Success Rate:** % successful students based on Course Settings (Absolute/Relative).
    *   **Student Performance Summary (Optional):** Individual student grades/outcomes.
    *   **Charts & Visualizations:** Graphical representation of results.

### Advanced Calculation Features

*   **Makeup Handling:** Auto-uses makeup score if available; inherits original weight.
*   **Mandatory Exams & Exclusion:**
    1.  Manually excluded students removed first.
    2.  If mandatory exams exist, students missing *all* mandatory exams (and their makeups) are auto-excluded.
    3.  Ensures results reflect active participants.
    4.  Course can be excluded from program aggregation via Course Settings.
*   **Precision:** Uses Decimal type to avoid floating-point errors.
*   **Debugging:** `Debug Calculations` button (on results page) shows step-by-step details for students, exams, outcomes (raw scores, weighted scores, CO/PO scores, exclusion status/reason).

### Exporting Results

From Calculation Results page:

*   **PDF Report:** Formatted summary for accreditation.
*   **CSV/Excel Export:** Raw calculation data.
*   **Student Results Export:** Detailed individual performance vs outcomes.
*   **Course Exams Export:** Structured exam/question/outcome data.

### Multi-Course Analysis (\"All Courses\" View)

Program-level insights (`Calculations` -> `All Courses`):

*   Aggregates results from non-excluded courses.
*   Calculates weighted average PO achievement based on `course.course_weight`.
*   Visualizes course contributions to POs.
*   Identifies curriculum-wide patterns.
*   Uses optimized, consistent calculation core.

> **⚖️ Note on Weights:** If exam weights don't sum to 100%, they are normalized during calculation. If no weights are set, exams are weighted equally.

---

## Utilities: Data Management & More 🛠️

Tools for data handling and system access.

### Remote Access with Cloudflared ☁️

*   **Purpose:** Access application securely from anywhere via Cloudflare Tunnel.
*   **Features:** Secure public URL, easy sharing, no firewall changes.
*   **Setup:** Install `cloudflared` client, run app with `--cloud` flag.
*   **Guide:** See [Remote Access Guide](#remote-access-guide-cloudflare-tunnel-).

### API Integration 🔌

*   **Purpose:** Programmatic access to data (JSON format).
*   **Endpoints:**
    *   `/api/exam/{exam_id}/question-outcomes`
    *   `/api/student/{student_id}/abet-scores?course_id={course_id}`
    *   `/api/batch-add-questions/{exam_id}`
    *   `/api/mass-associate-outcomes`
    *   `/api/update-question-outcome`
    *   `/api/course/{course_id}/achievement-levels`
*   **Use Cases:** LMS integration, custom dashboards, reporting tools.
    > **⚠️ Security:** No built-in authentication. Secure if exposed externally.

### Backup Database 💾

*   **Purpose:** Create safe copies of `accredit_data.db`.
*   **Features:** Custom descriptions, timestamps, history, download.
*   **When:** Before major changes, end of term, regularly.
*   **Access:** `Utilities` -> `Backup Database`.

### Restore Database 🔄

*   **Purpose:** Recover from a previous backup.
*   **Features:** View backups, auto-backup current DB before restore.
*   **When:** Data loss/corruption, rollback needed.
*   **Access:** `Utilities` -> `Restore Database`.

### Import Database 📥

*   **Purpose:** Merge data from backup files *without* replacing existing data.
*   **Features:** Select data types, preview changes, auto-backup before import, summary report.
*   **When:** Consolidating data, migrating courses from others.
*   **Access:** `Utilities` -> `Import Database`.

### Merge Courses ➕

*   **Purpose:** Combine data from multiple related courses into one.
*   **Features:** Merge students/scores/assessments, preview changes.
*   **When:** Combining sections, consolidating historical data.
*   **Access:** `Utilities` -> `Merge Courses`.

### System Logs 📜

*   **Purpose:** Track application activity and changes.
*   **Features:** Filter by action/date, export logs, color-coded actions (ADD, EDIT, DELETE, IMPORT, BACKUP/RESTORE, OTHER).
*   **When:** Troubleshooting, auditing changes.
*   **Access:** `Utilities` -> `System Logs`.

### Support & Feedback 💬

*   **Purpose:** Report issues, request features, get help.
*   **Access:** `Utilities` -> `Support & Feedback` or `Help` -> `Contact & Support`. See [Contact Section](#contact--support-).

---

## Remote Access Guide (Cloudflare Tunnel) ☁️

Access Accredit Helper Pro securely from anywhere.

### About Remote Access

Uses Cloudflare Tunnel (`cloudflared`) to create a secure link from your local app to the internet via a temporary public URL. Benefits include easy sharing and no network configuration.

### Installation Guide

Install the `cloudflared` client:

*   **Windows:** Download `.msi` or `.exe` from [Cloudflare Releases](https://github.com/cloudflare/cloudflared/releases). Run installer. Verify with `cloudflared --version` in Command Prompt.
*   **macOS:** Use Homebrew: `brew install cloudflare/cloudflare/cloudflared`. Or download package from releases. Verify with `cloudflared --version` in Terminal.
*   **Linux (Debian/Ubuntu):**
    ```bash
    curl -L https://pkg.cloudflare.com/cloudflared-stable-linux-amd64.deb -o cloudflared.deb
    sudo dpkg -i cloudflared.deb
    ```
    Verify with `cloudflared --version`. Check releases page for other distros.

> **⚠️ Important:** `cloudflared` needs to be in your system's PATH. Restart might be needed.

### Using Remote Access

1.  **Start with Cloudflare:**
    *   **Windows:** Use `Windows_Start_CloudFlare_Public_Url.bat`.
    *   **Command Line (All OS):**
        ```bash
        # Navigate to app directory, activate venv if needed
        python app.py --cloud
        ```
2.  **Get URL:** Console displays a public URL like `https://random-words.trycloudflare.com`.
3.  **Access/Share:** Use this URL from any device. It's active only while your app runs.

> **🛡️ Security Note:** Anyone with the URL can access the app while it's running. Share carefully. Close the app to deactivate the URL.

### Troubleshooting Remote Access

*   **\"cloudflared is not installed\" error:** Verify installation and PATH. Restart.
*   **No public URL displayed:** Check `--cloud` flag, look for console errors, check firewall, test manually (`cloudflared tunnel --url http://localhost:5000`).
*   **Can't connect via URL:** Check app is running, verify URL, check remote internet, try new URL (restart app).
*   **Slow remote performance:** Normal to some extent. Check local upload speed. Use locally for heavy tasks.

---

## Troubleshooting Guide 🐛

Common issues and solutions.

### Database & File Issues

*   **Backup/Restore Fails:** Check permissions, disk space, file integrity. Run with admin rights if needed. Ensure compatible app versions for restore.
*   **File System Errors (Save Fails):** Check disk space, write permissions for `instance` folder.
*   **Database Locked (`OperationalError: database is locked`):** Ensure only one app instance runs. Close external DB browser tools accessing `accredit_data.db`. Check permissions.
*   **Missing/Unexpected Data:** Accidental deletion (check logs, restore backup)? Wrong DB file active? Import issues (restore pre-import backup)?

### Calculation & Results Issues

*   **Unexpected Results:** Missing Q->CO links? Missing CO->PO links? Incorrect Exam Weights (must sum to 100)? Missing Scores? Wrong Success Rate Method (check Course Settings)? Student Exclusion (manual or mandatory)?
*   **Calculation Errors/Failures:** Division by zero (check question max scores > 0, students exist)? Inconsistent data structure (missing COs, exams, etc.)? Timeout (large courses - restart app)? Use Debug Calculations tool.

### Import/Export & Data Transfer Issues

*   **Student Import Problems:** Incorrect format (check preview)? Duplicate IDs? File Encoding (use UTF-8)?
*   **Database Merge/Import Issues:** Incompatible versions? ID conflicts? Always backup before merging/importing.
*   **Export Problems:** Browser blocking downloads? File permission issues? No data to export (check filters)?

### Performance & Responsiveness Issues

*   **Slow Application:** Large database (archive old courses)? Low system resources (RAM/CPU)? Browser issues (clear cache, try different browser)?
*   **Slow Score Entry Grid:** Use exam-specific view for large classes. Enter scores in batches. Try Chrome.

### Troubleshooting & Common Issues

*   **Application Won't Start:** Missing dependencies (reinstall `requirements.txt`)? DB corruption (move DB file, restore backup)? Port conflict (try `python app.py --port 5001`)?
*   **Charts Not Displaying:** Browser issues (try different browser, enable JS, clear cache)? Insufficient data? Network issues (remote access)? Check developer console for errors.
*   **Unexpected Error Messages:** Potential bug (report with details/screenshot)? Data format issue? Version mismatch (update app)?
