"""
Tests for morpher module.
"""

import unittest
import numpy as np
from PIL import Image

from core.morpher import Morpher, MorphConfig, MorphStrategy, morph_images


class TestMorpher(unittest.TestCase):
    
    def setUp(self):
        """Create test images."""
        # Create two different colored images
        self.img1 = np.full((600, 800, 3), [255, 100, 100], dtype=np.uint8)  # Red-ish
        self.img2 = np.full((600, 800, 3), [100, 100, 255], dtype=np.uint8)  # Blue-ish
        self.morpher = Morpher(target_size=(640, 480))
    
    def test_letterbox(self):
        """Test letterboxing preserves aspect ratio."""
        # Wide image
        wide_img = np.zeros((300, 800, 3), dtype=np.uint8)
        result = self.morpher._letterbox(wide_img)
        self.assertEqual(result.shape, (480, 640, 3))
        
        # Tall image
        tall_img = np.zeros((800, 300, 3), dtype=np.uint8)
        result = self.morpher._letterbox(tall_img)
        self.assertEqual(result.shape, (480, 640, 3))
    
    def test_crossfade(self):
        """Test crossfade morphing."""
        config = MorphConfig(strategy=MorphStrategy.CROSSFADE, duration_frames=10)
        frames = self.morpher.morph(self.img1, self.img2, config)
        
        self.assertEqual(len(frames), 10)
        
        # First frame should be more like img1
        self.assertGreater(np.mean(frames[0][:,:,0]), 200)  # Red channel high
        
        # Last frame should be more like img2
        self.assertGreater(np.mean(frames[-1][:,:,2]), 200)  # Blue channel high
    
    def test_ken_burns(self):
        """Test Ken Burns effect."""
        config = MorphConfig(
            strategy=MorphStrategy.KEN_BURNS,
            duration_frames=24,
            ken_burns_zoom=1.5
        )
        frames = self.morpher.morph(self.img1, self.img2, config)
        
        self.assertEqual(len(frames), 24)
        
        # All frames should be target size
        for frame in frames:
            self.assertEqual(frame.shape, (480, 640, 3))
    
    def test_slide(self):
        """Test slide transition."""
        config = MorphConfig(
            strategy=MorphStrategy.SLIDE,
            duration_frames=10,
            slide_direction="left"
        )
        frames = self.morpher.morph(self.img1, self.img2, config)
        
        self.assertEqual(len(frames), 10)
    
    def test_zoom(self):
        """Test zoom transition."""
        config = MorphConfig(strategy=MorphStrategy.ZOOM, duration_frames=10)
        frames = self.morpher.morph(self.img1, self.img2, config)
        
        self.assertEqual(len(frames), 10)
    
    def test_convenience_function(self):
        """Test morph_images convenience function."""
        frames = morph_images(
            self.img1, self.img2,
            strategy="crossfade",
            duration_frames=5,
            target_size=(320, 240)
        )
        
        self.assertEqual(len(frames), 5)
        self.assertEqual(frames[0].shape, (240, 320, 3))
    
    def test_easing_functions(self):
        """Test different easing functions."""
        for easing in ["linear", "ease_in", "ease_out", "ease_in_out"]:
            config = MorphConfig(
                strategy=MorphStrategy.CROSSFADE,
                duration_frames=5,
                easing=easing
            )
            frames = self.morpher.morph(self.img1, self.img2, config)
            self.assertEqual(len(frames), 5)


if __name__ == '__main__':
    unittest.main()
