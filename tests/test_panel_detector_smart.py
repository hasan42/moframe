"""
Тесты для SmartPanelDetector.
"""

import pytest
import numpy as np
import cv2

from core.panel_detector_smart import SmartPanelDetector, SmartPanel, PanelType, detect_panels_smart


class TestSmartPanelDetector:
    """Tests for SmartPanelDetector."""
    
    def test_detects_simple_grid(self):
        """Test detection of 2x2 grid."""
        # Create image with 2x2 grid
        img = np.ones((600, 800, 3), dtype=np.uint8) * 255
        
        # Draw panels
        cv2.rectangle(img, (50, 50), (350, 250), (0, 0, 0), 3)
        cv2.rectangle(img, (400, 50), (750, 250), (0, 0, 0), 3)
        cv2.rectangle(img, (50, 300), (350, 550), (0, 0, 0), 3)
        cv2.rectangle(img, (400, 300), (750, 550), (0, 0, 0), 3)
        
        detector = SmartPanelDetector()
        panels = detector.detect(img)
        
        assert len(panels) == 4
        
        # Check order (left-to-right, top-to-bottom)
        assert panels[0].x < panels[1].x
        assert panels[0].y < panels[2].y
    
    def test_adaptive_thresholds(self):
        """Test that thresholds adapt to image."""
        # High contrast image
        img1 = np.ones((400, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(img1, (50, 50), (350, 350), (0, 0, 0), 3)
        
        # Low contrast image
        img2 = np.ones((400, 400, 3), dtype=np.uint8) * 180
        cv2.rectangle(img2, (50, 50), (350, 350), (100, 100, 100), 3)
        
        detector = SmartPanelDetector()
        
        panels1 = detector.detect(img1)
        panels2 = detector.detect(img2)
        
        assert len(panels1) >= 1
        assert len(panels2) >= 1
    
    def test_detects_speech_bubbles(self):
        """Test speech bubble detection."""
        img = np.ones((600, 800, 3), dtype=np.uint8) * 240
        
        # Draw speech bubble (circle)
        cv2.circle(img, (400, 300), 100, (255, 255, 255), -1)
        cv2.circle(img, (400, 300), 100, (0, 0, 0), 3)
        
        # Add text inside
        cv2.putText(img, "Hello!", (350, 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        
        detector = SmartPanelDetector(detect_bubbles=True)
        panels = detector.detect(img)
        
        # Should find at least the bubble
        assert len(panels) >= 1
    
    def test_confidence_scores(self):
        """Test that confidence scores are reasonable."""
        img = np.ones((400, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(img, (50, 50), (350, 350), (0, 0, 0), 3)
        
        detector = SmartPanelDetector()
        panels = detector.detect(img)
        
        assert len(panels) >= 1
        for panel in panels:
            assert 0 <= panel.confidence <= 1.0
    
    def test_fallback_single_panel(self):
        """Test fallback to single panel."""
        # Image with no clear panels - just gradient
        img = np.zeros((400, 400, 3), dtype=np.uint8)
        for i in range(400):
            img[i, :] = i // 2
        
        detector = SmartPanelDetector()
        panels = detector.detect(img)
        
        # Should still find at least something (maybe the whole page)
        assert len(panels) >= 1, "Should fallback to single panel"
    
    def test_convenience_function(self):
        """Test detect_panels_smart function."""
        img = np.ones((600, 800, 3), dtype=np.uint8) * 255
        cv2.rectangle(img, (50, 50), (350, 250), (0, 0, 0), 3)
        
        panels = detect_panels_smart(img, reading_order="ltr")
        
        assert len(panels) >= 1
    
    def test_rtl_reading_order(self):
        """Test right-to-left reading order."""
        img = np.ones((400, 600, 3), dtype=np.uint8) * 255
        cv2.rectangle(img, (50, 50), (250, 250), (0, 0, 0), 3)
        cv2.rectangle(img, (300, 50), (550, 250), (0, 0, 0), 3)
        
        from core.panel_detector import ReadingOrder
        detector = SmartPanelDetector(reading_order=ReadingOrder.RIGHT_TO_LEFT)
        panels = detector.detect(img)
        
        assert len(panels) == 2
        # RTL: right panel should be first
        assert panels[0].x > panels[1].x


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
