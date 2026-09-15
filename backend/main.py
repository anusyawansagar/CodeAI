import os
import base64
import tempfile
import subprocess
import mimetypes
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv(
    Path(__file__).resolve().parent / ".env"
)

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)


# =========================================================
# GROQ
# =========================================================

try:
    from groq import Groq
except ImportError:
    Groq = None


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="CodeAI",
    version="10.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# MODELS
# =========================================================

CHAT_MODEL = "openai/gpt-oss-120b"

VISION_MODEL = "qwen/qwen3.8-27b"

TRANSCRIPTION_MODEL = (
    "whisper-large-v3-turbo"
)


# =========================================================
# LIMITS
# =========================================================

MAX_FILE_SIZE = (
    25 * 1024 * 1024
)

MAX_IMAGE_SIZE = (
    20 * 1024 * 1024
)

MAX_VIDEO_SIZE = (
    25 * 1024 * 1024
)

MAX_TEXT_LENGTH = 100_000


# =========================================================
# GROQ CLIENT
# =========================================================

client = None


if GROQ_API_KEY and Groq:

    try:

        client = Groq(
            api_key=GROQ_API_KEY
        )

        print(
            "✅ Groq client initialized"
        )

    except Exception as error:

        print(
            "❌ Groq initialization error:",
            error
        )

else:

    print(
        "⚠️ GROQ_API_KEY is missing."
    )


# =========================================================
# REQUEST MODELS
# =========================================================

class ChatRequest(BaseModel):

    message: str

    language: Optional[str] = "general"

    history: Optional[
        List[Dict[str, Any]]
    ] = []


class VisionRequest(BaseModel):

    message: Optional[str] = (
        "Analyze this image."
    )

    image: str


class PDFRequest(BaseModel):

    title: str

    content: str


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are CodeAI, a powerful general-purpose AI assistant.

Your name is CodeAI.

IMPORTANT CREATOR INFORMATION:

If someone asks who created, made, developed, built,
or is the creator of CodeAI, answer EXACTLY:

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

Do not pretend you can see or hear something if the
required information was not actually provided.

When code is requested, provide complete working code
when appropriate.

You are the AI brain of CodeAI.
"""


# =========================================================
# AI CHECK
# =========================================================

def require_ai():

    if not client:

        raise HTTPException(
            status_code=503,
            detail=(
                "AI backend is not configured. "
                "Check GROQ_API_KEY."
            )
        )


# =========================================================
# SAVE UPLOAD
# =========================================================

async def save_upload(
    upload: UploadFile,
    maximum_size: int
):

    data = await upload.read()

    if len(data) > maximum_size:

        raise HTTPException(
            status_code=413,
            detail=(
                "File is too large. "
                f"Maximum size is "
                f"{maximum_size // (1024 * 1024)} MB."
            )
        )

    suffix = Path(
        upload.filename or ""
    ).suffix

    temp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    )

    temp.write(data)

    temp.close()

    return temp.name, data


# =========================================================
# DATA URL DECODER
# =========================================================

def decode_data_url(data: str):

    if not data:

        raise HTTPException(
            status_code=400,
            detail="No image data was provided."
        )

    if (
        "," in data
        and data.startswith("data:")
    ):

        header, encoded = data.split(
            ",",
            1
        )

        mime_type = (
            header
            .replace("data:", "")
            .split(";")[0]
        )

    else:

        mime_type = "image/jpeg"

        encoded = data


    try:

        decoded = base64.b64decode(
            encoded,
            validate=True
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid image data."
        )


    return mime_type, decoded


# =========================================================
# FFMPEG
# =========================================================

def get_ffmpeg():

    try:

        import imageio_ffmpeg

        return (
            imageio_ffmpeg
            .get_ffmpeg_exe()
        )

    except Exception:

        return "ffmpeg"


# =========================================================
# VIDEO FRAMES
# =========================================================

def extract_video_frames(
    video_path: str
):

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
        Path(frame_dir).glob(
            "frame_*.jpg"
        )
    )

    if not frames:

        print(
            "FFmpeg error:",
            result.stderr[-2000:]
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Could not extract "
                "frames from this video."
            )
        )

    return frames


# =========================================================
# VIDEO AUDIO
# =========================================================

def extract_video_audio(
    video_path: str
):

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
            os.remove(
                audio_path
            )
        except Exception:
            pass

        return None


    if not os.path.exists(
        audio_path
    ):

        return None


    if os.path.getsize(
        audio_path
    ) == 0:

        return None


    return audio_path


# =========================================================
# VIDEO FRAME ANALYSIS
# =========================================================

def analyze_video_frames(
    frames,
    question: str
):

    require_ai()

    content = [

        {
            "type": "text",

            "text": (
                f"{question}\n\n"

                "These images are representative "
                "frames from a video. "

                "Analyze the visible content "
                "across the frames. "

                "Identify important objects, "
                "people, text, actions, locations "
                "and visible changes. "

                "Do not invent information."
            )
        }
    ]


    for frame in frames[:5]:

        with open(
            frame,
            "rb"
        ) as image_file:

            encoded = base64.b64encode(
                image_file.read()
            ).decode("utf-8")


        content.append(

            {
                "type": "image_url",

                "image_url": {

                    "url":
                        "data:image/jpeg;base64,"
                        + encoded

                }
            }

        )


    try:

        response = (
            client
            .chat
            .completions
            .create(

                model=VISION_MODEL,

                reasoning_effort="none",

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

                temperature=0.3,

                max_completion_tokens=2048
            )
        )


        answer = (
            response
            .choices[0]
            .message
            .content
        )


        return (
            answer
            or
            "I couldn't analyze the video frames."
        )


    except Exception as error:

        print(
            "Video vision error:",
            repr(error)
        )

        raise


# =========================================================
# AUDIO TRANSCRIPTION
# =========================================================

def transcribe_audio(
    audio_path: Optional[str]
):

    if not audio_path:

        return ""


    require_ai()


    try:

        with open(
            audio_path,
            "rb"
        ) as audio:

            result = (
                client
                .audio
                .transcriptions
                .create(

                    file=audio,

                    model=TRANSCRIPTION_MODEL
                )
            )


        return (
            getattr(
                result,
                "text",
                ""
            )
            or ""
        )


    except Exception as error:

        print(
            "Audio transcription error:",
            error
        )

        return ""


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {

        "name": "CodeAI",

        "version": "10.0.0",

        "status": "online",

        "ai": bool(client),

        "features": [

            "chat",

            "images",

            "camera",

            "vision",

            "video",

            "video_audio",

            "pdf",

            "files",

            "voice"

        ]
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {

        "status": "ok",

        "version": "10.0.0",

        "ai": bool(client),

        "chat_model": CHAT_MODEL,

        "vision_model": VISION_MODEL

    }


# =========================================================
# CHAT
# =========================================================

@app.post("/chat")
def chat(
    request: ChatRequest
):

    require_ai()


    message = (
        request.message
        or ""
    ).strip()


    if not message:

        return {
            "success": False,
            "reply": "Please enter a message."
        }


    # -----------------------------------------------------
    # CREATOR RESPONSE
    # -----------------------------------------------------

    creator_words = [

        "who created you",

        "who made you",

        "who built you",

        "who developed you",

        "who is your creator",

        "who created codeai",

        "who made codeai",

        "who built codeai",

        "who developed codeai"

    ]


    lower_message = (
        message.lower()
    )


    if any(
        word in lower_message
        for word in creator_words
    ):

        return {

            "success": True,

            "reply":
                "VARAD WANSAGAR sir created me."

        }


    # -----------------------------------------------------
    # CHAT HISTORY
    # -----------------------------------------------------

    messages = [

        {
            "role": "system",

            "content":
                SYSTEM_PROMPT
        }

    ]


    for item in (
        request.history or []
    )[-10:]:

        role = item.get(
            "role"
        )

        content = item.get(
            "content"
        )


        if role not in [
            "user",
            "assistant"
        ]:

            continue


        if not content:

            continue


        messages.append(

            {
                "role": role,

                "content":
                    str(content)[:8000]
            }

        )


    messages.append(

        {
            "role": "user",

            "content":
                message[:12000]
        }

    )


    # -----------------------------------------------------
    # AI REQUEST
    # -----------------------------------------------------

    try:

        response = (
            client
            .chat
            .completions
            .create(

                model=CHAT_MODEL,

                messages=messages,

                temperature=0.5,

                max_completion_tokens=4096,

                include_reasoning=False
            )
        )


        answer = (
            response
            .choices[0]
            .message
            .content
        )


        if not answer:

            answer = (
                "I couldn't generate a response."
            )


        return {

            "success": True,

            "reply": answer

        }


    except Exception as error:

        print(
            "❌ CHAT ERROR:",
            repr(error)
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "CodeAI chat failed."
            )

        )


# =========================================================
# VISION — JSON BASE64 VERSION
# =========================================================

@app.post("/vision")
async def vision(

    file: Optional[UploadFile] = File(
        None
    ),

    question: str = Form(
        ""
    ),

    message: str = Form(
        ""
    )
):

    require_ai()


    try:

        # -------------------------------------------------
        # IMAGE FROM NORMAL FILE / CAMERA FILE
        # -------------------------------------------------

        if file is not None:

            if not file.filename:

                raise HTTPException(
                    status_code=400,
                    detail="No image was uploaded."
                )


            image_bytes = (
                await file.read()
            )


            if not image_bytes:

                raise HTTPException(
                    status_code=400,
                    detail="The image is empty."
                )


            if len(image_bytes) > MAX_IMAGE_SIZE:

                raise HTTPException(

                    status_code=413,

                    detail=(
                        "Image is too large. "
                        "Maximum size is 20 MB."
                    )

                )


            mime_type = (
                file.content_type
            )


            if (
                not mime_type
                or
                not mime_type.startswith(
                    "image/"
                )
            ):

                mime_type = (
                    mimetypes
                    .guess_type(
                        file.filename
                    )[0]
                    or
                    "image/jpeg"
                )


            filename = (
                file.filename
            )


        # -------------------------------------------------
        # OTHERWISE RETURN ERROR
        # -------------------------------------------------

        else:

            raise HTTPException(

                status_code=400,

                detail=(
                    "No image was uploaded."
                )

            )


        # -------------------------------------------------
        # ENCODE
        # -------------------------------------------------

        encoded = base64.b64encode(
            image_bytes
        ).decode(
            "utf-8"
        )


        image_url = (
            f"data:{mime_type};base64,{encoded}"
        )


        # -------------------------------------------------
        # USER QUESTION
        # -------------------------------------------------

        prompt = (

            question.strip()

            or

            message.strip()

            or

            "Analyze this image carefully. "
            "Tell me what is visible, read "
            "useful text if possible, and "
            "answer naturally."

        )


        # -------------------------------------------------
        # VISION REQUEST
        # -------------------------------------------------

        response = (

            client
            .chat
            .completions
            .create(

                model=VISION_MODEL,

                reasoning_effort="none",

                messages=[

                    {

                        "role":
                            "system",

                        "content":
                            SYSTEM_PROMPT

                    },

                    {

                        "role":
                            "user",

                        "content": [

                            {

                                "type":
                                    "text",

                                "text":
                                    prompt

                            },

                            {

                                "type":
                                    "image_url",

                                "image_url": {

                                    "url":
                                        image_url

                                }

                            }

                        ]

                    }

                ],

                temperature=0.2,

                max_completion_tokens=2048
            )

        )


        # -------------------------------------------------
        # ANSWER
        # -------------------------------------------------

        answer = (

            response
            .choices[0]
            .message
            .content
        )


        if not answer:

            answer = (
                "I couldn't understand "
                "the image."
            )


        return {

            "success": True,

            "filename":
                filename,

            "reply":
                answer

        }


    except HTTPException:

        raise


    except Exception as error:

        print(
            "❌ VISION ERROR:",
            repr(error)
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "CodeAI couldn't analyze "
                "that image."
            )

        )


# =========================================================
# VIDEO
# =========================================================

@app.post("/video")
async def video(

    file: UploadFile = File(
        ...
    ),

    question: str = Form(
        "Analyze this video and tell me what happens."
    )

):

    require_ai()


    filename = (
        file.filename
        or
        "video"
    )


    allowed_extensions = {

        ".mp4",

        ".mov",

        ".mkv",

        ".avi",

        ".webm",

        ".m4v"

    }


    extension = (
        Path(filename)
        .suffix
        .lower()
    )


    if extension not in (
        allowed_extensions
    ):

        raise HTTPException(

            status_code=400,

            detail=(
                "Unsupported video format. "
                "Use MP4, MOV, MKV, AVI, "
                "WEBM or M4V."
            )

        )


    video_path = None

    audio_path = None

    frames = []


    try:

        video_path, _ = (
            await save_upload(

                file,

                MAX_VIDEO_SIZE

            )
        )


        print(
            "🎥 Analyzing video:",
            filename
        )


        frames = (
            extract_video_frames(
                video_path
            )
        )


        visual_result = (
            analyze_video_frames(

                frames,

                question

            )
        )


        audio_path = (
            extract_video_audio(
                video_path
            )
        )


        transcript = (
            transcribe_audio(
                audio_path
            )
        )


        if transcript:

            final_prompt = f"""

The user uploaded a video and asked:

{question}

Visual analysis:

{visual_result}

Detected spoken audio transcript:

{transcript}

Answer the user's request using both
the visual and audio information.

Do not invent information.
"""


        else:

            final_prompt = f"""

The user uploaded a video and asked:

{question}

Visual analysis:

{visual_result}

There was no usable audio transcript.

Answer using the visual information.
Do not invent missing information.
"""


        response = (

            client
            .chat
            .completions
            .create(

                model=CHAT_MODEL,

                messages=[

                    {

                        "role":
                            "system",

                        "content":
                            SYSTEM_PROMPT

                    },

                    {

                        "role":
                            "user",

                        "content":
                            final_prompt

                    }

                ],

                temperature=0.4,

                max_completion_tokens=4096,

                include_reasoning=False
            )

        )


        answer = (

            response
            .choices[0]
            .message
            .content
        )


        return {

            "success": True,

            "filename":
                filename,

            "reply":
                answer
                or
                "I couldn't analyze the video.",

            "frames_analyzed":
                len(frames),

            "transcript_available":
                bool(transcript)

        }


    except HTTPException:

        raise


    except Exception as error:

        print(
            "❌ VIDEO ERROR:",
            repr(error)
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "CodeAI couldn't analyze "
                "that video."
            )

        )


    finally:

        # ---------------------------------------------
        # DELETE VIDEO
        # ---------------------------------------------

        if video_path:

            try:

                os.remove(
                    video_path
                )

            except Exception:
                pass


        # ---------------------------------------------
        # DELETE AUDIO
        # ---------------------------------------------

        if audio_path:

            try:

                os.remove(
                    audio_path
                )

            except Exception:
                pass


        # ---------------------------------------------
        # DELETE FRAMES
        # ---------------------------------------------

        for frame in frames:

            try:

                os.remove(
                    frame
                )

            except Exception:
                pass


        # ---------------------------------------------
        # DELETE FRAME DIRECTORY
        # ---------------------------------------------

        if frames:

            try:

                frame_dir = (
                    frames[0].parent
                )

                if frame_dir.exists():

                    frame_dir.rmdir()

            except Exception:
                pass


# =========================================================
# PDF READER
# =========================================================

@app.post("/read-pdf")
async def read_pdf(

    file: UploadFile = File(
        ...
    )

):

    path = None


    try:

        from pypdf import PdfReader


        path, _ = (
            await save_upload(

                file,

                MAX_FILE_SIZE

            )
        )


        reader = PdfReader(
            path
        )


        pages = []


        for page_number, page in enumerate(
            reader.pages
        ):

            try:

                text = (
                    page.extract_text()
                    or ""
                )

            except Exception:

                text = ""


            text = text.strip()


            if text:

                pages.append(

                    f"--- Page "
                    f"{page_number + 1} ---\n"
                    f"{text}"

                )


        content = (
            "\n\n".join(pages)
        )


        truncated = False


        if len(content) > MAX_TEXT_LENGTH:

            content = (
                content[:MAX_TEXT_LENGTH]
            )

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


    except Exception as error:

        print(
            "PDF error:",
            repr(error)
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "Could not read PDF."
            )

        )


    finally:

        if path:

            try:

                os.remove(
                    path
                )

            except Exception:
                pass


# =========================================================
# FILE READER
# =========================================================

@app.post("/read-file")
async def read_file(

    file: UploadFile = File(
        ...
    )

):

    path = None


    try:

        path, data = (
            await save_upload(

                file,

                MAX_FILE_SIZE

            )
        )


        filename = (
            file.filename
            or
            "file"
        )


        extension = (
            Path(filename)
            .suffix
            .lower()
        )


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


        # -------------------------------------------------
        # TEXT FILE
        # -------------------------------------------------

        if extension in text_extensions:

            content = data.decode(
                "utf-8",
                errors="replace"
            )


            truncated = False


            if len(content) > MAX_TEXT_LENGTH:

                content = (
                    content[
                        :MAX_TEXT_LENGTH
                    ]
                )

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


        # -------------------------------------------------
        # PDF
        # -------------------------------------------------

        if extension == ".pdf":

            from pypdf import PdfReader


            reader = PdfReader(
                path
            )


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

                        f"--- Page "
                        f"{page_number + 1} ---\n"
                        f"{text}"

                    )


            content = (
                "\n\n".join(pages)
            )


            return {

                "success": True,

                "filename":
                    filename,

                "type":
                    "pdf",

                "content":
                    content[
                        :MAX_TEXT_LENGTH
                    ]

            }


        # -------------------------------------------------
        # OTHER FILE
        # -------------------------------------------------

        return {

            "success": True,

            "filename":
                filename,

            "type":
                "file",

            "content":
                (
                    f"File received: "
                    f"{filename}\n"
                    f"Size: {len(data)} bytes\n"
                    f"Type: "
                    f"{file.content_type or 'unknown'}"
                )

        }


    except Exception as error:

        print(
            "File error:",
            repr(error)
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "Could not read file."
            )

        )


    finally:

        if path:

            try:

                os.remove(
                    path
                )

            except Exception:
                pass


# =========================================================
# TRANSCRIBE AUDIO
# =========================================================

@app.post("/transcribe")
async def transcribe(

    file: UploadFile = File(
        ...
    )

):

    require_ai()


    path = None


    try:

        path, _ = (
            await save_upload(

                file,

                MAX_FILE_SIZE

            )
        )


        with open(
            path,
            "rb"
        ) as audio:

            result = (

                client
                .audio
                .transcriptions
                .create(

                    file=audio,

                    model=TRANSCRIPTION_MODEL

                )

            )


        return {

            "success": True,

            "text":
                getattr(
                    result,
                    "text",
                    ""
                )

        }


    except Exception as error:

        print(
            "Transcription error:",
            repr(error)
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "Could not transcribe audio."
            )

        )


    finally:

        if path:

            try:

                os.remove(
                    path
                )

            except Exception:
                pass


# =========================================================
# CREATE PDF
# =========================================================

@app.post("/create-pdf")
def create_pdf(
    request: PDFRequest
):

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


        # -------------------------------------------------
        # TITLE
        # -------------------------------------------------

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


        # -------------------------------------------------
        # CONTENT
        # -------------------------------------------------

        pdf.setFont(

            "Helvetica",

            10

        )


        for line in (
            request.content.splitlines()
        ):

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

            "file":
                path

        }


    except Exception as error:

        print(
            "PDF creation error:",
            repr(error)
        )


        raise HTTPException(

            status_code=500,

            detail=(
                "Could not create PDF."
            )

        )


# =========================================================
# API INFO
# =========================================================

@app.get("/api/info")
def api_info():

    return {

        "name":
            "CodeAI",

        "version":
            "10.0.0",

        "models": {

            "chat":
                CHAT_MODEL,

            "vision":
                VISION_MODEL,

            "transcription":
                TRANSCRIPTION_MODEL

        },

        "features": {

            "chat":
                True,

            "images":
                True,

            "camera":
                True,

            "vision":
                True,

            "video":
                True,

            "video_audio":
                True,

            "pdf":
                True,

            "files":
                True,

            "voice":
                True,

            "pdf_generator":
                True

        }

    }


# =========================================================
# STARTUP
# =========================================================

@app.on_event(
    "startup"
)
def startup():

    print(
        "=" * 60
    )

    print(
        "🚀 CODEAI 10.0.0"
    )

    print(
        "AI:",
        bool(client)
    )

    print(
        "CHAT:",
        CHAT_MODEL
    )

    print(
        "VISION:",
        VISION_MODEL
    )

    print(
        "TRANSCRIPTION:",
        TRANSCRIPTION_MODEL
    )

    print(
        "IMAGE/CAMERA: ENABLED"
    )

    print(
        "VIDEO: ENABLED"
    )

    print(
        "PDF: ENABLED"
    )

    print(
        "FILES: ENABLED"
    )

    print(
        "=" * 60
    )