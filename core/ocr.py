"""
OCR Module for MoFrame - Extract text from comic panels.

Uses pytesseract (Tesseract) for text extraction.
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from PIL import Image


@dataclass
class TextBlock:
    """Represents a block of text found in an image."""
    text: str
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    block_type: str = "unknown"  # "speech", "sfx", "caption", "unknown"


class OCRProcessor:
    """OCR processor for comic panels."""
    
    def __init__(self, lang: str = "rus+eng"):
        self.lang = lang
        self._check_tesseract()
    
    def _check_tesseract(self):
        """Check if tesseract is available."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
        except Exception as e:
            print(f"⚠️ Tesseract not available: {e}")
            print("   Install: brew install tesseract")
            raise
    
    def extract_text(self, image: np.ndarray) -> List[TextBlock]:
        """
        Extract text blocks from image.
        
        Args:
            image: numpy array (H, W, 3) or PIL Image
            
        Returns:
            List of TextBlock objects
        """
        import pytesseract
        
        # Convert to PIL if needed
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Get detailed data
        data = pytesseract.image_to_data(
            image,
            lang=self.lang,
            output_type=pytesseract.Output.DICT
        )
        
        blocks = []
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            text = data['text'][i].strip()
            if not text:
                continue
            
            conf = int(data['conf'][i])
            if conf < 30:  # Skip low confidence
                continue
            
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            
            # Classify block type
            block_type = self._classify_text(text)
            
            blocks.append(TextBlock(
                text=text,
                bbox=(x, y, w, h),
                confidence=conf / 100.0,
                block_type=block_type
            ))
        
        return blocks
    
    def _classify_text(self, text: str) -> str:
        """
        Classify text block type based on heuristics.
        
        Args:
            text: Extracted text
            
        Returns:
            Block type: "speech", "sfx", "caption"
        """
        text = text.strip()
        
        # SFX: short, ALL CAPS, often with !?
        if len(text) <= 8 and text.isupper() and any(c in text for c in '!?*'):
            return "sfx"
        
        # Speech: contains quotes or typical speech patterns
        if text.startswith('"') or text.startswith('«') or text.startswith('—') or text.startswith('-'):
            return "speech"
        
        # Default to speech for now (most common in comics)
        return "speech"
    
    def merge_nearby_blocks(
        self,
        blocks: List[TextBlock],
        max_distance: int = 20
    ) -> List[TextBlock]:
        """
        Merge nearby text blocks (e.g., multi-line speech bubbles).
        
        Args:
            blocks: List of TextBlock
            max_distance: Maximum pixel distance to merge
            
        Returns:
            Merged blocks
        """
        if not blocks:
            return []
        
        # Sort by y position
        sorted_blocks = sorted(blocks, key=lambda b: b.bbox[1])
        
        merged = []
        current = sorted_blocks[0]
        
        for block in sorted_blocks[1:]:
            # Check vertical distance
            _, y1, _, h1 = current.bbox
            _, y2, _, _ = block.bbox
            
            if abs(y2 - (y1 + h1)) <= max_distance:
                # Merge
                x1, y1, w1, h1 = current.bbox
                x2, y2, w2, h2 = block.bbox
                
                new_x = min(x1, x2)
                new_y = min(y1, y2)
                new_w = max(x1 + w1, x2 + w2) - new_x
                new_h = max(y1 + h1, y2 + h2) - new_y
                
                current = TextBlock(
                    text=current.text + " " + block.text,
                    bbox=(new_x, new_y, new_w, new_h),
                    confidence=min(current.confidence, block.confidence),
                    block_type=current.block_type
                )
            else:
                merged.append(current)
                current = block
        
        merged.append(current)
        return merged
    
    def extract_panel_text(self, image: np.ndarray) -> str:
        """
        Extract and merge all text from a panel into single string.
        
        Args:
            image: Panel image
            
        Returns:
            Merged text string
        """
        blocks = self.extract_text(image)
        merged = self.merge_nearby_blocks(blocks)
        
        # Filter only speech and caption (skip SFX)
        speech_blocks = [b for b in merged if b.block_type in ("speech", "caption")]
        
        return " ".join(b.text for b in speech_blocks)


# Test
if __name__ == "__main__":
    print("OCR module loaded successfully")
    print("Tesseract + pytesseract required:")
    print("  brew install tesseract")
    print("  pip install pytesseract Pillow")
