export const STOP_AUDIO_PLAYBACK_EVENT = "talos:stop-audio-playback";

export function stopAudioPlayback() {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new Event(STOP_AUDIO_PLAYBACK_EVENT));

  window.speechSynthesis?.cancel?.();

  document.querySelectorAll("audio").forEach((audioElement) => {
    audioElement.pause();
  });
}
