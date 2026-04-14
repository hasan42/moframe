"""
Tests for panel detector.
"""

import unittest
import numpy as np
from PIL import Image, ImageDraw
import tempfile
from pathlib import Path

from core.panel_detector import PanelDetector, Panel, ReadingOrder, detect_panels


class TestPanelDetector(unittest.TestCase):
    
    def _create_test_page(self, panels_config):
        """Create a synthetic comic page with defined panels."""
        # White background (1000x1400, typical comic page)
        img = Image.new('RGB', (1000, 1400), color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw black lines for panels
        for x, y, w, h in panels_config:
            draw.rectangle([x, y, x+w, y+h], outline='black', width=5)
        
        return np.array(img)
    
    def test_detect_single_panel(self):
        """Test detection of single panel page."""
        config = [(50, 50, 900, 1300)]
        img = self._create_test_page(config)
        
        detector = PanelDetector()
        panels = detector.detect(img)
        
        self.assertEqual(len(panels), 1)
        self.assertGreater(panels[0].width, 800)
        self.assertGreater(panels[0].height, 1200)
    
    def test_detect_multiple_panels(self):
        """Test detection of multiple panels."""
        # 2x2 grid
        config = [
            (50, 50, 440, 640),    # Top-left
            (510, 50, 440, 640),   # Top-right
            (50, 710, 440, 640),   # Bottom-left
            (510, 710, 440, 640),  # Bottom-right
        ]
        img = self._create_test_page(config)
        
        detector = PanelDetector()
        panels = detector.detect(img)
        
        # Should find at least 3-4 panels
        self.assertGreaterEqual(len(panels), 3)
        
        # Check reading order (LTR)
        centers = [p.center for p in panels]
        for i in range(len(centers) - 1):
            # Either next panel is to the right, or below
            self.assertTrue(
                centers[i+1][0] > centers[i][0] or centers[i+1][1] > centers[i][1]
            )
    
    def test_panel_extraction(self):
        """Test extracting panel from image."""
        config = [(100, 100, 200, 300)]
        img = self._create_test_page(config)
        
        panel = Panel(100, 100, 200, 300)
        extracted = panel.extract(img)
        
        self.assertEqual(extracted.shape, (300, 200, 3))
    
    def test_reading_order_rtl(self):
        """Test right-to-left reading order."""
        config = [
            (50, 50, 440, 640),    # Left
            (510, 50, 440, 640),   # Right
        ]
        img = self._create_test_page(config)
        
        detector = PanelDetector(reading_order=ReadingOrder.RIGHT_TO_LEFT)
        panels = detector.detect(img)
        
        # First panel should be on the right
        if len(panels) >= 2:
            self.assertGreater(panels[0].x, panels[1].x)
    
    def test_convenience_function(self):
        """Test detect_panels convenience function."""
        config = [(50, 50, 400, 600)]
        img = self._create_test_page(config)
        
        panels = detect_panels(img, reading_order="ltr")
        self.assertGreater(len(panels), 0)


if __name__ == '__main__':
    unittest.main()
