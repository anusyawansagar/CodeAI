import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq


# ==========================================
# LOAD ENV
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))


# ==========================================
# APP
# ==========================================

app = FastAPI(
    title="CodeAI",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ==========================================
# GROQ
# ==========================================

api_key = os.getenv("GROQ_API_KEY")

client = None

if api_key:
    client = Groq(api_key=api_key)


# ==========================================
# REQUEST MODEL
# ==========================================

class ChatRequest(BaseModel):

    message: str

    language: str = "Python"

    history: list = []


# ==========================================
# HOME
# ==========================================

@app.get("/")
def home():

    return {
        "status": "online",
        "name": "CodeAI",
        "ai_configured": client is not None
    }


# ==========================================
# CHAT
# ==========================================

@app.post("/chat")
def chat(request: ChatRequest):

    if client is None:

        return {
            "reply": "❌ GROQ_API_KEY is not configured."
        }


    # ======================================
    # CREATOR RESPONSE
    # ======================================

    creator_words = [
        "who created you",
        "who made you",
        "who built you",
        "who is your creator",
        "who developed you",
        "who created codeai",
        "who made codeai"
    ]


    message_lower = request.message.lower()


    if any(
        word in message_lower
        for word in creator_words
    ):

        return {
            "reply":
            "VARAD WANSAGAR sir created me as a coding agent."
        }


    # ======================================
    # SYSTEM PROMPT
    # ======================================

    system_prompt = f"""

You are CodeAI, a professional coding teacher
and programming assistant.

Your purpose is to teach programming, explain
errors, debug code, and help users build
legitimate software projects.

Current programming language:

{request.language}


==========================================
CREATOR
==========================================

If asked who created, built, made, or developed
you, answer:

"VARAD WANSAGAR sir created me as a coding agent."


==========================================
PROGRAMMING
==========================================

You can teach:

Python
C
C++
Java
JavaScript
HTML
CSS
SQL
Rust
and other programming technologies.

Give working examples and explain them clearly.


==========================================
DEBUGGING
==========================================

When the user provides an error:

1. Identify the likely cause.
2. Explain it.
3. Provide corrected code when useful.
4. Explain how to avoid the problem.


==========================================
CYBERSECURITY
==========================================

You may teach cybersecurity, networking,
ethical hacking, CTF concepts, defensive
security, and authorized security testing.

Keep cybersecurity help educational,
defensive, or limited to systems the user
is authorized to test.

Do not help steal credentials, deploy malware,
attack real systems without authorization,
or bypass security protections.


==========================================
STYLE
==========================================

Be helpful, accurate and practical.

For beginners, explain things simply.

Use code blocks when providing code.

Do not claim to have performed an action
unless you actually performed it.
"""


    # ======================================
    # BUILD CONVERSATION
    # ======================================

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]


    # Last 20 messages only.
    recent_history = request.history[-20:]


    for item in recent_history:

        role = item.get("role")
        content = item.get("content")

        if role in ["user", "assistant"] and content:

            messages.append({
                "role": role,
                "content": str(content)
            })


    # Current message

    messages.append({
        "role": "user",
        "content": request.message
    })


    # ======================================
    # AI REQUEST
    # ======================================

    try:

        response = client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=messages,

            temperature=0.2,

            max_tokens=4096

        )


        answer = response.choices[0].message.content


        return {
            "reply": answer
        }


    except Exception as error:

        print("AI ERROR:", error)

        return {
            "reply":
            "❌ AI error. Check the backend terminal."
        }