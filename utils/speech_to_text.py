"""
Lightweight speech-to-text compatibility layer.

Voice input is disabled for the low-end PC build. Keeping this small module
preserves existing imports without loading audio, numpy, or speech-recognition
libraries during product/category form startup.
"""

from loguru import logger

LANGUAGE_MYANMAR = "my"
LANGUAGE_ENGLISH = "en"


class SpeechButton:
    """No-op speech button handler used when voice input is disabled."""

    def __init__(self, parent, text_input, duration=5, language=LANGUAGE_MYANMAR):
        self.parent = parent
        self.text_input = text_input
        self.duration = duration
        self.language = language
        self.is_recording = False

    def get_text(self):
        try:
            if hasattr(self.text_input, "toPlainText"):
                return self.text_input.toPlainText()
            if hasattr(self.text_input, "text"):
                return self.text_input.text()
        except Exception:
            pass
        return ""

    def set_text(self, text):
        try:
            if hasattr(self.text_input, "setPlainText"):
                self.text_input.setPlainText(text)
            elif hasattr(self.text_input, "setText"):
                self.text_input.setText(text)
        except Exception:
            pass

    def set_placeholder(self, text):
        try:
            self.text_input.setPlaceholderText(text)
        except Exception:
            pass

    def set_style(self, style):
        try:
            self.text_input.setStyleSheet(style)
        except Exception:
            pass

    def set_language(self, language):
        self.language = language

    def toggle_recording(self):
        self.start_recording()

    def start_recording(self):
        logger.info("Speech-to-text is disabled in low-end PC mode")
        try:
            self.parent.show_message(
                "Voice Disabled",
                "Voice-to-text is disabled for better performance on low-end PCs.",
            )
        except Exception:
            pass

    def stop_recording(self):
        self.is_recording = False

    def cleanup(self):
        self.stop_recording()
