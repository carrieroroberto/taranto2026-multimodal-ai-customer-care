import os
import uuid
from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from backend.app.config import settings
from backend.app.schemas import ChatRequestDTO, ChatResponseDTO
from backend.app.services.chat_service import answer_chat
from backend.app.services.multimodal_service import transcribe_audio, extract_text_from_image, describe_image_vision

router = APIRouter(tags=["chat"])

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "../../data/uploads")


def local_multimodal_disabled() -> bool:
    return settings.ai_disabled


def media_extension_for_content_type(content_type: str, default: str) -> str:
    normalized = (content_type or "").split(";")[0].lower()
    return {
        "audio/aac": ".aac",
        "audio/mp4": ".m4a",
        "audio/mpeg": ".mp3",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/webm": ".webm",
        "image/gif": ".gif",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(normalized, default)

@router.post("/chat", response_model=ChatResponseDTO)
async def chat_endpoint(request: ChatRequestDTO) -> ChatResponseDTO:
    return await answer_chat(request)


@router.post("/chat/audio", response_model=ChatResponseDTO)
async def chat_audio_endpoint(
    file: Annotated[UploadFile, File()],
    session_id: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
) -> ChatResponseDTO:
    """Transcribes an audio message and processes it through the chat pipeline."""
    content_type = file.content_type or ""
    if not content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload an audio file.")

    # Save audio file for persistence
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = media_extension_for_content_type(content_type, ".audio")
    
    filename = f"{file_id}{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    await file.seek(0) # Seek back for transcription
    
    audio_url = f"/api/uploads/{filename}"
    extracted_text = "" if local_multimodal_disabled() else await transcribe_audio(file)
    
    # If transcription fails (empty), we send a special tag
    if not extracted_text:
        extracted_text = "[AUDIO_INCOMPRENSIBILE]"

    response = await answer_chat(
        ChatRequestDTO(
            message=extracted_text,
            session_id=session_id,
            language=language,
            message_type="audio",
            stored_user_content=None,
            media_url=audio_url,
        )
    )
    response.extracted_text = None
    return response


@router.post("/chat/multimodal", response_model=ChatResponseDTO)
async def chat_multimodal_endpoint(
    file: Annotated[UploadFile, File()],
    message: Annotated[str | None, Form()] = None,
    session_id: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
) -> ChatResponseDTO:
    """Handles audio or image files, converts them to text, and processes them through the RAG pipeline."""
    content_type = file.content_type or ""
    user_message = (message or "").strip()
    extracted_text = ""
    final_message = ""

    if content_type.startswith("audio/"):
        if user_message:
            raise HTTPException(status_code=400, detail="Audio messages cannot be combined with text.")
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        file_id = str(uuid.uuid4())
        ext = media_extension_for_content_type(content_type, ".audio")
        filename = f"{file_id}{ext}"
        filepath = os.path.join(UPLOADS_DIR, filename)

        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        await file.seek(0)

        audio_url = f"/api/uploads/{filename}"
        extracted_text = "" if local_multimodal_disabled() else await transcribe_audio(file)
        if not extracted_text:
            extracted_text = "[AUDIO_INCOMPRENSIBILE]"
        response = await answer_chat(
            ChatRequestDTO(
                message=extracted_text,
                session_id=session_id,
                language=language,
                message_type="audio",
                stored_user_content=None,
                media_url=audio_url,
            )
        )
        response.extracted_text = None
        return response
    elif content_type.startswith("image/"):
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        ext = media_extension_for_content_type(content_type, ".image")
        file_id = str(uuid.uuid4())
        filename = f"{file_id}{ext}"
        filepath = os.path.join(UPLOADS_DIR, filename)
        
        # We need to save the file without consuming the stream or we seek back
        file.file.seek(0)
        content = file.file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        file.file.seek(0)
        
        image_url = f"/api/uploads/{filename}"

        if local_multimodal_disabled():
            extracted_text = ""
            visual_description = ""
        else:
            extracted_text = await extract_text_from_image(file)
            visual_description = await describe_image_vision(file, user_message)
        
        visual_context = build_visual_context(visual_description, extracted_text)
        final_message = build_image_internal_message(
            user_message,
            visual_description,
            extracted_text,
        )
        planning_message = user_message or "Analizza l'immagine inviata."
        request = ChatRequestDTO(
            message=final_message, 
            visual_context=visual_context or None, 
            planning_message=planning_message,
            session_id=session_id,
            language=language,
            message_type="image",
            stored_user_content=None,
            media_url=image_url,
        )
        response = await answer_chat(request)
        
        response.extracted_text = None
        return response
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type.")


def build_visual_context(visual_description: str, extracted_text: str) -> str:
    parts = []
    if visual_description:
        parts.append(f"Descrizione visiva dell'immagine: {visual_description.strip()}")
    if extracted_text:
        parts.append(f"Testo leggibile nell'immagine: {extracted_text.strip()}")
    return "\n".join(parts).strip()


def build_image_internal_message(
    user_message: str,
    visual_description: str,
    extracted_text: str,
) -> str:
    focus = user_message or "Analizza l'immagine inviata e rispondi in base a cio che si vede."
    visual_context = build_visual_context(visual_description, extracted_text)
    if not visual_context:
        visual_context = "Nessuna descrizione visiva affidabile disponibile."

    return (
        "Richiesta multimodale con immagine.\n"
        "L'immagine e' l'elemento principale da interpretare. "
        "Il testo dell'utente serve solo come focus o domanda riferita all'immagine, "
        "non come richiesta separata.\n\n"
        f"DATI DELL'IMMAGINE:\n{visual_context}\n\n"
        f"FOCUS TESTUALE DELL'UTENTE:\n{focus}"
    )
