import os
import random
import json
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'cyber-security-dev-2026'),
    SQLALCHEMY_DATABASE_URI='sqlite:///modern_edu_pro.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

# --- AI CONFIG ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True)
    index_number = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    quizzes = db.relationship('Quiz', backref='creator', lazy=True)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, index=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100))
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    questions = db.relationship('Question', backref='parent_quiz', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct = db.Column(db.String(1), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher': return redirect(url_for('student_home'))
    return render_template('dashboard.html', quizzes=current_user.quizzes)

# --- API: CREATE QUIZ ---
@app.route('/api/quiz/create_with_ai', methods=['POST'])
@login_required
def create_with_ai():
    # Use request.form for multipart/form-data (buttons & file uploads)
    title = request.form.get('title')
    subject = request.form.get('subject')
    
    if not title or not subject:
        return jsonify({"status": "error", "message": "Missing title or subject"}), 400

    quiz_code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    
    try:
        new_quiz = Quiz(code=quiz_code, title=title, subject=subject, teacher_id=current_user.id)
        db.session.add(new_quiz)
        db.session.commit()
        
        # Note: We aren't forcing AI question generation here yet to ensure 
        # the "Initialize" part works first. 
        return jsonify({"status": "success", "code": quiz_code})
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API: MANUAL & BULK QUESTIONS ---
@app.route('/api/quiz/add_question', methods=['POST'])
@login_required
def add_question():
    data = request.json
    new_q = Question(
        quiz_id=data['quiz_id'], text=data['text'], 
        option_a=data['a'], option_b=data['b'], 
        option_c=data['c'], option_d=data['d'], correct=data['correct']
    )
    db.session.add(new_q)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/quiz/bulk_paste', methods=['POST'])
@login_required
def bulk_paste():
    data = request.json
    lines = data.get('text', '').strip().split('\n')
    count = 0
    for line in lines:
        parts = [p.strip() for p in line.split('|')]
        if len(parts) == 6:
            new_q = Question(
                quiz_id=data['quiz_id'], text=parts[0], 
                option_a=parts[1], option_b=parts[2], 
                option_c=parts[3], option_d=parts[4], correct=parts[5].upper()
            )
            db.session.add(new_q)
            count += 1
    db.session.commit()
    return jsonify({"status": "success", "count": count})

# --- AUTH ---
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    uid = data.get('login_id')
    user = User.query.filter((User.username == uid) | (User.index_number == uid)).first()
    if user and check_password_hash(user.password, data.get('password')):
        login_user(user)
        return jsonify({"status": "success", "role": user.role})
    return jsonify({"status": "error"}), 401

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
