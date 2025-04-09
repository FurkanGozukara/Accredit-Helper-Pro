#  Accredit Helper Pro  Accreditation & Assessment Management Tool 📊🎓

Welcome to Accredit Helper Pro, your comprehensive tool for managing course data, tracking student performance against learning outcomes, and streamlining the accreditation process.

---

## Table of Contents

*   [ℹ️ Overview](#️-overview)
*   [🚀 Getting Started](#-getting-started)
*   [📚 Courses](#-courses)
*   [🎯 Outcomes (POs & COs)](#-outcomes-pos--cos)
*   [📄 Exams & Questions](#-exams--questions)
*   [🎓 Students & Scores](#-students--scores)
*   [🧮 Accredit Calculations](#-accredit-calculations)
*   [🛠️ Utilities](#️-utilities)
*   [☁️ Remote Access (Cloudflared)](#️-remote-access-cloudflared)
*   [🔧 Troubleshooting](#️-troubleshooting)
*   [🛡️ Privacy Policy](#️-privacy-policy)
*   [⚖️ Terms of Use](#️-terms-of-use)
*   [✉️ Contact & Support](#️-contact--support)

---

## ℹ️ Overview

Accredit Helper Pro is designed to assist educational institutions, particularly engineering programs, in managing the data required for accreditation processes like MÜDEK (Association for Evaluation and Accreditation of Engineering Programs) in Turkey or ABET internationally. It focuses on tracking student performance against defined Program Outcomes (POs) and Course Outcomes (COs).

> [!NOTE]
> **What is Accreditation?** Accreditation is a quality assurance process where educational institutions demonstrate they meet established standards. This application aids in the assessment component by tracking how well students achieve program learning outcomes through course assessments.

### ⭐ Key Features

**Core Functionality:**

*   **Program Outcomes (PO):** Define high-level program goals aligned with accreditation criteria.
*   **Course Outcomes (CO):** Create measurable, course-specific outcomes linked to POs.
*   **Exam Management:** Organize assessments (exams, quizzes, projects) with flexible weighting.
*   **Question-Outcome Mapping:** Link individual assessment questions to specific COs.
*   **Student Management:** Import and track individual students across course instances.
*   **Score Tracking:** Record student performance on each question with auto-save.
*   **Automated Calculations:** Generate precise outcome achievement metrics (Absolute & Relative methods).
*   **Reporting:** Create accreditation-ready reports and data exports (PDF, CSV/Excel).

**Advanced Features:**

*   **Attendance Tracking:** Record and import student attendance for exams.
*   **Student Exclusion Control:** Manually include/exclude students from calculations.
*   **Makeup Exams:** Support for makeup exams with automatic weight inheritance.
*   **Mandatory Exams:** Flag critical exams to ensure calculations reflect active participation.
*   **Custom Achievement Levels:** Define performance bands (e.g., Excellent, Good).
*   **Data Management:** Backup, restore, merge, and import database utilities.
*   **Course Duplication:** Quickly set up new course instances from templates.
*   **Batch Operations:** Efficiently add/manage questions, outcomes, students, and attendance.
*   **Mass Association Tool:** Quickly link many questions to outcomes using simple syntax.
*   **Activity Logging:** Track significant user actions within the system.
*   **AJAX Interface:** Responsive UI for score entry and attendance.
*   **Secure Remote Access:** Integrated Cloudflare Tunnel support.
*   **API Integration:** Access data programmatically via REST endpoints.
*   **Multi-course Analysis:** Analyze POs across all courses with optimized performance.
*   **Data Visualization:** View interactive charts for outcome achievement.
*   **Detailed Exports:** Export student scores, exam structures, and calculation data.

### ⚡ Recent Performance Improvements

> [!TIP]
> **Optimized Calculation System:**
> *   🚀 **Faster Multi-Course Analysis:** Significant speed improvements for program-wide results.
> *   💾 **Efficient Resource Usage:** Minimized database queries for large datasets.
> *   🔄 **Consistent Makeup Handling:** Enhanced synchronization of makeup exam weights.
> *   🧑‍⚖️ **Standardized Exclusion:** Improved logic for mandatory exam attendance handling.
> *   ✅ **Enhanced Attendance:** AJAX-based tracking with bulk import/export.
> *   🌐 **Robust Remote Access:** Improved Cloudflare Tunnel integration.

### 🧑‍🏫 Who Should Use This Application?

*   **Faculty Members:** Track student performance and outcome achievement in their courses.
*   **Department Chairs:** Aggregate and analyze program-wide outcome data.
*   **Accreditation Coordinators:** Prepare comprehensive reports and documentation.
*   **Assessment Committees:** Monitor and improve educational quality.
*   **Program Administrators:** Oversee continuous improvement processes.

### ⚙️ Technical Architecture

*   **Backend:** Python Flask framework with SQLAlchemy ORM.
*   **Database:** SQLite (portable, file-based).
*   **Frontend:** Bootstrap 5 (responsive design).
*   **Security:** Input validation, protected file operations.
*   **Remote Access:** Cloudflare Tunnel integration.

> [!NOTE]
> **Navigation Tip:** Use the Table of Contents above or scroll through this document. If you're new, start with the [🚀 Getting Started](#-getting-started) section.

---

## 🚀 Getting Started

Follow this comprehensive workflow to set up and use Accredit Helper Pro effectively.

> [!IMPORTANT]
> **Before You Begin:** Ensure the application is installed and running (typically at `http://localhost:5000`). Refer to the installation guide if needed.

### 🗺️ Understanding the Data Hierarchy

Data is organized hierarchically:

*   **Program Outcomes (POs):** High-level goals (shared across courses).
*   **Courses:** Specific instances (e.g., CENG301 Fall 2023).
    *   **Course Outcomes (COs):** Course-specific goals, linked to POs.
    *   **Exams:** Assessments within a course (Midterm, Final, Project).
        *   **Questions:** Individual items on an exam, linked to COs.
    *   **Students:** Enrolled individuals.
        *   **Scores:** Performance on specific Questions.

### ✅ Step-by-Step Implementation Guide

Follow these steps for a typical course setup:

#### Step 1: Define Program Outcomes (POs)

POs are the foundation, representing program-level competencies.

1.  Navigate to `Utilities -> Program Outcomes` in the application.
2.  Review the pre-loaded default outcomes (based on Turkish engineering criteria).
3.  Edit existing or add new POs to match your program's requirements.
4.  Ensure each PO has a unique code (e.g., `PO1`) and a clear description.

> [!TIP]
> POs should align with your accreditation body's requirements (e.g., MÜDEK, ABET).

#### Step 2: Create a Course

Represent a specific offering of a course (e.g., CENG301 for Fall 2023).

1.  From the application's Homepage, click "Add Course".
2.  Enter **Course Code** (e.g., `CENG301`).
3.  Enter **Course Name** (e.g., `Software Engineering`).
4.  Enter **Semester** (e.g., `Fall 2023` or `2023-2024 Spring`).
5.  Click "Save Course".

> [!WARNING]
> Create a *separate* course instance for each semester or distinct section you teach.

#### Step 3: Define Course Outcomes (COs)

Specific, measurable learning objectives for *this* course, linked to POs.

1.  On the Course Detail page, find the "Course Outcomes" section.
2.  Click "Add Course Outcome".
3.  Enter **Course Outcome Code** (e.g., `CO1`).
4.  Write a clear, measurable **Description** (start with an action verb, e.g., "Design software systems...").
5.  **Critical:** Select the **Program Outcome(s) (POs)** this CO supports. *This link is essential.*
6.  Click "Save". Repeat for all COs (typically 5-10 per course).

> [!NOTE]
> **Example CO-PO Mapping:**
> *   CO1: "Apply software testing techniques..." -> maps to PO2, PO3
> *   CO2: "Communicate technical information..." -> maps to PO7

#### Step 4: Add Exams and Set Weights

Exams represent *all* assessed activities (tests, quizzes, projects, homework).

1.  On the Course Detail page, find the "Exams" section.
2.  Click "Add Exam".
3.  Enter a descriptive **Name** (e.g., `Midterm 1`, `Final Project`).
4.  Set **Max Score** (overall for the exam, e.g., `100`).
5.  Optionally set an **Exam Date**.
6.  Check relevant flags:
    *   `Is Final Exam?`: For the final examination.
    *   `Is Mandatory?`: If participation is required. (See [Mandatory Exam Logic](#-mandatory-exam-logic) below).
    *   `Is Makeup Exam?`: If it's a makeup. Select the original exam it replaces.
7.  Save the exam. Repeat for all assessments.

**Setting Exam Weights:**

1.  After adding all exams, click "Manage Weights" in the Exams section.
2.  Assign a percentage weight to each *non-makeup* exam (e.g., Midterm 1: 30%, Final: 40%).
3.  **Critical:** Weights must sum to exactly **100%**.
4.  Click "Save Weights".

> [!IMPORTANT]
> Exam weights determine each assessment's contribution to the final grade and outcome calculations. Makeup exams automatically inherit the weight of the original.

**Managing Makeup Exams:**

1.  Check "Is Makeup Exam?" and select the original exam when creating it.
2.  The system uses a student's makeup score if available; otherwise, it uses the original score.
3.  Use the "Fix Makeup Relations" button (in Exams section) if links become inconsistent.

#### Step 5: Add Questions & Link to Course Outcomes (COs)

Define individual items within each exam and link them to the COs they assess.

1.  Go to the Exam Detail page (click an exam name from the Course Detail page).
2.  Click "Add Question".
3.  Enter **Question Number** (e.g., `1`, `2a`).
4.  Optionally enter **Question Text**.
5.  Set **Max Score** for *this specific question* (e.g., `10`, `25`).
6.  **Critical:** Select the **Course Outcome(s) (COs)** this question assesses. *This mapping is fundamental.*
7.  Click "Save Question". Repeat for all questions in the exam.
8.  Repeat this process for all exams in the course.

> [!TIP]
> *   **Batch Operations:** Use "Batch Add Questions" on the Exam Detail page for efficiency.
> *   **Mass Association Tool:** See [Step 7](#step-7-advanced-feature-mass-association-tool) for quickly linking many questions to outcomes.
> *   For projects/essays, break down the rubric into multiple "questions" assessing different COs.

#### Step 6: Add Students to the Course

Populate the course with enrolled students.

*   **Method 1: Manual Entry:** (Course Detail -> Students -> Add Student) - Suitable for very small classes.
*   **Method 2: Batch Import (Recommended):** (Course Detail -> Students -> Import Students)
    *   Paste student list from text/spreadsheet. Supported formats:
        ```
        # Space/Tab Delimited
        11220030102  Name1  Surname
        11220030126  Name1 Name2  Surname
        ```
        ```
        # Semicolon Delimited
        11220030102;Name1;Surname
        11220030126;Name1 Name2;Surname
        ```
    *   Review the preview before confirming import.
*   **Method 3: CSV File Upload:** (Course Detail -> Students -> Import Students)
    *   Upload a CSV file with columns for ID, First Name, Last Name.

**Managing Student Exclusion:**

*   On the Course Detail page (Students list), use the "Exclude/Include" toggle next to a student's name to manually remove them from outcome calculations (e.g., late drops).
*   Students might also be *automatically* excluded based on [Mandatory Exam Logic](#-mandatory-exam-logic).

**Tracking Attendance:**

*   (Exam Detail -> Manage Attendance) - Optionally track attendance for each exam.
*   Attendance data can influence automatic exclusion based on mandatory exam settings.
*   Batch import/export of attendance is available.

> [!NOTE]
> You can export the student list as a CSV file anytime using the "Export Students" button.

#### Step 7: Enter Student Scores

Record performance on each question for every student.

1.  Access the score entry grid:
    *   Course Detail -> Students -> Enter/Edit Scores (shows all exams).
    *   Exam Detail -> Enter Scores (shows only that exam).
2.  The grid shows Students (rows) vs. Questions (columns).
3.  Enter the score for each student on each question. Must not exceed the question's Max Score.
4.  Scores **auto-save** as you move to the next cell (Tab, Enter, click).

> [!TIP]
> Use keyboard navigation (Tab, Shift+Tab, Arrows, Enter) for faster entry.

> [!WARNING]
> **Makeup Scores:** Only enter scores for students who took the *makeup*. Leave blank for others. The system handles the logic.

#### Step 7 (Advanced Feature): Mass Association Tool

Quickly link many questions to outcomes using text syntax.

1.  On the Exam Detail page, click "Mass Associate Outcomes".
2.  Enter associations in the text area using the format: `q#:oc#:oc#;q#:oc#;...`
    *   `q#`: Question number (e.g., `q1`).
    *   `oc#`: Course Outcome number (e.g., `oc1` for CO1).
    *   Use `:` to separate question from outcomes and list multiple outcomes.
    *   Use `;` to separate different question associations.
    *   Example: `q1:oc1:oc2;q2:oc3;q3:oc1:oc3:oc4;`
        *   Links Q1 to CO1 & CO2.
        *   Links Q2 to CO3.
        *   Links Q3 to CO1, CO3, & CO4.
3.  Click "Apply Associations".

> [!CAUTION]
> This tool **replaces** existing associations for the specified questions. Include *all* desired links in your syntax.

#### Step 8: Calculate Results & Generate Reports

Analyze outcome achievement and create reports.

1.  From the Course Detail page, click "Calculate Results".
2.  The system processes data based on CO-PO links, Question-CO links, scores, and weights.
3.  Review the results page:
    *   CO achievement percentages.
    *   PO contribution from this course.
    *   Student success rates.
    *   Interactive charts and graphs.
4.  Export results:
    *   **PDF Report:** Formatted summary for accreditation.
    *   **CSV/Excel:** Raw calculation data.
    *   **Student Score Export:** Detailed performance per student.
    *   **Detailed Exam Data Export:** Full exam structure, questions, outcomes, scores.

> [!NOTE]
> **Optional Configuration:** Before calculating, adjust Course Settings (via "Settings" button on Course Detail page):
> *   Define **Achievement Levels** (e.g., Excellent: 90-100%).
> *   Set **Success Rate Method** (Absolute vs. Relative). See [Outcome Calculation Methods](#outcome-calculation-methods).

#### Step 9: Use "All Courses" Analysis for Program-Wide Assessment

Aggregate results across multiple courses for program-level insights.

1.  Navigate to `Calculations -> All Courses`.
2.  The system processes all non-excluded courses and aggregates PO results.
3.  Sort courses, toggle calculation methods (Absolute/Relative).
4.  View the comprehensive PO achievement table.
5.  Export results for program-level accreditation reports.

> [!TIP]
> The "All Courses" analysis uses an optimized engine for significantly better performance with many courses.

### ⏱️ Quick Start for Returning Users

Setting up a new semester for an existing course:

1.  Use the **"Duplicate Course"** feature (on the original course's detail page).
2.  Update the Semester, review copied settings (COs, Exams, Questions, Weights).
3.  Import the new student list for the duplicated course.
4.  Enter scores throughout the semester.
5.  Calculate results periodically and at the end of the term.

---

## 📚 Courses

Courses are the central containers for all related assessment data.

### ➕ Creating & Managing Courses

*   **Adding:** Homepage -> "Add Course" button. Enter Code, Name, Semester, optional Course Weight (for program-level calculations, default 1.0).
*   **Editing:** Course Detail page -> "Edit" button in Overview section. Modify Code, Name, Semester, Weight.
*   **Deleting:** Course Detail page -> "Delete" button.
    > [!CAUTION]
    > Deleting a course **permanently removes all associated data** (exams, questions, outcomes, students, scores). The application prevents deletion if related data exists; you must delete dependents first or use the Merge utility. **Backup first!**

### 📊 Course Dashboard (Detail Page)

The central hub for managing a course instance. Key sections:

*   **Overview:** Basic info, Edit/Delete buttons, Timestamps.
*   **Course Outcomes (COs):** List, Add/Edit/Delete COs, View PO mappings.
*   **Exams:** List, Add/Edit/Delete Exams, Manage Weights, Access Score Entry, View Exam Types (Final, Makeup, Mandatory).
*   **Students:** List, Add/Edit/Delete Students, Import/Export, Enter Scores, Manage Exclusion.

### ⚖️ Managing Exam Weights

Define how assessments contribute to outcomes.

1.  Course Detail page -> Exams section -> "Manage Weights" button.
2.  Enter percentage weight for each *non-makeup* exam.
3.  **Critical:** Weights **must sum to 100%**. (If they don't, the system normalizes them during calculation, but setting them correctly is best practice).
4.  Save Weights.

> [!NOTE]
> Makeup exams automatically inherit the weight of the original exam.

### ⚙️ Course Settings

Customize calculations and display for this course.

1.  Course Detail page -> "Settings" button.
2.  Adjust settings:
    *   **Success Rate Method:**
        *   **Absolute:** Average score approach. Achievement = Average % score. Success = Score >= threshold (e.g., 60%).
        *   **Relative:** Threshold-based approach. Achievement = % of students achieving threshold. Success = Score >= threshold OR Score >= % of class average.
    *   **Achievement Levels:** Define custom performance bands (e.g., Excellent 90-100, Good 75-89.99) with names and colors. These appear in reports.
    *   **Exclude Course from Reports:** Check to omit this course from aggregated "All Courses" analysis (useful for old/experimental courses).
3.  Save Settings.

### ✨ Duplicating a Course

Quickly set up a new instance based on an existing one (ideal for subsequent semesters).

1.  Go to the detail page of the course to duplicate.
2.  Click "Duplicate Course".
3.  Enter New Code, Name, Semester, Weight.
4.  Select components to copy (COs, Exams structure, Questions, Weights, Settings are typically copied).
5.  Click "Duplicate".

> [!WARNING]
> Student data and scores are **never** copied. You must import a new student list.

### 🔍 Searching for Courses

1.  Go to the main "Courses" list page.
2.  Use the search box at the top.
3.  Search by Code, Name, or Semester (case-insensitive, partial match).

### 📤 Exporting Courses

Export a summary list of all courses.

1.  Go to the main "Courses" list page.
2.  Click the "Export" button.
3.  Downloads a CSV/Excel file with Code, Name, Semester, Weight, Student Count, Exam Count, CO Count for each course.

---

## 🎯 Outcomes (POs & COs)

Outcomes define what students should know and be able to do.

> [!NOTE]
> **Outcome-Based Education:** POs are program-wide, COs are course-specific.

### 🏛️ Program Outcomes (POs)

High-level competencies achieved by program completion (e.g., MÜDEK criteria).

*   **Manage POs:** `Utilities -> Program Outcomes`.
*   **View:** See list, codes, descriptions. Click "View" on a PO to see linked COs across courses.
*   **Add/Edit/Delete:** Use buttons on the Program Outcomes page.
    *   Requires unique Code and Description.
    *   Deleting a PO removes its links to COs. COs only linked to the deleted PO become "orphaned".

> [!TIP]
> Default POs based on Turkish engineering criteria are pre-loaded. Modify as needed.

**Example POs:**

| Code | Description                                                                                      |
| :--- | :----------------------------------------------------------------------------------------------- |
| PO1  | Ability to apply knowledge of mathematics, science, and engineering principles...              |
| PO2  | Ability to design and conduct experiments, analyze and interpret data...                       |
| PO3  | Ability to design a system, component, or process to meet desired needs within constraints... |

### 📋 Course Outcomes (COs)

Specific, measurable objectives for a *single course*, linked to POs.

*   **Manage COs:** On the Course Detail page -> "Course Outcomes" section.
*   **Add:** Click "Add Course Outcome". Enter Code, Description (action verb), and **select the PO(s) it supports**.
*   **View:** List shows Code, Description, linked POs. Click "View" on a CO for details and linked questions.
*   **Edit/Delete:** Use buttons next to each CO.
    *   Deleting a CO removes its links to Questions. Questions only linked to the deleted CO become "orphaned".

**Example COs & PO Mappings:**

| Code | Description                                                                   | Mapped to POs |
| :--- | :---------------------------------------------------------------------------- | :------------ |
| CO1  | Apply object-oriented design principles...                                    | PO1, PO3      |
| CO2  | Conduct software testing using appropriate methods...                         | PO2, PO4      |
| CO3  | Communicate software design decisions effectively through documentation...     | PO7           |
| CO4  | Work effectively in a team to develop a software project...                   | PO5, PO6      |

> [!IMPORTANT]
> Writing Effective COs: Use SMART criteria (Specific, Measurable, Achievable, Relevant, Time-bound). Start with action verbs (Analyze, Design, Evaluate).

### 🔗 Understanding the Outcome Hierarchy

Assessment flows from specific questions up to program-level goals:

```mermaid
graph TD
    A[Exam Questions] -->|assess| B(Course Outcomes COs);
    B -->|support| C(Program Outcomes POs);

    style A fill:#f8f9fa,stroke:#6c757d,stroke-width:2px
    style B fill:#e2f0e4,stroke:#28a745,stroke-width:2px
    style C fill:#ddeffd,stroke:#007bff,stroke-width:2px
