import { useEffect, useRef, useState } from "react";

import { ImageLightbox } from "./ImageLightbox.jsx";

export function ChatComposer({ isSending, t, onSend, onFileSend, onStop }) {
  const [message, setMessage] = useState("");
  const [selectedImage, setSelectedImage] = useState(null);
  const [selectedImagePreviewUrl, setSelectedImagePreviewUrl] = useState(null);
  const [isImagePreviewOpen, setIsImagePreviewOpen] = useState(false);
  const [isImageDragActive, setIsImageDragActive] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(max-width: 767px)").matches
      : false,
  );
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const imageDragDepthRef = useRef(0);
  const mediaRecorderRef = useRef(null);
  const recordingStartedAtRef = useRef(0);
  const audioDurationMsRef = useRef(0);
  const audioShouldSendRef = useRef(false);
  const audioChunksRef = useRef([]);
  const trimmedMessage = message.trim();
  const hasText = trimmedMessage.length > 0;
  const hasSelectedImage = Boolean(selectedImage);
  const canStartRecording = !isSending && !hasText && !hasSelectedImage;
  const canDropImage = !isMobileViewport && !isSending && !isRecording;
  const canPasteImage = !isSending && !isRecording;
  const shouldShowImageActionButton = !selectedImage || !isMobileViewport;
  const uploadImageLabel = t.uploadImage || "Upload image";
  const removeImageLabel = t.removeImage || "Remove image";
  const recordAudioLabel = t.recordAudio || "Record audio";
  const stopRecordingLabel = t.stopRecording || "Stop recording";
  const cancelRecordingLabel = t.cancelRecording || stopRecordingLabel;
  const sendAudioLabel = t.sendAudio || t.sendMessage;
  const stopMessageLabel = t.stopMessage || "Stop";

  useEffect(() => {
    autosize();
  }, [message]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 767px)");

    function handleViewportChange(event) {
      setIsMobileViewport(event.matches);
    }

    setIsMobileViewport(mediaQuery.matches);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleViewportChange);
    } else {
      mediaQuery.addListener(handleViewportChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleViewportChange);
      } else {
        mediaQuery.removeListener(handleViewportChange);
      }
    };
  }, []);

  useEffect(() => {
    if (!selectedImage) {
      setSelectedImagePreviewUrl(null);
      return undefined;
    }

    const previewUrl = URL.createObjectURL(selectedImage);
    setSelectedImagePreviewUrl(previewUrl);

    return () => {
      URL.revokeObjectURL(previewUrl);
    };
  }, [selectedImage]);

  useEffect(() => {
    if (!canDropImage) {
      imageDragDepthRef.current = 0;
      setIsImageDragActive(false);
      return undefined;
    }

    function resetDragState() {
      imageDragDepthRef.current = 0;
      setIsImageDragActive(false);
    }

    function handleWindowDragEnter(event) {
      if (!hasDraggedImage(event.dataTransfer)) {
        return;
      }

      event.preventDefault();
      imageDragDepthRef.current += 1;
      setIsImageDragActive(true);
    }

    function handleWindowDragOver(event) {
      if (!hasDraggedImage(event.dataTransfer)) {
        return;
      }

      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
      setIsImageDragActive(true);
    }

    function handleWindowDragLeave(event) {
      if (!hasDraggedImage(event.dataTransfer)) {
        return;
      }

      event.preventDefault();
      imageDragDepthRef.current = Math.max(0, imageDragDepthRef.current - 1);

      const hasLeftWindow =
        event.clientX <= 0 ||
        event.clientY <= 0 ||
        event.clientX >= window.innerWidth ||
        event.clientY >= window.innerHeight;

      if (hasLeftWindow || imageDragDepthRef.current === 0) {
        resetDragState();
      }
    }

    function handleWindowDrop(event) {
      if (!hasDraggedImage(event.dataTransfer)) {
        return;
      }

      event.preventDefault();
      const imageFile = getDroppedImageFile(event.dataTransfer);
      resetDragState();

      if (imageFile) {
        selectImageFile(imageFile);
      }
    }

    window.addEventListener("dragenter", handleWindowDragEnter);
    window.addEventListener("dragover", handleWindowDragOver);
    window.addEventListener("dragleave", handleWindowDragLeave);
    window.addEventListener("drop", handleWindowDrop);

    return () => {
      window.removeEventListener("dragenter", handleWindowDragEnter);
      window.removeEventListener("dragover", handleWindowDragOver);
      window.removeEventListener("dragleave", handleWindowDragLeave);
      window.removeEventListener("drop", handleWindowDrop);
    };
  }, [canDropImage]);

  useEffect(() => {
    if (!canPasteImage) {
      return undefined;
    }

    function handleWindowPaste(event) {
      const imageFile = getClipboardImageFile(event.clipboardData);
      if (!imageFile) {
        return;
      }

      event.preventDefault();
      selectImageFile(imageFile);
    }

    window.addEventListener("paste", handleWindowPaste);

    return () => {
      window.removeEventListener("paste", handleWindowPaste);
    };
  }, [canPasteImage]);

  function handleSubmit(event) {
    event.preventDefault();

    if (isSending) {
      onStop?.();
      return;
    }

    if (isRecording) {
      stopRecording(true);
      return;
    }

    if (!hasText) {
      return;
    }

    if (selectedImage && onFileSend) {
      onFileSend(selectedImage, trimmedMessage);
      clearSelectedImage();
    } else {
      onSend(trimmedMessage);
    }

    setMessage("");
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function autosize() {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }

    textarea.style.height = "auto";
    const maxHeight = Number.parseFloat(
      window.getComputedStyle(textarea).maxHeight,
    );
    const nextHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY =
      textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  }

  function handleImageClick() {
    if (selectedImage) {
      clearSelectedImage();
      return;
    }

    fileInputRef.current?.click();
  }

  function clearSelectedImage() {
    setIsImagePreviewOpen(false);
    setSelectedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function selectImageFile(file) {
    if (!file?.type.startsWith("image/")) {
      return;
    }

    setIsImagePreviewOpen(false);
    setSelectedImage(file);
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0];
    selectImageFile(file);
  }

  async function toggleRecording() {
    if (isRecording) {
      stopRecording(false);
    } else {
      if (!canStartRecording) {
        return;
      }

      let stream;
      try {
        if (typeof MediaRecorder === "undefined") {
          throw new Error("MediaRecorder is not supported by this browser.");
        }

        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const recorderOptions = getSupportedAudioRecorderOptions();
        const mediaRecorder = recorderOptions
          ? new MediaRecorder(stream, recorderOptions)
          : new MediaRecorder(stream);
        const audioMimeType =
          mediaRecorder.mimeType || recorderOptions?.mimeType || "audio/mp4";
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];
        audioDurationMsRef.current = 0;
        audioShouldSendRef.current = false;

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };

        mediaRecorder.onstop = async () => {
          if (audioShouldSendRef.current && onFileSend && audioChunksRef.current.length) {
            const audioBlob = new Blob(audioChunksRef.current, { type: audioMimeType });
            const extension = getAudioFileExtension(audioMimeType);
            const file = new File([audioBlob], `recording.${extension}`, {
              type: audioMimeType,
            });
            const waveform = await createWaveformFromBlob(audioBlob);
            onFileSend(file, "", {
              durationMs: audioDurationMsRef.current,
              waveform,
            });
          }

          stream.getTracks().forEach(track => track.stop());
          audioChunksRef.current = [];
          audioDurationMsRef.current = 0;
          audioShouldSendRef.current = false;
          mediaRecorderRef.current = null;
          recordingStartedAtRef.current = 0;
          setIsRecording(false);
        };

        mediaRecorder.start();
        recordingStartedAtRef.current = performance.now();
        setIsRecording(true);
      } catch (error) {
        stream?.getTracks().forEach((track) => track.stop());
        console.error("Error accessing microphone:", error);
        alert("Non è stato possibile accedere al microfono.");
      }
    }
  }

  function stopRecording(shouldSend) {
    audioShouldSendRef.current = shouldSend;
    audioDurationMsRef.current = recordingStartedAtRef.current
      ? Math.max(0, performance.now() - recordingStartedAtRef.current)
      : 0;
    const mediaRecorder = mediaRecorderRef.current;

    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      setIsRecording(false);
      return;
    }

    mediaRecorder.stop();
  }

  return (
    <form
      className="chat-composer shrink-0 border-t p-3 sm:p-4"
      onSubmit={handleSubmit}
    >
      <div
        className={`composer-shell flex items-center gap-2${
          selectedImage ? " composer-shell-has-image" : ""
        }${isImageDragActive ? " composer-shell-drag-active" : ""}`}
      >
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept="image/*"
          onChange={handleFileChange}
        />

        {selectedImagePreviewUrl ? (
          <div className="composer-image-preview-wrap">
            <button
              className="composer-image-preview"
              type="button"
              aria-label={selectedImage?.name || uploadImageLabel}
              onClick={() => setIsImagePreviewOpen(true)}
            >
              <img src={selectedImagePreviewUrl} alt="" aria-hidden="true" />
            </button>
            <button
              className="composer-image-remove-mobile"
              type="button"
              aria-label={removeImageLabel}
              onClick={clearSelectedImage}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.8"
                aria-hidden="true"
              >
                <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        ) : null}

        <textarea
          ref={textareaRef}
          id="messageInput"
          className="message-textarea flex-1 resize-none border-0 bg-transparent px-3 py-3 text-base outline-none focus:ring-0"
          rows="1"
          placeholder={t.messagePlaceholder}
          required={!isRecording}
          disabled={isSending || isRecording}
          value={message}
          dir="auto"
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={handleKeyDown}
        />

        {shouldShowImageActionButton ? (
          <button
            type="button"
            className={`composer-action-button composer-image-action ${
              selectedImage
                ? "composer-action-button-selected composer-image-action-selected"
                : ""
            }`}
            onClick={handleImageClick}
            disabled={isSending || isRecording}
            title={selectedImage ? removeImageLabel : uploadImageLabel}
            aria-label={selectedImage ? removeImageLabel : uploadImageLabel}
          >
            {selectedImage ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
            )}
          </button>
        ) : null}

        <button
          type="button"
          className={`composer-action-button ${
            isRecording ? "composer-action-button-selected" : ""
          }`}
          onClick={toggleRecording}
          disabled={isSending || (!isRecording && !canStartRecording)}
          title={isRecording ? cancelRecordingLabel : recordAudioLabel}
          aria-label={isRecording ? cancelRecordingLabel : recordAudioLabel}
        >
          {isRecording ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
              <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          )}
        </button>
        <button
          id="sendButton"
          className={`send-button flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-white shadow-sm transition focus:outline-none focus:ring-4 focus:ring-sky-700/20 ${
            isSending ? "send-button-stop" : ""
          }`}
          type="submit"
          aria-label={isSending ? stopMessageLabel : isRecording ? sendAudioLabel : t.sendMessage}
          disabled={!isSending && !isRecording && !hasText}
        >
          {isSending ? (
            <svg className="h-[22px] w-[22px]" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" />
            </svg>
          ) : (
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M12 19V5m0 0-6 6m6-6 6 6"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </button>
      </div>
      {selectedImagePreviewUrl ? (
        <ImageLightbox
          closeLabel={t.closeImage}
          image={isImagePreviewOpen ? selectedImagePreviewUrl : null}
          onClose={() => setIsImagePreviewOpen(false)}
        />
      ) : null}
    </form>
  );
}

const AUDIO_RECORDER_MIME_TYPES = [
  "audio/mp4",
  "audio/aac",
  "audio/webm;codecs=opus",
  "audio/webm",
];

function getSupportedAudioRecorderOptions() {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
    return undefined;
  }

  const mimeType = AUDIO_RECORDER_MIME_TYPES.find((candidateMimeType) =>
    MediaRecorder.isTypeSupported(candidateMimeType),
  );

  return mimeType ? { mimeType } : undefined;
}

function getAudioFileExtension(mimeType) {
  if (mimeType.includes("mp4")) {
    return "m4a";
  }

  if (mimeType.includes("aac")) {
    return "aac";
  }

  if (mimeType.includes("webm")) {
    return "webm";
  }

  if (mimeType.includes("ogg")) {
    return "ogg";
  }

  if (mimeType.includes("wav")) {
    return "wav";
  }

  return "audio";
}

function hasDraggedImage(dataTransfer) {
  return Array.from(dataTransfer?.items || []).some(
    (item) => item.kind === "file" && item.type.startsWith("image/"),
  );
}

function getDroppedImageFile(dataTransfer) {
  return Array.from(dataTransfer?.files || []).find((file) =>
    file.type.startsWith("image/"),
  );
}

function getClipboardImageFile(clipboardData) {
  const fileFromClipboard = Array.from(clipboardData?.files || []).find(
    (file) => file.type.startsWith("image/"),
  );

  if (fileFromClipboard) {
    return fileFromClipboard;
  }

  const imageItem = Array.from(clipboardData?.items || []).find(
    (item) => item.kind === "file" && item.type.startsWith("image/"),
  );
  const imageBlob = imageItem?.getAsFile?.();

  if (!imageBlob) {
    return null;
  }

  if (imageBlob.name) {
    return imageBlob;
  }

  const extension = getImageFileExtension(imageBlob.type);
  return new File([imageBlob], `clipboard-image.${extension}`, {
    type: imageBlob.type,
  });
}

function getImageFileExtension(mimeType) {
  if (mimeType.includes("jpeg") || mimeType.includes("jpg")) {
    return "jpg";
  }

  if (mimeType.includes("webp")) {
    return "webp";
  }

  if (mimeType.includes("gif")) {
    return "gif";
  }

  return "png";
}

async function createWaveformFromBlob(audioBlob, barCount = 18) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    return null;
  }

  let audioContext;
  try {
    audioContext = new AudioContextClass();
    const arrayBuffer = await audioBlob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    const channelData = audioBuffer.getChannelData(0);
    const samplesPerBar = Math.max(1, Math.floor(channelData.length / barCount));
    const rawBars = [];

    for (let barIndex = 0; barIndex < barCount; barIndex += 1) {
      const start = barIndex * samplesPerBar;
      const end =
        barIndex === barCount - 1
          ? channelData.length
          : Math.min(channelData.length, start + samplesPerBar);
      let sum = 0;

      for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
        sum += channelData[sampleIndex] ** 2;
      }

      const sampleCount = Math.max(1, end - start);
      rawBars.push(Math.sqrt(sum / sampleCount));
    }

    const maxAmplitude = Math.max(...rawBars, 0.001);
    return rawBars.map((amplitude) =>
      Math.round(8 + (amplitude / maxAmplitude) * 22),
    );
  } catch (_error) {
    return null;
  } finally {
    if (audioContext?.state !== "closed") {
      audioContext?.close?.();
    }
  }
}
