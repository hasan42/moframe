"""
Loader module for MoFrame.
Handles loading comics from various formats: images, archives (CBZ/CBR), PDF.
"""

import os
import tempfile
import zipfile
from pathlib import Path
from typing import List, Union
import warnings

import numpy as np
from PIL import Image

# Suppress PyMuPDF warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)


def load_comic(source: Union[str, Path]) -> List[np.ndarray]:
    """
    Load comic from any supported format.
    
    Args:
        source: Path to file or directory
        
    Returns:
        List of images as numpy arrays (RGB)
        
    Raises:
        FileNotFoundError: If source doesn't exist
        ValueError: If format is unsupported
    """
    source = Path(source)
    
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    
    if source.is_dir():
        return _load_from_directory(source)
    
    suffix = source.suffix.lower()
    
    if suffix in {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'}:
        return _load_single_image(source)
    elif suffix == '.cbz' or (suffix == '.zip' and _is_comic_archive(source)):
        return _load_from_cbz(source)
    elif suffix == '.cbr' or (suffix == '.rar' and _is_comic_archive(source)):
        return _load_from_cbr(source)
    elif suffix == '.pdf':
        return _load_from_pdf(source)
    else:
        raise ValueError(f"Unsupported format: {suffix}")


def _load_single_image(path: Path) -> List[np.ndarray]:
    """Load a single image file."""
    img = Image.open(path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return [np.array(img)]


def _load_from_directory(path: Path) -> List[np.ndarray]:
    """Load all images from directory, sorted by filename."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'}
    image_files = [
        f for f in path.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    image_files.sort()
    
    if not image_files:
        raise ValueError(f"No images found in directory: {path}")
    
    images = []
    for img_path in image_files:
        try:
            img = Image.open(img_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(np.array(img))
        except Exception as e:
            print(f"Warning: Failed to load {img_path}: {e}")
            continue
    
    return images


def _is_comic_archive(path: Path) -> bool:
    """Check if archive contains comic images."""
    # Simple heuristic: check if archive contains mostly images
    try:
        if path.suffix.lower() == '.zip':
            with zipfile.ZipFile(path, 'r') as zf:
                files = zf.namelist()
                image_files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                return len(image_files) > len(files) * 0.5
    except:
        pass
    return False


def _load_from_cbz(path: Path) -> List[np.ndarray]:
    """Load images from CBZ (ZIP) archive."""
    images = []
    
    with zipfile.ZipFile(path, 'r') as zf:
        # Get image files, sorted
        image_files = [
            f for f in zf.namelist()
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'))
            and not f.startswith('__')  # Skip macOS metadata
            and not f.startswith('.')     # Skip hidden files
        ]
        image_files.sort()
        
        for img_name in image_files:
            try:
                with zf.open(img_name) as img_file:
                    img = Image.open(img_file)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    images.append(np.array(img))
            except Exception as e:
                print(f"Warning: Failed to load {img_name}: {e}")
                continue
    
    if not images:
        raise ValueError(f"No images found in CBZ: {path}")
    
    return images


def _load_from_cbr(path: Path) -> List[np.ndarray]:
    """Load images from CBR (RAR) archive."""
    try:
        import rarfile
    except ImportError:
        raise ImportError(
            "rarfile not installed. Run: pip install rarfile. "
            "Also requires unrar: brew install unrar (macOS) or apt-get install unrar (Linux)"
        )
    
    images = []
    
    with rarfile.RarFile(path, 'r') as rf:
        # Get image files, sorted
        image_files = [
            f for f in rf.namelist()
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'))
            and not f.startswith('__')
            and not f.startswith('.')
        ]
        image_files.sort()
        
        for img_name in image_files:
            try:
                with rf.open(img_name) as img_file:
                    img = Image.open(img_file)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    images.append(np.array(img))
            except Exception as e:
                print(f"Warning: Failed to load {img_name}: {e}")
                continue
    
    if not images:
        raise ValueError(f"No images found in CBR: {path}")
    
    return images


def _load_from_pdf(path: Path) -> List[np.ndarray]:
    """Load images from PDF file."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")
    
    images = []
    
    with fitz.open(path) as pdf:
        for page_num in range(len(pdf)):
            page = pdf[page_num]
            # Render at high resolution (300 DPI equivalent)
            mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(np.array(img))
    
    if not images:
        raise ValueError(f"No pages found in PDF: {path}")
    
    return images


def get_file_info(path: Union[str, Path]) -> dict:
    """
    Get information about the source file without loading images.
    
    Returns:
        dict with keys: format, page_count, estimated_size
    """
    source = Path(path)
    
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    
    info = {
        'path': str(source),
        'format': 'unknown',
        'page_count': 0,
        'size_bytes': source.stat().st_size if source.is_file() else 0
    }
    
    if source.is_dir():
        info['format'] = 'directory'
        image_files = [
            f for f in source.iterdir()
            if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'}
        ]
        info['page_count'] = len(image_files)
    else:
        suffix = source.suffix.lower()
        
        if suffix in {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'}:
            info['format'] = 'image'
            info['page_count'] = 1
        elif suffix in {'.cbz', '.zip'}:
            info['format'] = 'cbz'
            try:
                with zipfile.ZipFile(source, 'r') as zf:
                    info['page_count'] = len([f for f in zf.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
            except:
                pass
        elif suffix in {'.cbr', '.rar'}:
            info['format'] = 'cbr'
            try:
                import rarfile
                with rarfile.RarFile(source, 'r') as rf:
                    info['page_count'] = len([f for f in rf.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
            except:
                pass
        elif suffix == '.pdf':
            info['format'] = 'pdf'
            try:
                import fitz
                with fitz.open(source) as pdf:
                    info['page_count'] = len(pdf)
            except:
                pass
    
    return info


if __name__ == "__main__":
    # Simple CLI test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python loader.py <path_to_comic>")
        sys.exit(1)
    
    path = sys.argv[1]
    
    # Show info
    print(f"\nFile info:")
    info = get_file_info(path)
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Load images
    print(f"\nLoading images...")
    images = load_comic(path)
    print(f"Loaded {len(images)} images")
    
    for i, img in enumerate(images[:5]):  # Show first 5
        print(f"  Image {i+1}: {img.shape}")
    
    if len(images) > 5:
        print(f"  ... and {len(images) - 5} more")
