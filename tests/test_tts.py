"""Tests for TTS and OCR modules."""

import unittest
import numpy as np
from PIL import Image


class TestTTS(unittest.TestCase):
    """Test TTS functionality."""
    
    def test_tts_config_creation(self):
        """Test TTSConfig creation."""
        from core.tts import TTSConfig
        config = TTSConfig(provider="edge", voice="ru-RU-SvetlanaNeural")
        self.assertEqual(config.provider, "edge")
        self.assertEqual(config.voice, "ru-RU-SvetlanaNeural")
    
    def test_tts_manager_creation(self):
        """Test TTSManager creation."""
        from core.tts import TTSManager, TTSConfig
        config = TTSConfig()
        manager = TTSManager(config)
        self.assertIsNotNone(manager)
    
    def test_tts_segment_creation(self):
        """Test TTSSegment dataclass."""
        from core.tts import TTSSegment
        segment = TTSSegment(text="Hello", panel_index=0)
        self.assertEqual(segment.text, "Hello")
        self.assertEqual(segment.panel_index, 0)


class TestOCR(unittest.TestCase):
    """Test OCR functionality."""
    
    def test_text_block_creation(self):
        """Test TextBlock dataclass."""
        from core.ocr import TextBlock
        block = TextBlock(text="Hello", bbox=(0, 0, 100, 50), confidence=0.95)
        self.assertEqual(block.text, "Hello")
        self.assertEqual(block.bbox, (0, 0, 100, 50))
    
    def test_classify_text(self):
        """Test text classification heuristics."""
        from core.ocr import OCRProcessor
        ocr = OCRProcessor.__new__(OCRProcessor)
        
        # SFX
        self.assertEqual(ocr._classify_text("BOOM!"), "sfx")
        self.assertEqual(ocr._classify_text("POW!"), "sfx")
        
        # Speech
        self.assertEqual(ocr._classify_text("— Hello"), "speech")
        self.assertEqual(ocr._classify_text("«Привет»"), "speech")
        
        # Default
        self.assertEqual(ocr._classify_text("Hello world"), "speech")
    
    def test_merge_blocks(self):
        """Test merging nearby text blocks."""
        from core.ocr import OCRProcessor, TextBlock
        ocr = OCRProcessor.__new__(OCRProcessor)
        
        blocks = [
            TextBlock("Hello", (0, 0, 100, 20), 0.9),
            TextBlock("world", (0, 25, 100, 20), 0.9),  # close vertically
            TextBlock("Far", (0, 100, 100, 20), 0.9),   # far away
        ]
        
        merged = ocr.merge_nearby_blocks(blocks, max_distance=30)
        self.assertEqual(len(merged), 2)  # "Hello world" + "Far"
        self.assertIn("Hello", merged[0].text)
        self.assertIn("world", merged[0].text)


class TestRendererTTS(unittest.TestCase):
    """Test renderer TTS integration."""
    
    def test_render_config_tts_fields(self):
        """Test that RenderConfig has TTS fields."""
        from core.renderer import RenderConfig
        config = RenderConfig(
            tts_enabled=True,
            tts_provider="edge",
            tts_voice="ru-RU-SvetlanaNeural",
            tts_language="ru"
        )
        self.assertTrue(config.tts_enabled)
        self.assertEqual(config.tts_provider, "edge")


if __name__ == "__main__":
    unittest.main()
