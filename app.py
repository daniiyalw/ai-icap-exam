from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import uuid
import os

app = Flask(__name__)
CORS(app)

# Configuration
USERS_FILE = "users.json"
CHAPTERS_FILE = "chapters.json"

# ---------- UTILITY FUNCTIONS ----------
def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f, indent=2)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# ---------- SIMPLE AI EVALUATION ----------
def evaluate_answer(answer_text):
    """Simple evaluation for demo"""
    word_count = len(answer_text.split())
    
    # Check for completely wrong answers
    if "mitochondria" in answer_text.lower():
        return {
            "score": "0/10",
            "feedback": "❌ WRONG TOPIC: You're writing about biology for a law question!",
            "strengths": "None - completely off topic",
            "improvements": "Read the question carefully. Law questions need legal concepts."
        }
    
    # Basic scoring
    score = min(2 + (word_count // 30), 10)
    
    return {
        "score": f"{score}/10",
        "feedback": f"✅ Basic answer. Add more legal terminology and examples.",
        "strengths": f"Attempted answer ({word_count} words)",
        "improvements": "Reference Contract Act 1872, include case law examples"
    }

# ---------- ROUTES ----------
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_file(filename):
    return send_from_directory('.', filename)

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username", "")
    password = data.get("password", "")
    
    users = load_json(USERS_FILE, {})
    
    # Demo credentials
    if username == "demo" and password == "demo123":
        return jsonify({
            "success": True,
            "token": "demo_token",
            "username": "demo",
            "mode": "demo"
        })
    
    if username in users and users[username]["password"] == password:
        token = str(uuid.uuid4())
        users[username]["token"] = token
        save_json(USERS_FILE, users)
        
        return jsonify({
            "success": True,
            "token": token,
            "username": username,
            "mode": "login"
        })
    
    return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route("/check-answer", methods=["POST"])
def check_answer():
    try:
        data = request.json
        answer = data.get("answer", "")
        chapter = data.get("chapter", 1)
        
        result = evaluate_answer(answer)
        
        return jsonify({
            "success": True,
            "result": f"""
🎓 ICAP AI EXAMINER - CHAPTER {chapter}
{'═' * 45}

📊 FINAL SCORE: {result['score']}

✅ FEEDBACK: {result['feedback']}

✨ STRENGTHS: {result['strengths']}

🔧 IMPROVEMENTS: {result['improvements']}

{'═' * 45}
🤖 AI Evaluation (Demo Mode)
""",
            "score": result['score']
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "result": "Error processing answer"
        })

@app.route("/chapter/<chapter_id>", methods=["GET"])
def get_chapter(chapter_id):
    chapters = load_json(CHAPTERS_FILE, {})
    
    if chapter_id in chapters:
        return jsonify(chapters[chapter_id])
    
    # Default chapter
    return jsonify({
        "name": "Introduction to Law",
        "questions": [
            {"id": "q1", "text": "What is a legal system?", "marks": 5},
            {"id": "q2", "text": "Explain contract law basics.", "marks": 5}
        ]
    })

# Admin routes (simplified)
@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json
    if data.get("username") == "admin" and data.get("password") == "admin123":
        return jsonify({
            "success": True,
            "admin_token": "admin_demo_token"
        })
    return jsonify({"success": False}), 401

if __name__ == "__main__":
    # Create default files if they don't exist
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({
                "demo": {"password": "demo", "token": ""},
                "admin": {"password": "admin123", "token": ""}
            }, f, indent=2)
    
    if not os.path.exists(CHAPTERS_FILE):
        with open(CHAPTERS_FILE, 'w') as f:
            json.dump({
                "chapter1": {
                    "name": "Introduction to Law",
                    "questions": [
                        {"id": "q1", "text": "What are the main sources of law?", "marks": 5},
                        {"id": "q2", "text": "Define legal system.", "marks": 5}
                    ]
                }
            }, f, indent=2)
    
    print("✅ Server ready! Open: http://localhost:5000")
    app.run(debug=True)
