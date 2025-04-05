from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Create a db instance to be initialized later
db = SQLAlchemy()

# Association tables for many-to-many relationships
course_outcome_program_outcome = db.Table(
    'course_outcome_program_outcome',
    db.Column('course_outcome_id', db.Integer, db.ForeignKey('course_outcome.id'), primary_key=True, index=True),
    db.Column('program_outcome_id', db.Integer, db.ForeignKey('program_outcome.id'), primary_key=True, index=True),
    db.Index('idx_co_po_combined', 'course_outcome_id', 'program_outcome_id')
)

question_course_outcome = db.Table(
    'question_course_outcome',
    db.Column('question_id', db.Integer, db.ForeignKey('question.id'), primary_key=True, index=True),
    db.Column('course_outcome_id', db.Integer, db.ForeignKey('course_outcome.id'), primary_key=True, index=True),
    db.Index('idx_qco_combined', 'question_id', 'course_outcome_id')
)

class Course(db.Model):
    """Course model representing a university/school course"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.String(20), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    exams = db.relationship('Exam', backref='course', lazy=True, cascade="all, delete-orphan")
    course_outcomes = db.relationship('CourseOutcome', backref='course', lazy=True, cascade="all, delete-orphan")
    students = db.relationship('Student', backref='course', lazy=True, cascade="all, delete-orphan")
    exam_weights = db.relationship('ExamWeight', backref='course', lazy=True, cascade="all, delete-orphan")
    # Note: 'settings' backref is defined in CourseSettings model
    
    def __repr__(self):
        return f"<Course {self.code}: {self.name}>"

class Exam(db.Model):
    """Exam model representing course assessments (midterm, final, homework, etc.)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    max_score = db.Column(db.Numeric(10, 2), nullable=False, default=100.0)
    exam_date = db.Column(db.Date, nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    is_makeup = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_final = db.Column(db.Boolean, default=False, nullable=False, index=True)
    makeup_for = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=True, index=True)
    is_mandatory = db.Column(db.Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    questions = db.relationship('Question', backref='exam', lazy=True, cascade="all, delete-orphan")
    scores = db.relationship('Score', backref='exam', lazy=True, cascade="all, delete-orphan")
    makeup_exam = db.relationship('Exam', backref=db.backref('original_exam', uselist=False), 
                                  remote_side=[id], uselist=False)
    attendances = db.relationship('StudentExamAttendance', backref='exam', lazy=True, cascade="all, delete-orphan")
    
    # Add additional composite indexes
    __table_args__ = (
        db.Index('idx_exam_course_makeup', 'course_id', 'is_makeup'),
        db.Index('idx_exam_course_mandatory', 'course_id', 'is_mandatory'),
        db.Index('idx_exam_course_name', 'course_id', 'name'),
        db.Index('idx_exam_course_final', 'course_id', 'is_final'),
    )
    
    def __repr__(self):
        return f"<Exam {self.name} for Course {self.course_id}>"

class ExamWeight(db.Model):
    """ExamWeight model for storing the weight of each exam type in the final calculation"""
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    weight = db.Column(db.Numeric(10, 4), nullable=False)  # Increased precision to 4 decimal places
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationship
    exam = db.relationship('Exam', foreign_keys=[exam_id])
    
    # Add compound index for exam_id + course_id
    __table_args__ = (db.Index('idx_exam_weight_exam_course', 'exam_id', 'course_id'),)
    
    def __repr__(self):
        return f"<ExamWeight {self.weight} for Exam {self.exam_id}>"

class CourseOutcome(db.Model):
    """CourseOutcome model representing learning outcomes for a course"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    program_outcomes = db.relationship('ProgramOutcome', secondary=course_outcome_program_outcome, 
                                      lazy='subquery', backref=db.backref('course_outcomes', lazy=True))
    questions = db.relationship('Question', secondary=question_course_outcome, 
                               lazy='subquery', backref=db.backref('course_outcomes', lazy=True))
    
    # Add more specific composite indexes for relationship lookups
    __table_args__ = (
        db.Index('idx_course_outcome_code_course', 'code', 'course_id'),
        db.Index('idx_course_outcome_course_created', 'course_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<CourseOutcome {self.code} for Course {self.course_id}>"

class ProgramOutcome(db.Model):
    """ProgramOutcome model representing program-level learning outcomes"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<ProgramOutcome {self.code}>"

class Question(db.Model):
    """Question model representing exam questions"""
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=True)
    number = db.Column(db.Integer, nullable=False, index=True)
    max_score = db.Column(db.Numeric(10, 2), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    scores = db.relationship('Score', backref='question', lazy=True, cascade="all, delete-orphan")
    
    # Add compound index for exam_id + number for ordering
    __table_args__ = (db.Index('idx_question_exam_number', 'exam_id', 'number'),)
    
    def __repr__(self):
        return f"<Question {self.number} for Exam {self.exam_id}>"

class Student(db.Model):
    """Student model representing students enrolled in a course"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), nullable=False, index=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    excluded = db.Column(db.Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    scores = db.relationship('Score', backref='student', lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship('StudentExamAttendance', backref='student', lazy=True, cascade="all, delete-orphan")
    
    # Add a unique constraint to ensure student_id is unique per course
    __table_args__ = (
        db.UniqueConstraint('student_id', 'course_id', name='_student_course_uc'),
        db.Index('idx_student_course_student_id', 'course_id', 'student_id'),
        db.Index('idx_student_excluded', 'excluded'),
    )
    
    def __repr__(self):
        return f"<Student {self.student_id}: {self.first_name} {self.last_name}>"

class Score(db.Model):
    """Score model representing a student's score on a specific question of an exam"""
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Numeric(10, 2), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False, index=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Add comprehensive compound indexes for all common query patterns
    __table_args__ = (
        db.Index('idx_score_student_exam', 'student_id', 'exam_id'),
        db.Index('idx_score_student_question_exam', 'student_id', 'question_id', 'exam_id'),
        db.Index('idx_score_exam_question', 'exam_id', 'question_id'),
        db.Index('idx_score_student_question', 'student_id', 'question_id'),
    )
    
    def __repr__(self):
        return f"<Score {self.score} for Student {self.student_id} on Question {self.question_id}>"

class Log(db.Model):
    """Log model for activity logging"""
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)
    
    def __repr__(self):
        return f"<Log {self.action} at {self.timestamp}>"

class CourseSettings(db.Model):
    """CourseSettings model for storing course-specific settings like success rate calculation method"""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    success_rate_method = db.Column(db.String(20), nullable=False, default='absolute')  # 'absolute' or 'relative'
    relative_success_threshold = db.Column(db.Numeric(10, 2), nullable=False, default=60.0)
    excluded = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationship
    course = db.relationship('Course', backref=db.backref('settings', uselist=False, cascade="all, delete-orphan"), lazy=True)
    
    def __repr__(self):
        return f"<CourseSettings for Course {self.course_id}>"

class AchievementLevel(db.Model):
    """AchievementLevel model for storing custom success metrics for courses"""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    min_score = db.Column(db.Numeric(10, 2), nullable=False)
    max_score = db.Column(db.Numeric(10, 2), nullable=False)
    color = db.Column(db.String(20), nullable=False, default='primary')  # Bootstrap color class
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationship
    course = db.relationship('Course', backref=db.backref('achievement_levels', lazy=True, cascade="all, delete-orphan"))
    
    def __repr__(self):
        return f"<AchievementLevel {self.name} ({self.min_score}-{self.max_score}%) for Course {self.course_id}>"

class StudentExamAttendance(db.Model):
    """Model to track whether a student attended an exam"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, index=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False, index=True)
    attended = db.Column(db.Boolean, default=True, nullable=False)  # Default is that student attended
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Add unique constraint to ensure one attendance record per student per exam
    __table_args__ = (
        db.UniqueConstraint('student_id', 'exam_id', name='_student_exam_attendance_uc'),
        db.Index('idx_attendance_student_exam', 'student_id', 'exam_id'),
    )
    
    def __repr__(self):
        attendance_status = "attended" if self.attended else "did not attend"
        return f"<StudentExamAttendance: Student {self.student_id} {attendance_status} Exam {self.exam_id}>" 