# MoFrame

Comic to animation converter with interactive panel editing and frame-by-frame morphing.

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Node.js dependencies for React editor
cd ui-react && npm install && cd ..

# 3. Start React dev server (Terminal 1)
cd ui-react && npm run dev

# 4. Start Streamlit app (Terminal 2)
cd ui && streamlit run app.py
```

Open browser: http://localhost:8501

## Workflow

The application uses a **4-step wizard interface**:

1. **📁 Upload** - Load comic file (CBZ, CBR, PDF, images)
2. **🔍 Panels** - Choose detection mode:
   - Auto Detect - automatic panel detection
   - Manual Draw - create panels manually
3. **✏️ Edit** - Interactive panel editor:
   - React Canvas editor - visual drag/drop/resize
   - Fine-tune fields - precise X/Y/Width/Height adjustment
4. **🎬 Render** - Configure and generate video

## Architecture

### Backend (Python)
- `core/loader.py` - Load comics from various formats
- `core/panel_detector.py` - Detect comic panels automatically
- `core/morpher.py` - Create smooth transitions between panels
- `core/renderer.py` - Assemble final video

### Frontend
- `ui/app.py` - Streamlit wizard interface
- `ui/components/panel_editor.py` - React Canvas wrapper
- `ui-react/src/PanelEditor.tsx` - Interactive React Canvas component

### React Canvas Editor Features
- 🖱️ **Drag** panels to move
- ↔️ **Drag corners** to resize
- 🗑️ **Double-click** to delete
- ➕ **Click empty space** to add new panel
- 📋 **Copy JSON** to export changes

## Supported Formats

- **Images**: JPG, PNG, WEBP, TIFF, BMP, GIF
- **Archives**: CBZ, CBR, ZIP, RAR
- **Documents**: PDF

## Transition Types

- **Crossfade** - Simple alpha blend
- **Ken Burns** - Slow zoom and pan effect
- **Slide** - Sliding transition between panels
- **Zoom** - Zoom in/out effect
- **Feature Morph** - Feature-based warping (for similar images)

## Requirements

- Python 3.9+
- Node.js 18+
- FFmpeg (for video rendering)

## Development Status

✅ Working: File loading, auto panel detection, manual panel editing, video rendering
🔧 In Progress: Advanced morphing algorithms, batch processing

## License

MIT
