from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from backend.app.schemas import ChatRequestDTO, ChatResponseDTO
from backend.app.services.chat_service import answer_chat
from backend.app.services.multimodal_service import transcribe_audio, extract_text_from_image


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponseDTO)
def chat_endpoint(request: ChatRequestDTO) -> ChatResponseDTO:
    return answer_chat(request)


@router.post("/chat/audio", response_model=ChatResponseDTO)
async def chat_audio_endpoint(
    file: Annotated[UploadFile, File()],
    session_id: Annotated[str | None, Form()] = None,
) -> ChatResponseDTO:
    """Transcribes an audio message and processes it through the chat pipeline."""
    content_type = file.content_type or ""
    if not content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload an audio file.")

    extracted_text = await transcribe_audio(file)
    if not extracted_text:
        raise HTTPException(status_code=400, detail="Could not transcribe the provided audio file.")

    response = answer_chat(ChatRequestDTO(message=extracted_text, session_id=session_id))
    response.extracted_text = extracted_text
    return response


@router.post("/chat/multimodal", response_model=ChatResponseDTO)
async def chat_multimodal_endpoint(
    file: Annotated[UploadFile, File()],
    message: Annotated[str | None, Form()] = None,
    session_id: Annotated[str | None, Form()] = None,
) -> ChatResponseDTO:
    """Handles audio or image files, converts them to text, and processes them through the RAG pipeline."""
    content_type = file.content_type or ""
    user_message = (message or "").strip()
    extracted_text = ""
    final_message = ""

    if content_type.startswith("audio/"):
        if user_message:
            raise HTTPException(status_code=400, detail="Audio messages cannot be combined with text.")
        extracted_text = await transcribe_audio(file)
        final_message = extracted_text
    elif content_type.startswith("image/"):
        if not user_message:
            raise HTTPException(status_code=400, detail="Image messages require a text prompt.")
        extracted_text = await extract_text_from_image(file)
        final_message = user_message
        if extracted_text:
            final_message = f"{user_message}\n\nTesto estratto dall'immagine: {extracted_text}"
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload an audio or image file.")

    if not final_message:
        raise HTTPException(status_code=400, detail="Could not extract text from the provided file.")

    # Create a ChatRequestDTO from the extracted message
    request = ChatRequestDTO(message=final_message, session_id=session_id)
    response = answer_chat(request)
    
    # Set the extracted text so the frontend can display what it heard/read
    response.extracted_text = extracted_text or None
    return response
