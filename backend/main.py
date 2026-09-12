import os
import base64
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

# ============================================================
# ENVIRONMENT
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ============================================================
# OPTIONAL IMPORTS
# ============================================================

try:
    from groq import Groq
except ImportError:
    Groq = None

# ============================================================
# FASTAPI
# ============================================================

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="CodeAI",
    version="7.0.0",
    description="CodeAI - General AI Assistant"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# MODELS
# ============================================================

CHAT_MODEL = "openai/gpt-oss-120b"
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
TRANSCRIPTION_MODEL = "whisper-large-v3-turbo"

# ============================================================
# GROQ CLIENT
# ============================================================

client = None

if GROQ_API_KEY and Groq:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print("Groq client error:", e)
        client = None

# ============================================================
# REQUEST MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = "general"
    history: Optional[List[Dict[str, Any]]] = []


class VisionRequest(BaseModel):
    message: str
    image: str


class PDFRequest(BaseModel):
    title: str
    content: str


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are CodeAI, a powerful general-purpose AI assistant.

Your name is CodeAI.

IMPORTANT CREATOR INFORMATION:
If someone asks who created, made, developed, built, or is the creator of CodeAI,
answer exactly:

"VARAD WANSAGAR sir created me."

Do not change that sentence.

GENERAL BEHAVIOR:
- Be helpful, accurate, clear and friendly.
- Help with coding, schoolwork, computers, technology, writing,
  explanations, ideas, debugging, mathematics and general questions.
- Do not pretend to have abilities you do not have.
- Give practical answers.
- When code is requested, provide complete working code when appropriate.
- Explain errors clearly.
- Do not advertise subscriptions.
- CodeAI has no subscriptions.
- CodeAI has no ads.
- CodeAI is designed to be free to use.

You are the AI brain of CodeAI.
"""


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():
    print()
    print("========================================")
    print("              CODEAI")
    print("          BACKEND 7.0")
    print("========================================")
    print("Status: ONLINE")

    if client:
        print("AI: CONFIGURED")
    else:
        print("AI: NOT CONFIGURED")

    print("Creator: VARAD WANSAGAR")
    print("Subscriptions: OFF")
    print("Ads: OFF")
    print("========================================")
    print()


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():
    return {
        "name": "CodeAI",
        "version": "7.0.0",
        "status": "online",
        "ai_configured": client is not None,
        "subscriptions": False,
        "ads": False,
        "accounts": "Firebase"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "ai_configured": client is not None
    }


# ============================================================
# CHAT
# ============================================================

@app.post("/chat")
async def chat(request: ChatRequest):

    if not client:
        raise HTTPException(
            status_code=503,
            detail="AI is not configured. Check GROQ_API_KEY in backend/.env."
        )

    message = request.message.strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty."
        )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    # Add previous conversation
    if request.history:
        for item in request.history[-20:]:
            role = item.get("role")
            content = item.get("content")

            if role in ("user", "assistant") and content:
                messages.append(
                    {
                        "role": role,
                        "content": str(content)
                    }
                )

    messages.append(
        {
            "role": "user",
            "content": message
        }
    )

    try:
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=4096
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = "I couldn't generate a response."

        return {
            "success": True,
            "answer": answer,
            "model": CHAT_MODEL
        }

    except Exception as e:
        print("CHAT ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"AI request failed: {str(e)}"
        )


# ============================================================
# VISION
# ============================================================

@app.post("/vision")
async def vision(request: VisionRequest):

    if not client:
        raise HTTPException(
            status_code=503,
            detail="AI is not configured."
        )

    if not request.image:
        raise HTTPException(
            status_code=400,
            detail="Image is missing."
        )

    try:
        image_data = request.image

        # Accept either:
        # data:image/png;base64,...
        # OR raw base64
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        image_url = f"data:image/jpeg;base64,{image_data}"

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": request.message or "Describe and analyze this image."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ]

        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=messages,
            temperature=0.5,
            max_tokens=2048
        )

        answer = response.choices[0].message.content

        return {
            "success": True,
            "answer": answer or "I couldn't analyze the image.",
            "model": VISION_MODEL
        }

    except Exception as e:
        print("VISION ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"Vision request failed: {str(e)}"
        )


# ============================================================
# READ SINGLE FILE
# ============================================================

@app.post("/read-file")
async def read_file(file: UploadFile = File(...)):

    try:
        data = await file.read()

        filename = file.filename or "file"

        # Text/code files
        text_extensions = {
            ".txt",
            ".py",
            ".js",
            ".html",
            ".css",
            ".cpp",
            ".c",
            ".java",
            ".json",
            ".xml",
            ".md",
            ".csv",
            ".sql",
            ".ts",
            ".tsx",
            ".jsx",
            ".php",
            ".sh",
            ".bat",
            ".ps1"
        }

        extension = Path(filename).suffix.lower()

        if extension in text_extensions:
            text = data.decode("utf-8", errors="replace")

            return {
                "success": True,
                "filename": filename,
                "content": text
            }

        return {
            "success": True,
            "filename": filename,
            "content": (
                f"File received successfully: {filename}\n"
                f"File type: {extension or 'unknown'}\n"
                f"File size: {len(data)} bytes"
            )
        }

    except Exception as e:
        print("FILE ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"Could not read file: {str(e)}"
        )


# ============================================================
# READ MULTIPLE FILES
# ============================================================

@app.post("/read-files")
async def read_files(files: List[UploadFile] = File(...)):

    results = []

    for file in files:

        try:
            data = await file.read()
            filename = file.filename or "file"
            extension = Path(filename).suffix.lower()

            text_extensions = {
                ".txt",
                ".py",
                ".js",
                ".html",
                ".css",
                ".cpp",
                ".c",
                ".java",
                ".json",
                ".xml",
                ".md",
                ".csv",
                ".sql",
                ".ts",
                ".tsx",
                ".jsx",
                ".php",
                ".sh",
                ".bat",
                ".ps1"
            }

            if extension in text_extensions:
                content = data.decode("utf-8", errors="replace")
            else:
                content = (
                    f"File received: {filename}\n"
                    f"Size: {len(data)} bytes"
                )

            results.append(
                {
                    "filename": filename,
                    "content": content
                }
            )

        except Exception as e:
            results.append(
                {
                    "filename": file.filename or "unknown",
                    "error": str(e)
                }
            )

    return {
        "success": True,
        "files": results
    }


# ============================================================
# TRANSCRIPTION
# ============================================================

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):

    if not client:
        raise HTTPException(
            status_code=503,
            detail="AI is not configured."
        )

    temp_path = None

    try:
        audio_data = await file.read()

        if not audio_data:
            raise HTTPException(
                status_code=400,
                detail="Audio file is empty."
            )

        suffix = Path(file.filename or "audio.webm").suffix

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp:
            temp.write(audio_data)
            temp_path = temp.name

        with open(temp_path, "rb") as audio_file:

            result = client.audio.transcriptions.create(
                file=audio_file,
                model=TRANSCRIPTION_MODEL
            )

        text = getattr(result, "text", "")

        return {
            "success": True,
            "text": text
        }

    except HTTPException:
        raise

    except Exception as e:
        print("TRANSCRIPTION ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )

    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                pass


# ============================================================
# CREATE PDF
# ============================================================

@app.post("/create-pdf")
async def create_pdf(request: PDFRequest):

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer
        )
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.enums import TA_CENTER
        from fastapi.responses import FileResponse

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="reportlab is not installed."
        )

    if not request.content.strip():
        raise HTTPException(
            status_code=400,
            detail="PDF content cannot be empty."
        )

    safe_title = "".join(
        c if c.isalnum() or c in (" ", "-", "_") else "_"
        for c in request.title
    ).strip()

    if not safe_title:
        safe_title = "CodeAI_Document"

    filename = f"{safe_title}.pdf"
    output_path = Path(tempfile.gettempdir()) / filename

    try:
        styles = getSampleStyleSheet()

        title_style = styles["Title"]
        title_style.alignment = TA_CENTER

        normal_style = styles["BodyText"]

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )

        story = []

        story.append(
            Paragraph(
                request.title,
                title_style
            )
        )

        story.append(Spacer(1, 20))

        # Keep line breaks
        paragraphs = request.content.split("\n")

        for paragraph in paragraphs:

            if paragraph.strip():
                safe_text = (
                    paragraph
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )

                story.append(
                    Paragraph(
                        safe_text,
                        normal_style
                    )
                )

                story.append(Spacer(1, 8))

        doc.build(story)

        return FileResponse(
            path=str(output_path),
            filename=filename,
            media_type="application/pdf"
        )

    except Exception as e:
        print("PDF ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"PDF creation failed: {str(e)}"
        )


# ============================================================
# SERVER INFO
# ============================================================

@app.get("/api/info")
async def api_info():

    return {
        "name": "CodeAI",
        "version": "7.0.0",
        "creator": "VARAD WANSAGAR",
        "ai": "Groq",
        "chat": CHAT_MODEL,
        "vision": VISION_MODEL,
        "transcription": TRANSCRIPTION_MODEL,
        "subscriptions": False,
        "ads": False,
        "firebase_accounts": True
    }