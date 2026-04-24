# MoFrame

Comic to animation converter with interactive panel editing and frame-by-frame morphing.

## Features

### Core
- 📁 **Upload** - CBZ, CBR, PDF, ZIP, RAR, and image files (JPG, PNG, WEBP)
- 🔍 **Panel Detection** - Auto (OpenCV contours) or Manual drawing
- ✏️ **Interactive Editor** - React Canvas with drag/resize/delete/add
- 🎬 **Video Render** - MP4 with smooth transitions

### Video Settings
- 🎯 **Social Media Presets** - Instagram Reels, TikTok, YouTube Shorts/Landscape, Twitter/X
- 🎨 **Aspect Ratios** - 16:9, 9:16 (Vertical), 1:1 (Square)
- ⚙️ **FPS** - 12 to 60
- 🎵 **Audio Track** - Upload audio with auto-fit, fade in/out

### Transitions
- Ken Burns (pan & zoom)
- Crossfade
- Slide (4 directions)
- Zoom

### React ↔ Streamlit Sync
- HTTP server on port 8765 for auto-sync
- JSON copy/paste fallback
- 🔄 Sync from Editor button

## Workflow

The application uses a **4-step wizard interface**:

1. **📁 Upload** - Load comic file (CBZ, CBR, PDF, ZIP, RAR, images)
2. **🔍 Panels** - Choose detection mode:
   - Auto Detect - automatic panel detection via OpenCV
   - Manual Draw - create panels manually
3. **✏️ Edit** - Interactive panel editor:
   - React Canvas editor - visual drag/drop/resize
   - Fine-tune fields - precise X/Y/Width/Height adjustment
   - HTTP auto-sync (port 8765) or JSON copy/paste
4. **🎬 Render** - Configure presets, preview, generate video:
   - Social media presets (Reels, TikTok, YouTube, Twitter)
   - Audio track upload with auto-fit
   - Resolution, FPS, transitions

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
