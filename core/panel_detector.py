"""
Panel detector for MoFrame.
Detects comic panels (frames) from page images using computer vision.
"""

import numpy as np
import cv2
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ReadingOrder(Enum):
    """Comic reading directions."""
    LEFT_TO_RIGHT = "ltr"
    RIGHT_TO_LEFT = "rtl"  # Manga style
    TOP_TO_BOTTOM = "ttb"  # Webtoon style


@dataclass
class Panel:
    """Represents a single comic panel."""
    x: int
    y: int
    width: int
    height: int
    page_index: int = 0
    panel_index: int = 0
    
    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """Return bounding box as (x, y, width, height)."""
        return (self.x, self.y, self.width, self.height)
    
    @property
    def center(self) -> Tuple[float, float]:
        """Return center point."""
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    @property
    def area(self) -> int:
        """Return panel area."""
        return self.width * self.height
    
    def extract(self, image: np.ndarray) -> np.ndarray:
        """Extract panel from image."""
        return image[self.y:self.y + self.height, self.x:self.x + self.width]


class PanelDetector:
    """
    Detects comic panels from page images.
    
    Uses contour detection to find rectangular regions that are likely panels.
    """
    
    def __init__(
        self,
        min_panel_area_ratio: float = 0.02,
        max_panel_area_ratio: float = 0.9,
        gap_threshold: int = 10,
        reading_order: ReadingOrder = ReadingOrder.LEFT_TO_RIGHT
    ):
        """
        Initialize detector.
        
        Args:
            min_panel_area_ratio: Minimum panel area as ratio of page area
            max_panel_area_ratio: Maximum panel area as ratio of page area
            gap_threshold: Minimum gap between panels (pixels)
            reading_order: Expected reading direction
        """
        self.min_panel_area_ratio = min_panel_area_ratio
        self.max_panel_area_ratio = max_panel_area_ratio
        self.gap_threshold = gap_threshold
        self.reading_order = reading_order
    
    def detect(self, image: np.ndarray, page_index: int = 0) -> List[Panel]:
        """
        Detect panels in a comic page.
        
        Args:
            image: RGB image as numpy array (H, W, 3)
            page_index: Index of the page for tracking
            
        Returns:
            List of Panel objects in reading order
        """
        # Convert to grayscale for processing
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # Get image dimensions
        height, width = gray.shape
        page_area = height * width
        
        # Strategy 1: Find panels by detecting enclosed regions
        panels = self._detect_by_contours(gray, page_area, width, height)
        
        # Strategy 2: If few panels found, try line-based detection
        if len(panels) < 2:
            panels = self._detect_by_lines(gray, page_area, width, height)
        
        # Add page index
        for i, panel in enumerate(panels):
            panel.page_index = page_index
            panel.panel_index = i
        
        # Sort by reading order
        panels = self._sort_by_reading_order(panels, width, height)
        
        return panels
    
    def _detect_by_contours(
        self, 
        gray: np.ndarray, 
        page_area: int,
        width: int, 
        height: int
    ) -> List[Panel]:
        """Detect panels using contour detection."""
        # Invert image (panels are usually lighter than gutters)
        inverted = cv2.bitwise_not(gray)
        
        # Apply adaptive threshold
        binary = cv2.adaptiveThreshold(
            inverted, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            15, 10
        )
        
        # Dilate to connect nearby panel edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(binary, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        panels = []
        
        for contour in contours:
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by area
            area = w * h
            area_ratio = area / page_area
            
            if not (self.min_panel_area_ratio <= area_ratio <= self.max_panel_area_ratio):
                continue
            
            # Filter by aspect ratio (panels shouldn't be too thin)
            aspect_ratio = max(w, h) / max(min(w, h), 1)
            if aspect_ratio > 10:  # Too thin, probably a line
                continue
            
            # Filter by solidity (panels should be solid rectangles)
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            if hull_area > 0:
                solidity = area / hull_area
                if solidity < 0.5:  # Too irregular
                    continue
            
            panels.append(Panel(x, y, w, h))
        
        return panels
    
    def _detect_by_lines(
        self, 
        gray: np.ndarray, 
        page_area: int,
        width: int, 
        height: int
    ) -> List[Panel]:
        """Detect panels by finding line gaps (alternative method)."""
        # Apply edge detection
        edges = cv2.Canny(gray, 50, 150)
        
        # Find horizontal and vertical lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (width // 4, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, height // 4))
        
        horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
        vertical_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, vertical_kernel)
        
        # Combine lines
        lines = cv2.addWeighted(horizontal_lines, 0.5, vertical_lines, 0.5, 0)
        
        # Find contours from lines
        contours, _ = cv2.findContours(
            lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        panels = []
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            area_ratio = area / page_area
            
            if self.min_panel_area_ratio <= area_ratio <= self.max_panel_area_ratio:
                aspect_ratio = max(w, h) / max(min(w, h), 1)
                if aspect_ratio <= 10:
                    panels.append(Panel(x, y, w, h))
        
        return panels
    
    def _sort_by_reading_order(
        self, 
        panels: List[Panel], 
        width: int, 
        height: int
    ) -> List[Panel]:
        """Sort panels by expected reading order."""
        if not panels:
            return panels
        
        # Group panels by rows (vertical position)
        row_threshold = height * 0.1  # 10% of page height
        
        rows = []
        current_row = [panels[0]]
        
        for panel in panels[1:]:
            if abs(panel.y - current_row[0].y) < row_threshold:
                current_row.append(panel)
            else:
                rows.append(current_row)
                current_row = [panel]
        rows.append(current_row)
        
        # Sort rows by vertical position (top to bottom)
        rows.sort(key=lambda row: sum(p.y for p in row) / len(row))
        
        # Sort panels within each row by horizontal position
        sorted_panels = []
        for row in rows:
            if self.reading_order == ReadingOrder.RIGHT_TO_LEFT:
                row.sort(key=lambda p: -p.x)  # Right to left
            else:
                row.sort(key=lambda p: p.x)  # Left to right
            sorted_panels.extend(row)
        
        # Update panel indices
        for i, panel in enumerate(sorted_panels):
            panel.panel_index = i
        
        return sorted_panels
    
    def visualize(
        self, 
        image: np.ndarray, 
        panels: List[Panel],
        show_numbers: bool = True
    ) -> np.ndarray:
        """
        Draw detected panels on image.
        
        Args:
            image: Original RGB image
            panels: Detected panels
            show_numbers: Whether to show panel numbers
            
        Returns:
            Visualization image
        """
        viz = image.copy()
        
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Cyan
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Yellow
        ]
        
        for i, panel in enumerate(panels):
            color = colors[i % len(colors)]
            
            # Draw rectangle
            cv2.rectangle(
                viz,
                (panel.x, panel.y),
                (panel.x + panel.width, panel.y + panel.height),
                color,
                3
            )
            
            # Draw number
            if show_numbers:
                cv2.putText(
                    viz,
                    str(i + 1),
                    (panel.x + 10, panel.y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    color,
                    2
                )
        
        return viz


def detect_panels(
    image: np.ndarray,
    reading_order: str = "ltr",
    **kwargs
) -> List[Panel]:
    """
    Convenience function to detect panels.
    
    Args:
        image: RGB image
        reading_order: "ltr", "rtl", or "ttb"
        **kwargs: Additional detector parameters
        
    Returns:
        List of detected panels
    """
    order = ReadingOrder.LEFT_TO_RIGHT
    if reading_order == "rtl":
        order = ReadingOrder.RIGHT_TO_LEFT
    elif reading_order == "ttb":
        order = ReadingOrder.TOP_TO_BOTTOM
    
    detector = PanelDetector(reading_order=order, **kwargs)
    return detector.detect(image)


if __name__ == "__main__":
    # CLI test
    import sys
    from loader import load_comic
    
    if len(sys.argv) < 2:
        print("Usage: python panel_detector.py <path_to_comic_page>")
        sys.exit(1)
    
    path = sys.argv[1]
    
    print(f"\nLoading image...")
    images = load_comic(path)
    
    if not images:
        print("No images loaded")
        sys.exit(1)
    
    image = images[0]
    print(f"Image shape: {image.shape}")
    
    print(f"\nDetecting panels...")
    detector = PanelDetector()
    panels = detector.detect(image)
    
    print(f"Found {len(panels)} panels:")
    for i, panel in enumerate(panels):
        print(f"  Panel {i+1}: pos=({panel.x}, {panel.y}), size={panel.width}x{panel.height}")
    
    # Save visualization
    if panels:
        viz = detector.visualize(image, panels)
        output_path = "panel_detection_test.jpg"
        cv2.imwrite(output_path, cv2.cvtColor(viz, cv2.COLOR_RGB2BGR))
        print(f"\nVisualization saved to: {output_path}")
