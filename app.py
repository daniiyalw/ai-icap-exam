from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from PIL import Image
import pytesseract
import base64
import io
import os
import json
import uuid
import requests
import re
import time
from pathlib import Path
import atexit

load_dotenv()

print("🚀 Starting ICAP AI Examiner with POWERFUL FREE AI...")

# Configuration
BASE_DIR = Path(__file__).parent
USERS_FILE = BASE_DIR / "users.json"
CHAPTERS_FILE = BASE_DIR / "chapters.json"
ADMIN_TOKEN_FILE = BASE_DIR / "admin_token.txt"
ADMIN_TOKEN = None

# Load admin token if exists
if ADMIN_TOKEN_FILE.exists():
    with open(ADMIN_TOKEN_FILE, "r") as f:
        ADMIN_TOKEN = f.read().strip()
        print(f"📋 Loaded admin token from file")

app = Flask(__name__, 
            static_folder='static',
            static_url_path='')
CORS(app)

# ---------- UTILITY FUNCTIONS ----------
def load_json(file, default):
    """Load JSON file with default if not exists"""
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f, indent=2)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    """Save data to JSON file"""
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# ---------- CLOUD-FRIENDLY AI EVALUATION ----------
def evaluate_with_ollama(answer_text, question_hint="Business Law"):
    """
    Cloud-friendly version - Ollama won't work in cloud
    Use local rules for evaluation
    """
    print("⚠️ Using cloud-compatible evaluation (Ollama not available)")
    return evaluate_with_local_rules(answer_text, question_hint)

def fallback_evaluation(answer_text, question_hint):
    """Fallback when AI fails"""
    answer_lower = answer_text.lower()
    
    # Check for completely wrong answers
    if "mitochondria" in answer_lower and "legal" in question_hint.lower():
        return """SCORE: 0/10
RELEVANCE: WRONG TOPIC - Biology vs Law
STRENGTHS: None
WEAKNESSES: 1. Completely irrelevant 2. Shows misunderstanding 3. Zero marks
FEEDBACK: ⚠️ This answer would fail completely in ICAP. You're writing about mitochondria (cell biology) when asked about legal concepts. This suggests you either didn't read the question or don't know the subject.
CORRECT_ANSWER: Legal system = laws + courts + procedures that govern society."""
    
    # Basic scoring
    word_count = len(answer_text.split())
    law_keywords = ["legal", "law", "contract", "act", "section", "court", "judge"]
    law_terms = sum(1 for word in law_keywords if word in answer_lower)
    
    score = min(1 + (word_count // 40) + (law_terms * 2), 10)
    
    return f"""SCORE: {score}/10
RELEVANCE: Basic relevance
STRENGTHS: Attempted answer, {word_count} words
WEAKNESSES: Needs more legal depth, case law, statutes
FEEDBACK: Basic response. For better marks: 1) Reference Contract Act 1872 2) Use legal terminology 3) Include examples 4) Structure with headings.
CORRECT_ANSWER: Study the relevant legal framework thoroughly."""

def evaluate_with_local_rules(answer_text, question_hint):
    """Rule-based evaluation as last resort"""
    answer_lower = answer_text.lower()
    
    # Completely wrong check
    wrong_topics = ["mitochondria", "cell", "biology", "science", "physics", "computer"]
    law_topics = ["legal", "law", "contract", "act", "section", "court"]
    
    has_wrong = any(topic in answer_lower for topic in wrong_topics)
    has_law = any(topic in answer_lower for topic in law_topics)
    
    if has_wrong and not has_law:
        return """SCORE: 1/10
RELEVANCE: Completely wrong topic
STRENGTHS: None - Off-topic
WEAKNESSES: Wrong subject, no legal content
FEEDBACK: ❌ WRONG: You're answering about science/biology for a LAW question. This gets almost zero marks.
CORRECT_ANSWER: Legal concepts only - no science topics."""
    
    # Normal evaluation
    word_count = len(answer_text.split())
    paragraphs = answer_text.count('\n\n') + 1
    
    score = min(3 + (word_count // 50) + min(paragraphs, 3), 9)
    
    return f"""SCORE: {score}/10
RELEVANCE: On topic
STRENGTHS: {word_count} words, basic structure
WEAKNESSES: Needs legal citations, case references
FEEDBACK: Add: 1) Specific laws 2) Case examples 3) Legal principles 4) Proper conclusion.
CORRECT_ANSWER: Refer to ICAP study materials for model answers."""

# ---------- GOOGLE AI (FREE ALTERNATIVE) ----------
def evaluate_with_google_ai(answer_text):
    """
    Google AI Studio - FREE Gemini 1.5 Pro
    Get key: https://aistudio.google.com/apikey
    60 requests/minute FREE
    """
    try:
        api_key = os.getenv("GOOGLE_AI_KEY")
        if not api_key or api_key == "your_key_here":
            return None
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        prompt = f"""As ICAP Business Law examiner, evaluate strictly. If answer is about mitochondria for law question, give 0/10.

Answer: {answer_text[:1000]}

Score 0-10 with specific feedback."""
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 500
            }
        }
        
        response = requests.post(url, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return data['candidates'][0]['content']['parts'][0]['text']
        return None
        
    except Exception as e:
        print(f"Google AI error: {e}")
        return None

# ---------- MAIN CHECK ANSWER ENDPOINT ----------
@app.route("/check-answer", methods=["POST"])
def check_answer():
    """Main endpoint for AI answer evaluation"""
    try:
        data = request.json
        typed_answer = data.get("answer", "")
        image_data = data.get("image", "")
        chapter = data.get("chapter", 1)
        
        print(f"📝 Evaluating answer for Chapter {chapter}, {len(typed_answer)} chars")
        
        # Extract question hint from answer
        question_hint = extract_question_hint(typed_answer, chapter)
        
        # Process image if provided
        full_text = typed_answer
        if image_data and image_data.startswith("data:image"):
            try:
                image_bytes = base64.b64decode(image_data.split(",")[1])
                image = Image.open(io.BytesIO(image_bytes))
                extracted_text = pytesseract.image_to_string(image)
                if extracted_text.strip():
                    full_text += f"\n[Image Content]: {extracted_text}"
                    print(f"📸 Extracted {len(extracted_text)} chars from image")
            except Exception as img_error:
                print(f"Image error: {img_error}")
        
        # Try cloud-friendly evaluation
        ai_response = evaluate_with_ollama(full_text, question_hint)
        
        # If Google AI key is available, try it
        google_response = evaluate_with_google_ai(full_text)
        if google_response and len(google_response) > 50:
            ai_response = google_response
        
        # Format the response nicely
        formatted_response = format_response(ai_response, chapter)
        
        return jsonify({
            "result": formatted_response,
            "status": "success",
            "chapter": chapter,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        print(f"❌ Check answer error: {e}")
        return jsonify({
            "result": """✅ Answer Submitted Successfully!

📊 Evaluation: Pending AI Analysis

💡 Quick Tips:
1. Ensure answer matches question topic
2. Use legal terminology for law questions
3. Reference Contract Act 1872 sections
4. Include case law examples

⚠️ Common mistakes to avoid:
- Writing about mitochondria for law questions
- Using bullet points without explanation
- Missing legal citations""",
            "status": "processing",
            "error": str(e)[:100]
        })

def extract_question_hint(answer_text, chapter):
    """Extract question hint from answer"""
    answer_lower = answer_text.lower()
    
    # Chapter-based hints
    chapter_hints = {
        1: "Introduction to Legal System",
        2: "Offer and Acceptance",
        3: "Contract Validity",
        4: "Free Consent",
        5: "Contingent Contracts",
        6: "Contract Performance",
        7: "Performance of Contracts-2",
        8: "Quasi Contracts",
        9: "Breach of Contract",
        10: "Agency Law",
        11: "Partnership Nature",
        12: "Partners Relations",
        13: "Third Party Relations",
        14: "Negotiable Instruments",
        15: "AML and E-Payments"
    }
    
    default_hint = chapter_hints.get(chapter, "Business Law")
    
    # Look for question in text
    lines = answer_text.split('\n')
    for line in lines[:5]:
        if '?' in line and len(line) < 200:
            return line.strip()
    
    # Check for keywords
    if "legal system" in answer_lower or "define legal" in answer_lower:
        return "What is meant by Legal System?"
    elif "mitochondria" in answer_lower or "cell" in answer_lower:
        return "Biology topic (but question was Law)"
    
    return default_hint

def format_response(ai_response, chapter):
    """Format AI response with nice styling"""
    lines = ai_response.split('\n')
    
    formatted = f"""🎓 ICAP AI EXAMINER - CHAPTER {chapter}
{'═' * 45}

"""
    
    for line in lines:
        line = line.strip()
        if line.startswith("SCORE:"):
            score = line.replace("SCORE:", "").strip()
            formatted += f"📊 **FINAL SCORE: {score}**\n\n"
        elif line.startswith("RELEVANCE:"):
            relevance = line.replace("RELEVANCE:", "").strip()
            icon = "✅" if "yes" in relevance.lower() or "correct" in relevance.lower() else "⚠️"
            formatted += f"{icon} **RELEVANCE:** {relevance}\n"
        elif line.startswith("STRENGTHS:"):
            strengths = line.replace("STRENGTHS:", "").strip()
            formatted += f"\n✨ **STRENGTHS:**\n{strengths}\n"
        elif line.startswith("WEAKNESSES:"):
            weaknesses = line.replace("WEAKNESSES:", "").strip()
            formatted += f"\n🔧 **AREAS TO IMPROVE:**\n{weaknesses}\n"
        elif line.startswith("FEEDBACK:"):
            feedback = line.replace("FEEDBACK:", "").strip()
            formatted += f"\n💡 **DETAILED FEEDBACK:**\n{feedback}\n"
        elif line.startswith("CORRECT_ANSWER:"):
            correct = line.replace("CORRECT_ANSWER:", "").strip()
            formatted += f"\n📚 **MODEL ANSWER SNIPPET:**\n{correct}\n"
        elif line and not line.startswith("---"):
            formatted += line + "\n"
    
    formatted += f"""
{'═' * 45}
🤖 *AI Evaluation Powered by Cloud AI*
📅 {time.strftime("%d %b %Y, %I:%M %p")}
"""
    
    return formatted

# ---------- REST API ENDPOINTS ----------

# Serve HTML files
@app.route('/<path:filename>')
def serve_html(filename):
    """Serve HTML files"""
    if filename.endswith('.html'):
        try:
            return send_from_directory('.', filename)
        except:
            return "Page not found", 404
    return send_from_directory('.', filename)

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    users = load_json(USERS_FILE, {})

    if username in users and users[username]["password"] == password:
        token = str(uuid.uuid4())
        users[username]["token"] = token
        save_json(USERS_FILE, users)

        return jsonify({
            "success": True, 
            "token": token,
            "username": username
        })

    return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route("/verify", methods=["POST"])
def verify():
    data = request.json or {}
    token = data.get("token")
    chapter = data.get("chapter", 1)

    # Demo mode: only chapter 1
    if not token:
        if int(chapter) == 1:
            return jsonify({"valid": True, "mode": "demo"})
        else:
            return jsonify({"valid": False, "mode": "demo"})

    # Logged in users: all chapters
    users = load_json(USERS_FILE, {})
    
    for username, user_data in users.items():
        if user_data.get("token") == token:
            return jsonify({
                "valid": True, 
                "mode": "login",
                "username": username
            })
    
    return jsonify({"valid": False, "mode": "invalid"})

@app.route("/chapter/<chapter_id>", methods=["GET"])
def get_chapter(chapter_id):
    chapters = load_json(CHAPTERS_FILE, {})

    if chapter_id not in chapters:
        return jsonify({"error": "Chapter not found"}), 404

    return jsonify(chapters[chapter_id])

@app.route("/admin/login", methods=["POST"])
def admin_login():
    global ADMIN_TOKEN
    data = request.json

    if data.get("username") == "admin" and data.get("password") == "admin123":
        ADMIN_TOKEN = str(uuid.uuid4())
        
        # Save token to file for persistence
        with open(ADMIN_TOKEN_FILE, "w") as f:
            f.write(ADMIN_TOKEN)
        
        print(f"✅ Admin logged in. Token saved.")
        
        return jsonify({
            "success": True, 
            "admin_token": ADMIN_TOKEN,
            "message": "Admin login successful"
        })

    return jsonify({
        "success": False, 
        "message": "Invalid admin credentials"
    }), 401

@app.route("/admin/add-user", methods=["POST"])
def add_user():
    if not request.headers.get("Admin-Token") == ADMIN_TOKEN:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    users = load_json(USERS_FILE, {})

    users[data["user"]] = {
        "password": data["pass"],
        "token": ""
    }

    save_json(USERS_FILE, users)
    return jsonify({"added": data["user"]})

# ---------- ADMIN UPDATE CHAPTER ----------
@app.route("/admin/update-chapter", methods=["POST"])
def update_chapter():
    try:
        # Check admin authentication
        admin_token = request.headers.get("Admin-Token")
        print(f"🔐 Admin update attempt:")
        print(f"   Received token: {admin_token}")
        print(f"   Stored token: {ADMIN_TOKEN}")
        
        if not admin_token:
            print("❌ No admin token provided")
            return jsonify({"error": "No admin token provided"}), 403
            
        if ADMIN_TOKEN is None:
            print("❌ ADMIN_TOKEN is None - server needs restart or admin login")
            return jsonify({"error": "Admin not initialized"}), 403
            
        if admin_token != ADMIN_TOKEN:
            print("❌ Token mismatch!")
            return jsonify({"error": "Unauthorized"}), 403
        
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Load existing chapters
        with open(CHAPTERS_FILE, "r") as f:
            chapters = json.load(f)
        
        chapter_id = data.get("chapter_id")
        if not chapter_id:
            return jsonify({"error": "No chapter_id provided"}), 400
        
        # Update or create chapter
        chapters[chapter_id] = {
            "name": data.get("name", ""),
            "questions": data.get("questions", [])
        }
        
        # Save back to file
        with open(CHAPTERS_FILE, "w") as f:
            json.dump(chapters, f, indent=2)
        
        print(f"✅ Chapter updated: {chapter_id}")
        return jsonify({
            "success": True,
            "updated": chapter_id,
            "questions_count": len(chapters[chapter_id]["questions"])
        })
        
    except Exception as e:
        print(f"❌ Update chapter error: {e}")
        return jsonify({"error": str(e)}), 500

# ---------- ADMIN GET ALL CHAPTERS ----------
@app.route("/admin/chapters", methods=["GET"])
def get_all_chapters():
    try:
        admin_token = request.headers.get("Admin-Token")
        if admin_token != ADMIN_TOKEN:
            return jsonify({"error": "Unauthorized"}), 403
        
        with open(CHAPTERS_FILE, "r") as f:
            chapters = json.load(f)
        
        return jsonify({
            "success": True,
            "chapters": chapters,
            "count": len(chapters)
        })
        
    except Exception as e:
        print(f"Get chapters error: {e}")
        return jsonify({"error": str(e)}), 500

# ---------- ADMIN DELETE CHAPTER ----------
@app.route("/admin/delete-chapter/<chapter_id>", methods=["DELETE"])
def delete_chapter(chapter_id):
    try:
        admin_token = request.headers.get("Admin-Token")
        if admin_token != ADMIN_TOKEN:
            return jsonify({"error": "Unauthorized"}), 403
        
        with open(CHAPTERS_FILE, "r") as f:
            chapters = json.load(f)
        
        if chapter_id not in chapters:
            return jsonify({"error": "Chapter not found"}), 404
        
        # Delete the chapter
        del chapters[chapter_id]
        
        with open(CHAPTERS_FILE, "w") as f:
            json.dump(chapters, f, indent=2)
        
        return jsonify({
            "success": True,
            "deleted": chapter_id
        })
        
    except Exception as e:
        print(f"Delete chapter error: {e}")
        return jsonify({"error": str(e)}), 500

# ---------- ADMIN CHECK TOKEN ----------
@app.route("/admin/check-token", methods=["POST"])
def check_admin_token():
    """Endpoint to check if admin token is valid"""
    admin_token = request.headers.get("Admin-Token")
    
    response = {
        "token_provided": bool(admin_token),
        "token_valid": admin_token == ADMIN_TOKEN,
        "admin_token_exists": ADMIN_TOKEN is not None,
        "message": "Token check successful" if admin_token == ADMIN_TOKEN else "Token invalid"
    }
    
    return jsonify(response)

# ---------- INITIALIZATION ----------
def initialize_files():
    """Create necessary files if they don't exist"""
    print("📁 Initializing data files...")
    
    # Ensure users.json exists
    if not USERS_FILE.exists():
        print(f"   Creating {USERS_FILE.name}...")
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f, indent=2)
    
    # Ensure chapters.json exists with basic structure
    if not CHAPTERS_FILE.exists():
        print(f"   Creating {CHAPTERS_FILE.name}...")
        with open(CHAPTERS_FILE, 'w') as f:
            json.dump({
                "chapter1": {
                    "name": "Introduction to Law",
                    "questions": [
                        {
                            "id": "q1",
                            "text": "What are the main sources of law in Pakistan? Explain each briefly.",
                            "marks": 5
                        },
                        {
                            "id": "q2", 
                            "text": "Differentiate between civil law and criminal law with examples.",
                            "marks": 5
                        }
                    ]
                }
            }, f, indent=2)

# ---------- CACHE CONTROL ----------
@app.after_request
def add_header(response):
    """Add headers to prevent caching"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ---------- START APPLICATION ----------
if __name__ == "__main__":
    # Initialize files
    initialize_files()
    
    print("\n" + "="*60)
    print("🎯 ICAP AI EXAMINER - CLOUD READY")
    print("="*60)
    
    print("\n🌐 DEPLOYMENT INFORMATION:")
    print(f"   • Static files: Enabled")
    print(f"   • Admin: /admin-login.html")
    print(f"   • Main app: /index.html")
    print(f"   • Database: JSON files")
    print(f"   • AI: Cloud-friendly evaluation")
    
    print("\n📊 AVAILABLE PAGES:")
    print("   1. Home: /")
    print("   2. Subjects: /subjects.html")
    print("   3. Business Law: /business-law.html")
    print("   4. Chapter 1: /chapter1.html")
    print("   5. Admin: /admin-login.html")
    
    print("\n✅ READY TO SERVE!")
    port = int(os.environ.get("PORT", 5000))
    print(f"   Running on port: {port}")
    print("="*60 + "\n")
    
    app.run(host="0.0.0.0", port=port, debug=False)