import { useEffect } from "react";
import { createPortal } from "react-dom";

export function ImageLightbox({ closeLabel = "Chiudi immagine", image, onClose }) {
  useEffect(() => {
    if (!image) {
      return undefined;
    }

    const previousBodyOverflow = document.body.style.overflow;

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [image, onClose]);

  if (!image || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      className="image-lightbox"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <button
        className="image-lightbox-close"
        type="button"
        aria-label={closeLabel}
        onClick={onClose}
      >
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M6 6l12 12M18 6L6 18"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="2.4"
          />
        </svg>
      </button>
      <img
        className="image-lightbox-image"
        src={image}
        alt=""
        aria-hidden="true"
        onClick={(event) => event.stopPropagation()}
      />
    </div>,
    document.body,
  );
}
