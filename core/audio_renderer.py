"""
Audio integration module for MoFrame renderer.
Adds TTS audio tracks to rendered video.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass

from .tts import TTSManager, TTSConfig, TTSSegment


@dataclass
class AudioRenderConfig:
    """Configuration for audio rendering."""
    enable_tts: bool = True
    tts_provider: str = "edge"
    tts_voice: str = "ru-RU-SvetlanaNeural"
    language: str = "ru"
    silence_between_panels_ms: int = 500
    background_music_path: Optional[str] = None
    background_music_volume: float = 0.3


class AudioRenderer:
    """Handles audio track creation and mixing with video."""
    
    def __init__(self, config: AudioRenderConfig):
        self.config = config
        self.tts_manager = None
        if config.enable_tts:
            tts_config = TTSConfig(
                provider=config.tts_provider,
                voice=config.tts_voice,
                language=config.language
            )
            self.tts_manager = TTSManager(tts_config)
    
    async def generate_audio_for_panels(
        self,
        panel_texts: List[str],
        panel_durations_ms: List[int]
    ) -> Optional[str]:
        """
        Generate TTS audio track for panels.
        
        Args:
            panel_texts: Text for each panel (empty string = no audio)
            panel_durations_ms: Duration each panel is shown in milliseconds
            
        Returns:
            Path to combined audio file, or None if no audio
        """
        if not self.tts_manager or not any(text.strip() for text in panel_texts):
            return None
        
        # Generate TTS for each panel
        segments = await self.tts_manager.generate_for_panels(panel_texts)
        
        # Combine into single track
        audio_path = self.tts_manager.combine_audio_tracks(
            segments,
            panel_durations_ms,
            silence_between_ms=self.config.silence_between_panels_ms
        )
        
        return audio_path
    
    def mix_audio_with_video(
        self,
        video_path: str,
        audio_path: str,
        output_path: str
    ) -> str:
        """
        Mix audio track with video.
        
        Args:
            video_path: Path to video file (no audio)
            audio_path: Path to audio file
            output_path: Path for output video
            
        Returns:
            Path to output video with audio
        """
        if not os.path.exists(audio_path):
            # No audio, just copy video
            import shutil
            shutil.copy(video_path, output_path)
            return output_path
        
        try:
            # Use ffmpeg to mix audio with video
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-shortest',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            return output_path
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            # ffmpeg not available, return video without audio
            import shutil
            shutil.copy(video_path, output_path)
            return output_path
    
    def add_background_music(
        self,
        video_path: str,
        music_path: str,
        output_path: str,
        music_volume: float = 0.3
    ) -> str:
        """
        Add background music to video.
        
        Args:
            video_path: Path to video with TTS audio
            music_path: Path to background music
            output_path: Path for output
            music_volume: Volume level (0.0 to 1.0)
            
        Returns:
            Path to output video with mixed audio
        """
        if not os.path.exists(music_path):
            return video_path
        
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', music_path,
                '-filter_complex',
                f'[1:a]volume={music_volume}[music];[0:a][music]amix=inputs=2:duration=first[aout]',
                '-map', '0:v',
                '-map', '[aout]',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            return output_path
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return video_path


# Convenience function for full pipeline
async def render_with_audio(
    video_path: str,
    panel_texts: List[str],
    panel_durations_ms: List[int],
    output_path: str,
    audio_config: Optional[AudioRenderConfig] = None
) -> str:
    """
    Full pipeline: generate TTS and mix with video.
    
    Args:
        video_path: Path to rendered video (no audio)
        panel_texts: Text for each panel
        panel_durations_ms: Duration each panel is shown
        output_path: Path for output video
        audio_config: Audio configuration
        
    Returns:
        Path to final video with audio
    """
    config = audio_config or AudioRenderConfig()
    renderer = AudioRenderer(config)
    
    # Generate TTS audio
    audio_path = await renderer.generate_audio_for_panels(
        panel_texts,
        panel_durations_ms
    )
    
    if not audio_path:
        # No TTS, just copy video
        import shutil
        shutil.copy(video_path, output_path)
        return output_path
    
    # Mix TTS with video
    video_with_tts = renderer.mix_audio_with_video(
        video_path,
        audio_path,
        output_path
    )
    
    # Add background music if configured
    if config.background_music_path:
        final_path = output_path.replace('.mp4', '_with_music.mp4')
        video_with_tts = renderer.add_background_music(
            video_with_tts,
            config.background_music_path,
            final_path,
            config.background_music_volume
        )
    
    return video_with_tts
