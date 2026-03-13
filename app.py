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
    SECRET_KEY=os.environ.get('SECRET_KEY', 'cyber-security-2026-v5'),
    SQLALCHEMY_DATABASE_URI='sqlite:///modern_edu_pro.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

# --- CONFIGURE AI SECURELY ---
# It will now look for the GEMINI_API_KEY in your Render Environment Variables
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=True)     # For Teachers
    index_number = db.Column(db.String(80), unique=True, nullable=True) # For Students
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

# --- NAVIGATION ROUTES ---
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
def student_home():
    if current_user.role != 'student': return redirect(url_for('dashboard'))
    return render_template('student_home.html')

# --- AUTHENTICATION API ---
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

# --- AI QUIZ GENERATION API ---
@app.route('/api/quiz/create_with_ai', methods=['POST'])
@login_required
def create_with_ai():
    if current_user.role != 'teacher': return jsonify({"status": "error"}), 403
    
    title = request.form.get('title')
    subject = request.form.get('subject')
    file = request.files.get('file')
    
    # Read text from file if uploaded, otherwise use subject context
    content = file.read().decode('utf-8') if file else f"General knowledge about {subject}"
    
    prompt = f"""
    Generate 5 multiple-choice questions about {subject} based on this text: {content}.
    Format the response as a valid JSON list of objects.
    Each object must have: "text", "a", "b", "c", "d", and "correct" (A, B, C, or D).
    Return ONLY the JSON.
    """
    
    try:
        response = model.generate_content(prompt)
        # Clean AI response to ensure it's pure JSON
        raw_json = response.text.replace('```json', '').replace('```', '').strip()
        questions_data = json.loads(raw_json)

        quiz_code = "".join([str(random.randint(0, 9)) for _ in range(6)])
        new_quiz = Quiz(code=quiz_code, title=title, subject=subject, teacher_id=current_user.id)
        db.session.add(new_quiz)
        db.session.commit()

        for q in questions_data:
            new_q = Question(
                quiz_id=new_quiz.id, text=q['text'], 
                option_a=q['a'], option_b=q['b'], 
                option_c=q['c'], option_d=q['d'], correct=q['correct']
            )
            db.session.add(new_q)
        
        db.session.commit()
        return jsonify({"status": "success", "code": quiz_code})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- DB INITIALIZATION ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
