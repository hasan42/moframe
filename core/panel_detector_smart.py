"""
Умный детектор панелей с адаптивными порогами и детекцией speech bubbles.

Улучшения:
- Адаптивные пороги на основе контраста/яркости
- Детекция speech bubbles (облачка с текстом)
- Лучшее восстановление порядка панелей
- Поддержка нестандартных раскладок
"""

import numpy as np
import cv2
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from core.panel_detector import Panel, PanelDetector, ReadingOrder


class PanelType(Enum):
    """Тип панели."""
    STANDARD = "standard"
    SPEECH_BUBBLE = "speech_bubble"
    FULL_PAGE = "full_page"
    INSET = "inset"


@dataclass
class SmartPanel(Panel):
    """Панель с дополнительной информацией."""
    panel_type: PanelType = PanelType.STANDARD
    confidence: float = 1.0
    has_text: bool = False
    text_regions: List[Tuple[int, int, int, int]] = None
    
    def __post_init__(self):
        if self.text_regions is None:
            self.text_regions = []


class SmartPanelDetector(PanelDetector):
    """
    Умный детектор с адаптивными порогами.
    
    Улучшения:
    1. Анализирует контраст/яркость изображения перед детекцией
    2. Адаптирует пороги под конкретное изображение
    3. Находит speech bubbles отдельно
    4. Улучшенное восстановление порядка
    """
    
    def __init__(
        self,
        min_panel_area_ratio: float = 0.02,
        max_panel_area_ratio: float = 0.9,
        gap_threshold: int = 10,
        reading_order: ReadingOrder = ReadingOrder.LEFT_TO_RIGHT,
        adaptive_thresholds: bool = True,
        detect_bubbles: bool = True
    ):
        super().__init__(
            min_panel_area_ratio=min_panel_area_ratio,
            max_panel_area_ratio=max_panel_area_ratio,
            gap_threshold=gap_threshold,
            reading_order=reading_order
        )
        self.adaptive_thresholds = adaptive_thresholds
        self.detect_bubbles = detect_bubbles
        self._last_image_stats = None
    
    def _analyze_image(self, gray: np.ndarray) -> dict:
        """Анализирует характеристики изображения."""
        stats = {
            'mean': np.mean(gray),
            'std': np.std(gray),
            'median': np.median(gray),
            'min': np.min(gray),
            'max': np.max(gray),
            'contrast': np.std(gray) / (np.mean(gray) + 1e-6)
        }
        self._last_image_stats = stats
        return stats
    
    def detect(self, image: np.ndarray, page_index: int = 0) -> List[SmartPanel]:
        """
        Detect panels with smart analysis.
        
        Args:
            image: RGB image
            page_index: Page index
            
        Returns:
            List of SmartPanel objects
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # Analyze image characteristics
        stats = self._analyze_image(gray)
        
        # Detect panels using improved algorithm
        panels = self._detect_smart(gray, image.shape[1], image.shape[0])
        
        # Detect speech bubbles if enabled
        if self.detect_bubbles:
            bubbles = self._detect_speech_bubbles(gray, image.shape[1], image.shape[0])
            panels.extend(bubbles)
        
        # Add metadata
        for i, panel in enumerate(panels):
            panel.page_index = page_index
            panel.panel_index = i
            panel.original_image = image.copy()
        
        # Sort by reading order
        panels = self._sort_by_reading_order(panels, image.shape[1], image.shape[0])
        
        return panels
    
    def _detect_smart(self, gray: np.ndarray, width: int, height: int) -> List[SmartPanel]:
        """Smart panel detection with adaptive thresholds."""
        page_area = width * height
        
        # Calculate adaptive thresholds based on image stats
        stats = self._last_image_stats or self._analyze_image(gray)
        contrast = stats['contrast']
        
        # Higher contrast = stronger edges = higher thresholds
        edge_threshold1 = int(50 * (1 + contrast * 0.5))
        edge_threshold2 = int(150 * (1 + contrast * 0.5))
        
        # Method 1: Edge detection with adaptive thresholds
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, edge_threshold1, edge_threshold2)
        
        # Dilate to connect nearby edges
        kernel_size = max(3, int(5 * contrast))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        edges = cv2.dilate(edges, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        panels = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Filter by size
            area_ratio = (w * h) / page_area
            if area_ratio < self.min_panel_area_ratio:
                continue
            if area_ratio > self.max_panel_area_ratio:
                continue
            
            # Filter by aspect ratio
            aspect = max(w, h) / max(min(w, h), 1)
            if aspect > 12:
                continue
            
            # Check if it's a panel (has 4 sides)
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            # Panels usually have 4 corners
            confidence = 1.0
            if len(approx) == 4:
                confidence = 0.9
            elif len(approx) > 4:
                confidence = 0.7  # Might be rounded panel
            else:
                confidence = 0.5
            
            # Check for text inside
            roi = gray[y:y+h, x:x+w]
            has_text = self._has_text_region(roi)
            
            panel = SmartPanel(
                x=x, y=y, width=w, height=h,
                panel_type=PanelType.STANDARD,
                confidence=confidence,
                has_text=has_text
            )
            panels.append(panel)
        
        # If no panels found, try line-based detection
        if len(panels) < 1:
            panels = self._detect_by_lines_smart(gray, width, height)
        
        return panels
    
    def _detect_by_lines_smart(self, gray: np.ndarray, width: int, height: int) -> List[SmartPanel]:
        """Line-based detection with adaptive thresholds."""
        page_area = width * height
        stats = self._last_image_stats or self._analyze_image(gray)
        
        # Adaptive threshold for dark lines
        dark_threshold = int(stats['mean'] * 0.4)
        
        # Find dark lines (panel borders)
        _, dark = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)
        
        # Morphological operations
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (width // 15, 1))
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, height // 15))
        h_lines = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, h_kernel)
        v_lines = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, v_kernel)
        
        borders = cv2.add(h_lines, v_lines)
        
        # Find lines
        border_edges = cv2.Canny(borders, 50, 150)
        lines = cv2.HoughLinesP(
            border_edges, 1, np.pi/180,
            threshold=min(width, height)//15,
            minLineLength=min(width, height)//6,
            maxLineGap=30
        )
        
        h_positions = set([0, height])
        v_positions = set([0, width])
        
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                
                if dx > dy * 4:  # Horizontal
                    y_avg = (y1 + y2) // 2
                    if 10 < y_avg < height - 10:
                        h_positions.add(y_avg)
                elif dy > dx * 4:  # Vertical
                    x_avg = (x1 + x2) // 2
                    if 10 < x_avg < width - 10:
                        v_positions.add(x_avg)
        
        # Cluster positions with adaptive threshold
        cluster_threshold = max(15, int(25 * stats['contrast']))
        h_positions = self._cluster_positions(sorted(h_positions), threshold=cluster_threshold)
        v_positions = self._cluster_positions(sorted(v_positions), threshold=cluster_threshold)
        
        # Build panels
        panels = []
        margin = 2
        
        for i in range(len(h_positions) - 1):
            for j in range(len(v_positions) - 1):
                x1 = v_positions[j] + margin
                x2 = v_positions[j + 1] - margin
                y1 = h_positions[i] + margin
                y2 = h_positions[i + 1] - margin
                
                w = max(0, x2 - x1)
                h = max(0, y2 - y1)
                
                if w < width // 10 or h < height // 12:
                    continue
                
                area_ratio = (w * h) / page_area
                if area_ratio < 0.015 or area_ratio > 0.95:
                    continue
                
                aspect = max(w, h) / max(min(w, h), 1)
                if aspect > 12:
                    continue
                
                # Check for text
                roi = gray[y1:y2, x1:x2]
                has_text = self._has_text_region(roi)
                
                panel = SmartPanel(
                    x=x1, y=y1, width=w, height=h,
                    panel_type=PanelType.STANDARD,
                    confidence=0.8,
                    has_text=has_text
                )
                panels.append(panel)
        
        return panels
    
    def _detect_speech_bubbles(self, gray: np.ndarray, width: int, height: int) -> List[SmartPanel]:
        """Detect speech bubbles."""
        page_area = width * height
        panels = []
        
        # Speech bubbles are usually white/light with dark text
        # Threshold to find light regions
        _, light = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(light, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < page_area * 0.005:  # Too small
                continue
            if area > page_area * 0.3:  # Too large
                continue
            
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Check if it's roughly circular/oval (bubble shape)
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            # Bubbles have many sides or are circular
            if len(approx) > 6:
                # Check if it contains text
                roi = gray[y:y+h, x:x+w]
                if self._has_text_region(roi):
                    panel = SmartPanel(
                        x=x, y=y, width=w, height=h,
                        panel_type=PanelType.SPEECH_BUBBLE,
                        confidence=0.7,
                        has_text=True
                    )
                    panels.append(panel)
        
        return panels
    
    def _has_text_region(self, roi: np.ndarray) -> bool:
        """Check if region contains text."""
        if roi.size == 0:
            return False
        
        # Text has high contrast
        edges = cv2.Canny(roi, 100, 200)
        edge_ratio = np.sum(edges > 0) / roi.size
        
        # Text regions have moderate edge density
        return 0.01 < edge_ratio < 0.3
    
    def _sort_by_reading_order(
        self,
        panels: List[SmartPanel],
        width: int,
        height: int
    ) -> List[SmartPanel]:
        """Sort panels by reading order with improved logic."""
        if not panels:
            return panels
        
        # Group panels by rows
        row_threshold = height * 0.2
        
        rows = []
        current_row = [panels[0]]
        
        for panel in panels[1:]:
            if abs(panel.y - current_row[0].y) < row_threshold:
                current_row.append(panel)
            else:
                rows.append(current_row)
                current_row = [panel]
        rows.append(current_row)
        
        # Sort rows by vertical position
        rows.sort(key=lambda row: sum(p.y for p in row) / len(row))
        
        # Sort panels within each row
        sorted_panels = []
        for row in rows:
            if self.reading_order == ReadingOrder.RIGHT_TO_LEFT:
                row.sort(key=lambda p: -p.x)
            elif self.reading_order == ReadingOrder.TOP_TO_BOTTOM:
                row.sort(key=lambda p: p.y)
            else:
                row.sort(key=lambda p: p.x)
            sorted_panels.extend(row)
        
        return sorted_panels


def detect_panels_smart(
    image: np.ndarray,
    reading_order: str = "ltr",
    detect_bubbles: bool = True
) -> List[SmartPanel]:
    """
    Convenience function for smart panel detection.
    
    Args:
        image: RGB image
        reading_order: "ltr", "rtl", or "ttb"
        detect_bubbles: Whether to detect speech bubbles
        
    Returns:
        List of SmartPanel objects
    """
    order_map = {
        "ltr": ReadingOrder.LEFT_TO_RIGHT,
        "rtl": ReadingOrder.RIGHT_TO_LEFT,
        "ttb": ReadingOrder.TOP_TO_BOTTOM
    }
    
    detector = SmartPanelDetector(
        reading_order=order_map.get(reading_order, ReadingOrder.LEFT_TO_RIGHT),
        detect_bubbles=detect_bubbles
    )
    
    return detector.detect(image)
