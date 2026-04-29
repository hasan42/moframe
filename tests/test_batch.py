"""Tests for batch processing module."""

import unittest
import tempfile
import os
from pathlib import Path
import numpy as np
from PIL import Image

from core.batch import BatchProcessor, BatchConfig, BatchStatus, batch_render


class TestBatchProcessor(unittest.TestCase):
    """Test batch processor functionality."""
    
    def setUp(self):
        """Create temp directory with test images."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test images
        self.test_images = []
        for i in range(3):
            img_path = os.path.join(self.temp_dir, f"test_comic_{i}.png")
            img = Image.new('RGB', (400, 300), color=(i*80, i*60, i*40))
            # Add some structure for panel detection
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.rectangle([10, 10, 190, 140], fill=(200, 200, 200), outline=(0,00,0))
            draw.rectangle([200, 10, 390, 140], fill=(200, 200, 200), outline=(0,0,0))
            draw.rectangle([10, 150, 390, 290], fill=(200, 200, 200), outline=(0,0,0))
            img.save(img_path)
            self.test_images.append(img_path)
        
        # Create output dir
        self.output_dir = os.path.join(self.temp_dir, "output")
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_batch_config_creation(self):
        """Test BatchConfig creation."""
        config = BatchConfig(fps=30, resolution=(1280, 720))
        self.assertEqual(config.fps, 30)
        self.assertEqual(config.resolution, (1280, 720))
    
    def test_add_file(self):
        """Test adding single file."""
        processor = BatchProcessor()
        processor.add_file(self.test_images[0])
        
        self.assertEqual(processor.total, 1)
        self.assertEqual(processor.items[0].input_path, self.test_images[0])
    
    def test_add_files(self):
        """Test adding multiple files."""
        processor = BatchProcessor()
        processor.add_files(self.test_images)
        
        self.assertEqual(processor.total, 3)
    
    def test_add_directory(self):
        """Test adding directory."""
        processor = BatchProcessor()
        processor.add_directory(self.temp_dir)
        
        # Should find 3 PNG files
        self.assertGreaterEqual(processor.total, 3)
    
    def test_output_path_generation(self):
        """Test output path generation."""
        config = BatchConfig(output_dir=self.output_dir)
        processor = BatchProcessor(config)
        processor.add_file(self.test_images[0])
        
        expected = os.path.join(self.output_dir, "test_comic_0.mp4")
        self.assertEqual(processor.items[0].output_path, expected)
    
    def test_process_with_skip_existing(self):
        """Test skip_existing option."""
        config = BatchConfig(output_dir=self.output_dir, skip_existing=True)
        processor = BatchProcessor(config)
        processor.add_file(self.test_images[0])
        
        # Create fake output file
        Path(processor.items[0].output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(processor.items[0].output_path).touch()
        
        summary = processor.process()
        
        # Should skip since output exists
        self.assertEqual(summary['completed'], 1)
        self.assertEqual(processor.items[0].status, BatchStatus.COMPLETED)
    
    def test_process_single_file(self):
        """Test processing a single file."""
        config = BatchConfig(
            output_dir=self.output_dir,
            fps=12,  # Low for speed
            resolution=(320, 240),
            panel_duration=0.5,
            transition_duration=0.25
        )
        processor = BatchProcessor(config)
        processor.add_file(self.test_images[0])
        
        summary = processor.process()
        
        self.assertEqual(summary['total'], 1)
        self.assertEqual(summary['completed'], 1)
        self.assertEqual(summary['failed'], 0)
        
        # Check output file exists
        self.assertTrue(Path(processor.items[0].output_path).exists())
    
    def test_process_multiple_files(self):
        """Test processing multiple files."""
        config = BatchConfig(
            output_dir=self.output_dir,
            fps=12,
            resolution=(320, 240),
            panel_duration=0.5,
            transition_duration=0.25
        )
        processor = BatchProcessor(config)
        processor.add_files(self.test_images)
        
        progress_calls = []
        def progress_callback(progress, message):
            progress_calls.append((progress, message))
        
        summary = processor.process(progress_callback=progress_callback)
        
        self.assertEqual(summary['total'], 3)
        self.assertGreaterEqual(summary['completed'], 2)  # At least 2 should work
        
        # Progress should have been called
        self.assertGreater(len(progress_calls), 0)
    
    def test_batch_render_function(self):
        """Test batch_render convenience function."""
        summary = batch_render(
            files=[self.test_images[0]],
            output_dir=self.output_dir,
            fps=12,
            resolution=(320, 240)
        )
        
        self.assertEqual(summary['total'], 1)
        self.assertEqual(summary['completed'], 1)
    
    def test_summary_structure(self):
        """Test summary has correct structure."""
        config = BatchConfig(output_dir=self.output_dir)
        processor = BatchProcessor(config)
        processor.add_files(self.test_images)
        
        summary = processor.get_summary()
        
        self.assertIn('total', summary)
        self.assertIn('completed', summary)
        self.assertIn('failed', summary)
        self.assertIn('duration_seconds', summary)
        self.assertIn('items', summary)
    
    def test_get_completed_files(self):
        """Test getting completed files list."""
        config = BatchConfig(
            output_dir=self.output_dir,
            fps=12,
            resolution=(320, 240),
            panel_duration=0.5,
            transition_duration=0.25
        )
        processor = BatchProcessor(config)
        processor.add_file(self.test_images[0])
        processor.process()
        
        completed = processor.get_completed_files()
        self.assertEqual(len(completed), 1)
        self.assertTrue(os.path.exists(completed[0]))
    
    def test_save_report(self):
        """Test saving JSON report."""
        config = BatchConfig(output_dir=self.output_dir)
        processor = BatchProcessor(config)
        processor.add_file(self.test_images[0])
        processor.process()
        
        report_path = os.path.join(self.temp_dir, "report.json")
        processor.save_report(report_path)
        
        self.assertTrue(os.path.exists(report_path))
        
        import json
        with open(report_path) as f:
            report = json.load(f)
        
        self.assertIn('total', report)
        self.assertIn('items', report)


if __name__ == "__main__":
    unittest.main()
