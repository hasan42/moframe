"""
Morpher module for MoFrame.
Creates smooth transitions between comic panels using various techniques.
"""

import numpy as np
import cv2
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import warnings


class MorphStrategy(Enum):
    """Available morphing strategies."""
    CROSSFADE = "crossfade"           # Simple alpha blend
    KEN_BURNS = "ken_burns"             # Pan and zoom
    FEATURE_MORPH = "feature_morph"     # Feature-based warping (for similar images)
    SLIDE = "slide"                     # Slide transition
    ZOOM = "zoom"                       # Zoom in/out


@dataclass
class MorphConfig:
    """Configuration for morphing."""
    strategy: MorphStrategy = MorphStrategy.CROSSFADE
    duration_frames: int = 24          # Frames at target FPS
    easing: str = "ease_in_out"         # ease_in, ease_out, ease_in_out, linear
    
    # Ken Burns specific
    ken_burns_zoom: float = 1.2         # Max zoom factor
    ken_burns_direction: str = "random" # "in", "out", "random"
    
    # Feature morph specific
    feature_method: str = "orb"         # "orb", "sift", "akaze"
    
    # Slide specific
    slide_direction: str = "left"       # "left", "right", "up", "down"


class Morpher:
    """
    Creates transitions between images.
    
    Supports multiple strategies:
    - CROSSFADE: Simple fade between images
    - KEN_BURNS: Slow zoom and pan (documentary style)
    - FEATURE_MORPH: Warps similar images using feature matching
    - SLIDE: Sliding transition
    - ZOOM: Zoom in/out transition
    """
    
    def __init__(self, target_size: Tuple[int, int] = (1920, 1080)):
        """
        Initialize morpher.
        
        Args:
            target_size: Output resolution (width, height)
        """
        self.target_size = target_size
        self.target_aspect = target_size[0] / target_size[1]
    
    def morph(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: MorphConfig
    ) -> List[np.ndarray]:
        """
        Generate transition frames between two images.
        
        Args:
            img1: Starting image (RGB)
            img2: Ending image (RGB)
            config: Morph configuration
            
        Returns:
            List of transition frames
        """
        # Preprocess images to target size
        img1_resized = self._letterbox(img1)
        img2_resized = self._letterbox(img2)
        
        if config.strategy == MorphStrategy.CROSSFADE:
            return self._crossfade(img1_resized, img2_resized, config)
        elif config.strategy == MorphStrategy.KEN_BURNS:
            return self._ken_burns(img1_resized, img2_resized, config)
        elif config.strategy == MorphStrategy.FEATURE_MORPH:
            return self._feature_morph(img1_resized, img2_resized, config)
        elif config.strategy == MorphStrategy.SLIDE:
            return self._slide(img1_resized, img2_resized, config)
        elif config.strategy == MorphStrategy.ZOOM:
            return self._zoom(img1_resized, img2_resized, config)
        else:
            raise ValueError(f"Unknown strategy: {config.strategy}")
    
    def _letterbox(self, img: np.ndarray) -> np.ndarray:
        """
        Resize image to target size preserving aspect ratio.
        Adds black bars if needed (letterbox/pillarbox).
        """
        h, w = img.shape[:2]
        img_aspect = w / h
        
        if img_aspect > self.target_aspect:
            # Image is wider - fit to width
            new_w = self.target_size[0]
            new_h = int(new_w / img_aspect)
        else:
            # Image is taller - fit to height
            new_h = self.target_size[1]
            new_w = int(new_h * img_aspect)
        
        # Resize
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        # Create letterbox canvas
        result = np.zeros((self.target_size[1], self.target_size[0], 3), dtype=np.uint8)
        
        # Center the image
        y_offset = (self.target_size[1] - new_h) // 2
        x_offset = (self.target_size[0] - new_w) // 2
        
        result[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
        
        return result
    
    def _ease(self, t: float, easing: str) -> float:
        """Apply easing function to time parameter."""
        if easing == "linear":
            return t
        elif easing == "ease_in":
            return t * t
        elif easing == "ease_out":
            return 1 - (1 - t) * (1 - t)
        elif easing == "ease_in_out":
            return 0.5 - 0.5 * np.cos(t * np.pi)
        else:
            return t
    
    def _crossfade(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: MorphConfig
    ) -> List[np.ndarray]:
        """Simple crossfade between images."""
        frames = []
        
        for i in range(config.duration_frames):
            t = i / (config.duration_frames - 1) if config.duration_frames > 1 else 0
            t = self._ease(t, config.easing)
            
            # Alpha blend
            frame = cv2.addWeighted(img1, 1 - t, img2, t, 0)
            frames.append(frame)
        
        return frames
    
    def _ken_burns(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: MorphConfig
    ) -> List[np.ndarray]:
        """
        Ken Burns effect - slow zoom and pan.
        First image zooms out, second zooms in (or vice versa).
        """
        frames = []
        
        # Determine zoom directions
        zoom1_start, zoom1_end = 1.0, 1.0
        zoom2_start, zoom2_end = 1.0, 1.0
        
        direction = config.ken_burns_direction
        if direction == "random":
            direction = np.random.choice(["in", "out"])
        
        if direction == "in":
            # Zoom in on first, then zoom out on second
            zoom1_start, zoom1_end = 1.0, config.ken_burns_zoom
            zoom2_start, zoom2_end = config.ken_burns_zoom, 1.0
        else:
            # Zoom out on first, then zoom in on second
            zoom1_start, zoom1_end = config.ken_burns_zoom, 1.0
            zoom2_start, zoom2_end = 1.0, config.ken_burns_zoom
        
        half_frames = config.duration_frames // 2
        
        # First half: zoom first image
        for i in range(half_frames):
            t = i / (half_frames - 1) if half_frames > 1 else 0
            t = self._ease(t, config.easing)
            
            zoom = zoom1_start + (zoom1_end - zoom1_start) * t
            frame = self._apply_zoom(img1, zoom)
            frames.append(frame)
        
        # Second half: zoom second image
        for i in range(config.duration_frames - half_frames):
            t = i / (config.duration_frames - half_frames - 1) if (config.duration_frames - half_frames) > 1 else 0
            t = self._ease(t, config.easing)
            
            zoom = zoom2_start + (zoom2_end - zoom2_start) * t
            frame = self._apply_zoom(img2, zoom)
            frames.append(frame)
        
        return frames
    
    def _apply_zoom(self, img: np.ndarray, zoom: float) -> np.ndarray:
        """Apply zoom to image, keeping centered."""
        if zoom == 1.0:
            return img.copy()
        
        h, w = img.shape[:2]
        
        # Calculate scaled size
        new_w = int(w / zoom)
        new_h = int(h / zoom)
        
        # Resize down
        scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        # Create full-size canvas and center the scaled image
        result = np.zeros_like(img)
        y_offset = (h - new_h) // 2
        x_offset = (w - new_w) // 2
        
        result[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = scaled
        
        return result
    
    def _slide(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: MorphConfig
    ) -> List[np.ndarray]:
        """Slide transition."""
        frames = []
        h, w = img1.shape[:2]
        
        direction = config.slide_direction
        
        for i in range(config.duration_frames):
            t = i / (config.duration_frames - 1) if config.duration_frames > 1 else 0
            t = self._ease(t, config.easing)
            
            frame = np.zeros_like(img1)
            
            if direction == "left":
                offset = int(w * t)
                frame[:, :w - offset] = img1[:, offset:]
                frame[:, w - offset:] = img2[:, :offset]
            elif direction == "right":
                offset = int(w * t)
                frame[:, offset:] = img1[:, :w - offset]
                frame[:, :offset] = img2[:, w - offset:]
            elif direction == "up":
                offset = int(h * t)
                frame[:h - offset, :] = img1[offset:, :]
                frame[h - offset:, :] = img2[:offset, :]
            elif direction == "down":
                offset = int(h * t)
                frame[offset:, :] = img1[:h - offset, :]
                frame[:offset, :] = img2[h - offset:, :]
            
            frames.append(frame)
        
        return frames
    
    def _zoom(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: MorphConfig
    ) -> List[np.ndarray]:
        """Zoom transition - first shrinks, second grows."""
        frames = []
        half_frames = config.duration_frames // 2
        
        for i in range(half_frames):
            t = i / (half_frames - 1) if half_frames > 1 else 0
            t = self._ease(t, config.easing)
            
            scale = 1.0 - t * 0.5  # Shrink to 50%
            frame = self._apply_zoom(img1, 1.0 / scale if scale > 0 else 1.0)
            frames.append(frame)
        
        for i in range(config.duration_frames - half_frames):
            t = i / (config.duration_frames - half_frames - 1) if (config.duration_frames - half_frames) > 1 else 0
            t = self._ease(t, config.easing)
            
            scale = 0.5 + t * 0.5  # Grow from 50% to 100%
            frame = self._apply_zoom(img2, scale)
            frames.append(frame)
        
        return frames
    
    def _feature_morph(
        self,
        img1: np.ndarray,
        img2: np.ndarray,
        config: MorphConfig
    ) -> List[np.ndarray]:
        """
        Feature-based morphing for similar images.
        Falls back to crossfade if not enough features found.
        """
        try:
            # Detect features
            if config.feature_method == "orb":
                detector = cv2.ORB_create(nfeatures=500)
            elif config.feature_method == "sift":
                detector = cv2.SIFT_create()
            elif config.feature_method == "akaze":
                detector = cv2.AKAZE_create()
            else:
                detector = cv2.ORB_create(nfeatures=500)
            
            # Convert to grayscale
            gray1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)
            
            # Find keypoints and descriptors
            kp1, des1 = detector.detectAndCompute(gray1, None)
            kp2, des2 = detector.detectAndCompute(gray2, None)
            
            if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
                # Not enough features, fall back to crossfade
                return self._crossfade(img1, img2, config)
            
            # Match features
            matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = matcher.match(des1, des2)
            
            if len(matches) < 10:
                return self._crossfade(img1, img2, config)
            
            # Sort by distance and take best matches
            matches = sorted(matches, key=lambda x: x.distance)
            matches = matches[:min(50, len(matches))]
            
            # Get matched points
            src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
            
            # Calculate homography
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            
            if H is None:
                return self._crossfade(img1, img2, config)
            
            # Generate morph frames using homography interpolation
            frames = []
            h, w = img1.shape[:2]
            
            for i in range(config.duration_frames):
                t = i / (config.duration_frames - 1) if config.duration_frames > 1 else 0
                t = self._ease(t, config.easing)
                
                # Interpolate homography
                H_interp = np.eye(3) * (1 - t) + H * t
                
                # Warp first image
                warped = cv2.warpPerspective(img1, H_interp, (w, h))
                
                # Blend with second image
                frame = cv2.addWeighted(warped, 1 - t, img2, t, 0)
                frames.append(frame)
            
            return frames
            
        except Exception as e:
            warnings.warn(f"Feature morph failed: {e}, using crossfade")
            return self._crossfade(img1, img2, config)


def morph_images(
    img1: np.ndarray,
    img2: np.ndarray,
    strategy: str = "crossfade",
    duration_frames: int = 24,
    target_size: Tuple[int, int] = (1920, 1080),
    **kwargs
) -> List[np.ndarray]:
    """
    Convenience function for morphing.
    
    Args:
        img1: Starting image
        img2: Ending image
        strategy: "crossfade", "ken_burns", "feature_morph", "slide", "zoom"
        duration_frames: Number of frames to generate
        target_size: Output resolution
        **kwargs: Additional config options
        
    Returns:
        List of transition frames
    """
    strategy_map = {
        "crossfade": MorphStrategy.CROSSFADE,
        "ken_burns": MorphStrategy.KEN_BURNS,
        "feature_morph": MorphStrategy.FEATURE_MORPH,
        "slide": MorphStrategy.SLIDE,
        "zoom": MorphStrategy.ZOOM
    }
    
    config = MorphConfig(
        strategy=strategy_map.get(strategy, MorphStrategy.CROSSFADE),
        duration_frames=duration_frames,
        **kwargs
    )
    
    morpher = Morpher(target_size=target_size)
    return morpher.morph(img1, img2, config)


if __name__ == "__main__":
    # CLI test
    import sys
    from loader import load_comic
    
    if len(sys.argv) < 3:
        print("Usage: python morpher.py <image1> <image2> [strategy]")
        print("Strategies: crossfade, ken_burns, feature_morph, slide, zoom")
        sys.exit(1)
    
    img1_path = sys.argv[1]
    img2_path = sys.argv[2]
    strategy = sys.argv[3] if len(sys.argv) > 3 else "crossfade"
    
    print(f"\nLoading images...")
    img1 = load_comic(img1_path)[0]
    img2 = load_comic(img2_path)[0]
    
    print(f"Image 1: {img1.shape}")
    print(f"Image 2: {img2.shape}")
    
    print(f"\nMorphing with strategy: {strategy}")
    morpher = Morpher(target_size=(1920, 1080))
    config = MorphConfig(
        strategy=MorphStrategy[strategy.upper()],
        duration_frames=30
    )
    
    frames = morpher.morph(img1, img2, config)
    print(f"Generated {len(frames)} frames")
    
    # Save sample frames
    for i in [0, len(frames)//2, -1]:
        output_path = f"morph_frame_{i}.jpg"
        cv2.imwrite(output_path, cv2.cvtColor(frames[i], cv2.COLOR_RGB2BGR))
        print(f"Saved frame {i} to: {output_path}")
