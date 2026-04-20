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
    original_image: Optional[np.ndarray] = None

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

    def extract(self, image: Optional[np.ndarray] = None) -> np.ndarray:
        """Extract panel from image. Uses stored image if not provided."""
        img = image if image is not None else self.original_image
        if img is None:
            raise ValueError("No image available for extraction")
        return img[self.y:self.y + self.height, self.x:self.x + self.width]

    def extract_from_original(self) -> np.ndarray:
        """Extract panel from stored original image."""
        if self.original_image is None:
            raise ValueError("No original image stored in panel")
        return self.extract(self.original_image)


class PanelDetector:
    """
    Detects comic panels from page images.
    Uses content projection to find panel boundaries.
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

        # Strategy: Find panels by splitting on content gaps
        panels = self._detect_by_projection(gray, page_area, width, height)

        # Fallback if no panels found
        if len(panels) < 1:
            panels = self._detect_by_fallback(gray, page_area, width, height)

        # Add page index and reference to original image
        for i, panel in enumerate(panels):
            panel.page_index = page_index
            panel.panel_index = i
            panel.original_image = image.copy()

        # Sort by reading order
        panels = self._sort_by_reading_order(panels, width, height)

        return panels

    def _detect_by_projection(
        self,
        gray: np.ndarray,
        page_area: int,
        width: int,
        height: int
    ) -> List[Panel]:
        """Detect panels by finding dark separator lines."""
        # Find very dark pixels (panel borders)
        _, dark = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY_INV)
        
        # Dilate horizontally to connect horizontal border segments
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (width // 8, 1))
        h_lines = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, h_kernel)
        
        # Dilate vertically to connect vertical border segments  
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, height // 8))
        v_lines = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, v_kernel)
        
        # Combine
        borders = cv2.add(h_lines, v_lines)
        
        # Dilate to connect corners
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        borders = cv2.dilate(borders, kernel, iterations=2)
        
        # Invert: borders become black, panels become white
        panel_mask = cv2.bitwise_not(borders)
        
        # Find connected components (panels)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            panel_mask, connectivity=8
        )
        
        panels = []
        margin = min(width, height) // 40
        
        for i in range(1, num_labels):
            x, y, w, h, area = stats[i]
            
            # Skip if covers almost full page
            if x < margin and y < margin and (x+w) > (width-margin) and (y+h) > (height-margin):
                continue
            
            area_ratio = (w * h) / page_area
            if area_ratio < 0.02:
                continue
            if area_ratio > 0.85:
                continue
            
            if w < width // 6 or h < height // 10:
                continue
                
            aspect = max(w, h) / max(min(w, h), 1)
            if aspect > 10:
                continue
            
            panels.append(Panel(x, y, w, h))
        
        # If not enough panels, try content-based approach
        if len(panels) < 2:
            panels = self._detect_by_content_gaps(gray, page_area, width, height)
        
        return panels
    
    def _detect_by_content_gaps(
        self,
        gray: np.ndarray,
        page_area: int,
        width: int,
        height: int
    ) -> List[Panel]:
        """Fallback: detect panels by content gaps."""
        # Binary: content = not pure white
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

        # Remove small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # Dilate to connect content within panels
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        binary = cv2.dilate(binary, dilate_kernel, iterations=2)

        # Find content bounding box
        rows = np.any(binary, axis=1)
        cols = np.any(binary, axis=0)

        if not np.any(rows) or not np.any(cols):
            return []

        y_min = max(0, np.where(rows)[0][0] - 5)
        y_max = min(height, np.where(rows)[0][-1] + 5)
        x_min = max(0, np.where(cols)[0][0] - 5)
        x_max = min(width, np.where(cols)[0][-1] + 5)

        content = binary[y_min:y_max, x_min:x_max]
        content_h, content_w = content.shape

        # Analyze horizontal gaps
        h_proj = np.sum(content, axis=1)
        h_threshold = np.mean(h_proj) * 0.05  # Lower threshold
        if h_threshold < 10:
            h_threshold = 10

        # Find horizontal splits (gaps)
        h_splits = [0]
        in_gap = False
        gap_start = 0
        min_gap = 8

        for i, val in enumerate(h_proj):
            if val < h_threshold and not in_gap:
                in_gap = True
                gap_start = i
            elif val >= h_threshold and in_gap:
                in_gap = False
                if i - gap_start >= min_gap:
                    h_splits.append((gap_start + i) // 2)

        if in_gap and content_h - gap_start >= min_gap:
            h_splits.append(content_h)
        else:
            h_splits.append(content_h)

        # Analyze vertical gaps
        v_proj = np.sum(content, axis=0)
        v_threshold = np.mean(v_proj) * 0.05  # Lower threshold
        if v_threshold < 10:
            v_threshold = 10

        v_splits = [0]
        in_gap = False
        gap_start = 0

        for i, val in enumerate(v_proj):
            if val < v_threshold and not in_gap:
                in_gap = True
                gap_start = i
            elif val >= v_threshold and in_gap:
                in_gap = False
                if i - gap_start >= min_gap:
                    v_splits.append((gap_start + i) // 2)

        if in_gap and content_w - gap_start >= min_gap:
            v_splits.append(content_w)
        else:
            v_splits.append(content_w)

        # Remove duplicates and sort
        h_splits = sorted(set(h_splits))
        v_splits = sorted(set(v_splits))

        # Build panels
        panels = []
        margin = 3

        for i in range(len(h_splits) - 1):
            for j in range(len(v_splits) - 1):
                x1 = x_min + v_splits[j] + margin
                x2 = x_min + v_splits[j + 1] - margin
                y1 = y_min + h_splits[i] + margin
                y2 = y_min + h_splits[i + 1] - margin

                w = max(0, x2 - x1)
                h = max(0, y2 - y1)

                if w < width // 8 or h < height // 12:
                    continue

                area_ratio = (w * h) / page_area
                if area_ratio < 0.015 or area_ratio > 0.95:
                    continue

                aspect = max(w, h) / max(min(w, h), 1)
                if aspect > 10:
                    continue

                panels.append(Panel(x1, y1, w, h))

        return panels

    def _detect_by_fallback(
        self,
        gray: np.ndarray,
        page_area: int,
        width: int,
        height: int
    ) -> List[Panel]:
        """Fallback: return whole page as one panel."""
        margin = min(width, height) // 40
        return [Panel(margin, margin, width - 2*margin, height - 2*margin)]

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
        row_threshold = height * 0.15  # 15% of page height

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
