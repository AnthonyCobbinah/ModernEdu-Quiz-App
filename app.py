import os
import random
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'cyber-pro-2026-secure-key'),
    SQLALCHEMY_DATABASE_URI='sqlite:///modern_edu_pro.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    username = db.Column(db.String(80), unique=True, nullable=True)
    index_number = db.Column(db.String(80), unique=True, nullable=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))
    quizzes = db.relationship('Quiz', backref='creator', lazy=True)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, index=True)
    title = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100))
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register/<role>')
def register_page(role):
    return render_template('register.html', role=role)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher':
        return redirect(url_for('student_home'))
    # If this fails, it's a 500 error. Delete the .db file to fix!
    user_quizzes = Quiz.query.filter_by(teacher_id=current_user.id).all()
    return render_template('dashboard.html', quizzes=user_quizzes)

@app.route('/student_home')
@login_required
def student_home():
    return render_template('student_home.html')

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
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
    return jsonify({"status": "success"})

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    uid = data.get('login_id')
    user = User.query.filter((User.username == uid) | (User.index_number == uid)).first()
    if user and check_password_hash(user.password, data.get('password')):
        login_user(user)
        return jsonify({"status": "success", "role": user.role})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/api/quiz/create', methods=['POST'])
@login_required
def api_create_quiz():
    data = request.json
    quiz_code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    new_quiz = Quiz(code=quiz_code, title=data['title'], subject=data['subject'], teacher_id=current_user.id)
    db.session.add(new_quiz)
    db.session.commit()
    return jsonify({"status": "success", "code": quiz_code})

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
