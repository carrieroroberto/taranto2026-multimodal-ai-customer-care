from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from backend.app.schemas import ChatRequestDTO, ChatResponseDTO
from backend.app.services.chat_service import answer_chat
from backend.app.services.multimodal_service import transcribe_audio, extract_text_from_image, describe_image_vision


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponseDTO)
def chat_endpoint(request: ChatRequestDTO) -> ChatResponseDTO:
    return answer_chat(request)


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

    extracted_text = await transcribe_audio(file)
    # If transcription fails (empty), we don't throw 400 anymore.
    # Instead, we send a 'could not hear' message to the LLM so it can trigger its 
    # own fallback/clarification logic which hides sources.
    if not extracted_text:
        extracted_text = "[AUDIO_INCOMPRENSIBILE]"

    response = answer_chat(ChatRequestDTO(message=extracted_text, session_id=session_id, language=language))
    response.extracted_text = extracted_text if extracted_text != "[AUDIO_INCOMPRENSIBILE]" else None
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
        extracted_text = await transcribe_audio(file)
        final_message = extracted_text
    elif content_type.startswith("image/"):
        # Combine OCR (text) and Vision (description)
        extracted_text = await extract_text_from_image(file)
        visual_description = await describe_image_vision(file)
        
        # Build pure visual context for semantic search (no chatty text)
        visual_context = ""
        if visual_description:
            visual_context = visual_description.strip()
        if extracted_text:
            visual_context = f"{visual_context} {extracted_text}".strip()

        # Build the final message for the LLM to ANSWER
        final_message = user_message or "Cosa vedi in questa immagine?"
        analysis_parts = []
        if visual_description:
            analysis_parts.append(f"Descrizione visiva: {visual_description}")
        if extracted_text:
            analysis_parts.append(f"Testo letto: {extracted_text}")
            
        if analysis_parts:
            final_message = f"{final_message}\n\nAnalisi immagine:\n" + "\n".join(analysis_parts)
            
        planning_message = user_message or "Cosa vedi in questa immagine?"
        request = ChatRequestDTO(
            message=final_message, 
            visual_context=visual_context or None, 
            planning_message=planning_message,
            session_id=session_id,
            language=language
        )
        response = answer_chat(request)
        
        # Set the extracted text so the frontend can display what it heard/read
        response.extracted_text = extracted_text or visual_description or None
        return response
