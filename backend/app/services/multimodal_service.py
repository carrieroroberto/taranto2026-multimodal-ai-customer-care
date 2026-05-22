import logging
import os
import tempfile
import whisper
import pytesseract
import base64
import json
import re
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
    """Transcribes an audio file using OpenAI Whisper, forced to Italian."""
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
        logger.info(f"Transcribing audio file: {file.filename}")
        # Force Italian language and use temperature 0 for better stability
        # Use initial_prompt to guide Whisper with specialized terminology
        result = model.transcribe(
            tmp_path, 
            language="it", 
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

async def describe_image_vision(file: UploadFile) -> str:
    """Describes an image using the Moondream vision model in Ollama."""
    try:
        logger.info(f"Analyzing image visually with moondream: {file.filename}")
        
        await file.seek(0)
        content = await file.read()
        await file.seek(0)
        
        if not content:
            logger.error("Empty image content received")
            return ""

        try:
            img = Image.open(BytesIO(content))
            img.thumbnail((768, 768))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            optimized_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"PIL error during vision processing: {e}")
            return ""

        ollama_url = settings.ollama_base_url.rstrip("/") + "/api/generate"
        logger.info(f"Sending vision request to: {ollama_url}")
        
        data = {
            "model": "moondream",
            "prompt": "What do you see in this image? Describe it briefly. If you see a mascot, a torch, or three interlocking rings, mention them explicitly.",
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
