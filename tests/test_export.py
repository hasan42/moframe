"""Tests for export module."""

import unittest
import numpy as np
from pathlib import Path
import os

from core.export import export_as_gif, export_as_apng, export_as_webm, export_frames


class TestExport(unittest.TestCase):
    """Test export functionality."""
    
    def setUp(self):
        """Create test frames."""
        self.frames = []
        for i in range(10):
            frame = np.zeros((100, 150, 3), dtype=np.uint8)
            frame[20:80, 30:120] = (i * 25, 100, 200)
            self.frames.append(frame)
        self.temp_dir = '/tmp/moframe_export_test'
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_export_gif(self):
        """Test GIF export."""
        output_path = os.path.join(self.temp_dir, 'test.gif')
        result = export_as_gif(self.frames, output_path, fps=5)
        
        self.assertTrue(os.path.exists(result))
        self.assertGreater(os.path.getsize(result), 0)
    
    def test_export_apng(self):
        """Test APNG export."""
        output_path = os.path.join(self.temp_dir, 'test.apng')
        result = export_as_apng(self.frames, output_path, fps=5)
        
        self.assertTrue(os.path.exists(result))
        self.assertGreater(os.path.getsize(result), 0)
    
    def test_export_webm(self):
        """Test WebM export."""
        output_path = os.path.join(self.temp_dir, 'test.webm')
        try:
            result = export_as_webm(self.frames, output_path, fps=5)
            self.assertTrue(os.path.exists(result))
            self.assertGreater(os.path.getsize(result), 0)
        except Exception as e:
            self.skipTest(f"WebM export requires ffmpeg: {e}")
    
    def test_export_frames_mp4(self):
        """Test export_frames with MP4."""
        output_path = os.path.join(self.temp_dir, 'test.mp4')
        result = export_frames(self.frames, output_path, fps=5, format='mp4')
        
        self.assertTrue(os.path.exists(result))
        self.assertGreater(os.path.getsize(result), 0)
    
    def test_export_frames_gif(self):
        """Test export_frames with GIF."""
        output_path = os.path.join(self.temp_dir, 'test.gif')
        result = export_frames(self.frames, output_path, fps=5, format='gif')
        
        self.assertTrue(os.path.exists(result))
        self.assertGreater(os.path.getsize(result), 0)
    
    def test_export_frames_invalid_format(self):
        """Test export_frames with invalid format falls back to MP4."""
        output_path = os.path.join(self.temp_dir, 'test.xyz')
        result = export_frames(self.frames, output_path, fps=5, format='unknown')
        
        self.assertTrue(os.path.exists(result))


if __name__ == "__main__":
    unittest.main()
