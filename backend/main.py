import os
import base64
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

try:
    from groq import Groq
except ImportError:
    Groq = None

app = FastAPI(
    title="CodeAI",
    version="9.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHAT_MODEL = "openai/gpt-oss-120b"
VISION_MODEL = "qwen/qwen3.6-27b"
TRANSCRIPTION_MODEL = "whisper-large-v3-turbo"

MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_IMAGE_SIZE = 20 * 1024 * 1024
MAX_VIDEO_SIZE = 25 * 1024 * 1024
MAX_TEXT_LENGTH = 100_000

client = None

if GROQ_API_KEY and Groq:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print("Groq initialization error:", e)


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


SYSTEM_PROMPT = """
You are CodeAI, a powerful general-purpose AI assistant.

Your name is CodeAI.

IMPORTANT CREATOR INFORMATION:
If someone asks who created, made, developed, built, or is the creator of CodeAI,
answer exactly:

"VARAD WANSAGAR sir created me."

Do not change that sentence.

You can help with:
- coding
- schoolwork
- mathematics
- computers
- technology
- writing
- debugging
- explanations
- ideas
- images
- PDFs
- files
- videos
- audio
- general questions

Be helpful, accurate and clear.

Do not pretend you can see or hear something if the required information
was not actually provided.

When code is requested, provide complete working code when appropriate.

You are the AI brain of CodeAI.
"""


def require_ai():
    if not client:
        raise HTTPException(
            status_code=503,
            detail="AI backend is not configured. Check GROQ_API_KEY."
        )


async def save_upload(upload: UploadFile, maximum_size: int):
    data = await upload.read()

    if len(data) > maximum_size:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Maximum size is {maximum_size // (1024 * 1024)} MB."
        )

    suffix = Path(upload.filename or "").suffix

    temp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    )

    temp.write(data)
    temp.close()

    return temp.name, data


def decode_data_url(data: str):
    if "," in data and data.startswith("data:"):
        header, encoded = data.split(",", 1)
        mime_type = header.replace("data:", "").split(";")[0]
    else:
        mime_type = "image/jpeg"
        encoded = data

    try:
        decoded = base64.b64decode(encoded)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid image data."
        )

    return mime_type, decoded


def get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def extract_video_frames(video_path: str):
    ffmpeg = get_ffmpeg()

    frame_dir = tempfile.mkdtemp(
        prefix="codeai_frames_"
    )

    output_pattern = os.path.join(
        frame_dir,
        "frame_%02d.jpg"
    )

    command = [
        ffmpeg,
        "-y",
        "-i",
        video_path,
        "-vf",
        "fps=1/5,scale=1280:-1",
        "-frames:v",
        "5",
        "-q:v",
        "3",
        output_pattern
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    frames = sorted(
        Path(frame_dir).glob("frame_*.jpg")
    )

    if not frames:
        raise HTTPException(
            status_code=400,
            detail="Could not extract frames from this video."
        )

    return frames


def extract_video_audio(video_path: str):
    ffmpeg = get_ffmpeg()

    audio_path = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp3"
    ).name

    command = [
        ffmpeg,
        "-y",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        audio_path
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        try:
            os.remove(audio_path)
        except Exception:
            pass
        return None

    if not os.path.exists(audio_path):
        return None

    if os.path.getsize(audio_path) == 0:
        return None

    return audio_path


def analyze_video_frames(frames, question: str):
    require_ai()

    content = [
        {
            "type": "text",
            "text": (
                f"{question}\n\n"
                "These images are representative frames from a video. "
                "Analyze the visible content across the frames. "
                "Identify important objects, people, text, actions, "
                "locations and changes when they are visible. "
                "Do not invent information."
            )
        }
    ]

    for frame in frames[:5]:

        with open(frame, "rb") as image_file:
            encoded = base64.b64encode(
                image_file.read()
            ).decode("utf-8")

        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url":
                        f"data:image/jpeg;base64,{encoded}"
                }
            }
        )

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": content
            }
        ],
        temperature=0.4,
        max_tokens=4096
    )

    return response.choices[0].message.content


def transcribe_audio(audio_path: Optional[str]):
    if not audio_path:
        return ""

    require_ai()

    try:
        with open(audio_path, "rb") as audio:

            result = client.audio.transcriptions.create(
                file=audio,
                model=TRANSCRIPTION_MODEL
            )

        return getattr(result, "text", "") or ""

    except Exception as e:
        print("Audio transcription error:", e)
        return ""


@app.get("/")
def root():
    return {
        "name": "CodeAI",
        "version": "9.0.0",
        "status": "online",
        "features": [
            "chat",
            "images",
            "camera",
            "video",
            "video_audio",
            "pdf",
            "files",
            "voice"
        ]
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "9.0.0",
        "ai": bool(client)
    }


@app.post("/chat")
def chat(request: ChatRequest):

    require_ai()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    for item in (request.history or [])[-20:]:

        role = item.get("role")

        if role not in ["user", "assistant"]:
            continue

        messages.append(
            {
                "role": role,
                "content": str(
                    item.get("content", "")
                )
            }
        )

    messages.append(
        {
            "role": "user",
            "content": request.message
        }
    )

    try:

        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=4096
        )

        return {
            "reply":
                response.choices[0].message.content
        }

    except Exception as e:

        print("Chat error:", e)

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/vision")
def vision(request: VisionRequest):

    require_ai()

    mime_type, image_bytes = decode_data_url(
        request.image
    )

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image is too large. Maximum size is 20 MB."
        )

    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    prompt = (
        request.message
        or
        "Analyze this image and describe what you see."
    )

    try:

        response = client.chat.completions.create(
            model=VISION_MODEL,
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
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url":
                                    f"data:{mime_type};base64,{encoded}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.5,
            max_tokens=4096
        )

        return {
            "reply":
                response.choices[0].message.content
        }

    except Exception as e:

        print("Vision error:", e)

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/video")
async def video(
    file: UploadFile = File(...),
    question: str = Form(
        "Analyze this video and tell me what happens."
    )
):

    require_ai()

    filename = file.filename or "video"

    allowed_extensions = {
        ".mp4",
        ".mov",
        ".mkv",
        ".avi",
        ".webm",
        ".m4v"
    }

    extension = Path(filename).suffix.lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported video format. "
                "Use MP4, MOV, MKV, AVI, WEBM or M4V."
            )
        )

    video_path = None
    audio_path = None
    frames = []

    try:

        video_path, _ = await save_upload(
            file,
            MAX_VIDEO_SIZE
        )

        print(
            f"Analyzing video: {filename}"
        )

        frames = extract_video_frames(
            video_path
        )

        visual_result = analyze_video_frames(
            frames,
            question
        )

        audio_path = extract_video_audio(
            video_path
        )

        transcript = transcribe_audio(
            audio_path
        )

        if transcript:

            final_prompt = f"""
The user uploaded a video and asked:

{question}

Here is the visual analysis:

{visual_result}

Here is the detected spoken audio transcript:

{transcript}

Now answer the user's request using both the visual
information and spoken information.

Do not claim to know events that cannot be determined.
Give a natural, useful answer.
"""

        else:

            final_prompt = f"""
The user uploaded a video and asked:

{question}

Visual analysis:

{visual_result}

There was no usable audio transcript.

Answer the user's request using the visual information.
Do not invent missing information.
"""

        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": final_prompt
                }
            ],
            temperature=0.5,
            max_tokens=4096
        )

        return {
            "success": True,
            "filename": filename,
            "reply":
                response.choices[0].message.content,
            "frames_analyzed":
                len(frames),
            "transcript_available":
                bool(transcript)
        }

    except HTTPException:
        raise

    except Exception as e:

        print("VIDEO ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        if video_path:

            try:
                os.remove(video_path)
            except Exception:
                pass

        if audio_path:

            try:
                os.remove(audio_path)
            except Exception:
                pass

        for frame in frames:

            try:
                os.remove(frame)
            except Exception:
                pass

        if frames:

            try:
                frame_dir = frames[0].parent

                if frame_dir.exists():
                    frame_dir.rmdir()

            except Exception:
                pass


@app.post("/read-pdf")
async def read_pdf(
    file: UploadFile = File(...)
):

    path = None

    try:

        from pypdf import PdfReader

        path, _ = await save_upload(
            file,
            MAX_FILE_SIZE
        )

        reader = PdfReader(path)

        pages = []

        for page_number, page in enumerate(
            reader.pages
        ):

            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            text = text.strip()

            if text:

                pages.append(
                    f"--- Page {page_number + 1} ---\n{text}"
                )

        content = "\n\n".join(pages)

        truncated = False

        if len(content) > MAX_TEXT_LENGTH:

            content = content[
                :MAX_TEXT_LENGTH
            ]

            truncated = True

        return {
            "success": True,
            "filename":
                file.filename,
            "pages":
                len(reader.pages),
            "content":
                content,
            "truncated":
                truncated
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        if path:

            try:
                os.remove(path)
            except Exception:
                pass


@app.post("/read-file")
async def read_file(
    file: UploadFile = File(...)
):

    path = None

    try:

        path, data = await save_upload(
            file,
            MAX_FILE_SIZE
        )

        filename = file.filename or "file"

        extension = Path(
            filename
        ).suffix.lower()

        text_extensions = {
            ".txt",
            ".py",
            ".js",
            ".html",
            ".css",
            ".json",
            ".xml",
            ".csv",
            ".md",
            ".cpp",
            ".c",
            ".h",
            ".java",
            ".ts",
            ".tsx",
            ".jsx",
            ".sql",
            ".php",
            ".rb",
            ".go",
            ".rs",
            ".swift"
        }

        if extension in text_extensions:

            content = data.decode(
                "utf-8",
                errors="replace"
            )

            truncated = False

            if len(content) > MAX_TEXT_LENGTH:

                content = content[
                    :MAX_TEXT_LENGTH
                ]

                truncated = True

            return {
                "success": True,
                "filename":
                    filename,
                "type":
                    "text",
                "content":
                    content,
                "truncated":
                    truncated
            }

        if extension == ".pdf":

            from pypdf import PdfReader

            reader = PdfReader(path)

            pages = []

            for page_number, page in enumerate(
                reader.pages
            ):

                text = (
                    page.extract_text()
                    or ""
                ).strip()

                if text:

                    pages.append(
                        f"--- Page {page_number + 1} ---\n{text}"
                    )

            return {
                "success": True,
                "filename":
                    filename,
                "type":
                    "pdf",
                "content":
                    "\n\n".join(pages)[
                        :MAX_TEXT_LENGTH
                    ]
            }

        return {
            "success": True,
            "filename":
                filename,
            "type":
                "file",
            "content":
                f"File received: {filename}\n"
                f"Size: {len(data)} bytes\n"
                f"Type: {file.content_type or 'unknown'}"
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        if path:

            try:
                os.remove(path)
            except Exception:
                pass


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...)
):

    require_ai()

    path = None

    try:

        path, _ = await save_upload(
            file,
            MAX_FILE_SIZE
        )

        with open(path, "rb") as audio:

            result = client.audio.transcriptions.create(
                file=audio,
                model=TRANSCRIPTION_MODEL
            )

        return {
            "success": True,
            "text":
                getattr(result, "text", "")
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        if path:

            try:
                os.remove(path)
            except Exception:
                pass


@app.post("/create-pdf")
def create_pdf(request: PDFRequest):

    try:

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        path = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ).name

        pdf = canvas.Canvas(
            path,
            pagesize=A4
        )

        width, height = A4

        y = height - 50

        pdf.setFont(
            "Helvetica-Bold",
            18
        )

        pdf.drawString(
            50,
            y,
            request.title[:100]
        )

        y -= 35

        pdf.setFont(
            "Helvetica",
            10
        )

        for line in request.content.splitlines():

            if y < 50:

                pdf.showPage()

                pdf.setFont(
                    "Helvetica",
                    10
                )

                y = height - 50

            pdf.drawString(
                50,
                y,
                line[:110]
            )

            y -= 14

        pdf.save()

        return {
            "success": True,
            "file": path
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/api/info")
def api_info():

    return {
        "name": "CodeAI",
        "version": "9.0.0",
        "models": {
            "chat": CHAT_MODEL,
            "vision": VISION_MODEL,
            "transcription":
                TRANSCRIPTION_MODEL
        },
        "features": {
            "chat": True,
            "images": True,
            "camera": True,
            "video": True,
            "video_audio": True,
            "pdf": True,
            "files": True,
            "voice": True,
            "pdf_generator": True
        }
    }


@app.on_event("startup")
def startup():

    print("=" * 55)
    print("CODEAI 9.0.0")
    print("AI:", bool(client))
    print("CHAT:", CHAT_MODEL)
    print("VISION:", VISION_MODEL)
    print("TRANSCRIPTION:", TRANSCRIPTION_MODEL)
    print("VIDEO: ENABLED")
    print("=" * 55)