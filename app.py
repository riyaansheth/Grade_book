from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
from io import BytesIO
import base64
from abc import ABC, abstractmethod
import os

#exceptions
class DatabaseError(Exception):
    """Base class for database-related exceptions"""
    pass

class DeleteError(DatabaseError):
    """Exception raised when deletion fails due to related records"""
    def __init__(self, entity_type, message):
        self.entity_type = entity_type
        self.message = message
        super().__init__(f"Cannot delete {entity_type}: {message}")

class ValidationError(Exception):
    """Exception raised for validation errors"""
    pass

#abstract base classs
class BaseEntity:
    def validate(self):
        """Validate the entity's data"""
        pass

    @classmethod
    def get_all(cls):
        """Get all instances of the entity"""
        return cls.query.all()

    @classmethod
    def get_by_id(cls, id):
        """Get entity by ID"""
        return cls.query.get_or_404(id)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'andestie.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

@app.route('/')
def index():
    return redirect(url_for('students'))

#db models
class Student(db.Model, BaseEntity):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    roll_number = db.Column(db.String(20), unique=True, nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    grades = db.relationship('Grade', backref='student', lazy=True)

    def validate(self):
        if not self.name or not self.roll_number or not self.class_name:
            raise ValidationError("All fields are required")
        if len(self.roll_number) < 3:
            raise ValidationError("Roll number must be at least 3 characters")

    @classmethod
    def get_by_roll_number(cls, roll_number):
        return cls.query.filter_by(roll_number=roll_number).first()

class Subject(db.Model, BaseEntity):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grades = db.relationship('Grade', backref='subject', lazy=True)

    def validate(self):
        if not self.name:
            raise ValidationError("Subject name is required")
        if len(self.name) < 2:
            raise ValidationError("Subject name must be at least 2 characters")

    @classmethod
    def get_by_name(cls, name):
        return cls.query.filter_by(name=name).first()

class Grade(db.Model, BaseEntity):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    grade_value = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def validate(self):
        if not 0 <= self.grade_value <= 100:
            raise ValidationError("Grade must be between 0 and 100")
        if not self.category:
            raise ValidationError("Category is required")

    @classmethod
    def get_student_grades(cls, student_id):
        return cls.query.filter_by(student_id=student_id).all()

    @classmethod
    def get_subject_grades(cls, subject_id):
        return cls.query.filter_by(subject_id=subject_id).all()

#student routes
@app.route('/students')
def students():
    students = Student.query.all()
    return render_template('students.html', students=students)

@app.route('/students/add', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        roll_number = request.form['roll_number']
        class_name = request.form['class_name']
        
        # Check if roll number already exists
        existing_student = Student.query.filter_by(roll_number=roll_number).first()
        if existing_student:
            flash('Roll number already exists!', 'danger')
            return redirect(url_for('add_student'))
        
        new_student = Student(name=name, roll_number=roll_number, class_name=class_name)
        db.session.add(new_student)
        db.session.commit()
        flash('Student added successfully!', 'success')
        return redirect(url_for('students'))
    
    return render_template('student_form.html')

@app.route('/students/edit/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        student.name = request.form['name']
        student.roll_number = request.form['roll_number']
        student.class_name = request.form['class_name']
        
        # check if roll number already exists for another student
        existing_student = Student.query.filter(
            Student.roll_number == student.roll_number,
            Student.id != student.id
        ).first()
        
        if existing_student:
            flash('Roll number already exists!', 'danger')
            return redirect(url_for('edit_student', student_id=student_id))
        
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('students'))
    
    return render_template('student_form.html', student=student)

@app.route('/students/delete/<int:student_id>')
def delete_student(student_id):
    try:
        student = Student.get_by_id(student_id)
        
        if student.grades:
            raise DeleteError("student", "This student has grades associated with them. Please delete the grades first.")
            
        db.session.delete(student)
        db.session.commit()
        flash('Student deleted successfully!', 'success')
    except DeleteError as e:
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting the student: {str(e)}', 'danger')
    
    return redirect(url_for('students'))

#subject Routes
@app.route('/subjects')
def subjects():
    subjects = Subject.query.all()
    return render_template('subjects.html', subjects=subjects)

@app.route('/subjects/add', methods=['GET', 'POST'])
def add_subject():
    if request.method == 'POST':
        name = request.form['name']
        
        #check if subject already exists
        existing_subject = Subject.query.filter_by(name=name).first()
        if existing_subject:
            flash('Subject already exists!', 'danger')
            return redirect(url_for('add_subject'))
        
        new_subject = Subject(name=name)
        db.session.add(new_subject)
        db.session.commit()
        flash('Subject added successfully!', 'success')
        return redirect(url_for('subjects'))
    
    return render_template('subject_form.html')

@app.route('/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    
    if request.method == 'POST':
        subject.name = request.form['name']
        
        #ccheck if subject name already exists for another subject
        existing_subject = Subject.query.filter(
            Subject.name == subject.name,
            Subject.id != subject.id
        ).first()
        
        if existing_subject:
            flash('Subject name already exists!', 'danger')
            return redirect(url_for('edit_subject', subject_id=subject_id))
        
        db.session.commit()
        flash('Subject updated successfully!', 'success')
        return redirect(url_for('subjects'))
    
    return render_template('subject_form.html', subject=subject)

@app.route('/subjects/delete/<int:subject_id>')
def delete_subject(subject_id):
    try:
        subject = Subject.get_by_id(subject_id)
        
        if subject.grades:
            raise DeleteError("subject", "This subject has grades associated with it. Please delete the grades first.")
            
        db.session.delete(subject)
        db.session.commit()
        flash('Subject deleted successfully!', 'success')
    except DeleteError as e:
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting the subject: {str(e)}', 'danger')
    
    return redirect(url_for('subjects'))

# graade Routes
@app.route('/grades')
def grades():
    grades = Grade.query.all()
    return render_template('grades.html', grades=grades)

@app.route('/grades/add', methods=['GET', 'POST'])
def add_grade():
    if request.method == 'POST':
        student_id = request.form['student_id']
        subject_id = request.form['subject_id']
        grade_value = float(request.form['grade_value'])
        category = request.form['category']
        
        new_grade = Grade(
            student_id=student_id,
            subject_id=subject_id,
            grade_value=grade_value,
            category=category
        )
        db.session.add(new_grade)
        db.session.commit()
        flash('Grade added successfully!', 'success')
        return redirect(url_for('grades'))
    
    students = Student.query.all()
    subjects = Subject.query.all()
    return render_template('grade_form.html', students=students, subjects=subjects)

@app.route('/grades/edit/<int:grade_id>', methods=['GET', 'POST'])
def edit_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    
    if request.method == 'POST':
        grade.student_id = request.form['student_id']
        grade.subject_id = request.form['subject_id']
        grade.grade_value = float(request.form['grade_value'])
        grade.category = request.form['category']
        
        db.session.commit()
        flash('Grade updated successfully!', 'success')
        return redirect(url_for('grades'))
    
    students = Student.query.all()
    subjects = Subject.query.all()
    return render_template('grade_form.html', grade=grade, students=students, subjects=subjects)

@app.route('/grades/delete/<int:grade_id>')
def delete_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    db.session.delete(grade)
    db.session.commit()
    flash('Grade deleted successfully!', 'success')
    return redirect(url_for('grades'))

#analytics Routes
@app.route('/analytics')
def analytics():
    #get all grades
    grades = Grade.query.all()
    
    #calculate averages
    subject_avg = {}
    student_avg = {}
    
    #group grades by subject
    subject_grades = {}
    for grade in grades:
        subject_name = grade.subject.name
        if subject_name not in subject_grades:
            subject_grades[subject_name] = []
        subject_grades[subject_name].append(grade.grade_value)
    
    #calculate subject averages
    for subject, grades_list in subject_grades.items():
        subject_avg[subject] = sum(grades_list) / len(grades_list)
    
    #group grades by student
    student_grades = {}
    for grade in grades:
        student_name = grade.student.name
        if student_name not in student_grades:
            student_grades[student_name] = []
        student_grades[student_name].append(grade.grade_value)
    
    #calculate student averages
    for student, grades_list in student_grades.items():
        student_avg[student] = sum(grades_list) / len(grades_list)
    
    return render_template('analytics.html', 
                         subject_avg=subject_avg,
                         student_avg=student_avg)

#repport Generation Routes
@app.route('/reports/students')
def student_report():
    students = Student.query.all()
    data = []
    for student in students:
        grades = Grade.query.filter_by(student_id=student.id).all()
        total_grades = len(grades)
        if total_grades > 0:
            avg_grade = sum(g.grade_value for g in grades) / total_grades
        else:
            avg_grade = 0
        
        data.append({
            'Name': student.name,
            'Roll Number': student.roll_number,
            'Class': student.class_name,
            'Total Grades': total_grades,
            'Average Grade': round(avg_grade, 2)
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name='student_report.csv'
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000) 