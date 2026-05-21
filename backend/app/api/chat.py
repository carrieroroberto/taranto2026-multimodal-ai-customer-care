from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Form

from backend.app.schemas import ChatRequestDTO, ChatResponseDTO
from backend.app.services.chat_service import answer_chat
from backend.app.services.multimodal_service import transcribe_audio, extract_text_from_image


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponseDTO)
def chat_endpoint(request: ChatRequestDTO) -> ChatResponseDTO:
    return answer_chat(request)


@router.post("/chat/multimodal", response_model=ChatResponseDTO)
async def chat_multimodal_endpoint(
    file: Annotated[UploadFile, File()],
    session_id: Annotated[str | None, Form()] = None,
) -> ChatResponseDTO:
    """Handles audio or image files, converts them to text, and processes them through the RAG pipeline."""
    content_type = file.content_type
    message = ""

    if content_type.startswith("audio/"):
        message = await transcribe_audio(file)
    elif content_type.startswith("image/"):
        message = await extract_text_from_image(file)
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload an audio or image file.")

    if not message:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Could not extract text from the provided file.")

    # Create a ChatRequestDTO from the extracted message
    request = ChatRequestDTO(message=message, session_id=session_id)
    response = answer_chat(request)
    
    # Set the extracted text so the frontend can display what it heard/read
    response.extracted_text = message
    return response
