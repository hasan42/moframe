"""
Tests for loader module.
"""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from core.loader import load_comic, get_file_info


class TestLoader(unittest.TestCase):
    
    def setUp(self):
        """Create temporary test images."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_images = []
        
        # Create test images
        for i in range(3):
            img = Image.new('RGB', (800, 600), color=(i*50, i*60, i*70))
            img_path = Path(self.temp_dir) / f"page_{i+1:02d}.png"
            img.save(img_path)
            self.test_images.append(img_path)
    
    def tearDown(self):
        """Clean up temp files."""
        for img_path in self.test_images:
            if img_path.exists():
                img_path.unlink()
        Path(self.temp_dir).rmdir()
    
    def test_load_single_image(self):
        """Test loading a single image."""
        images = load_comic(self.test_images[0])
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].shape, (600, 800, 3))
    
    def test_load_directory(self):
        """Test loading from directory."""
        images = load_comic(self.temp_dir)
        self.assertEqual(len(images), 3)
        for img in images:
            self.assertEqual(img.shape, (600, 800, 3))
    
    def test_get_file_info(self):
        """Test file info extraction."""
        info = get_file_info(self.test_images[0])
        self.assertEqual(info['format'], 'image')
        self.assertEqual(info['page_count'], 1)
        
        info_dir = get_file_info(self.temp_dir)
        self.assertEqual(info_dir['format'], 'directory')
        self.assertEqual(info_dir['page_count'], 3)


if __name__ == '__main__':
    unittest.main()
