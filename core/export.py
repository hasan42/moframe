"""
Export utilities for MoFrame.
Supports multiple output formats: MP4, WebM, GIF, APNG.
"""

import numpy as np
from PIL import Image
import cv2
from pathlib import Path
from typing import List, Optional, Tuple
import warnings


def export_as_gif(
    frames: List[np.ndarray],
    output_path: str,
    fps: int = 24,
    loop: int = 0,
    optimize: bool = True
) -> str:
    """
    Export frames as animated GIF.
    
    Args:
        frames: List of RGB frames
        output_path: Output file path
        fps: Frames per second
        loop: Number of loops (0 = infinite)
        optimize: Optimize palette
        
    Returns:
        Path to output file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to PIL Images
    images = []
    for frame in frames:
        # Ensure uint8
        if frame.dtype != np.uint8:
            frame = (frame * 255).astype(np.uint8)
        img = Image.fromarray(frame)
        
        # Convert to palette mode for smaller file size
        if optimize:
            img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
        
        images.append(img)
    
    # Calculate duration per frame in milliseconds
    duration_ms = int(1000 / fps)
    
    # Save as GIF
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=loop,
        optimize=optimize
    )
    
    return str(output_path)


def export_as_apng(
    frames: List[np.ndarray],
    output_path: str,
    fps: int = 24,
    loop: int = 0,
    compress_level: int = 6
) -> str:
    """
    Export frames as animated PNG (APNG).
    
    Args:
        frames: List of RGB frames
        output_path: Output file path
        fps: Frames per second
        loop: Number of loops (0 = infinite)
        compress_level: PNG compression (0-9)
        
    Returns:
        Path to output file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to PIL Images
    images = []
    for frame in frames:
        if frame.dtype != np.uint8:
            frame = (frame * 255).astype(np.uint8)
        img = Image.fromarray(frame)
        images.append(img)
    
    # Calculate duration per frame in milliseconds
    duration_ms = int(1000 / fps)
    
    # Save as APNG
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=loop,
        compress_level=compress_level,
        format='PNG'
    )
    
    return str(output_path)


def export_as_webm(
    frames: List[np.ndarray],
    output_path: str,
    fps: int = 24,
    quality: int = 80,
    audio_path: Optional[str] = None
) -> str:
    """
    Export frames as WebM video.
    
    Uses ffmpeg if available, otherwise falls back to OpenCV.
    
    Args:
        frames: List of RGB frames
        output_path: Output file path
        fps: Frames per second
        quality: Quality (0-100)
        audio_path: Optional audio file to mix
        
    Returns:
        Path to output file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Try ffmpeg first (better quality)
    try:
        import subprocess
        import tempfile
        
        # Save frames to temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Save frames as images
            for i, frame in enumerate(frames):
                if frame.dtype != np.uint8:
                    frame = (frame * 255).astype(np.uint8)
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                cv2.imwrite(str(tmpdir / f"frame_{i:06d}.png"), frame_bgr)
            
            # Build ffmpeg command
            cmd = [
                'ffmpeg', '-y',
                '-framerate', str(fps),
                '-i', str(tmpdir / 'frame_%06d.png'),
                '-c:v', 'libvpx-vp9',
                '-b:v', '0',
                '-crf', str(int((100 - quality) / 5)),
                '-pix_fmt', 'yuv420p',
            ]
            
            # Add audio if provided
            if audio_path and Path(audio_path).exists():
                cmd.extend(['-i', audio_path, '-c:a', 'libopus', '-b:a', '128k'])
            
            cmd.append(str(output_path))
            
            # Run ffmpeg
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return str(output_path)
            else:
                warnings.warn(f"ffmpeg failed: {result.stderr}. Using OpenCV fallback.")
    
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Fallback: OpenCV with VP8 codec
    fourcc = cv2.VideoWriter_fourcc(*'VP80')
    writer = cv2.VideoWriter(
        str(output_path),
        fourcc,
        fps,
        (frames[0].shape[1], frames[0].shape[0])
    )
    
    if not writer.isOpened():
        # Fallback to MP4 if WebM not supported
        warnings.warn("WebM codec not available. Falling back to MP4.")
        output_path = output_path.with_suffix('.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(
            str(output_path),
            fourcc,
            fps,
            (frames[0].shape[1], frames[0].shape[0])
        )
    
    try:
        for frame in frames:
            if frame.dtype != np.uint8:
                frame = (frame * 255).astype(np.uint8)
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            writer.write(bgr_frame)
    finally:
        writer.release()
    
    return str(output_path)


def export_frames(
    frames: List[np.ndarray],
    output_path: str,
    fps: int = 24,
    audio_path: Optional[str] = None,
    format: str = "mp4"
) -> str:
    """
    Export frames to any supported format.
    
    Args:
        frames: List of RGB frames
        output_path: Output file path
        fps: Frames per second
        audio_path: Optional audio file
        format: Output format (mp4, webm, gif, apng)
        
    Returns:
        Path to output file
    """
    output_path = Path(output_path)
    
    if format.lower() == 'gif':
        return export_as_gif(frames, output_path, fps)
    elif format.lower() == 'apng':
        return export_as_apng(frames, output_path, fps)
    elif format.lower() == 'webm':
        return export_as_webm(frames, output_path, fps, audio_path=audio_path)
    else:
        # Default: use OpenCV for MP4/AVI/MOV
        # Ensure output has valid extension
        if format.lower() not in ('mp4', 'avi', 'mov'):
            format = 'mp4'
            output_path = output_path.with_suffix('.mp4')
        
        fourcc_map = {
            'mp4': 'mp4v',
            'avi': 'XVID',
            'mov': 'mp4v',
        }
        
        fourcc = cv2.VideoWriter_fourcc(*fourcc_map.get(format.lower(), 'mp4v'))
        
        writer = cv2.VideoWriter(
            str(output_path),
            fourcc,
            fps,
            (frames[0].shape[1], frames[0].shape[0])
        )
        
        try:
            for frame in frames:
                if frame.dtype != np.uint8:
                    frame = (frame * 255).astype(np.uint8)
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                writer.write(bgr_frame)
        finally:
            writer.release()
        
        return str(output_path)


# Test
def test_export():
    """Test export functions."""
    print("Testing export utilities...")
    
    # Create test frames
    frames = []
    for i in range(10):
        frame = np.zeros((200, 300, 3), dtype=np.uint8)
        frame[50:150, 50:250] = (i * 25, 100, 200)
        frames.append(frame)
    
    # Test GIF
    print("Testing GIF export...")
    export_as_gif(frames, '/tmp/test_export.gif', fps=5)
    print(f"  GIF: {Path('/tmp/test_export.gif').stat().st_size} bytes")
    
    # Test APNG
    print("Testing APNG export...")
    export_as_apng(frames, '/tmp/test_export.apng', fps=5)
    print(f"  APNG: {Path('/tmp/test_export.apng').stat().st_size} bytes")
    
    # Test WebM
    print("Testing WebM export...")
    try:
        export_as_webm(frames, '/tmp/test_export.webm', fps=5)
        print(f"  WebM: {Path('/tmp/test_export.webm').stat().st_size} bytes")
    except Exception as e:
        print(f"  WebM failed: {e}")
    
    print("Done!")


if __name__ == "__main__":
    test_export()
