# utils/audio.py
"""
Audio utilities for speech recognition.
"""

from loguru import logger


def fix_audio_libraries():
    """Fix audio library errors."""
    try:
        import sounddevice as sd
        sd.default.callback = lambda *args: None
        
        try:
            devices = sd.query_devices()
            logger.info(f"✅ Audio devices found: {len(devices)}")
            has_input = False
            for i, dev in enumerate(devices):
                if dev.get('max_input_channels', 0) > 0:
                    has_input = True
                    logger.info(f"✅ Input device: {dev.get('name')}")
                    break
            if not has_input:
                logger.warning("⚠️ No input device found for speech recognition")
        except Exception as e:
            logger.warning(f"⚠️ Audio device detection warning: {e}")
    except ImportError:
        logger.warning("⚠️ sounddevice not available - speech recognition disabled")
    except Exception as e:
        logger.warning(f"⚠️ Audio library initialization warning: {e}")