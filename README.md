# MoFrame

Comic to animation converter with frame-by-frame morphing.

## Quick Start

```bash
# Setup
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run UI
streamlit run ui/app.py
```

## Structure

- `core/` - Image processing, morphing, rendering
  - `loader.py` - Load comics from various formats
  - `panel_detector.py` - Detect comic panels
  - `morpher.py` - Create transitions between panels
  - `renderer.py` - Assemble video from panels
- `ui/` - Streamlit interface
- `utils/` - Helpers
- `tests/` - Unit tests

## Supported Formats

- Images: JPG, PNG, WEBP, TIFF, BMP, GIF
- Archives: CBZ, CBR, ZIP, RAR
- Documents: PDF

## Transition Types

- **Crossfade** - Simple alpha blend
- **Ken Burns** - Slow zoom and pan
- **Slide** - Sliding transition
- **Zoom** - Zoom in/out effect
- **Feature Morph** - Feature-based warping (for similar images)

## Status

🚧 In development
