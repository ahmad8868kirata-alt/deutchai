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

CEFR_DESCRIPTIONS = {
    "A1": "Anfänger: Kann vertraute, alltägliche Ausdrücke und ganz einfache Sätze verstehen und verwenden, die auf die Befriedigung konkreter Bedürfnisse zielen. Kann sich und andere vorstellen und anderen Leuten Fragen zu ihrer Person stellen – z. B. wo sie wohnen, was für Leute sie kennen oder was für Dinge sie haben – und kann auf Fragen dieser Art Antwort geben. Kann sich auf einfache Art verständigen, wenn die Gesprächspartnerinnen oder Gesprächspartner langsam und deutlich sprechen und bereit sind zu helfen.",
    "A2": "Grundlegende Kenntnisse: Kann Sätze und häufig gebrauchte Ausdrücke verstehen, die mit Bereichen von ganz unmittelbarer Bedeutung zusammenhängen (z. B. Informationen zur Person und zur Familie, Einkaufen, Arbeit, nähere Umgebung). Kann sich in einfachen, routinemäßigen Situationen verständigen, in denen es um einen einfachen und direkten Austausch von Informationen über vertraute und geläufige Dinge geht. Kann mit einfachen Mitteln die eigene Herkunft und Ausbildung, die direkte Umgebung und Dinge im Zusammenhang mit unmittelbaren Bedürfnissen beschreiben.",
    "B1": "Fortgeschrittene Sprachverwendung: Kann die Hauptpunkte verstehen, wenn klare Standardsprache verwendet wird und wenn es um vertraute Dinge aus Arbeit, Schule, Freizeit usw. geht. Kann die meisten Situationen bewältigen, denen man auf Reisen im Sprachgebiet begegnet. Kann sich einfach und zusammenhängend über vertraute Themen und persönliche Interessengebiete äußern. Kann über Erfahrungen und Ereignisse berichten, Träume, Hoffnungen und Ziele beschreiben und zu Plänen und Ansichten kurze Begründungen oder Erklärungen geben.",
    "B2": "Selbständige Sprachverwendung: Kann die Hauptinhalte komplexer Texte zu konkreten und abstrakten Themen verstehen; versteht im eigenen Spezialgebiet auch Fachdiskussionen. Kann sich so spontan und fließend verständigen, dass ein normales Gespräch mit Muttersprachlern ohne größere Anstrengung auf beiden Seiten gut möglich ist. Kann sich zu einem breiten Themenspektrum klar und detailliert ausdrücken, einen Standpunkt zu einer aktuellen Frage erläutern und die Vor- und Nachteile verschiedener Möglichkeiten angeben.",
    "C1": "Fachkundige Sprachkenntnisse: Kann ein breites Spektrum anspruchsvoller, längerer Texte verstehen und auch implizite Bedeutungen erfassen. Kann sich spontan und fließend ausdrücken, ohne öfter deutlich erkennbar nach Worten suchen zu müssen. Kann die Sprache im gesellschaftlichen und beruflichen Leben oder in Ausbildung und Studium wirksam und flexibel gebrauchen. Kann sich klar, strukturiert und ausführlich zu komplexen Sachverhalten äußern und dabei verschiedene Mittel zur Textverknüpfung angemessen verwenden.",
    "C2": "Annähernd muttersprachliche Kenntnisse: Kann praktisch alles, was er/sie liest oder hört, mühelos verstehen. Kann Informationen aus verschiedenen schriftlichen und mündlichen Quellen zusammenfassen und dabei Begründungen und Erklärungen in einer zusammenhängenden Darstellung wiedergeben. Kann sich spontan, sehr flüssig und genau ausdrücken und auch bei komplexeren Sachverhalten feinere Bedeutungsnuancen deutlich machen."
}

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
    Der Schüler lernt gerade die Lektion: "{lesson.title}".
    Inhalt: {lesson.content[:500]}...
    Niveau: {lesson.level}.
    
    GER-KONTEXT FÜR NIVEAU {lesson.level}:
    {CEFR_DESCRIPTIONS.get(lesson.level, "Allgemeiner GER-Standard")}

    Bitte gib eine hilfreiche, ermutigende Erklärung der wichtigsten Grammatikpunkte dieser Lektion auf Deutsch.
    Halte dich dabei strikt an die Standards des Gemeinsamen Europäischen Referenzrahmens (GER) für das Niveau {lesson.level}.
    
    WICHTIGE ANWEISUNGEN FÜR NIVEAU {lesson.level}:
    {"- Verwende 'Leichte Sprache': nur einfache Hauptsätze, ein Gedanke pro Satz, kein Passiv, kein Genitiv." if lesson.level == 'A1' else ""}
    {"- Verwende 'Einfache Sprache': Sätze ca. 12-15 Wörter, einfache Konjunktionen (und, aber, denn) sind erlaubt." if lesson.level == 'A2' else ""}
    {"- Verwende klare Standardsprache: Komplexere Satzstrukturen (weil, obwohl) sind möglich." if lesson.level in ['B1', 'B2'] else ""}
    {"- Verwende anspruchsvolle Sprache: Komplexe Satzstrukturen und Fachbegriffe sind angemessen." if lesson.level in ['C1', 'C2'] else ""}
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
    Erstelle eine wissenschaftlich fundierte und umfassende Deutsch-Lektion zum Thema "{topic}" für das Niveau {level} (nach GER-Standard).
    
    GER-KONTEXT FÜR NIVEAU {level}:
    {CEFR_DESCRIPTIONS.get(level, "Allgemeiner GER-Standard")}

    Die Lektion MUSS in zwei Hauptteile gegliedert sein:
    1. **Erklärung**: Detaillierte Grammatikregeln und Verwendung unter Berücksichtigung von {"Leichter Sprache" if level == 'A1' else "Einfacher Sprache" if level == 'A2' else "Standard-GER"}.
    2. **Beispielübungen**: Mindestens 3 detaillierte Beispiele mit der richtigen Antwort und einer kurzen wissenschaftlichen Begründung (warum diese Antwort korrekt ist).
    
    WICHTIGE REGELN FÜR NIVEAU {level}:
    {"- Maximal 8-10 Wörter pro Satz, keine Nebensätze, Vokabular aus der offiziellen VHS-A1-Liste." if level == 'A1' else ""}
    {"- Sätze ca. 12-15 Wörter, Fokus auf Alltagssituationen und routinemäßige Aufgaben." if level == 'A2' else ""}
    {"- Zusammenhängende Texte, Begründungen für Meinungen und Pläne, Nebensätze erlaubt." if level == 'B1' else ""}
    {"- Komplexe Texte zu konkreten/abstrakten Themen, Fachdiskussionen, spontane und fließende Verständigung." if level == 'B2' else ""}
    {"- Anspruchsvolle, längere Texte, implizite Bedeutungen, flexible Sprachverwendung im Beruf/Studium." if level == 'C1' else ""}
    {"- Nahezu alles mühelos verstehen, Informationen zusammenfassen, feine Bedeutungsnuancen ausdrücken." if level == 'C2' else ""}

    Das Format MUSS ein JSON-Objekt sein:
    {{
        "title": "Titel der Lektion",
        "content_html": "HTML-String. Verwende <div class='explanation'>...</div> für Grammatik und <div class='examples'>...</div> für gelöste Übungen. Nutze h3 für Abschnitte.",
        "questions": [
            {{
                "text": "Frage auf Niveau {level}",
                "a": "Antwort A", "b": "Antwort B", "c": "Antwort C", "d": "Antwort D",
                "correct": "A|B|C|D"
            }}
        ]
    }}
    Erstelle am Ende 3 Quizfragen, die das Niveau {level} genau prüfen.
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
        ChatMessage.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

    new_user_msg = ChatMessage(user_id=current_user.id, role='user', content=user_message, topic=context)
    db.session.add(new_user_msg)
    db.session.commit()

    past_messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.timestamp.desc()).limit(10).all()
    formatted_history = []
    for m in reversed(past_messages):
        formatted_history.append({"role": m.role, "content": m.content})

    level_description = CEFR_DESCRIPTIONS.get(current_user.german_level, "")
    level_instruction = f"Folge strikt dem GER-Standard für {current_user.german_level}: {level_description}\n"
    
    if current_user.german_level == 'A1':
        level_instruction += "Zusatzregel: Folge dem Standard 'Leichte Sprache'. Nutze nur einfache Hauptsätze (S-V-O). Ein Gedanke pro Satz. Nutze nur Vokabeln der A1-Wortliste (Familie, Alltag)."
    elif current_user.german_level == 'A2':
        level_instruction += "Zusatzregel: Folge dem Standard 'Einfache Sprache'. Sätze ca. 12-15 Wörter. Nutze einfache Konjunktionen. Fokus auf Arbeit und unmittelbare Umgebung."
    elif current_user.german_level == 'B1':
        level_instruction += "Zusatzregel: Folge dem Standard GER B1. Nutze zusammenhängende Texte. Du kannst über Erfahrungen, Ziele und Meinungen sprechen und diese kurz begründen."
    elif current_user.german_level == 'B2':
        level_instruction += "Zusatzregel: Folge dem Standard GER B2. Kannst komplexe Texte verstehen und Fachdiskussionen führen. Drücke dich klar und detailliert aus."
    else: # C1, C2
        level_instruction += f"Zusatzregel: Nutze hochkomplexe Strukturen, Nuancen und Fachterminologie wie für {current_user.german_level} vorgesehen."

    system_content = f"""
    Du bist Hans, ein erfahrener Deutschlehrer.
    Das Deutschniveau des Nutzers ist {current_user.german_level}.
    
    WISSENSCHAFTLICHE ANWEISUNG:
    {level_instruction}
    
    KRITISCHE REGELN:
    1. Aktuelles Thema: {context}. Bleibe strikt bei diesem Thema.
    2. Tonfall: Ermutigend, professionell und geduldig.
    3. Methode: Antworte primär auf Deutsch. Wenn der Nutzer einen kleinen Fehler macht, korrigiere ihn sanft in deiner Antwort nach DUDEN-Standards.
    4. Interaktion: Beende jede Antwort mit einer Anschlussfrage, die zum Niveau {current_user.german_level} passt.
    """

    api_key = "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"
    messages = [{"role": "system", "content": system_content}]
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
    level_description = CEFR_DESCRIPTIONS.get(current_user.german_level, "Allgemeiner GER-Standard")
    
    system_prompt = f"""
    Du bist ein Experte für deutsche Grammatikprüfung nach DUDEN- und VHS-Prüfungsstandards.
    Das Deutschniveau des Nutzers ist {current_user.german_level}.
    
    GER-KONTEXT FÜR NIVEAU {current_user.german_level}:
    {level_description}

    Analysiere den folgenden deutschen Text auf:
    1. Grammatikfehler (gemäß GER-Regeln für {current_user.german_level})
    2. Rechtschreibfehler
    3. Verbesserungsvorschläge für bessere Natürlichkeit und Übereinstimmung mit dem GER-Niveau {current_user.german_level}
    4. Bestimmung des tatsächlichen GER-Niveaus des verwendeten Wortschatzes (ist er unter, auf oder über {current_user.german_level}?)
    5. Eine Gesamtbewertung (0-100%) basierend darauf, wie gut der Text den Anforderungen von {current_user.german_level} entspricht.
    6. Die korrigierte Version des Textes.

    WICHTIG: Identifiziere JEDEN einzelnen Fehler separat in der Liste 'corrections'. 
    Erkläre für jeden Fehler genau die wissenschaftliche Regel (z.B. Verbposition, Kasus, Deklination) unter Bezugnahme auf den GER-Standard für {current_user.german_level}.
    
    Die Antwort MUSS ein JSON-Objekt sein:
    {{
        "score": number,
        "vocab_level": "string (A1-C2)",
        "analysis_summary": "Zusammenfassung auf Deutsch, die explizit auf die GER-Kriterien für {current_user.german_level} eingeht",
        "corrected_sentence": "Vollständig korrigierte Version",
        "corrections": [
            {{
                "original": "falsches Wort/Phrase",
                "correction": "korrekte Form",
                "explanation": "Wissenschaftliche Erklärung der Regel auf Deutsch, bezogen auf {current_user.german_level}",
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
