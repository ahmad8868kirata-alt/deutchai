import os
import requests
import json
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///deutschai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    german_level = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    progress = db.Column(db.Integer, default=0)
    xp = db.Column(db.Integer, default=0)
    vocabularies = db.relationship('Vocabulary', backref='owner', lazy=True)
    activities = db.relationship('Activity', backref='owner', lazy=True)

class Vocabulary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    word = db.Column(db.String(100), nullable=False)
    correction = db.Column(db.String(100), nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False) # 'chat', 'practice', 'vocab', 'lesson'
    description = db.Column(db.String(200), nullable=False)
    points = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(20), nullable=False) # A1, A2, B1, etc.
    order = db.Column(db.Integer, default=0)
    questions = db.relationship('Question', backref='lesson', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    text = db.Column(db.String(255), nullable=False)
    option_a = db.Column(db.String(100), nullable=False)
    option_b = db.Column(db.String(100), nullable=False)
    option_c = db.Column(db.String(100), nullable=False)
    option_d = db.Column(db.String(100), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False) # 'A', 'B', 'C', or 'D'

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    topic = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

def log_activity(user, type, description, points):
    activity = Activity(user_id=user.id, type=type, description=description, points=points)
    user.xp += points
    # Simple logic: 1000 XP per level, progress is % of current 1000
    user.progress = (user.xp % 1000) // 10
    if user.progress > 100: user.progress = 100
    db.session.add(activity)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error logging activity: {e}")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_user():
    return dict(user=current_user)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        german_level = request.form.get('german_level')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('signup'))

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already registered!', 'danger')
            return redirect(url_for('signup'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(first_name=first_name, last_name=last_name, german_level=german_level, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    activities = Activity.query.filter_by(user_id=current_user.id).order_by(Activity.timestamp.desc()).limit(5).all()
    return render_template('dashboard.html', activities=activities)

@app.route('/lessons')
@login_required
def lessons():
    lessons = Lesson.query.filter_by(level=current_user.german_level).order_by(Lesson.order).all()
    return render_template('lessons.html', lessons=lessons)

@app.route('/lessons/<int:lesson_id>')
@login_required
def lesson_detail(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.level != current_user.german_level:
        flash('Diese Lektion ist nicht für Ihr aktuelles Niveau verfügbar.', 'warning')
        return redirect(url_for('lessons'))
    return render_template('lesson_detail.html', lesson=lesson)

@app.route('/api/lessons/submit-quiz', methods=['POST'])
@login_required
def submit_quiz():
    data = request.json
    lesson_id = data.get('lesson_id')
    score = data.get('score') # percentage
    
    lesson = Lesson.query.get_or_404(lesson_id)
    points = int(score // 10) # Max 10 XP for 100%
    
    log_activity(current_user, 'lesson', f'Lektion abgeschlossen: {lesson.title} ({score}%)', points)
    
    return jsonify({"success": True, "points": points})

@app.route('/api/lessons/explain', methods=['POST'])
@login_required
def explain_lesson():
    data = request.json
    lesson_id = data.get('lesson_id')
    lesson = Lesson.query.get_or_404(lesson_id)
    
    api_key = "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"
    
    prompt = f"""
    The student is studying the lesson: "{lesson.title}".
    Content: {lesson.content[:500]}...
    Level: {lesson.level}.
    Please provide a helpful, encouraging explanation of the key grammar points in this lesson in German.
    Keep it concise but detailed enough to clarify doubts.
    """
    
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "DeutschAI",
        },
        data=json.dumps({
            "model": "openai/gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are Hans, a friendly German tutor."},
                {"role": "user", "content": prompt}
            ]
        })
    )
    
    if response.status_code == 200:
        res_data = response.json()
        explanation = res_data['choices'][0]['message']['content']
        return jsonify({"explanation": explanation})
    return jsonify({"error": "Failed to get explanation"}), 500

@app.route('/api/lessons/generate', methods=['POST'])
@login_required
def generate_lesson():
    data = request.json
    topic = data.get('topic')
    level = data.get('level', current_user.german_level)
    
    api_key = "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"
    
    prompt = f"""
    Generate a highly educational and comprehensive German lesson about "{topic}" for level {level}.
    The lesson MUST be structured into two main parts:
    1. **Erklärung (Explanation)**: Detailed grammar rules and usage.
    2. **Beispielübungen (Solved Exercises)**: At least 3 detailed examples with the correct answer shown and a brief explanation of why.
    
    The response must be in JSON format:
    {{
        "title": "string",
        "content_html": "HTML string. Use <div class='explanation'>...</div> for grammar and <div class='examples'>...</div> for solved exercises. Use h3 for section headers.",
        "questions": [
            {{
                "text": "string",
                "a": "string", "b": "string", "c": "string", "d": "string",
                "correct": "A|B|C|D"
            }}
        ]
    }}
    Provide 3 challenging quiz questions at the end.
    """
    
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "DeutschAI",
        },
        data=json.dumps({
            "model": "openai/gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": { "type": "json_object" }
        })
    )
    
    if response.status_code == 200:
        res_data = response.json()
        lesson_data = json.loads(res_data['choices'][0]['message']['content'])
        
        new_lesson = Lesson(
            title=lesson_data['title'],
            content=lesson_data['content_html'],
            level=level,
            order=Lesson.query.filter_by(level=level).count() + 1
        )
        db.session.add(new_lesson)
        db.session.commit()
        
        for q in lesson_data['questions']:
            question = Question(
                lesson_id=new_lesson.id,
                text=q['text'],
                option_a=q['a'],
                option_b=q['b'],
                option_c=q['c'],
                option_d=q['d'],
                correct_option=q['correct']
            )
            db.session.add(question)
        
        db.session.commit()
        return jsonify({"success": True, "lesson_id": new_lesson.id})
    return jsonify({"error": "Failed to generate lesson"}), 500

@app.route('/chat')
@login_required
def chat():
    # Clear old chat history to start fresh
    ChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return render_template('chat.html', history=[])

@app.route('/chat/api', methods=['POST'])
@login_required
def chat_api():
    data = request.json
    user_message = data.get('message')
    context = data.get('context', 'General')
    clear_history = data.get('clear_history', False)

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    if clear_history:
        # Delete old messages for this user to start fresh
        ChatMessage.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

    # Save user message
    new_user_msg = ChatMessage(user_id=current_user.id, role='user', content=user_message, topic=context)
    db.session.add(new_user_msg)
    db.session.commit()

    # Get recent history for context
    past_messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.timestamp.desc()).limit(10).all()
    formatted_history = []
    for m in reversed(past_messages):
        formatted_history.append({"role": m.role, "content": m.content})

    # Level-based persona instructions
    level_instruction = ""
    if current_user.german_level in ['A1', 'A2']:
        level_instruction = "The user is a beginner. Give easy, simple, and short answers. Use basic vocabulary."
    else:
        level_instruction = "The user is at an advanced level. Give longer, more detailed, and natural responses. Use sophisticated vocabulary."

    system_content = f"""
    You are Hans, an expert German language tutor. 
    The user's German level is {current_user.german_level}. {level_instruction}
    
    CRITICAL INSTRUCTION:
    1. Current Topic: {context}. You MUST stay strictly on this topic. If the user wanders off, politely bring them back to "{context}".
    2. Tone: Extremely encouraging, professional, and patient.
    3. Method: Primarily speak in German. If the user makes a small mistake, gently provide the correct form in your response.
    4. Engagement: Always end your response with a follow-up question related to the topic to keep the conversation going.
    """

    api_key = "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"
    
    messages = [{"role": "system", "content": system_content}]
    # Add history (excluding the one we just saved to avoid duplication if it's already there, 
    # but we just committed it, so it will be in past_messages)
    # Actually, formatted_history already includes the last user message.
    messages.extend(formatted_history)

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "DeutschAI",
        },
        data=json.dumps({
            "model": "openai/gpt-3.5-turbo",
            "messages": messages
        })
    )
    
    if response.status_code == 200:
        res_data = response.json()
        ai_content = res_data['choices'][0]['message']['content']
        
        # Save AI response
        new_ai_msg = ChatMessage(user_id=current_user.id, role='assistant', content=ai_content, topic=context)
        db.session.add(new_ai_msg)
        db.session.commit()
        
        log_activity(current_user, 'chat', f'Konversation über {context} geführt', 10)
        return jsonify(res_data)
    else:
        return jsonify({"error": "Failed to get response from AI"}), response.status_code

@app.route('/practice')
@login_required
def practice():
    return render_template('practice.html')

@app.route('/practice/api', methods=['POST'])
@login_required
def practice_api():
    data = request.json
    user_text = data.get('text')
    
    if not user_text:
        return jsonify({"error": "No text provided"}), 400

    api_key = "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"
    
    system_prompt = f"""
    You are an expert German grammar checker. The user's level is {current_user.german_level}.
    Analyze the following German text for:
    1. Grammar errors
    2. Spelling mistakes
    3. Suggested improvements for better fluency
    4. CEFR level of the vocabulary used
    5. An overall grammar score (0-100%)
    6. The corrected version of the entire sentence/text

    CRITICAL: You MUST identify and extract EACH AND EVERY misspelled word or grammar mistake as a separate entry in the 'corrections' list. Do not group multiple distinct errors into one entry unless they are part of the same phrase. Ensure that every single original word that had a mistake is listed.

    IMPORTANT: Your response MUST be in JSON format with the following structure:
    {{
        "score": number,
        "vocab_level": "string (A1-C2)",
        "analysis_summary": "string in German",
        "corrected_sentence": "string - the fully corrected version of the input text",
        "corrections": [
            {{
                "original": "string",
                "correction": "string",
                "explanation": "string in German",
                "type": "grammar" | "spelling" | "style"
            }}
        ]
    }}
    """
    
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "DeutschAI",
        },
        data=json.dumps({
            "model": "openai/gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            "response_format": { "type": "json_object" }
        })
    )
    
    if response.status_code == 200:
        result_data = response.json()
        try:
            content = json.loads(result_data['choices'][0]['message']['content'])
            score = content.get('score', 0)
            log_activity(current_user, 'practice', f'Grammatik-Übung abgeschlossen ({score}%)', score // 5)
        except:
            pass
        return jsonify(result_data)
    else:
        return jsonify({"error": "Failed to get response from AI"}), response.status_code

@app.route('/setting', methods=['GET', 'POST'])
@login_required
def setting():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.email = request.form.get('email')
        current_user.german_level = request.form.get('cefr_level')
        
        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating your profile.', 'danger')
        
        return redirect(url_for('setting'))
    return render_template('setting.html')

@app.route('/vocabulary')
@login_required
def vocabulary():
    return render_template('vocabulary.html')

@app.route('/vocabulary/api/add', methods=['POST'])
@login_required
def add_vocabulary():
    data = request.json
    word = data.get('word')
    correction = data.get('correction')
    explanation = data.get('explanation')

    if not word or not correction:
        return jsonify({"error": "Missing word or correction"}), 400

    # Avoid duplicates for the same user
    existing = Vocabulary.query.filter_by(user_id=current_user.id, word=word, correction=correction).first()
    if existing:
        return jsonify({"message": "Word already in vocabulary"}), 200

    new_vocab = Vocabulary(
        user_id=current_user.id,
        word=word,
        correction=correction,
        explanation=explanation
    )
    db.session.add(new_vocab)
    log_activity(current_user, 'vocab', f'Neues Wort gelernt: {correction}', 5)
    db.session.commit()
    return jsonify({"message": "Vocabulary added successfully"}), 201

@app.route('/vocabulary/api/list', methods=['GET'])
@login_required
def list_vocabulary():
    vocabs = Vocabulary.query.filter_by(user_id=current_user.id).order_by(Vocabulary.timestamp.desc()).all()
    return jsonify([{
        "id": v.id,
        "word": v.word,
        "correction": v.correction,
        "explanation": v.explanation,
        "timestamp": v.timestamp.isoformat()
    } for v in vocabs])

@app.route('/vocabulary/api/delete/<int:vocab_id>', methods=['DELETE'])
@login_required
def delete_vocabulary(vocab_id):
    vocab = Vocabulary.query.filter_by(id=vocab_id, user_id=current_user.id).first()
    if not vocab:
        return jsonify({"error": "Vocabulary item not found"}), 404
    
    db.session.delete(vocab)
    db.session.commit()
    return jsonify({"message": "Vocabulary item deleted"}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
