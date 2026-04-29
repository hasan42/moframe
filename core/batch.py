"""Batch processing module for MoFrame.

Handles multiple comic files in a queue with progress tracking.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum
import time
import json

import numpy as np

from core.loader import load_comic
from core.panel_detector import PanelDetector
from core.renderer import Renderer, RenderConfig
from core.morpher import MorphStrategy


class BatchStatus(Enum):
    """Status of a batch job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BatchItem:
    """Single item in a batch job."""
    input_path: str
    output_path: str
    status: BatchStatus = BatchStatus.PENDING
    error: Optional[str] = None
    progress: float = 0.0
    panel_count: int = 0
    panels: Optional[List] = None  # Will be Panel objects


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    # Video settings (passed to RenderConfig)
    fps: int = 24
    resolution: tuple = (1920, 1080)
    panel_duration: float = 2.0
    transition_duration: float = 1.0
    transition_strategy: MorphStrategy = MorphStrategy.KEN_BURNS
    
    # Audio
    audio_path: Optional[str] = None
    audio_volume: float = 1.0
    
    # TTS
    tts_enabled: bool = False
    tts_provider: str = "edge"
    tts_voice: str = "ru-RU-SvetlanaNeural"
    
    # Output
    output_dir: str = "output"
    output_suffix: str = ""
    
    # Processing
    skip_existing: bool = True  # Skip if output exists
    parallel: bool = False  # TODO: parallel processing
    
    # Detection settings
    detection_mode: str = "auto"  # "auto" or "manual"
    reading_order: str = "ltr"  # "ltr" or "rtl"


class BatchProcessor:
    """Process multiple comics in a batch."""
    
    def __init__(self, config: Optional[BatchConfig] = None):
        self.config = config or BatchConfig()
        self.items: List[BatchItem] = []
        self.completed: int = 0
        self.failed: int = 0
        self.total: int = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def add_file(self, file_path: str) -> 'BatchProcessor':
        """Add a single file to the batch."""
        self.items.append(BatchItem(
            input_path=file_path,
            output_path=self._get_output_path(file_path)
        ))
        self.total = len(self.items)
        return self
    
    def add_files(self, file_paths: List[str]) -> 'BatchProcessor':
        """Add multiple files to the batch."""
        for path in file_paths:
            self.add_file(path)
        return self
    
    def add_directory(
        self,
        directory: str,
        recursive: bool = False,
        extensions: tuple = ('.cbz', '.cbr', '.pdf', '.zip', '.rar', '.jpg', '.jpeg', '.png', '.webp')
    ) -> 'BatchProcessor':
        """Add all supported files from a directory."""
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        pattern = "**/*" if recursive else "*"
        files = []
        
        for ext in extensions:
            files.extend(directory.glob(f"{pattern}{ext}"))
            files.extend(directory.glob(f"{pattern}{ext.upper()}"))
        
        # Sort for consistent ordering
        files = sorted(set(files))
        
        for file_path in files:
            self.add_file(str(file_path))
        
        return self
    
    def _get_output_path(self, input_path: str) -> str:
        """Generate output path for an input file."""
        input_path = Path(input_path)
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        base_name = input_path.stem
        if self.config.output_suffix:
            base_name += f"_{self.config.output_suffix}"
        
        return str(output_dir / f"{base_name}.mp4")
    
    def process(
        self,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        item_callback: Optional[Callable[[BatchItem], None]] = None
    ) -> Dict:
        """
        Process all items in the batch.
        
        Args:
            progress_callback: Called with (overall_progress, message)
            item_callback: Called after each item completes
            
        Returns:
            Summary dict with stats
        """
        self.start_time = time.time()
        self.completed = 0
        self.failed = 0
        
        for i, item in enumerate(self.items):
            # Update status
            item.status = BatchStatus.PROCESSING
            
            # Report overall progress
            overall_progress = i / self.total if self.total > 0 else 0
            if progress_callback:
                progress_callback(
                    overall_progress,
                    f"Processing {i+1}/{self.total}: {Path(item.input_path).name}"
                )
            
            # Skip if output exists
            if self.config.skip_existing and Path(item.output_path).exists():
                item.status = BatchStatus.COMPLETED
                item.progress = 1.0
                self.completed += 1
                continue
            
            try:
                # Load comic
                pages = load_comic(item.input_path)
                
                # Detect panels
                detector = PanelDetector()
                all_panels = []
                
                for page in pages:
                    panels = detector.detect(page)
                    if panels:
                        all_panels.extend(panels)
                
                item.panel_count = len(all_panels)
                item.panels = all_panels
                
                if not all_panels:
                    item.status = BatchStatus.FAILED
                    item.error = "No panels detected"
                    self.failed += 1
                    continue
                
                # Create render config
                render_config = RenderConfig(
                    fps=self.config.fps,
                    resolution=self.config.resolution,
                    panel_duration_frames=int(self.config.panel_duration * self.config.fps),
                    transition_duration_frames=int(self.config.transition_duration * self.config.fps),
                    transition_strategy=self.config.transition_strategy,
                    audio_path=self.config.audio_path,
                    audio_volume=self.config.audio_volume,
                    tts_enabled=self.config.tts_enabled,
                    tts_provider=self.config.tts_provider,
                    tts_voice=self.config.tts_voice,
                    output_path=item.output_path,
                    progress_callback=lambda p, m: setattr(item, 'progress', p)
                )
                
                # Render
                renderer = Renderer(render_config)
                
                # Get panel texts for TTS
                panel_texts = None
                if self.config.tts_enabled:
                    try:
                        from core.ocr import OCRProcessor
                        ocr = OCRProcessor()
                        panel_texts = []
                        for panel in all_panels:
                            panel_img = panel.extract_from_original()
                            text = ocr.extract_panel_text(panel_img)
                            panel_texts.append(text)
                    except Exception as e:
                        # TTS failed, continue without it
                        pass
                
                result_path = renderer.render(all_panels, panel_texts=panel_texts)
                
                if result_path and Path(result_path).exists():
                    item.status = BatchStatus.COMPLETED
                    item.progress = 1.0
                    self.completed += 1
                else:
                    item.status = BatchStatus.FAILED
                    item.error = "Render failed"
                    self.failed += 1
                
            except Exception as e:
                item.status = BatchStatus.FAILED
                item.error = str(e)
                self.failed += 1
            
            # Item callback
            if item_callback:
                item_callback(item)
        
        self.end_time = time.time()
        
        # Final progress
        if progress_callback:
            progress_callback(1.0, f"Done! {self.completed} completed, {self.failed} failed")
        
        return self.get_summary()
    
    def get_summary(self) -> Dict:
        """Get processing summary."""
        duration = (self.end_time or time.time()) - (self.start_time or time.time())
        
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "duration_seconds": duration,
            "items": [
                {
                    "input": item.input_path,
                    "output": item.output_path,
                    "status": item.status.value,
                    "error": item.error,
                    "panel_count": item.panel_count
                }
                for item in self.items
            ]
        }
    
    def save_report(self, path: str):
        """Save processing report as JSON."""
        summary = self.get_summary()
        with open(path, 'w') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    
    def get_completed_files(self) -> List[str]:
        """Get list of successfully processed output files."""
        return [
            item.output_path
            for item in self.items
            if item.status == BatchStatus.COMPLETED
        ]
    
    def get_failed_items(self) -> List[BatchItem]:
        """Get list of failed items."""
        return [
            item
            for item in self.items
            if item.status == BatchStatus.FAILED
        ]


# Convenience function
def batch_render(
    files: List[str],
    output_dir: str = "output",
    fps: int = 24,
    resolution: tuple = (1920, 1080),
    **kwargs
) -> Dict:
    """
    Quick batch render function.
    
    Args:
        files: List of file paths
        output_dir: Output directory
        fps: Frames per second
        resolution: Output resolution
        **kwargs: Additional BatchConfig options
        
    Returns:
        Processing summary
    """
    config = BatchConfig(
        output_dir=output_dir,
        fps=fps,
        resolution=resolution,
        **kwargs
    )
    
    processor = BatchProcessor(config)
    processor.add_files(files)
    return processor.process()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python batch.py <directory or files...>")
        print("Example: python batch.py ./comics/")
        sys.exit(1)
    
    sources = sys.argv[1:]
    processor = BatchProcessor()
    
    for source in sources:
        if os.path.isdir(source):
            processor.add_directory(source)
        else:
            processor.add_file(source)
    
    if not processor.items:
        print("No files found")
        sys.exit(1)
    
    print(f"Found {processor.total} files to process")
    print()
    
    def progress_callback(progress, message):
        print(f"[{progress*100:.0f}%] {message}")
    
    summary = processor.process(progress_callback=progress_callback)
    
    print()
    print(f"Done! {summary['completed']}/{summary['total']} completed")
    if summary['failed'] > 0:
        print(f"Failed: {summary['failed']}")
        for item in processor.get_failed_items():
            print(f"  ❌ {Path(item.input_path).name}: {item.error}")
    
    # Save report
    processor.save_report("batch_report.json")
    print(f"Report saved to: batch_report.json")
