"""
Renderer module for MoFrame.
Assembles panels and transitions into final MP4 video.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Union, Callable
from dataclasses import dataclass
from enum import Enum
import warnings

import numpy as np
import cv2
from tqdm import tqdm

try:
    from moviepy.editor import ImageSequenceClip, AudioFileClip, CompositeAudioClip
    from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    warnings.warn("moviepy not installed. Video rendering will use OpenCV fallback.")

from core.panel_detector import Panel, PanelDetector
from .morpher import Morpher, MorphConfig, MorphStrategy


class VideoFormat(Enum):
    """Output video formats."""
    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    WEBM = "webm"


@dataclass
class RenderConfig:
    """Configuration for video rendering."""
    # Video settings
    fps: int = 24
    resolution: tuple = (1920, 1080)  # width, height
    bitrate: str = "8000k"
    codec: str = "libx264"
    
    # Panel timing
    panel_duration_frames: int = 48  # How long to show each panel
    
    # Transition settings
    transition_strategy: MorphStrategy = MorphStrategy.KEN_BURNS
    transition_duration_frames: int = 24
    transition_easing: str = "ease_in_out"
    
    # Audio (optional)
    audio_path: Optional[str] = None
    audio_fade_in: float = 0.5
    audio_fade_out: float = 0.5
    audio_volume: float = 1.0
    
    # Progress callback
    progress_callback: Optional[Callable[[float, str], None]] = None
    
    # Output
    output_path: Optional[str] = None


class Renderer:
    """
    Renders comic panels to video.
    
    Workflow:
    1. For each page: detect panels
    2. For each panel: show static image for panel_duration_frames
    3. Between panels: add transition for transition_duration_frames
    4. Export to MP4
    """
    
    def __init__(self, config: RenderConfig = None):
        """
        Initialize renderer.
        
        Args:
            config: Render configuration
        """
        self.config = config or RenderConfig()
        self.morpher = Morpher(target_size=self.config.resolution)
    
    def render(
        self,
        panels: List[Panel],
        output_path: Optional[str] = None,
        save_frames: bool = False,
        temp_dir: Optional[str] = None
    ) -> str:
        """
        Render panels to video.
        
        Args:
            panels: List of panels to render
            output_path: Where to save the video (overrides config)
            save_frames: Whether to save intermediate frames
            temp_dir: Directory for temporary frames
            
        Returns:
            Path to output video
        """
        if not panels:
            raise ValueError("No panels to render")
        
        output_path = output_path or self.config.output_path
        if not output_path:
            raise ValueError("No output path specified")
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create temp directory for frames if needed
        if save_frames or temp_dir:
            frames_dir = Path(temp_dir or tempfile.mkdtemp())
            frames_dir.mkdir(parents=True, exist_ok=True)
        else:
            frames_dir = None
        
        # Calculate total frames
        num_panels = len(panels)
        num_transitions = num_panels - 1
        total_frames = (
            num_panels * self.config.panel_duration_frames +
            num_transitions * self.config.transition_duration_frames
        )
        
        if self.config.progress_callback:
            self.config.progress_callback(0.0, "Starting render...")
        
        # Generate all frames
        all_frames = []
        frame_idx = 0
        
        for i, panel in enumerate(panels):
            # Report progress
            if self.config.progress_callback:
                progress = i / num_panels
                self.config.progress_callback(progress, f"Processing panel {i+1}/{num_panels}")
            
            # Add static panel frames
            panel_frames = self._generate_panel_frames(panel)
            all_frames.extend(panel_frames)
            
            # Save frames if requested
            if frames_dir:
                for frame in panel_frames:
                    cv2.imwrite(
                        str(frames_dir / f"frame_{frame_idx:06d}.jpg"),
                        cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    )
                    frame_idx += 1
            else:
                frame_idx += len(panel_frames)
            
            # Add transition to next panel (if not last)
            if i < num_panels - 1:
                next_panel = panels[i + 1]
                transition_frames = self._generate_transition(panel, next_panel)
                all_frames.extend(transition_frames)
                
                if frames_dir:
                    for frame in transition_frames:
                        cv2.imwrite(
                            str(frames_dir / f"frame_{frame_idx:06d}.jpg"),
                            cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        )
                        frame_idx += 1
                else:
                    frame_idx += len(transition_frames)
        
        if self.config.progress_callback:
            self.config.progress_callback(0.95, "Encoding video...")
        
        # Export to video
        if MOVIEPY_AVAILABLE:
            self._export_with_moviepy(all_frames, output_path)
        else:
            self._export_with_opencv(all_frames, output_path)
        
        if self.config.progress_callback:
            self.config.progress_callback(1.0, "Done!")
        
        return str(output_path)
    
    def _generate_panel_frames(self, panel: Panel) -> List[np.ndarray]:
        """Generate static frames for a panel (with subtle Ken Burns effect)."""
        frames = []
        
        # Extract panel image
        panel_img = panel.extract_from_original()
        
        # Resize to target resolution with letterbox
        base_frame = self.morpher._letterbox(panel_img)
        
        # Add subtle motion (slow zoom/pan) to prevent static image feeling
        if self.config.panel_duration_frames > 30:
            # Very subtle Ken Burns during panel display
            zoom_range = 0.05  # 5% zoom max
            pan_range = 10     # 10 pixels pan max
            
            for i in range(self.config.panel_duration_frames):
                t = i / self.config.panel_duration_frames
                
                # Subtle zoom oscillation
                zoom = 1.0 + zoom_range * np.sin(t * 2 * np.pi)
                
                # Subtle pan oscillation
                pan_x = int(pan_range * np.sin(t * 2 * np.pi))
                pan_y = int(pan_range * np.cos(t * 2 * np.pi))
                
                # Apply zoom
                zoomed = self._apply_zoom_and_pan(base_frame, zoom, pan_x, pan_y)
                frames.append(zoomed)
        else:
            # Just repeat the same frame
            for _ in range(self.config.panel_duration_frames):
                frames.append(base_frame.copy())
        
        return frames
    
    def _generate_transition(self, panel1: Panel, panel2: Panel) -> List[np.ndarray]:
        """Generate transition frames between two panels."""
        img1 = panel1.extract_from_original()
        img2 = panel2.extract_from_original()
        
        config = MorphConfig(
            strategy=self.config.transition_strategy,
            duration_frames=self.config.transition_duration_frames,
            easing=self.config.transition_easing
        )
        
        return self.morpher.morph(img1, img2, config)
    
    def _apply_zoom_and_pan(
        self,
        img: np.ndarray,
        zoom: float,
        pan_x: int,
        pan_y: int
    ) -> np.ndarray:
        """Apply zoom and pan to image."""
        # Clamp zoom to prevent oversized output
        zoom = max(1.0, zoom)
        
        if zoom == 1.0 and pan_x == 0 and pan_y == 0:
            return img.copy()
        
        h, w = img.shape[:2]
        
        # Calculate scaled size
        new_w = int(w / zoom)
        new_h = int(h / zoom)
        
        # Ensure we don't exceed original size
        new_w = min(new_w, w)
        new_h = min(new_h, h)
        
        # Resize
        scaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        # Create output canvas
        result = np.zeros_like(img)
        
        # Calculate position with pan
        y_offset = (h - new_h) // 2 + pan_y
        x_offset = (w - new_w) // 2 + pan_x
        
        # Clamp offsets
        y_offset = max(0, min(y_offset, h - new_h))
        x_offset = max(0, min(x_offset, w - new_w))
        
        # Place scaled image
        result[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = scaled
        
        return result
    
    def _export_with_moviepy(self, frames: List[np.ndarray], output_path: Path):
        """Export frames to video using moviepy."""
        # Convert frames to list of PIL Images
        from PIL import Image
        
        pil_frames = [Image.fromarray(frame) for frame in frames]
        
        # Create video clip
        clip = ImageSequenceClip(pil_frames, fps=self.config.fps)
        
        # Add audio if specified
        if self.config.audio_path and Path(self.config.audio_path).exists():
            try:
                audio = AudioFileClip(self.config.audio_path)
                
                # Loop audio if shorter than video
                video_duration = len(frames) / self.config.fps
                if audio.duration < video_duration:
                    n_loops = int(np.ceil(video_duration / audio.duration))
                    audio = CompositeAudioClip([audio] * n_loops)
                
                # Trim to video length
                audio = audio.subclip(0, video_duration)
                
                # Apply volume and fades
                audio = audio.volumex(self.config.audio_volume)
                audio = audio.audio_fadein(self.config.audio_fade_in)
                audio = audio.audio_fadeout(self.config.audio_fade_out)
                
                clip = clip.set_audio(audio)
            except Exception as e:
                warnings.warn(f"Could not add audio: {e}")
        
        # Write video
        clip.write_videofile(
            str(output_path),
            codec=self.config.codec,
            bitrate=self.config.bitrate,
            fps=self.config.fps,
            threads=4,
            logger=None  # Suppress moviepy output
        )
        
        clip.close()
    
    def _export_with_opencv(self, frames: List[np.ndarray], output_path: Path):
        """Export frames to video using OpenCV (fallback)."""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        writer = cv2.VideoWriter(
            str(output_path),
            fourcc,
            self.config.fps,
            self.config.resolution
        )
        
        if not writer.isOpened():
            raise RuntimeError(f"Failed to open video writer for {output_path}")
        
        try:
            for frame in frames:
                # Convert RGB to BGR for OpenCV
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                writer.write(bgr_frame)
        finally:
            writer.release()
    
    def preview_transition(
        self,
        panel1: Panel,
        panel2: Panel,
        num_samples: int = 5
    ) -> List[np.ndarray]:
        """
        Generate preview frames for a transition.
        
        Args:
            panel1: First panel
            panel2: Second panel
            num_samples: Number of sample frames to generate
            
        Returns:
            List of sample frames
        """
        frames = self._generate_transition(panel1, panel2)
        
        # Sample evenly
        indices = np.linspace(0, len(frames) - 1, num_samples, dtype=int)
        return [frames[i] for i in indices]


def render_comic(
    panels: List[Panel],
    output_path: str,
    fps: int = 24,
    resolution: tuple = (1920, 1080),
    panel_duration: float = 2.0,  # seconds
    transition_duration: float = 1.0,  # seconds
    transition_strategy: str = "ken_burns",
    audio_path: Optional[str] = None
) -> str:
    """
    Convenience function to render comic to video.
    
    Args:
        panels: List of panels
        output_path: Output video path
        fps: Frames per second
        resolution: Output resolution (width, height)
        panel_duration: How long to show each panel (seconds)
        transition_duration: Transition duration (seconds)
        transition_strategy: "crossfade", "ken_burns", "slide", "zoom", "feature_morph"
        audio_path: Optional background audio
        
    Returns:
        Path to output video
    """
    strategy_map = {
        "crossfade": MorphStrategy.CROSSFADE,
        "ken_burns": MorphStrategy.KEN_BURNS,
        "slide": MorphStrategy.SLIDE,
        "zoom": MorphStrategy.ZOOM,
        "feature_morph": MorphStrategy.FEATURE_MORPH
    }
    
    config = RenderConfig(
        fps=fps,
        resolution=resolution,
        panel_duration_frames=int(panel_duration * fps),
        transition_duration_frames=int(transition_duration * fps),
        transition_strategy=strategy_map.get(transition_strategy, MorphStrategy.KEN_BURNS),
        audio_path=audio_path,
        output_path=output_path
    )
    
    renderer = Renderer(config)
    return renderer.render(panels)


if __name__ == "__main__":
    # CLI test
    import sys
    from core.loader import load_comic
    from core.panel_detector import PanelDetector
    
    if len(sys.argv) < 3:
        print("Usage: python renderer.py <input_path> <output_path>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    print(f"\nLoading comic from: {input_path}")
    images = load_comic(input_path)
    print(f"Loaded {len(images)} pages")
    
    print(f"\nDetecting panels...")
    detector = PanelDetector()
    all_panels = []
    
    for i, img in enumerate(images):
        panels = detector.detect(img, page_index=i)
        all_panels.extend(panels)
        print(f"  Page {i+1}: {len(panels)} panels")
    
    print(f"\nTotal panels: {len(all_panels)}")
    
    print(f"\nRendering video to: {output_path}")
    config = RenderConfig(
        fps=24,
        resolution=(1280, 720),  # Lower res for testing
        panel_duration_frames=24,
        transition_duration_frames=12,
        output_path=output_path
    )
    
    def progress_callback(progress, message):
        print(f"[{progress*100:.0f}%] {message}")
    
    config.progress_callback = progress_callback
    
    renderer = Renderer(config)
    result = renderer.render(all_panels)
    
    print(f"\nDone! Video saved to: {result}")
