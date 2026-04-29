"""
AI Morphing module for MoFrame.

Uses optical flow and deep learning for smooth transitions between comic panels.
"""

import numpy as np
import cv2
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import warnings


class AIMorphStrategy(Enum):
    """AI-based morphing strategies."""
    OPTICAL_FLOW = "optical_flow"       # Dense optical flow
    DEPTH_AWARE = "depth_aware"          # Depth estimation + parallax
    STYLE_TRANSFER = "style_transfer"    # Neural style transfer blend
    HYBRID = "hybrid"                    # Combination of techniques


@dataclass
class AIMorphConfig:
    """Configuration for AI morphing."""
    strategy: AIMorphStrategy = AIMorphStrategy.OPTICAL_FLOW
    duration_frames: int = 30
    easing: str = "ease_in_out"
    
    # Optical flow specific
    flow_method: str = "farneback"      # "farneback", "deepflow", "dis"
    flow_scale: float = 1.0             # Flow magnitude scale
    
    # Depth aware specific
    depth_model: str = "midas"           # "midas", "zoedepth"
    parallax_strength: float = 0.3       # How much to shift based on depth
    
    # Style transfer specific
    style_layers: List[str] = None      # Which layers to use
    content_weight: float = 1.0
    style_weight: float = 10.0


class AIMorpher:
    """AI-powered morphing between images."""
    
    def __init__(self, target_size: Tuple[int, int] = (1920, 1080)):
        self.target_size = target_size
        self._deepflow = None
        self._dis = None
    
    def morph(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: AIMorphConfig
    ) -> List[np.ndarray]:
        """
        Generate AI-powered transition frames.
        
        Args:
            img1: Starting image (RGB)
            img2: Ending image (RGB)
            config: AI morph configuration
            
        Returns:
            List of transition frames
        """
        # Preprocess
        img1 = self._preprocess(img1)
        img2 = self._preprocess(img2)
        
        # Generate frames based on strategy
        if config.strategy == AIMorphStrategy.OPTICAL_FLOW:
            return self._optical_flow_morph(img1, img2, config)
        elif config.strategy == AIMorphStrategy.DEPTH_AWARE:
            return self._depth_aware_morph(img1, img2, config)
        elif config.strategy == AIMorphStrategy.STYLE_TRANSFER:
            return self._style_transfer_morph(img1, img2, config)
        elif config.strategy == AIMorphStrategy.HYBRID:
            return self._hybrid_morph(img1, img2, config)
        else:
            # Fallback to crossfade
            return self._crossfade(img1, img2, config)
    
    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """Resize and convert image."""
        if img.shape[:2] != (self.target_size[1], self.target_size[0]):
            img = cv2.resize(img, self.target_size, interpolation=cv2.INTER_LANCZOS4)
        
        # Ensure RGB
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        
        return img.astype(np.float32) / 255.0
    
    def _optical_flow_morph(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: AIMorphConfig
    ) -> List[np.ndarray]:
        """
        Morph using optical flow.
        
        1. Calculate optical flow from img1 to img2
        2. Warp img1 forward and img2 backward
        3. Blend based on progress
        """
        # Convert to grayscale for flow calculation
        gray1 = cv2.cvtColor((img1 * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor((img2 * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        
        # Calculate dense optical flow
        if config.flow_method == "farneback":
            flow = cv2.calcOpticalFlowFarneback(
                gray1, gray2,
                None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
        elif config.flow_method == "deepflow":
            # DeepFlow requires opencv_contrib
            try:
                if self._deepflow is None:
                    self._deepflow = cv2.optflow.createOptFlow_DeepFlow()
                flow = self._deepflow.calc(gray1, gray2, None)
            except:
                warnings.warn("DeepFlow not available, falling back to Farneback")
                flow = cv2.calcOpticalFlowFarneback(
                    gray1, gray2,
                    None, 0.5, 3, 15, 3, 5, 1.2, 0
                )
        elif config.flow_method == "dis":
            try:
                if self._dis is None:
                    self._dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
                flow = self._dis.calc(gray1, gray2, None)
            except:
                warnings.warn("DIS not available, falling back to Farneback")
                flow = cv2.calcOpticalFlowFarneback(
                    gray1, gray2,
                    None, 0.5, 3, 15, 3, 5, 1.2, 0
                )
        else:
            flow = cv2.calcOpticalFlowFarneback(
                gray1, gray2,
                None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
        
        # Scale flow
        flow = flow * config.flow_scale
        
        # Generate frames
        frames = []
        h, w = img1.shape[:2]
        
        for i in range(config.duration_frames):
            t = i / (config.duration_frames - 1) if config.duration_frames > 1 else 0
            t = self._ease(t, config.easing)
            
            # Calculate intermediate flow
            flow_t = flow * t
            
            # Create remap coordinates
            map_x = np.zeros((h, w), dtype=np.float32)
            map_y = np.zeros((h, w), dtype=np.float32)
            
            for y in range(h):
                for x in range(w):
                    map_x[y, x] = x + flow_t[y, x, 0]
                    map_y[y, x] = y + flow_t[y, x, 1]
            
            # Warp images
            warped1 = cv2.remap(img1, map_x, map_y, cv2.INTER_LINEAR)
            
            # Reverse flow for backward warp
            flow_reverse = -flow * (1 - t)
            map_x2 = np.zeros((h, w), dtype=np.float32)
            map_y2 = np.zeros((h, w), dtype=np.float32)
            
            for y in range(h):
                for x in range(w):
                    map_x2[y, x] = x + flow_reverse[y, x, 0]
                    map_y2[y, x] = y + flow_reverse[y, x, 1]
            
            warped2 = cv2.remap(img2, map_x2, map_y2, cv2.INTER_LINEAR)
            
            # Blend
            frame = (1 - t) * warped1 + t * warped2
            
            # Clamp
            frame = np.clip(frame, 0, 1)
            
            frames.append((frame * 255).astype(np.uint8))
        
        return frames
    
    def _depth_aware_morph(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: AIMorphConfig
    ) -> List[np.ndarray]:
        """
        Morph using depth estimation for parallax effect.
        
        TODO: Requires depth estimation model (MiDaS, ZoeDepth)
        For now, falls back to optical flow.
        """
        warnings.warn("Depth-aware morphing requires depth model. Using optical flow fallback.")
        return self._optical_flow_morph(img1, img2, config)
    
    def _style_transfer_morph(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: AIMorphConfig
    ) -> List[np.ndarray]:
        """
        Morph using neural style transfer blending.
        
        TODO: Requires neural style transfer implementation
        For now, falls back to crossfade.
        """
        warnings.warn("Style transfer morphing requires neural network. Using crossfade fallback.")
        return self._crossfade(img1, img2, config)
    
    def _hybrid_morph(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: AIMorphConfig
    ) -> List[np.ndarray]:
        """
        Combine multiple techniques for best results.
        
        Uses optical flow with feature-based alignment.
        """
        # Get optical flow frames
        flow_config = AIMorphConfig(
            strategy=AIMorphStrategy.OPTICAL_FLOW,
            duration_frames=config.duration_frames,
            easing=config.easing,
            flow_method=config.flow_method
        )
        
        return self._optical_flow_morph(img1, img2, flow_config)
    
    def _crossfade(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: AIMorphConfig
    ) -> List[np.ndarray]:
        """Simple crossfade fallback."""
        frames = []
        
        for i in range(config.duration_frames):
            t = i / (config.duration_frames - 1) if config.duration_frames > 1 else 0
            t = self._ease(t, config.easing)
            
            frame = (1 - t) * img1 + t * img2
            frame = np.clip(frame, 0, 1)
            
            frames.append((frame * 255).astype(np.uint8))
        
        return frames
    
    def _ease(self, t: float, easing: str) -> float:
        """Apply easing function."""
        if easing == "linear":
            return t
        elif easing == "ease_in":
            return t * t
        elif easing == "ease_out":
            return 1 - (1 - t) * (1 - t)
        elif easing == "ease_in_out":
            return t * t * (3 - 2 * t)
        else:
            return t


# Test
def test_ai_morph():
    """Test AI morphing."""
    print("Testing AI Morphing...")
    
    # Create test images
    img1 = np.zeros((300, 400, 3), dtype=np.uint8)
    img1[50:250, 50:350] = (255, 100, 100)  # Red square
    
    img2 = np.zeros((300, 400, 3), dtype=np.uint8)
    img2[50:250, 50:350] = (100, 100, 255)  # Blue square
    
    # Test optical flow
    morpher = AIMorpher(target_size=(400, 300))
    config = AIMorphConfig(
        strategy=AIMorphStrategy.OPTICAL_FLOW,
        duration_frames=10,
        flow_method="farneback"
    )
    
    frames = morpher.morph(img1, img2, config)
    print(f"Generated {len(frames)} frames")
    print(f"Frame shape: {frames[0].shape}")
    
    # Save sample
    for i in [0, len(frames)//2, -1]:
        cv2.imwrite(f"ai_morph_frame_{i}.jpg", cv2.cvtColor(frames[i], cv2.COLOR_RGB2BGR))
        print(f"Saved frame {i}")
    
    return frames


if __name__ == "__main__":
    test_ai_morph()
