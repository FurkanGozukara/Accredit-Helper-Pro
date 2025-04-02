from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Create a db instance to be initialized later
db = SQLAlchemy()

# Association tables for many-to-many relationships
course_outcome_program_outcome = db.Table(
    'course_outcome_program_outcome',
    db.Column('course_outcome_id', db.Integer, db.ForeignKey('course_outcome.id'), primary_key=True),
    db.Column('program_outcome_id', db.Integer, db.ForeignKey('program_outcome.id'), primary_key=True)
)

question_course_outcome = db.Table(
    'question_course_outcome',
    db.Column('question_id', db.Integer, db.ForeignKey('question.id'), primary_key=True),
    db.Column('course_outcome_id', db.Integer, db.ForeignKey('course_outcome.id'), primary_key=True)
)

class Course(db.Model):
    """Course model representing a university/school course"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    exams = db.relationship('Exam', backref='course', lazy=True, cascade="all, delete-orphan")
    course_outcomes = db.relationship('CourseOutcome', backref='course', lazy=True, cascade="all, delete-orphan")
    students = db.relationship('Student', backref='course', lazy=True, cascade="all, delete-orphan")
    exam_weights = db.relationship('ExamWeight', backref='course', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Course {self.code}: {self.name}>"

class Exam(db.Model):
    """Exam model representing course assessments (midterm, final, homework, etc.)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    max_score = db.Column(db.Numeric(10, 2), nullable=False, default=100.0)
    exam_date = db.Column(db.Date, nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    is_makeup = db.Column(db.Boolean, default=False)
    makeup_for = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=True)
    
    # Relationships
    questions = db.relationship('Question', backref='exam', lazy=True, cascade="all, delete-orphan")
    scores = db.relationship('Score', backref='exam', lazy=True, cascade="all, delete-orphan")
    makeup_exam = db.relationship('Exam', backref=db.backref('original_exam', uselist=False), 
                                  remote_side=[id], uselist=False)
    
    def __repr__(self):
        return f"<Exam {self.name} for Course {self.course_id}>"

class ExamWeight(db.Model):
    """ExamWeight model for storing the weight of each exam type in the final calculation"""
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    weight = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationship
    exam = db.relationship('Exam', foreign_keys=[exam_id])
    
    def __repr__(self):
        return f"<ExamWeight {self.weight} for Exam {self.exam_id}>"

class CourseOutcome(db.Model):
    """CourseOutcome model representing learning outcomes for a course"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    program_outcomes = db.relationship('ProgramOutcome', secondary=course_outcome_program_outcome, 
                                      lazy='subquery', backref=db.backref('course_outcomes', lazy=True))
    questions = db.relationship('Question', secondary=question_course_outcome, 
                               lazy='subquery', backref=db.backref('course_outcomes', lazy=True))
    
    def __repr__(self):
        return f"<CourseOutcome {self.code} for Course {self.course_id}>"

class ProgramOutcome(db.Model):
    """ProgramOutcome model representing program-level learning outcomes"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<ProgramOutcome {self.code}>"

class Question(db.Model):
    """Question model representing exam questions"""
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=True)
    number = db.Column(db.Integer, nullable=False)
    max_score = db.Column(db.Numeric(10, 2), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    scores = db.relationship('Score', backref='question', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Question {self.number} for Exam {self.exam_id}>"

class Student(db.Model):
    """Student model representing students enrolled in a course"""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    scores = db.relationship('Score', backref='student', lazy=True, cascade="all, delete-orphan")
    
    # Add a unique constraint to ensure student_id is unique per course
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id', name='_student_course_uc'),)
    
    def __repr__(self):
        return f"<Student {self.student_id}: {self.first_name} {self.last_name}>"

class Score(db.Model):
    """Score model representing a student's score on a specific question of an exam"""
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Numeric(10, 2), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Score {self.score} for Student {self.student_id} on Question {self.question_id}>"

class Log(db.Model):
    """Log model for activity logging"""
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Log {self.action} at {self.timestamp}>" 