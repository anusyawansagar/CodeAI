import os
import base64
import tempfile
import html
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
# OPTIONAL GROQ IMPORT
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
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="CodeAI",
    version="8.0.0",
    description="CodeAI - General AI Assistant with Files, Images, PDF and Voice"
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

# Current Groq multimodal model
VISION_MODEL = "qwen/qwen3.6-27b"

TRANSCRIPTION_MODEL = "whisper-large-v3-turbo"

# ============================================================
# LIMITS
# ============================================================

MAX_FILE_SIZE = 25 * 1024 * 1024       # 25 MB
MAX_IMAGE_SIZE = 20 * 1024 * 1024      # 20 MB
MAX_TEXT_LENGTH = 100_000

# ============================================================
# GROQ CLIENT
# ============================================================

client = None

if GROQ_API_KEY and Groq:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print("Groq client error:", repr(e))
        client = None

# ============================================================
# REQUEST MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = "general"
    history: Optional[List[Dict[str, Any]]] = []


class VisionRequest(BaseModel):
    message: Optional[str] = "Analyze this image."
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
- Help users understand images, documents and files when they provide them.
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
# HELPERS
# ============================================================

TEXT_EXTENSIONS = {
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".java",
    ".cs",
    ".php",
    ".rb",
    ".go",
    ".rs",
    ".swift",
    ".kt",
    ".kts",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".md",
    ".csv",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
    ".ini",
    ".env",
    ".log",
}


def require_ai():
    if not client:
        raise HTTPException(
            status_code=503,
            detail="AI is not configured. Check GROQ_API_KEY in backend/.env."
        )


def check_file_size(data: bytes, maximum: int = MAX_FILE_SIZE):
    if len(data) > maximum:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Maximum allowed size is {maximum // (1024 * 1024)} MB."
        )


def clean_filename(filename: str) -> str:
    name = Path(filename).name

    safe = "".join(
        c if c.isalnum() or c in (" ", "-", "_", ".")
        else "_"
        for c in name
    )

    return safe or "file"


def decode_data_url(data_url: str):
    """
    Returns:
        mime_type, raw_bytes
    """

    if not data_url:
        raise HTTPException(
            status_code=400,
            detail="Image data is missing."
        )

    if data_url.startswith("data:"):

        try:
            header, encoded = data_url.split(",", 1)

            mime_type = header.split(";", 1)[0].replace(
                "data:",
                ""
            )

            raw = base64.b64decode(encoded)

            return mime_type or "image/jpeg", raw

        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid base64 image data."
            )

    try:
        raw = base64.b64decode(data_url)

        return "image/jpeg", raw

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid image data."
        )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    print()
    print("========================================")
    print("              CODEAI")
    print("          BACKEND 8.0")
    print("========================================")
    print("Status: ONLINE")

    if client:
        print("AI: CONFIGURED")
    else:
        print("AI: NOT CONFIGURED")

    print()
    print("Chat:", CHAT_MODEL)
    print("Vision:", VISION_MODEL)
    print("Voice:", TRANSCRIPTION_MODEL)
    print()
    print("Files: ENABLED")
    print("Images: ENABLED")
    print("PDF Reader: ENABLED")
    print("PDF Creator: ENABLED")
    print("Voice: ENABLED")
    print()
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
        "version": "8.0.0",
        "status": "online",
        "ai_configured": client is not None,
        "features": {
            "chat": True,
            "images": True,
            "files": True,
            "pdf_reader": True,
            "pdf_creator": True,
            "voice": True
        },
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
        "ai_configured": client is not None,
        "version": "8.0.0"
    }


# ============================================================
# CHAT
# ============================================================

@app.post("/chat")
async def chat(request: ChatRequest):

    require_ai()

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
# VISION / CAMERA / IMAGE ANALYSIS
# ============================================================

@app.post("/vision")
async def vision(request: VisionRequest):

    require_ai()

    if not request.image:
        raise HTTPException(
            status_code=400,
            detail="Image is missing."
        )

    try:

        mime_type, image_bytes = decode_data_url(
            request.image
        )

        if len(image_bytes) > MAX_IMAGE_SIZE:

            raise HTTPException(
                status_code=413,
                detail="Image is too large. Maximum image size is 20 MB."
            )

        encoded = base64.b64encode(
            image_bytes
        ).decode("utf-8")

        image_url = (
            f"data:{mime_type};base64,{encoded}"
        )

        prompt = (
            request.message.strip()
            if request.message
            else "Analyze this image carefully. Describe what is visible and answer any useful observations."
        )

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
                        "text": prompt
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
            max_tokens=4096
        )

        answer = response.choices[0].message.content

        return {
            "success": True,
            "answer": answer or "I couldn't analyze the image.",
            "model": VISION_MODEL
        }

    except HTTPException:
        raise

    except Exception as e:

        print("VISION ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"Vision request failed: {str(e)}"
        )


# ============================================================
# READ PDF
# ============================================================

@app.post("/read-pdf")
async def read_pdf(file: UploadFile = File(...)):

    data = await file.read()

    if not data:
        raise HTTPException(
            status_code=400,
            detail="PDF file is empty."
        )

    check_file_size(data)

    filename = clean_filename(
        file.filename or "document.pdf"
    )

    try:

        from pypdf import PdfReader

    except ImportError:

        raise HTTPException(
            status_code=500,
            detail="pypdf is not installed. Add pypdf to requirements.txt."
        )

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as temp:

            temp.write(data)
            temp_path = temp.name

        reader = PdfReader(temp_path)

        pages = []
        total_characters = 0

        for page_number, page in enumerate(reader.pages):

            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            text = text.strip()

            if text:

                pages.append(
                    {
                        "page": page_number + 1,
                        "text": text
                    }
                )

                total_characters += len(text)

        combined_text = "\n\n".join(
            f"--- Page {item['page']} ---\n{item['text']}"
            for item in pages
        )

        if len(combined_text) > MAX_TEXT_LENGTH:

            combined_text = combined_text[
                :MAX_TEXT_LENGTH
            ]

            truncated = True

        else:
            truncated = False

        return {
            "success": True,
            "filename": filename,
            "pages": len(reader.pages),
            "pages_with_text": len(pages),
            "content": combined_text,
            "truncated": truncated,
            "characters": total_characters
        }

    except HTTPException:
        raise

    except Exception as e:

        print("PDF READ ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"Could not read PDF: {str(e)}"
        )

    finally:

        if temp_path:

            try:
                os.remove(temp_path)
            except Exception:
                pass


# ============================================================
# READ SINGLE FILE
# ============================================================

@app.post("/read-file")
async def read_file(file: UploadFile = File(...)):

    try:

        data = await file.read()

        if not data:

            raise HTTPException(
                status_code=400,
                detail="File is empty."
            )

        check_file_size(data)

        filename = clean_filename(
            file.filename or "file"
        )

        extension = Path(filename).suffix.lower()

        # -----------------------------
        # PDF
        # -----------------------------

        if extension == ".pdf":

            try:

                from pypdf import PdfReader

            except ImportError:

                raise HTTPException(
                    status_code=500,
                    detail="pypdf is not installed."
                )

            temp_path = None

            try:

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".pdf"
                ) as temp:

                    temp.write(data)
                    temp_path = temp.name

                reader = PdfReader(temp_path)

                pages = []

                for index, page in enumerate(reader.pages):

                    text = page.extract_text() or ""

                    if text.strip():

                        pages.append(
                            f"--- Page {index + 1} ---\n{text.strip()}"
                        )

                content = "\n\n".join(pages)

                if len(content) > MAX_TEXT_LENGTH:
                    content = content[:MAX_TEXT_LENGTH]

                return {
                    "success": True,
                    "filename": filename,
                    "type": "pdf",
                    "pages": len(reader.pages),
                    "content": content
                }

            finally:

                if temp_path:

                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

        # -----------------------------
        # TEXT / CODE
        # -----------------------------

        if extension in TEXT_EXTENSIONS:

            text = data.decode(
                "utf-8",
                errors="replace"
            )

            truncated = False

            if len(text) > MAX_TEXT_LENGTH:

                text = text[:MAX_TEXT_LENGTH]
                truncated = True

            return {
                "success": True,
                "filename": filename,
                "type": "text",
                "extension": extension,
                "content": text,
                "truncated": truncated
            }

        # -----------------------------
        # IMAGE
        # -----------------------------

        if extension in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif"
        }:

            return {
                "success": True,
                "filename": filename,
                "type": "image",
                "size": len(data),
                "message": (
                    "Image received. Use the /vision endpoint "
                    "for AI image analysis."
                )
            }

        # -----------------------------
        # OTHER FILE
        # -----------------------------

        return {
            "success": True,
            "filename": filename,
            "type": "file",
            "extension": extension or "unknown",
            "size": len(data),
            "content": (
                f"File received successfully.\n"
                f"Filename: {filename}\n"
                f"Type: {extension or 'unknown'}\n"
                f"Size: {len(data)} bytes"
            )
        }

    except HTTPException:
        raise

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

            if len(data) > MAX_FILE_SIZE:

                results.append(
                    {
                        "filename": file.filename or "unknown",
                        "error": "File exceeds 25 MB limit."
                    }
                )

                continue

            filename = clean_filename(
                file.filename or "file"
            )

            extension = Path(filename).suffix.lower()

            if extension in TEXT_EXTENSIONS:

                content = data.decode(
                    "utf-8",
                    errors="replace"
                )

                if len(content) > MAX_TEXT_LENGTH:
                    content = content[:MAX_TEXT_LENGTH]

                results.append(
                    {
                        "filename": filename,
                        "type": "text",
                        "content": content
                    }
                )

            elif extension == ".pdf":

                try:

                    from pypdf import PdfReader

                    temp_path = None

                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=".pdf"
                    ) as temp:

                        temp.write(data)
                        temp_path = temp.name

                    reader = PdfReader(temp_path)

                    pages = []

                    for index, page in enumerate(reader.pages):

                        text = page.extract_text() or ""

                        if text.strip():

                            pages.append(
                                f"--- Page {index + 1} ---\n{text.strip()}"
                            )

                    content = "\n\n".join(pages)

                    if len(content) > MAX_TEXT_LENGTH:
                        content = content[:MAX_TEXT_LENGTH]

                    results.append(
                        {
                            "filename": filename,
                            "type": "pdf",
                            "pages": len(reader.pages),
                            "content": content
                        }
                    )

                except Exception as e:

                    results.append(
                        {
                            "filename": filename,
                            "type": "pdf",
                            "error": str(e)
                        }
                    )

                finally:

                    if temp_path:

                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass

            else:

                results.append(
                    {
                        "filename": filename,
                        "type": "file",
                        "size": len(data),
                        "content": (
                            f"File received: {filename}\n"
                            f"Size: {len(data)} bytes"
                        )
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
# TRANSCRIPTION / VOICE
# ============================================================

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):

    require_ai()

    temp_path = None

    try:

        audio_data = await file.read()

        if not audio_data:

            raise HTTPException(
                status_code=400,
                detail="Audio file is empty."
            )

        # Current Groq docs allow up to 25 MB on the free tier.
        if len(audio_data) > MAX_FILE_SIZE:

            raise HTTPException(
                status_code=413,
                detail="Audio file is too large. Maximum size is 25 MB."
            )

        original_name = file.filename or "audio.webm"

        suffix = Path(
            original_name
        ).suffix or ".webm"

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp:

            temp.write(audio_data)
            temp_path = temp.name

        with open(
            temp_path,
            "rb"
        ) as audio_file:

            result = client.audio.transcriptions.create(
                file=audio_file,
                model=TRANSCRIPTION_MODEL
            )

        text = getattr(
            result,
            "text",
            ""
        )

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

    if not request.content.strip():

        raise HTTPException(
            status_code=400,
            detail="PDF content cannot be empty."
        )

    try:

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer
        )
        from reportlab.lib.styles import (
            getSampleStyleSheet,
            ParagraphStyle
        )
        from reportlab.lib.enums import TA_CENTER

    except ImportError:

        raise HTTPException(
            status_code=500,
            detail="reportlab is not installed."
        )

    safe_title = "".join(
        c if c.isalnum() or c in (" ", "-", "_")
        else "_"
        for c in request.title
    ).strip()

    if not safe_title:
        safe_title = "CodeAI_Document"

    filename = f"{safe_title}.pdf"

    output_path = (
        Path(tempfile.gettempdir())
        / filename
    )

    try:

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "CodeAITitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=20,
            leading=24,
            spaceAfter=20
        )

        normal_style = ParagraphStyle(
            "CodeAINormal",
            parent=styles["BodyText"],
            fontSize=10.5,
            leading=16,
            spaceAfter=8
        )

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
                html.escape(
                    request.title
                ),
                title_style
            )
        )

        story.append(
            Spacer(1, 10)
        )

        paragraphs = request.content.split("\n")

        for paragraph in paragraphs:

            if paragraph.strip():

                safe_text = html.escape(
                    paragraph
                )

                story.append(
                    Paragraph(
                        safe_text,
                        normal_style
                    )
                )

        doc.build(story)

        return FileResponse(
            path=str(output_path),
            filename=filename,
            media_type="application/pdf"
        )

    except Exception as e:

        print("PDF CREATE ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"PDF creation failed: {str(e)}"
        )


# ============================================================
# API INFO
# ============================================================

@app.get("/api/info")
async def api_info():

    return {
        "name": "CodeAI",
        "version": "8.0.0",
        "creator": "VARAD WANSAGAR",
        "ai": "Groq",
        "chat": CHAT_MODEL,
        "vision": VISION_MODEL,
        "transcription": TRANSCRIPTION_MODEL,
        "features": {
            "chat": True,
            "vision": True,
            "camera": True,
            "files": True,
            "pdf_reader": True,
            "pdf_creator": True,
            "voice": True
        },
        "subscriptions": False,
        "ads": False,
        "firebase_accounts": True
    }