# --- START OF FILE models.py ---

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import Index # Import Index explicitly

# Create a db instance to be initialized later
db = SQLAlchemy()

def init_db_session(app):
    """Initialize SQLAlchemy with a scoped session to ensure the remove() method is available"""
    with app.app_context():
        engine = db.get_engine()
        session_factory = sessionmaker(bind=engine)
        db.session = scoped_session(session_factory)
        return db.session

# Association tables for many-to-many relationships
# Added individual and composite indexes
course_outcome_program_outcome = db.Table(
    'course_outcome_program_outcome',
    db.Column('course_outcome_id', db.Integer, db.ForeignKey('course_outcome.id'), primary_key=True),
    db.Column('program_outcome_id', db.Integer, db.ForeignKey('program_outcome.id'), primary_key=True),
    db.Column('relative_weight', db.Numeric(10, 2), nullable=False, default=1.0),  # New column for CO-PO weight
    Index('idx_co_po_co_id', 'course_outcome_id'),
    Index('idx_co_po_po_id', 'program_outcome_id'),
    Index('idx_co_po_combined', 'course_outcome_id', 'program_outcome_id')
)

question_course_outcome = db.Table(
    'question_course_outcome',
    db.Column('question_id', db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), primary_key=True), # Added ondelete cascade
    db.Column('course_outcome_id', db.Integer, db.ForeignKey('course_outcome.id', ondelete='CASCADE'), primary_key=True), # Added ondelete cascade
    db.Column('relative_weight', db.Numeric(10, 2), nullable=False, default=1.0), # New column for Q-CO weight
    Index('idx_qco_q_id', 'question_id'),
    Index('idx_qco_co_id', 'course_outcome_id'),
    Index('idx_qco_combined', 'question_id', 'course_outcome_id')
)

class Course(db.Model):
    """Course model representing a university/school course"""
    __tablename__ = 'course' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, index=True) # Indexed
    name = db.Column(db.String(100), nullable=False, index=True) # Indexed name for search
    semester = db.Column(db.String(20), nullable=False, index=True) # Indexed
    course_weight = db.Column(db.Numeric(10, 2), nullable=False, default=1.0, index=True) # Indexed weight
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships (Reverted lazy loading, kept cascades if they were likely intended/safe)
    exams = db.relationship('Exam', backref='course', lazy=True, cascade="all, delete-orphan")
    course_outcomes = db.relationship('CourseOutcome', backref='course', lazy=True, cascade="all, delete-orphan")
    students = db.relationship('Student', backref='course', lazy=True, cascade="all, delete-orphan")
    exam_weights = db.relationship('ExamWeight', backref='course', lazy=True, cascade="all, delete-orphan")
    settings = db.relationship('CourseSettings', backref='course', uselist=False, cascade="all, delete-orphan")
    achievement_levels = db.relationship('AchievementLevel', backref='course', lazy=True, cascade="all, delete-orphan")

    # Step 4 Optimization: Coverage indexes for bulk loading performance
    __table_args__ = (
        db.UniqueConstraint('code', 'semester', name='_code_semester_uc'),
        Index('idx_course_code_semester', 'code', 'semester'),
        # Step 4: Coverage index for bulk course loading
        Index('idx_course_coverage_bulk_load', 'id', 'code', 'name', 'semester', 'course_weight'),
    )

    def __repr__(self):
        return f"<Course {self.code}: {self.name}>"

class Exam(db.Model):
    """Exam model representing course assessments"""
    __tablename__ = 'exam'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True) # Indexed
    max_score = db.Column(db.Numeric(10, 2), nullable=False, default=100.0)
    exam_date = db.Column(db.Date, nullable=True, index=True) # Indexed date
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    is_makeup = db.Column(db.Boolean, default=False, nullable=False, index=True) # Indexed
    is_final = db.Column(db.Boolean, default=False, nullable=False, index=True) # Indexed
    makeup_for = db.Column(db.Integer, db.ForeignKey('exam.id', ondelete='SET NULL'), nullable=True, index=True) # Indexed FK
    is_mandatory = db.Column(db.Boolean, default=False, nullable=False, index=True) # Indexed

    # Relationships (Reverted lazy loading)
    questions = db.relationship('Question', backref='exam', lazy=True, cascade="all, delete-orphan")
    scores = db.relationship('Score', backref='exam', lazy=True, cascade="all, delete-orphan")
    # Use original_exam backref if your code relies on it
    original_exam = db.relationship('Exam', remote_side=[id], backref=db.backref('makeup_exam', uselist=False))
    attendances = db.relationship('StudentExamAttendance', backref='exam', lazy=True, cascade="all, delete-orphan")
    weights = db.relationship('ExamWeight', backref='exam', lazy=True, cascade="all, delete-orphan")

    # Composite indexes for performance + Step 4 optimizations
    __table_args__ = (
        Index('idx_exam_course_makeup', 'course_id', 'is_makeup'),
        Index('idx_exam_course_mandatory', 'course_id', 'is_mandatory'),
        Index('idx_exam_course_name', 'course_id', 'name'),
        Index('idx_exam_course_final', 'course_id', 'is_final'),
        # Step 4: Coverage index for bulk exam loading
        Index('idx_exam_bulk_load_coverage', 'course_id', 'id', 'is_makeup', 'is_mandatory', 'name'),
    )

    def __repr__(self):
        return f"<Exam {self.name} for Course {self.course_id}>"

class ExamWeight(db.Model):
    """ExamWeight model"""
    __tablename__ = 'exam_weight'
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    weight = db.Column(db.Numeric(10, 4), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Composite index for performance + Step 4 optimizations
    __table_args__ = (
        Index('idx_exam_weight_exam_course', 'exam_id', 'course_id'),
        # Step 4: Coverage index for exam weight lookups
        Index('idx_exam_weight_bulk_lookup', 'course_id', 'exam_id', 'weight'),
    )

    def __repr__(self):
        return f"<ExamWeight {self.weight} for Exam {self.exam_id}>"

class CourseOutcome(db.Model):
    """CourseOutcome model"""
    __tablename__ = 'course_outcome'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, index=True) # Indexed
    description = db.Column(db.Text, nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships (Kept subquery for many-to-many, reverted backref lazy)
    program_outcomes = db.relationship('ProgramOutcome', secondary=course_outcome_program_outcome,
                                      lazy='subquery', backref=db.backref('course_outcomes', lazy=True))
    questions = db.relationship('Question', secondary=question_course_outcome,
                               lazy='subquery', backref=db.backref('course_outcomes', lazy=True))

    # Composite index + Step 4 optimizations
    __table_args__ = (
        Index('idx_course_outcome_course_code', 'course_id', 'code'),
        # Step 4: Optimized index for course outcome bulk loading
        Index('idx_course_outcome_bulk_load', 'course_id', 'code', 'id'),
    )

    def __repr__(self):
        return f"<CourseOutcome {self.code} for Course {self.course_id}>"

class ProgramOutcome(db.Model):
    """ProgramOutcome model"""
    __tablename__ = 'program_outcome'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, unique=True, index=True) # Indexed, kept unique
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<ProgramOutcome {self.code}>"

class Question(db.Model):
    """Question model"""
    __tablename__ = 'question'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=True)
    number = db.Column(db.Integer, nullable=False, index=True) # Indexed
    max_score = db.Column(db.Numeric(10, 2), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships (Reverted lazy loading)
    scores = db.relationship('Score', backref='question', lazy=True, cascade="all, delete-orphan")
    # (relationship to course_outcomes defined via secondary table)

    # Composite index + Step 4 optimizations
    __table_args__ = (
        Index('idx_question_exam_number', 'exam_id', 'number'),
        # Step 4: Coverage index for question bulk loading with ordering
        Index('idx_question_exam_bulk_load', 'exam_id', 'number', 'id', 'max_score'),
    )

    def __repr__(self):
        return f"<Question {self.number} for Exam {self.exam_id}>"

class Student(db.Model):
    """Student model"""
    __tablename__ = 'student'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), nullable=False, index=True) # Indexed
    first_name = db.Column(db.String(50), nullable=False, index=True) # Indexed name
    last_name = db.Column(db.String(50), nullable=True) # Allow null last names
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    excluded = db.Column(db.Boolean, default=False, nullable=False, index=True) # Indexed

    # Relationships (Reverted lazy loading)
    scores = db.relationship('Score', backref='student', lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship('StudentExamAttendance', backref='student', lazy=True, cascade="all, delete-orphan")

    # Performance indexes + Step 4 optimizations
    __table_args__ = (
        db.UniqueConstraint('student_id', 'course_id', name='_student_course_uc'),
        Index('idx_student_course_student_id', 'course_id', 'student_id'), # Performance index
        Index('idx_student_course_excluded', 'course_id', 'excluded'), # Performance index
        # Step 4: Optimized index for student filtering in bulk operations
        Index('idx_student_bulk_load_optimized', 'course_id', 'excluded', 'id', 'student_id'),
    )

    def __repr__(self):
        return f"<Student {self.student_id}: {self.first_name} {self.last_name}>"

class Score(db.Model):
    """Score model"""
    __tablename__ = 'score'
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Numeric(10, 2), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Composite indexes for performance + Step 4 optimizations
    __table_args__ = (
        Index('idx_score_student_exam_question', 'student_id', 'exam_id', 'question_id'),
        Index('idx_score_exam_question_student', 'exam_id', 'question_id', 'student_id'),
        # Step 4: Coverage index for score lookups (includes score value for covering index)
        Index('idx_score_bulk_lookup_optimized', 'student_id', 'exam_id', 'question_id', 'score'),
        # Step 4: Index for score statistics and range queries
        Index('idx_score_statistics', 'exam_id', 'score'),
    )

    def __repr__(self):
        return f"<Score {self.score} for Student {self.student_id} on Question {self.question_id}>"

class Log(db.Model):
    """Log model"""
    __tablename__ = 'log'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False, index=True) # Indexed
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True) # Indexed

    def __repr__(self):
        return f"<Log {self.action} at {self.timestamp}>"

class CourseSettings(db.Model):
    """CourseSettings model"""
    __tablename__ = 'course_settings'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), nullable=False, unique=True, index=True) # Indexed FK, kept unique
    success_rate_method = db.Column(db.String(20), nullable=False, default='absolute')
    relative_success_threshold = db.Column(db.Numeric(10, 2), nullable=False, default=60.0)
    excluded = db.Column(db.Boolean, nullable=False, default=False, index=True) # Indexed
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Step 4 optimization: Index for filtering excluded courses
    __table_args__ = (
        Index('idx_course_settings_filtering', 'excluded', 'course_id'),
    )

    def __repr__(self):
        return f"<CourseSettings for Course {self.course_id}>"

class AchievementLevel(db.Model):
    """AchievementLevel model"""
    __tablename__ = 'achievement_level'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    name = db.Column(db.String(50), nullable=False)
    min_score = db.Column(db.Numeric(10, 2), nullable=False, index=True) # Indexed
    max_score = db.Column(db.Numeric(10, 2), nullable=False, index=True) # Indexed
    color = db.Column(db.String(20), nullable=False, default='primary')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Composite index for performance
    __table_args__ = (
        Index('idx_achievement_level_course_min_max', 'course_id', 'min_score', 'max_score'),
    )

    def __repr__(self):
        return f"<AchievementLevel {self.name} ({self.min_score}-{self.max_score}%) for Course {self.course_id}>"

class GlobalAchievementLevel(db.Model):
    """Global Achievement Level model for all courses page"""
    __tablename__ = 'global_achievement_level'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    min_score = db.Column(db.Numeric(10, 2), nullable=False, index=True) # Indexed
    max_score = db.Column(db.Numeric(10, 2), nullable=False, index=True) # Indexed
    color = db.Column(db.String(20), nullable=False, default='primary')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<GlobalAchievementLevel {self.name} ({self.min_score}-{self.max_score}%)>"

class StudentExamAttendance(db.Model):
    """Model to track student attendance"""
    __tablename__ = 'student_exam_attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id', ondelete='CASCADE'), nullable=False, index=True) # Indexed FK
    attended = db.Column(db.Boolean, default=True, nullable=False, index=True) # Indexed
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Composite index + Step 4 optimizations
    __table_args__ = (
        Index('idx_attendance_student_exam', 'student_id', 'exam_id'),
        # Step 4: Coverage index for attendance lookups
        Index('idx_attendance_bulk_lookup', 'student_id', 'exam_id', 'attended'),
        # Original had unique constraint _student_exam_attendance_uc, keep if necessary
        # db.UniqueConstraint('student_id', 'exam_id', name='_student_exam_attendance_uc'),
    )

    def __repr__(self):
        attendance_status = "attended" if self.attended else "did not attend"
        return f"<StudentExamAttendance: Student {self.student_id} {attendance_status} Exam {self.exam_id}>"

class GraduatingStudent(db.Model):
    """Simple model to track student IDs that will graduate (for MÜDEK filtering)"""
    __tablename__ = 'graduating_student'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), nullable=False, unique=True, index=True)  # Unique student ID
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Performance index for fast lookups
    __table_args__ = (
        Index('idx_graduating_student_student_id', 'student_id'),
    )
    
    def __repr__(self):
        return f"<GraduatingStudent {self.student_id}>"

# --- END OF FILE models.py ---