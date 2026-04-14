"""
Tests for renderer module.
"""

import unittest
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from core.renderer import Renderer, RenderConfig, render_comic
from core.panel_detector import Panel


class MockPanel:
    """Mock panel for testing."""
    def __init__(self, width=640, height=480, color=None):
        self.width = width
        self.height = height
        self.x = 0
        self.y = 0
        self.page_index = 0
        self.panel_index = 0
        self.color = color or (255, 0, 0)
        # Create synthetic image
        self._image = np.full((height, width, 3), self.color, dtype=np.uint8)
        
    def extract_from_original(self):
        return self._image.copy()


class TestRenderer(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_path = Path(self.temp_dir) / "test_output.mp4"
    
    def test_render_config_defaults(self):
        """Test RenderConfig default values."""
        config = RenderConfig()
        self.assertEqual(config.fps, 24)
        self.assertEqual(config.resolution, (1920, 1080))
        self.assertEqual(config.panel_duration_frames, 48)
        self.assertEqual(config.transition_duration_frames, 24)
    
    def test_renderer_initialization(self):
        """Test renderer initialization."""
        config = RenderConfig(
            fps=30,
            resolution=(1280, 720)
        )
        renderer = Renderer(config)
        self.assertEqual(renderer.config.fps, 30)
        self.assertEqual(renderer.config.resolution, (1280, 720))
    
    def test_generate_panel_frames(self):
        """Test panel frame generation."""
        config = RenderConfig(
            resolution=(640, 480),
            panel_duration_frames=10
        )
        renderer = Renderer(config)
        
        panel = MockPanel(color=(100, 150, 200))
        frames = renderer._generate_panel_frames(panel)
        
        self.assertEqual(len(frames), 10)
        # All frames should be target resolution
        for frame in frames:
            self.assertEqual(frame.shape, (480, 640, 3))
    
    def test_letterbox_zoom_pan(self):
        """Test letterboxing and zoom/pan."""
        config = RenderConfig(resolution=(640, 480))
        renderer = Renderer(config)
        
        # Create small image
        img = np.full((300, 400, 3), 128, dtype=np.uint8)
        
        # Test letterbox
        letterboxed = renderer.morpher._letterbox(img)
        self.assertEqual(letterboxed.shape, (480, 640, 3))
        
        # Test zoom
        zoomed = renderer._apply_zoom_and_pan(img, 1.5, 0, 0)
        self.assertEqual(zoomed.shape, img.shape)
    
    def test_full_render(self):
        """Test full rendering pipeline."""
        # Create mock panels with different colors
        panels = [
            MockPanel(color=(255, 0, 0)),    # Red
            MockPanel(color=(0, 255, 0)),    # Green
            MockPanel(color=(0, 0, 255)),    # Blue
        ]
        
        config = RenderConfig(
            fps=12,  # Lower for faster test
            resolution=(320, 240),
            panel_duration_frames=6,
            transition_duration_frames=3,
            output_path=str(self.output_path)
        )
        
        renderer = Renderer(config)
        
        progress_calls = []
        def track_progress(p, m):
            progress_calls.append((p, m))
        
        config.progress_callback = track_progress
        
        # Run render
        result = renderer.render(panels)
        
        # Check output
        self.assertTrue(Path(result).exists())
        self.assertGreater(Path(result).stat().st_size, 0)
        
        # Check progress was called
        self.assertGreater(len(progress_calls), 0)
        # Last call should be 1.0
        self.assertEqual(progress_calls[-1][0], 1.0)
    
    def test_render_comic_convenience(self):
        """Test render_comic convenience function."""
        panels = [
            MockPanel(color=(255, 100, 100)),
            MockPanel(color=(100, 255, 100)),
        ]
        
        output = Path(self.temp_dir) / "convenience_test.mp4"
        
        result = render_comic(
            panels=panels,
            output_path=str(output),
            fps=12,
            resolution=(320, 240),
            panel_duration=0.5,  # 0.5 seconds
            transition_duration=0.25,
            transition_strategy="crossfade"
        )
        
        self.assertTrue(Path(result).exists())


if __name__ == '__main__':
    unittest.main()
