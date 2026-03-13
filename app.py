
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
    SECRET_KEY=os.environ.get('SECRET_KEY', 'cyber-security-2026'),
    SQLALCHEMY_DATABASE_URI='sqlite:///modern_edu_pro.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

# --- CONFIGURE AI ---
genai.configure(api_key="    ")
model = genai.GenerativeModel('gemini-1.5-flash')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    username = db.Column(db.String(80), unique=True)
    index_number = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))
    quizzes = db.relationship('Quiz', backref='creator', lazy=True)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True)
    title = db.Column(db.String(100))
    subject = db.Column(db.String(100))
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    questions = db.relationship('Question', backref='parent_quiz', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'))
    text = db.Column(db.String(500))
    option_a = db.Column(db.String(200))
    option_b = db.Column(db.String(200))
    option_c = db.Column(db.String(200))
    option_d = db.Column(db.String(200))
    correct = db.Column(db.String(1))

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/login')
def login(): return render_template('login.html')

@app.route('/register/<role>')
def register_page(role): return render_template('register.html', role=role)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher': return redirect(url_for('student_home'))
    return render_template('dashboard.html', quizzes=current_user.quizzes)

@app.route('/student_home')
@login_required
def student_home(): return render_template('student_home.html')

# --- AI GENERATION LOGIC ---
@app.route('/api/quiz/create_with_ai', methods=['POST'])
@login_required
def create_with_ai():
    title = request.form.get('title')
    subject = request.form.get('subject')
    file = request.files.get('file')
    
    content = file.read().decode('utf-8') if file else "General knowledge"
    
    prompt = f"""
    Generate 5 multiple-choice questions about {subject} based on this text: {content}.
    Return ONLY a JSON list like this:
    [{"text": "...", "a": "...", "b": "...", "c": "...", "d": "...", "correct": "A"}]
    """
    
    response = model.generate_content(prompt)
    raw_json = response.text.replace('```json', '').replace('```', '').strip()
    questions_data = json.loads(raw_json)

    quiz_code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    new_quiz = Quiz(code=quiz_code, title=title, subject=subject, teacher_id=current_user.id)
    db.session.add(new_quiz)
    db.session.commit()

    for q in questions_data:
        new_q = Question(quiz_id=new_quiz.id, text=q['text'], option_a=q['a'], 
                         option_b=q['b'], option_c=q['c'], option_d=q['d'], correct=q['correct'])
        db.session.add(new_q)
    
    db.session.commit()
    return jsonify({"status": "success", "code": quiz_code})

# ... (Auth routes remain same as previous message) ...

with app.app_context(): db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
