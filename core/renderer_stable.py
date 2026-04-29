"""
Стабильный рендерер с retry и graceful degradation.
Обёртка над основным Renderer.
"""

import os
import tempfile
import time
import warnings
from pathlib import Path
from typing import List, Optional

from core.renderer import Renderer, RenderConfig
from core.panel_detector import Panel


class StableRenderer(Renderer):
    """Renderer с retry логикой и graceful degradation."""
    
    def render(
        self,
        panels: List[Panel],
        output_path: Optional[str] = None,
        save_frames: bool = False,
        temp_dir: Optional[str] = None,
        panel_texts: Optional[List[str]] = None,
        max_retries: int = 2,
        fallback_on_error: bool = True
    ) -> str:
        """
        Render panels to video with retry logic.
        
        Args:
            panels: List of panels to render
            output_path: Where to save the video
            save_frames: Whether to save intermediate frames
            temp_dir: Directory for temporary frames
            panel_texts: Optional texts for TTS
            max_retries: Number of retries on failure
            fallback_on_error: If True, render without audio on audio errors
            
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
        
        # Try with TTS first
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return self._render_with_cleanup(
                    panels, output_path, save_frames, temp_dir, panel_texts
                )
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 0.5 * (attempt + 1)
                    warnings.warn(
                        f"Render attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    warnings.warn(
                        f"Render failed after {max_retries + 1} attempts: {e}"
                    )
        
        # If fallback enabled and error was with audio, try without audio
        if fallback_on_error and last_error:
            error_msg = str(last_error).lower()
            if any(x in error_msg for x in ['audio', 'tts', 'sound', 'permission']):
                warnings.warn(
                    "Audio/TTS failed. Trying render without audio..."
                )
                try:
                    # Save original TTS state
                    original_tts = self.config.tts_enabled
                    original_audio = self.config.audio_path
                    
                    # Disable audio
                    self.config.tts_enabled = False
                    self.config.audio_path = None
                    
                    result = self._render_with_cleanup(
                        panels, output_path, save_frames, temp_dir, None
                    )
                    
                    # Restore settings
                    self.config.tts_enabled = original_tts
                    self.config.audio_path = original_audio
                    
                    return result
                except Exception as e2:
                    warnings.warn(f"Fallback render also failed: {e2}")
        
        raise RuntimeError(
            f"Render failed after {max_retries + 1} attempts: {last_error}"
        )
    
    def _render_with_cleanup(
        self,
        panels: List[Panel],
        output_path: Path,
        save_frames: bool = False,
        temp_dir: Optional[str] = None,
        panel_texts: Optional[List[str]] = None
    ) -> str:
        """Render with guaranteed cleanup."""
        import shutil
        
        # Create temp directory
        if save_frames or temp_dir:
            frames_dir = Path(temp_dir or tempfile.mkdtemp(prefix='moframe_'))
            frames_dir.mkdir(parents=True, exist_ok=True)
        else:
            frames_dir = None
        
        # Create temp file for TTS audio
        tts_temp = None
        
        try:
            # Use parent's render logic
            result = super().render(
                panels=panels,
                output_path=str(output_path),
                save_frames=save_frames,
                temp_dir=str(frames_dir) if frames_dir else None,
                panel_texts=panel_texts
            )
            return result
        finally:
            # Cleanup
            if frames_dir and not save_frames:
                shutil.rmtree(frames_dir, ignore_errors=True)


def render_comic_stable(
    panels: List[Panel],
    output_path: str,
    fps: int = 24,
    resolution: tuple = (1920, 1080),
    panel_duration: float = 2.0,
    transition_duration: float = 1.0,
    transition_strategy: str = "ken_burns",
    audio_path: Optional[str] = None,
    tts_enabled: bool = False,
    tts_provider: str = "edge",
    tts_voice: str = "ru-RU-SvetlanaNeural",
    panel_texts: Optional[List[str]] = None,
    max_retries: int = 2,
) -> str:
    """
    Convenience function for stable rendering.
    
    Args:
        panels: List of panels
        output_path: Output video path
        fps: Frames per second
        resolution: Output resolution
        panel_duration: How long to show each panel (seconds)
        transition_duration: Transition duration (seconds)
        transition_strategy: "crossfade", "ken_burns", "slide", "zoom"
        audio_path: Optional background audio
        tts_enabled: Whether to use TTS
        tts_provider: TTS provider ("edge", "google", "elevenlabs")
        tts_voice: Voice ID
        panel_texts: Texts for TTS
        max_retries: Number of retries on failure
        
    Returns:
        Path to output video
    """
    from .morpher import MorphStrategy
    
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
        tts_enabled=tts_enabled,
        tts_provider=tts_provider,
        tts_voice=tts_voice,
        output_path=output_path
    )
    
    renderer = StableRenderer(config)
    return renderer.render(
        panels=panels,
        output_path=output_path,
        panel_texts=panel_texts,
        max_retries=max_retries
    )
