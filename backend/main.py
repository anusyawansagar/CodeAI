import os
import io
import base64
import mimetypes

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq

import fitz  # PyMuPDF

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


# =========================================================
# ENVIRONMENT
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="CodeAI",
    version="2.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# =========================================================
# GROQ
# =========================================================

client = None

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)


# =========================================================
# REQUEST MODELS
# =========================================================

class ChatRequest(BaseModel):
    message: str
    language: str = "Python"
    history: list = []


class PDFRequest(BaseModel):
    title: str = "CodeAI Document"
    content: str


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are CodeAI, an advanced AI assistant and coding agent.

Your creator is:

VARAD WANSAGAR

If the user asks who created, made, built, or developed you,
say:

"VARAD WANSAGAR sir created me as a coding agent."

========================================================
IDENTITY
========================================================

Your name is CodeAI.

You are friendly, intelligent, practical and honest.

You can help with:

- General questions
- Programming
- Mathematics
- Science
- Technology
- Computers
- School learning
- Writing
- Brainstorming
- Debugging
- Software projects
- Websites
- Apps
- Game development
- Programming languages
- File analysis
- Documents
- Images
- PDFs
- Research

Do not pretend you performed an action when you did not.

========================================================
CODING
========================================================

You are an expert programming teacher.

Support:

Python
JavaScript
HTML
CSS
C
C++
Java
Rust
Go
SQL
PHP
and other legitimate programming technologies.

When debugging:

1. Find the likely problem.
2. Explain why it happens.
3. Give corrected code.
4. Explain how the fix works.

Prefer complete working examples when appropriate.

========================================================
GENERAL QUESTIONS
========================================================

Do not force every question into programming.

If someone asks a normal question, answer normally.

Be conversational and friendly.

========================================================
FILES
========================================================

If file contents are provided, analyze the contents carefully.

Do not claim to have read a file unless its contents were actually provided.

========================================================
IMAGES
========================================================

When image information is provided, describe what is actually visible.

Do not invent objects, text, people or details that cannot be determined.

========================================================
CYBERSECURITY
========================================================

Cybersecurity help should remain educational,
defensive, ethical, or limited to systems the user is authorized to test.

Do not help steal credentials, deploy malware,
attack real systems without authorization,
or bypass security protections.

========================================================
STYLE
========================================================

Be friendly like a helpful expert.

For beginners, explain things simply.

For advanced users, give technical detail.

Use Markdown-style formatting.

Use code blocks for code.

Do not unnecessarily repeat the question.

Give practical answers.

If you are uncertain, say so instead of inventing facts.
"""


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {
        "status": "online",
        "name": "CodeAI",
        "version": "2.0.0",
        "ai_configured": client is not None,
        "features": [
            "chat",
            "web",
            "code",
            "pdf",
            "files",
            "images"
        ]
    }


# =========================================================
# CHAT
# =========================================================

@app.post("/chat")
def chat(request: ChatRequest):

    if client is None:
        return {
            "reply": "❌ GROQ_API_KEY is not configured."
        }

    message_lower = request.message.lower()

    creator_words = [
        "who created you",
        "who made you",
        "who built you",
        "who is your creator",
        "who developed you",
        "who created codeai",
        "who made codeai"
    ]

    if any(word in message_lower for word in creator_words):

        return {
            "reply":
            "VARAD WANSAGAR sir created me as a coding agent."
        }

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    recent_history = request.history[-20:]

    for item in recent_history:

        role = item.get("role")
        content = item.get("content")

        if role in ["user", "assistant"] and content:

            messages.append({
                "role": role,
                "content": str(content)
            })

    messages.append({
        "role": "user",
        "content": request.message
    })

    try:

        # Groq Compound can use built-in tools such as
        # web search and code execution.
        response = client.chat.completions.create(

            model="groq/compound",

            messages=messages,

            temperature=0.3,

            max_completion_tokens=4096
        )

        answer = response.choices[0].message.content

        return {
            "reply": answer
        }

    except Exception as error:

        print("AI ERROR:", error)

        return {
            "reply":
            "❌ AI error. Please try again."
        }


# =========================================================
# READ FILE
# =========================================================

@app.post("/read-file")
async def read_file(file: UploadFile = File(...)):

    try:

        filename = file.filename or "unknown"

        data = await file.read()

        lower_name = filename.lower()

        # -----------------------------------------------
        # PDF
        # -----------------------------------------------

        if lower_name.endswith(".pdf"):

            document = fitz.open(
                stream=data,
                filetype="pdf"
            )

            text_parts = []

            for page in document:

                text_parts.append(
                    page.get_text()
                )

            document.close()

            text = "\n".join(text_parts)

            return {
                "filename": filename,
                "type": "pdf",
                "text": text[:100000]
            }

        # -----------------------------------------------
        # TEXT / CODE
        # -----------------------------------------------

        text_extensions = (
            ".txt",
            ".py",
            ".js",
            ".html",
            ".css",
            ".json",
            ".xml",
            ".csv",
            ".md",
            ".sql",
            ".cpp",
            ".c",
            ".java",
            ".rs",
            ".go"
        )

        if lower_name.endswith(text_extensions):

            text = data.decode(
                "utf-8",
                errors="replace"
            )

            return {
                "filename": filename,
                "type": "text",
                "text": text[:100000]
            }

        return {
            "filename": filename,
            "type": "unsupported",
            "text": "",
            "message": "This file type is not currently supported."
        }

    except Exception as error:

        print("FILE ERROR:", error)

        return {
            "filename": file.filename,
            "type": "error",
            "text": "",
            "message": "Could not read this file."
        }


# =========================================================
# READ MULTIPLE FILES / FOLDER
# =========================================================

@app.post("/read-files")
async def read_files(files: list[UploadFile] = File(...)):

    results = []

    for file in files:

        try:

            data = await file.read()

            filename = file.filename or "unknown"

            lower_name = filename.lower()

            text = ""

            # PDF
            if lower_name.endswith(".pdf"):

                document = fitz.open(
                    stream=data,
                    filetype="pdf"
                )

                parts = []

                for page in document:

                    parts.append(
                        page.get_text()
                    )

                document.close()

                text = "\n".join(parts)

            # Text/code
            elif lower_name.endswith((
                ".txt",
                ".py",
                ".js",
                ".html",
                ".css",
                ".json",
                ".xml",
                ".csv",
                ".md",
                ".sql",
                ".cpp",
                ".c",
                ".java",
                ".rs",
                ".go"
            )):

                text = data.decode(
                    "utf-8",
                    errors="replace"
                )

            else:

                continue

            results.append({
                "filename": filename,
                "text": text[:50000]
            })

        except Exception as error:

            print(
                "MULTI FILE ERROR:",
                error
            )

    return {
        "count": len(results),
        "files": results
    }


# =========================================================
# IMAGE READER
# =========================================================

@app.post("/vision")
async def vision(
    file: UploadFile = File(...),
    question: str = Form(
        "Describe this image."
    )
):

    if client is None:

        return {
            "reply":
            "❌ GROQ_API_KEY is not configured."
        }

    try:

        data = await file.read()

        if len(data) > 20 * 1024 * 1024:

            return {
                "reply":
                "❌ Image is too large. Please use an image under 20 MB."
            }

        mime_type = file.content_type

        if not mime_type or not mime_type.startswith("image/"):

            mime_type = (
                mimetypes.guess_type(
                    file.filename or ""
                )[0]
                or "image/jpeg"
            )

        encoded = base64.b64encode(
            data
        ).decode("utf-8")

        image_url = (
            f"data:{mime_type};base64,{encoded}"
        )

        response = client.chat.completions.create(

            model="qwen/qwen3.8-27b",

            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": question
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ],

            temperature=0.2,

            max_completion_tokens=2048
        )

        return {
            "reply":
            response.choices[0].message.content
        }

    except Exception as error:

        print(
            "VISION ERROR:",
            error
        )

        return {
            "reply":
            "❌ Could not analyze the image."
        }


# =========================================================
# CREATE PDF
# =========================================================

@app.post("/create-pdf")
def create_pdf(request: PDFRequest):

    try:

        buffer = io.BytesIO()

        pdf = canvas.Canvas(
            buffer,
            pagesize=A4
        )

        width, height = A4

        margin = 45

        y = height - margin

        pdf.setTitle(
            request.title
        )

        # Title
        pdf.setFont(
            "Helvetica-Bold",
            18
        )

        pdf.drawString(
            margin,
            y,
            request.title[:80]
        )

        y -= 35

        # Body
        pdf.setFont(
            "Helvetica",
            10
        )

        lines = request.content.splitlines()

        for line in lines:

            # ReportLab's default font does not
            # support every Unicode character.
            safe_line = (
                line
                .encode(
                    "latin-1",
                    "replace"
                )
                .decode("latin-1")
            )

            # Basic wrapping
            while len(safe_line) > 100:

                part = safe_line[:100]

                pdf.drawString(
                    margin,
                    y,
                    part
                )

                y -= 14

                if y < margin:

                    pdf.showPage()

                    pdf.setFont(
                        "Helvetica",
                        10
                    )

                    y = height - margin

                safe_line = safe_line[100:]

            pdf.drawString(
                margin,
                y,
                safe_line
            )

            y -= 14

            if y < margin:

                pdf.showPage()

                pdf.setFont(
                    "Helvetica",
                    10
                )

                y = height - margin

        pdf.save()

        buffer.seek(0)

        filename = (
            request.title
            .replace(" ", "_")
            + ".pdf"
        )

        return StreamingResponse(

            buffer,

            media_type="application/pdf",

            headers={
                "Content-Disposition":
                f'attachment; filename="{filename}"'
            }
        )

    except Exception as error:

        print(
            "PDF ERROR:",
            error
        )

        return {
            "error":
            "Could not create PDF."
        }