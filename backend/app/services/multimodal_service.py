import logging
import os
import tempfile
import whisper
import pytesseract
import base64
import json
import re
import httpx
from io import BytesIO
from PIL import Image, ImageOps, ImageFilter
from fastapi import UploadFile
from urllib.request import Request, urlopen
from backend.app.config import settings

logger = logging.getLogger(__name__)

# Load Whisper model (small is better for Italian accuracy)
_whisper_model = None

_AUDIO_SUFFIX_BY_CONTENT_TYPE = {
    "audio/aac": ".aac",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
}

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper model (medium)...")
        _whisper_model = whisper.load_model("medium")
    return _whisper_model

async def transcribe_audio(file: UploadFile) -> str:
    """Transcribes an audio file using the configured multimodal provider."""
    provider = normalized_multimodal_provider()
    if provider in {"groq", "auto"} and groq_api_key():
        text = await transcribe_audio_groq(file)
        if text or provider == "groq":
            return text

    if provider == "groq":
        return ""

    return await transcribe_audio_local(file)


async def transcribe_audio_groq(file: UploadFile) -> str:
    await file.seek(0)
    content = await file.read()
    await file.seek(0)

    if len(content) < 100:
        return ""

    filename = file.filename or f"audio{_get_upload_suffix(file)}"
    content_type = file.content_type or "application/octet-stream"
    data = {
        "model": settings.groq_transcription_model,
        "response_format": "json",
    }
    files = {"file": (filename, content, content_type)}
    headers = {"Authorization": f"Bearer {groq_api_key()}"}

    try:
        logger.info("Transcribing audio with Groq model: %s", settings.groq_transcription_model)
        async with httpx.AsyncClient(timeout=max(settings.llm_timeout_seconds, 60)) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers=headers,
                data=data,
                files=files,
            )
            response.raise_for_status()
        text = response.json().get("text", "").strip()
        logger.info("Groq transcription complete: %s", text)
        return text
    except Exception as exc:
        logger.error("Groq transcription error: %s", exc)
        return ""


async def transcribe_audio_local(file: UploadFile) -> str:
    """Transcribes an audio file using local Whisper."""
    model = get_whisper_model()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=_get_upload_suffix(file)) as tmp:
        await file.seek(0)
        content = await file.read()
        await file.seek(0)
        
        if len(content) < 100: # Reduced threshold to be safer
            return ""
        tmp.write(content)
        tmp_path = tmp.name

    try:
        logger.info(f"Transcribing audio file locally: {file.filename}")
        result = model.transcribe(
            tmp_path, 
            task="transcribe", 
            temperature=0,
            initial_prompt="Giochi del Mediterraneo Taranto 2026, Ionios, mascotte, sport, sedi, trasporti, biglietti."
        )
        text = result.get("text", "").strip()
        
        # Whisper often hallucinates common phrases for silence
        hallucination_phrases = ["grazie per la visione", "sottotitoli", "one, two", "1, 2", "grazie", "ciao"]
        if len(text) < 5 and any(phrase in text.lower() for phrase in hallucination_phrases):
             logger.info(f"Ignored short Whisper hallucination: {text}")
             return ""

        logger.info(f"Transcription complete: {text}")
        return text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _get_upload_suffix(file: UploadFile) -> str:
    filename_suffix = os.path.splitext(file.filename or "")[1]
    if filename_suffix:
        return filename_suffix

    content_type = (file.content_type or "").split(";")[0].lower()
    return _AUDIO_SUFFIX_BY_CONTENT_TYPE.get(content_type, ".audio")

async def extract_text_from_image(file: UploadFile) -> str:
    """Extracts text from an image file using Tesseract OCR."""
    try:
        logger.info(f"Extracting text from image: {file.filename}")
        
        await file.seek(0)
        content = await file.read()
        await file.seek(0)
        
        if not content:
            return ""

        image = Image.open(BytesIO(content))
        
        # --- Preprocessing for better OCR ---
        image = ImageOps.grayscale(image)
        image = image.filter(ImageFilter.SHARPEN)
        threshold = 140
        image = image.point(lambda p: 255 if p > threshold else 0)
        
        custom_config = r'--oem 3 --psm 3'
        text = pytesseract.image_to_string(image, lang='ita', config=custom_config)
        
        if len(text.strip()) < 5:
            text = pytesseract.image_to_string(image, lang='ita', config=r'--psm 11')
            
        
        # Filter out gibberish or non-meaningful text
        cleaned_text = re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()
        if len(cleaned_text) < 5 or not any(c.isalpha() for c in cleaned_text):
            return ""
            
        return text.strip()
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""

async def describe_image_vision(file: UploadFile, user_focus: str | None = None) -> str:
    """Describes an image using the configured vision provider."""
    try:
        logger.info(f"Analyzing image visually: {file.filename}")
        await file.seek(0)
        content = await file.read()
        await file.seek(0)
        
        if not content:
            logger.error("Empty image content received")
            return ""

        optimized_base64 = image_content_to_jpeg_base64(content)
        if not optimized_base64:
            return ""

        provider = normalized_multimodal_provider()
        if provider in {"groq", "auto"} and groq_api_key():
            description = await describe_image_groq(optimized_base64, user_focus)
            if description or provider == "groq":
                return description

        if provider == "groq":
            return ""

        return await describe_image_ollama(optimized_base64, user_focus)
    except Exception as e:
        logger.error(f"Vision error detail: {str(e)}")
        return ""


async def describe_image_groq(optimized_base64: str, user_focus: str | None = None) -> str:
    focus_text = (user_focus or "").strip()
    prompt = (
        "Analyze the image as the primary source of information. "
        "Describe only what is visible and relevant to answer the user's focus. "
        "If you see a mascot, torch, sport symbols, venue, ticket, calendar, map, "
        "or text related to Taranto 2026, mention it explicitly. "
        "Do not invent names, dates, prices or links."
    )
    if focus_text:
        prompt += (
            "\nThe user's text is a focus about the image, not a separate request: "
            f"{focus_text}"
        )

    data = {
        "model": settings.groq_vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{optimized_base64}"
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 220,
    }
    headers = {
        "Authorization": f"Bearer {groq_api_key()}",
        "Content-Type": "application/json",
    }

    try:
        logger.info("Analyzing image with Groq vision model: %s", settings.groq_vision_model)
        async with httpx.AsyncClient(timeout=max(settings.llm_timeout_seconds, 60)) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=data,
            )
            response.raise_for_status()
        result = response.json()
        description = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        logger.info("Groq vision analysis complete: %s", description)
        return description
    except Exception as exc:
        logger.error("Groq vision error: %s", exc)
        return ""


async def describe_image_ollama(optimized_base64: str, user_focus: str | None = None) -> str:
    try:
        ollama_url = settings.ollama_base_url.rstrip("/") + "/api/generate"
        logger.info(f"Sending vision request to: {ollama_url}")
        focus_text = (user_focus or "").strip()
        prompt = (
            "Analyze the image as the main input. Describe briefly what is visible "
            "and focus on details needed to answer the user's text. If you see a "
            "mascot, torch, sport symbols, venue, ticket, calendar, map, or "
            "Taranto 2026 text, mention it explicitly. Do not invent names, dates, "
            "prices or links."
        )
        if focus_text:
            prompt += f"\nUser focus about the image: {focus_text}"
        
        data = {
            "model": settings.vision_model,
            "prompt": prompt,
            "images": [optimized_base64],
            "stream": False
        }
        
        req = Request(ollama_url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=180) as response: # High timeout for first load
            resp_body = response.read().decode('utf-8')
            result = json.loads(resp_body)
            description = result.get("response", "").strip()
            logger.info(f"Vision analysis complete: {description}")
            return description
            
    except Exception as e:
        logger.error(f"Vision error detail: {str(e)}")
        return ""


def image_content_to_jpeg_base64(content: bytes) -> str:
    try:
        img = Image.open(BytesIO(content))
        img.thumbnail((768, 768))
        if img.mode != 'RGB':
            img = img.convert('RGB')

        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"PIL error during vision processing: {e}")
        return ""


def groq_api_key() -> str:
    return (settings.groq_api_key or "").strip().strip('"').strip("'")


def normalized_multimodal_provider() -> str:
    provider = (settings.multimodal_provider or "auto").strip().lower()
    return provider if provider in {"auto", "groq", "local"} else "auto"
