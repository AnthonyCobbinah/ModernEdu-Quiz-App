import os
import random
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'cyber-pro-v4-2026'),
    SQLALCHEMY_DATABASE_URI='sqlite:///modern_edu_pro.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=True)
    index_number = db.Column(db.String(80), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    quizzes = db.relationship('Quiz', backref='creator', lazy=True)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, index=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100))
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Relationship: A quiz has many questions
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

@app.route('/login')
def login(): return render_template('login.html')

@app.route('/register/<role>')
def register_page(role): return render_template('register.html', role=role)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher': return redirect(url_for('student_home'))
    user_quizzes = Quiz.query.filter_by(teacher_id=current_user.id).all()
    return render_template('dashboard.html', quizzes=user_quizzes)

@app.route('/student_home')
@login_required
def student_home():
    if current_user.role != 'student': return redirect(url_for('dashboard'))
    return render_template('student_home.html')

# --- API ---
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
    hashed_pw = generate_password_hash(data['password'], method='pbkdf2:sha256')
    new_user = User(full_name=data['full_name'], username=data.get('username'),
                    index_number=data.get('index_number'), password=hashed_pw, role=data['role'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    user = User.query.filter((User.username == data['login_id']) | (User.index_number == data['login_id'])).first()
    if user and check_password_hash(user.password, data['password']):
        login_user(user)
        return jsonify({"status": "success", "role": user.role})
    return jsonify({"status": "error", "message": "Invalid Credentials"}), 401

@app.route('/api/quiz/create', methods=['POST'])
@login_required
def api_create_quiz():
    data = request.json
    code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    new_quiz = Quiz(code=code, title=data['title'], subject=data['subject'], teacher_id=current_user.id)
    db.session.add(new_quiz)
    db.session.commit()
    return jsonify({"status": "success", "code": code})

@app.route('/api/quiz/add_question', methods=['POST'])
@login_required
def api_add_question():
    data = request.json
    quiz = Quiz.query.get(data['quiz_id'])
    if quiz.teacher_id != current_user.id: return jsonify({"status": "error"}), 403
    
    new_q = Question(quiz_id=data['quiz_id'], text=data['text'], 
                     option_a=data['a'], option_b=data['b'], 
                     option_c=data['c'], option_d=data['d'], correct=data['correct'])
    db.session.add(new_q)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

with app.app_context(): db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
