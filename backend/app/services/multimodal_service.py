import logging
import os
import tempfile
import whisper
import pytesseract
from PIL import Image
from fastapi import UploadFile

logger = logging.getLogger(__name__)

# Load Whisper model (base is good for a prototype)
# We use 'base' for speed, can be changed to 'small' or 'medium'
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper model...")
        _whisper_model = whisper.load_model("base")
    return _whisper_model

async def transcribe_audio(file: UploadFile) -> str:
    """Transcribes an audio file using OpenAI Whisper."""
    model = get_whisper_model()
    
    # Save the uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        logger.info(f"Transcribing audio file: {file.filename}")
        result = model.transcribe(tmp_path)
        text = result.get("text", "").strip()
        logger.info(f"Transcription complete: {text}")
        return text
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

async def extract_text_from_image(file: UploadFile) -> str:
    """Extracts text from an image file using Tesseract OCR."""
    try:
        logger.info(f"Extracting text from image: {file.filename}")
        image = Image.open(file.file)
        # Use Italian language for OCR
        text = pytesseract.image_to_string(image, lang='ita')
        logger.info(f"OCR complete: {text.strip()}")
        return text.strip()
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""
