import os
import random
import logging
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError

# --- CONFIGURATION ---
app = Flask(__name__)

# Security: Set session to expire after 2 hours of inactivity
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'cyber-sec-99-alpha'),
    SQLALCHEMY_DATABASE_URI='sqlite:///modern_edu_pro.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2)
)

# Logging: Professional audit trail for security events
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS (Secure Schema) ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, index=True) # For Teachers
    index_number = db.Column(db.String(80), unique=True, index=True) # For Students
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    
    # Relationship: One User can have many results
    results = db.relationship('Result', backref='student', lazy=True)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, index=True)
    title = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100))
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    questions = db.relationship('Question', backref='quiz', lazy='joined', cascade="all, delete-orphan")

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'))
    text = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.String(200), nullable=False)

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer)
    total = db.Column(db.Integer)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- CORE VIEWS ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher':
        return redirect(url_for('index'))
    quizzes = Quiz.query.filter_by(teacher_id=current_user.id).all()
    return render_template('dashboard.html', quizzes=quizzes)

# --- AUTHENTICATION API (AJAX Driven) ---
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    try:
        data = request.json
        # Hashing with PBKDF2 (NIST Recommended)
        hashed_pw = generate_password_hash(data['password'], method='pbkdf2:sha256')
        
        new_user = User(
            full_name=data['full_name'],
            username=data.get('username'),
            index_number=data.get('index_number'),
            password=hashed_pw,
            role=data['role']
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"status": "success", "message": "Provisioning complete"}), 201
    except IntegrityError:
        return jsonify({"status": "error", "message": "Identifier already exists"}), 400

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    uid = data.get('login_id')
    user = User.query.filter((User.username == uid) | (User.index_number == uid)).first()
    
    if user and check_password_hash(user.password, data.get('password')):
        login_user(user, remember=True)
        logger.info(f"User {uid} authenticated successfully.")
        return jsonify({"status": "success", "role": user.role})
    
    logger.warning(f"Failed login attempt for {uid}")
    return jsonify({"status": "error", "message": "Identity verification failed"}), 401

# --- QUIZ ENGINE API ---
@app.route('/api/quiz/create', methods=['POST'])
@login_required
def api_create_quiz():
    data = request.json
    # Generate unique 6-digit access code
    code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    
    new_quiz = Quiz(
        code=code, 
        title=data['title'], 
        subject=data.get('subject', 'General'), 
        teacher_id=current_user.id
    )
    db.session.add(new_quiz)
    db.session.commit()
    return jsonify({"status": "success", "code": code})

# --- GLOBAL UTILITIES ---
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(e):
    return render_template('index.html'), 404

# --- INITIALIZATION ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Running with high-performance settings
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))