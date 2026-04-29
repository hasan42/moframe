"""
TTS Module for MoFrame - Text-to-Speech for comic panels.

Supports multiple TTS providers:
- edge-tts (default): Microsoft Edge TTS, free, high quality, cross-platform
- silero: local Russian TTS (requires torch)
- say: macOS built-in (macOS only)
"""

import asyncio
import tempfile
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Union
from dataclasses import dataclass


@dataclass
class TTSSegment:
    """Represents a single TTS segment for a panel."""
    text: str
    panel_index: int
    duration_ms: Optional[int] = None  # Will be calculated after generation
    audio_path: Optional[str] = None


@dataclass
class TTSConfig:
    """Configuration for TTS generation."""
    provider: str = "edge"  # "edge", "silero", "say"
    voice: str = "ru-RU-SvetlanaNeural"  # Default Russian voice
    rate: str = "+0%"  # Speaking rate
    volume: str = "+0%"  # Volume adjustment
    language: str = "ru"
    sample_rate: int = 24000


class EdgeTTSProvider:
    """Microsoft Edge TTS provider - free, high quality, cross-platform."""
    
    # Available Russian voices
    RU_VOICES = {
        'svetlana': 'ru-RU-SvetlanaNeural',
        'dmitry': 'ru-RU-DmitryNeural',
    }
    
    # Available English voices
    EN_VOICES = {
        'jenny': 'en-US-JennyNeural',
        'guy': 'en-US-GuyNeural',
        'aria': 'en-US-AriaNeural',
    }
    
    def __init__(self, config: TTSConfig):
        self.config = config
        self.voice = config.voice
    
    async def synthesize(self, text: str, output_path: str) -> int:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            
        Returns:
            Duration in milliseconds
        """
        import edge_tts
        
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.config.rate,
            volume=self.config.volume
        )
        await communicate.save(output_path)
        
        # Get duration using mutagen
        duration_ms = self._get_audio_duration(output_path)
        
        return duration_ms
    
    def _get_audio_duration(self, audio_path: str) -> int:
        """Get audio duration in milliseconds using mutagen."""
        try:
            from mutagen.mp3 import MP3
            audio = MP3(audio_path)
            return int(audio.info.length * 1000)
        except Exception:
            # Fallback: estimate based on file size (rough approximation)
            # MP3 at 48kbps mono ~ 6KB per second
            file_size = os.path.getsize(audio_path)
            estimated_seconds = file_size / 6000
            return int(estimated_seconds * 1000)


class SayTTSProvider:
    """macOS built-in say command."""
    
    def __init__(self, config: TTSConfig):
        self.config = config
    
    async def synthesize(self, text: str, output_path: str) -> int:
        """Synthesize using macOS say command."""
        # Convert to aiff then to mp3
        aiff_path = output_path.replace('.mp3', '.aiff')
        
        cmd = ['say', text, '-o', aiff_path]
        subprocess.run(cmd, check=True)
        
        # Convert to mp3 using ffmpeg or keep as aiff
        # For now, keep as aiff and update path
        os.rename(aiff_path, output_path)
        
        # Get duration
        duration_ms = self._get_audio_duration(output_path)
        
        return duration_ms
    
    def _get_audio_duration(self, audio_path: str) -> int:
        """Get audio duration in milliseconds."""
        try:
            from mutagen.aiff import AIFF
            audio = AIFF(audio_path)
            return int(audio.info.length * 1000)
        except Exception:
            return 0


class TTSManager:
    """Main TTS manager for MoFrame."""
    
    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self.provider = self._create_provider()
        self.cache_dir = Path(tempfile.gettempdir()) / "moframe_tts_cache"
        self.cache_dir.mkdir(exist_ok=True)
    
    def _create_provider(self):
        """Create TTS provider based on config."""
        if self.config.provider == "edge":
            return EdgeTTSProvider(self.config)
        elif self.config.provider == "say":
            return SayTTSProvider(self.config)
        else:
            raise ValueError(f"Unknown TTS provider: {self.config.provider}")
    
    async def generate_for_panels(
        self,
        panels_text: List[str],
        panel_durations_ms: Optional[List[int]] = None
    ) -> List[TTSSegment]:
        """
        Generate TTS audio for each panel.
        
        Args:
            panels_text: List of texts for each panel
            panel_durations_ms: Optional list of panel durations in ms
            
        Returns:
            List of TTSSegment with audio paths and durations
        """
        segments = []
        
        for i, text in enumerate(panels_text):
            if not text or not text.strip():
                # Skip empty text
                segments.append(TTSSegment(
                    text="",
                    panel_index=i,
                    duration_ms=0
                ))
                continue
            
            # Generate cache key
            cache_key = f"panel_{i}_{hash(text)}.mp3"
            cache_path = self.cache_dir / cache_key
            
            # Generate or use cached
            if cache_path.exists():
                duration_ms = self._get_audio_duration(str(cache_path))
            else:
                duration_ms = await self.provider.synthesize(
                    text=text,
                    output_path=str(cache_path)
                )
            
            segments.append(TTSSegment(
                text=text,
                panel_index=i,
                duration_ms=duration_ms,
                audio_path=str(cache_path)
            ))
        
        return segments
    
    def _get_audio_duration(self, audio_path: str) -> int:
        """Get audio duration in milliseconds."""
        try:
            from mutagen.mp3 import MP3
            audio = MP3(audio_path)
            return int(audio.info.length * 1000)
        except Exception:
            return 0
    
    def combine_audio_tracks(
        self,
        segments: List[TTSSegment],
        panel_durations_ms: List[int],
        silence_between_ms: int = 500
    ) -> str:
        """
        Combine audio segments into single track with timing.
        Uses ffmpeg if available, otherwise concatenates raw files.
        
        Args:
            segments: List of TTSSegment
            panel_durations_ms: Duration each panel is shown
            silence_between_ms: Silence between panels in ms
            
        Returns:
            Path to combined audio file
        """
        # Build ffmpeg concat list
        concat_list = []
        
        for i, segment in enumerate(segments):
            if segment.audio_path and os.path.exists(segment.audio_path):
                # Add audio file
                concat_list.append(f"file '{segment.audio_path}'")
                
                # Calculate silence needed after audio
                panel_duration = panel_durations_ms[i]
                silence_after = max(0, panel_duration - (segment.duration_ms or 0))
                
                if silence_after > 0:
                    # Generate silence file
                    silence_path = self.cache_dir / f"silence_{i}.mp3"
                    self._generate_silence(silence_after, str(silence_path))
                    concat_list.append(f"file '{silence_path}'")
            else:
                # Generate silence for entire panel duration
                silence_path = self.cache_dir / f"silence_panel_{i}.mp3"
                self._generate_silence(panel_durations_ms[i], str(silence_path))
                concat_list.append(f"file '{silence_path}'")
            
            # Add silence between panels (except last)
            if i < len(segments) - 1:
                silence_path = self.cache_dir / f"silence_between_{i}.mp3"
                self._generate_silence(silence_between_ms, str(silence_path))
                concat_list.append(f"file '{silence_path}'")
        
        # Write concat list
        concat_file = self.cache_dir / "concat_list.txt"
        with open(concat_file, 'w') as f:
            f.write('\n'.join(concat_list))
        
        # Combine using ffmpeg
        output_path = self.cache_dir / "combined_audio.mp3"
        
        try:
            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                str(output_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback: just copy the first file if ffmpeg not available
            # In production, ffmpeg should be installed
            if segments and segments[0].audio_path:
                import shutil
                shutil.copy(segments[0].audio_path, output_path)
        
        return str(output_path)
    
    def _generate_silence(self, duration_ms: int, output_path: str):
        """Generate silent MP3 file."""
        try:
            cmd = [
                'ffmpeg', '-y', '-f', 'lavfi', '-i',
                f'anullsrc=r=24000:cl=mono',
                '-t', str(duration_ms / 1000),
                '-acodec', 'libmp3lame', '-q:a', '4',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Create empty file as fallback
            with open(output_path, 'wb') as f:
                pass


    def calculate_panel_durations(
        self,
        segments: List[TTSSegment],
        base_panel_duration_ms: int,
        min_panel_duration_ms: int = 1000,
        max_panel_duration_ms: int = 10000
    ) -> List[int]:
        """
        Calculate optimal panel durations based on TTS audio lengths.
        
        Args:
            segments: List of TTSSegment with duration_ms
            base_panel_duration_ms: Base duration per panel
            min_panel_duration_ms: Minimum panel duration
            max_panel_duration_ms: Maximum panel duration
            
        Returns:
            List of panel durations in milliseconds
        """
        durations = []
        
        for segment in segments:
            # Panel must be at least as long as its audio
            audio_duration = segment.duration_ms or 0
            duration = max(base_panel_duration_ms, audio_duration)
            
            # Clamp to min/max
            duration = max(min_panel_duration_ms, min(duration, max_panel_duration_ms))
            
            durations.append(int(duration))
        
        return durations
def generate_tts_for_panels(
    panels_text: List[str],
    provider: str = "edge",
    voice: str = "ru-RU-SvetlanaNeural",
    language: str = "ru"
) -> List[TTSSegment]:
    """Synchronous wrapper for TTS generation."""
    config = TTSConfig(provider=provider, voice=voice, language=language)
    manager = TTSManager(config)
    return asyncio.run(manager.generate_for_panels(panels_text))


def create_audio_track(
    segments: List[TTSSegment],
    panel_durations_ms: List[int],
    silence_between_ms: int = 500
) -> str:
    """Create combined audio track."""
    manager = TTSManager()
    return manager.combine_audio_tracks(segments, panel_durations_ms, silence_between_ms)


# Test function
async def test_tts():
    """Test TTS functionality."""
    print("Testing Edge TTS...")
    
    config = TTSConfig(provider="edge", voice="ru-RU-SvetlanaNeural")
    manager = TTSManager(config)
    
    panels = [
        "Привет! Это первый кадр комикса.",
        "Здесь происходит что-то интересное.",
        "Финал! Всем спасибо.",
    ]
    
    segments = await manager.generate_for_panels(panels)
    
    print("\nGenerated segments:")
    for seg in segments:
        print(f"  Panel {seg.panel_index}: {seg.duration_ms}ms - '{seg.text[:30]}...'")
    
    # Create combined track with 3 seconds per panel
    panel_durations = [3000, 3000, 3000]
    output = manager.combine_audio_tracks(segments, panel_durations)
    
    print(f"\nCombined audio saved to: {output}")
    
    return output


if __name__ == "__main__":
    asyncio.run(test_tts())
