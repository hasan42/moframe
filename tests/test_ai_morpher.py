"""Tests for AI morphing module."""

import unittest
import numpy as np
import cv2

from core.ai_morpher import AIMorpher, AIMorphConfig, AIMorphStrategy


class TestAIMorpher(unittest.TestCase):
    """Test AI morpher functionality."""
    
    def setUp(self):
        """Create test images."""
        # Simple test images with clear features
        self.img1 = np.zeros((300, 400, 3), dtype=np.uint8)
        cv2.rectangle(self.img1, (50, 50), (350, 250), (255, 100, 100), -1)
        
        self.img2 = np.zeros((300, 400, 3), dtype=np.uint8)
        cv2.rectangle(self.img2, (50, 50), (350, 250), (100, 100, 255), -1)
    
    def test_optical_flow_morph(self):
        """Test optical flow morphing."""
        morpher = AIMorpher(target_size=(400, 300))
        config = AIMorphConfig(
            strategy=AIMorphStrategy.OPTICAL_FLOW,
            duration_frames=10,
            flow_method="farneback"
        )
        
        frames = morpher.morph(self.img1, self.img2, config)
        
        self.assertEqual(len(frames), 10)
        self.assertEqual(frames[0].shape, (300, 400, 3))
        
        # First and last frames should be the original images
        np.testing.assert_array_equal(frames[0], self.img1)
        np.testing.assert_array_equal(frames[-1], self.img2)
    
    def test_crossfade_fallback(self):
        """Test crossfade fallback."""
        morpher = AIMorpher(target_size=(400, 300))
        config = AIMorphConfig(
            strategy=AIMorphStrategy.STYLE_TRANSFER,  # Will fall back
            duration_frames=5
        )
        
        frames = morpher.morph(self.img1, self.img2, config)
        
        self.assertEqual(len(frames), 5)
        self.assertEqual(frames[0].shape, (300, 400, 3))
    
    def test_hybrid_morph(self):
        """Test hybrid morphing."""
        morpher = AIMorpher(target_size=(400, 300))
        config = AIMorphConfig(
            strategy=AIMorphStrategy.HYBRID,
            duration_frames=8,
            flow_method="farneback"
        )
        
        frames = morpher.morph(self.img1, self.img2, config)
        
        self.assertEqual(len(frames), 8)
    
    def test_preprocess(self):
        """Test image preprocessing."""
        morpher = AIMorpher(target_size=(640, 480))
        
        # Test with smaller image
        small_img = np.zeros((150, 200, 3), dtype=np.uint8)
        processed = morpher._preprocess(small_img)
        
        self.assertEqual(processed.shape, (480, 640, 3))
        self.assertTrue(processed.dtype == np.float32)
        self.assertTrue(np.max(processed) <= 1.0)
    
    def test_preprocess_grayscale(self):
        """Test preprocessing grayscale image."""
        morpher = AIMorpher(target_size=(400, 300))
        gray = np.zeros((300, 400), dtype=np.uint8)
        processed = morpher._preprocess(gray)
        
        self.assertEqual(processed.shape, (300, 400, 3))
    
    def test_preprocess_rgba(self):
        """Test preprocessing RGBA image."""
        morpher = AIMorpher(target_size=(400, 300))
        rgba = np.zeros((300, 400, 4), dtype=np.uint8)
        processed = morpher._preprocess(rgba)
        
        self.assertEqual(processed.shape, (300, 400, 3))
    
    def test_easing_functions(self):
        """Test easing functions."""
        morpher = AIMorpher()
        
        # Test that easing returns values in [0, 1]
        for easing in ["linear", "ease_in", "ease_out", "ease_in_out"]:
            self.assertEqual(morpher._ease(0, easing), 0.0)
            self.assertEqual(morpher._ease(1, easing), 1.0)
        
        # Test ease_in_out at t=0.5 gives 0.5 (smooth curve through center)
        self.assertAlmostEqual(morpher._ease(0.5, "ease_in_out"), 0.5, places=5)
    
    def test_depth_aware_fallback(self):
        """Test depth-aware fallback to optical flow."""
        morpher = AIMorpher(target_size=(400, 300))
        config = AIMorphConfig(
            strategy=AIMorphStrategy.DEPTH_AWARE,
            duration_frames=5
        )
        
        frames = morpher.morph(self.img1, self.img2, config)
        
        self.assertEqual(len(frames), 5)
    
    def test_frame_consistency(self):
        """Test that frames are consistent."""
        morpher = AIMorpher(target_size=(400, 300))
        config = AIMorphConfig(
            strategy=AIMorphStrategy.OPTICAL_FLOW,
            duration_frames=10
        )
        
        frames = morpher.morph(self.img1, self.img2, config)
        
        # All frames should have same shape
        for frame in frames:
            self.assertEqual(frame.shape, (300, 400, 3))
            self.assertTrue(frame.dtype == np.uint8)
        
        # Check that first and last frames are the original images
        np.testing.assert_array_equal(frames[0], self.img1)
        np.testing.assert_array_equal(frames[-1], self.img2)


if __name__ == "__main__":
    unittest.main()
