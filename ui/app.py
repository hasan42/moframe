"""
MoFrame - Streamlit UI (Wizard Interface)
Step-by-step workflow for converting comics to animated videos.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional
import json
import base64
import io
import http.server
import threading
from queue import Queue

import streamlit as st
import streamlit.components.v1 as components
import numpy as np
from PIL import Image
import cv2

# HTTP server for React -> Streamlit sync
panel_update_queue = Queue()

class PanelHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        if self.path == '/update':
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            data = json.loads(body)
            panel_update_queue.put(data)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
    
    def log_message(self, format, *args):
        pass  # Quiet

def start_panel_server():
    """Start HTTP server for panel updates."""
    try:
        server = http.server.HTTPServer(('localhost', 8765), PanelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
    except OSError:
        pass  # Port already in use

start_panel_server()

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.loader import load_comic, get_file_info
from core.panel_detector import PanelDetector, ReadingOrder
from core.renderer import Renderer, RenderConfig
from core.morpher import MorphStrategy


# Page configuration
st.set_page_config(
    page_title="MoFrame - Comic to Animation",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Custom CSS
st.markdown("""
<style>
    .step-indicator {
        display: flex;
        justify-content: center;
        margin-bottom: 2rem;
        padding: 1rem;
        background: #f5f5f5;
        border-radius: 8px;
    }
    .step {
        padding: 0.5rem 1rem;
        margin: 0 0.5rem;
        border-radius: 20px;
        background: #ddd;
        color: #666;
    }
    .step.active {
        background: #4CAF50;
        color: white;
        font-weight: bold;
    }
    .step.completed {
        background: #2196F3;
        color: white;
    }
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize Streamlit session state."""
    # Wizard step
    if 'step' not in st.session_state:
        st.session_state.step = 1
    
    # Step 1: File upload
    if 'loaded_images' not in st.session_state:
        st.session_state.loaded_images = []
    if 'uploaded_file_name' not in st.session_state:
        st.session_state.uploaded_file_name = None
    
    # Step 2: Panel detection
    if 'detected_panels' not in st.session_state:
        st.session_state.detected_panels = []
    if 'panel_order' not in st.session_state:
        st.session_state.panel_order = []
    if 'manual_panels' not in st.session_state:
        st.session_state.manual_panels = []
    
    # Step 3: Review
    if 'preview_frames' not in st.session_state:
        st.session_state.preview_frames = []
    
    # Step 4: Render
    if 'rendered_video_path' not in st.session_state:
        st.session_state.rendered_video_path = None
    
    # Common settings
    if 'temp_dir' not in st.session_state:
        st.session_state.temp_dir = tempfile.mkdtemp()
    if 'reading_order' not in st.session_state:
        st.session_state.reading_order = "Left to Right"


def render_step_indicator(current_step: int):
    """Render step indicator at top."""
    steps = [
        (1, "📁 Upload"),
        (2, "🔍 Panels"),
        (3, "✏️ Edit"),
        (4, "🎬 Render")
    ]
    
    html = '<div class="step-indicator">'
    for step_num, step_label in steps:
        if step_num == current_step:
            css_class = "step active"
        elif step_num < current_step:
            css_class = "step completed"
        else:
            css_class = "step"
        html += f'<span class="{css_class}">{step_label}</span>'
    html += '</div>'
    
    st.markdown(html, unsafe_allow_html=True)


def step_1_upload():
    """Step 1: Upload comic file."""
    st.markdown('<p class="main-header">🎬 MoFrame</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Step 1: Upload your comic</p>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Drop your comic file here",
        type=['cbz', 'cbr', 'pdf', 'zip', 'rar', 'jpg', 'jpeg', 'png', 'webp'],
        help="Supported formats: CBZ, CBR, PDF, ZIP, RAR, and image files"
    )
    
    if uploaded_file:
        st.session_state.uploaded_file_name = uploaded_file.name
        
        if st.button("📂 Load Comic", type="primary", use_container_width=True):
            with st.spinner("Loading comic..."):
                # Save uploaded file
                file_path = Path(st.session_state.temp_dir) / uploaded_file.name
                with open(file_path, 'wb') as f:
                    f.write(uploaded_file.getvalue())
                
                # Load images
                try:
                    from core.loader import load_comic
                    st.session_state.loaded_images = load_comic(file_path)
                    st.session_state.step = 2
                    st.rerun()
                except Exception as e:
                    st.error(f"Error loading file: {e}")
    
    # Show loaded images if already loaded
    if st.session_state.loaded_images:
        st.success(f"✅ Loaded {len(st.session_state.loaded_images)} pages from {st.session_state.uploaded_file_name}")
        
        # Preview first few pages
        cols = st.columns(min(4, len(st.session_state.loaded_images)))
        for i, img in enumerate(st.session_state.loaded_images[:4]):
            with cols[i]:
                st.image(img, caption=f"Page {i+1}", use_container_width=True)
        
        if st.button("➡️ Continue to Panel Detection", type="primary"):
            st.session_state.step = 2
            st.rerun()


def step_2_panels():
    """Step 2: Detect or define panels."""
    st.markdown('<p class="main-header">🔍 Panel Detection</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Step 2: Choose how to detect panels</p>', unsafe_allow_html=True)
    
    # Navigation buttons
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⬅️ Back to Upload", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    
    # Detection mode
    detection_mode = st.radio(
        "Detection Mode",
        ["🤖 Auto Detect", "✏️ Manual Draw"],
        help="Auto: automatic panel detection. Manual: draw panel regions yourself"
    )
    
    if "Auto" in detection_mode:
        # Auto detection
        st.session_state.reading_order = st.selectbox(
            "Reading Order",
            ["Left to Right", "Right to Left (Manga)"]
        )
        
        if st.button("🔎 Detect Panels", type="primary", use_container_width=True):
            with st.spinner("Analyzing pages..."):
                order_map = {
                    "Left to Right": ReadingOrder.LEFT_TO_RIGHT,
                    "Right to Left (Manga)": ReadingOrder.RIGHT_TO_LEFT
                }
                
                detector = PanelDetector(
                    reading_order=order_map.get(st.session_state.reading_order, ReadingOrder.LEFT_TO_RIGHT)
                )
                
                all_panels = []
                progress = st.progress(0)
                for i, img in enumerate(st.session_state.loaded_images):
                    panels = detector.detect(img, page_index=i)
                    all_panels.extend(panels)
                    progress.progress((i + 1) / len(st.session_state.loaded_images))
                
                st.session_state.detected_panels = all_panels
                st.session_state.panel_order = list(range(len(all_panels)))
                progress.empty()
                
                st.success(f"✅ Found {len(all_panels)} panels!")
                
                if st.button("➡️ Continue to Edit Panels", type="primary"):
                    st.session_state.step = 3
                    st.rerun()
    
    else:
        # Manual mode
        st.info("In manual mode you'll draw panel regions in the next step")
        
        if st.button("➡️ Continue to Manual Drawing", type="primary", use_container_width=True):
            st.session_state.manual_panels = []
            st.session_state.step = 3
            st.rerun()


def step_3_edit():
    """Step 3: Edit panels."""
    st.markdown('<p class="main-header">✏️ Edit Panels</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Step 3: Adjust panel positions and order</p>', unsafe_allow_html=True)
    
    # Navigation
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⬅️ Back to Detection", use_container_width=True):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.session_state.detected_panels or st.session_state.manual_panels:
            if st.button("➡️ Continue to Render", type="primary", use_container_width=True):
                st.session_state.step = 4
                st.rerun()
    
    # Page selector if multiple pages
    if len(st.session_state.loaded_images) > 1:
        page_options = [f"Page {i+1}" for i in range(len(st.session_state.loaded_images))]
        selected_page = st.selectbox("Select page to edit", page_options)
        page_idx = page_options.index(selected_page)
    else:
        page_idx = 0
    
    img = st.session_state.loaded_images[page_idx]
    
    # Show current panels
    if st.session_state.detected_panels:
        page_panels = [p for p in st.session_state.detected_panels if getattr(p, 'page_index', 0) == page_idx]
        st.info(f"📊 {len(page_panels)} panels on this page (auto-detected)")
    elif st.session_state.manual_panels:
        page_panels = [p for p in st.session_state.manual_panels if getattr(p, 'page_index', 0) == page_idx]
        st.info(f"✏️ {len(page_panels)} panels on this page (manual)")
    else:
        page_panels = []
        st.warning("No panels yet. Add panels below.")
    
    # Check for auto-sync panel updates from React editor
    if not panel_update_queue.empty():
        try:
            data = panel_update_queue.get_nowait()
            print(f"DEBUG: Received data: {data}")
            if data.get('panels'):
                from core.panel_detector import Panel
                new_panels = []
                for p_data in data['panels']:
                    panel = Panel(p_data['x'], p_data['y'], p_data['width'], p_data['height'])
                    panel.original_image = img.copy()
                    panel.page_index = page_idx
                    new_panels.append(panel)
                
                # Update session state
                if st.session_state.detected_panels:
                    other_panels = [p for p in st.session_state.detected_panels if getattr(p, 'page_index', 0) != page_idx]
                    st.session_state.detected_panels = other_panels + new_panels
                else:
                    other_panels = [p for p in st.session_state.manual_panels if getattr(p, 'page_index', 0) != page_idx]
                    st.session_state.manual_panels = other_panels + new_panels
                
                st.toast(f"✅ Panels updated: {len(new_panels)} panels", icon="🔄")
                st.rerun()
        except Exception as e:
            print(f"DEBUG: Error: {e}")

    # React Panel Editor
    st.markdown("### Interactive Canvas Editor")
    st.info("🖱️ Drag to move | Drag corners to resize | Double-click to delete | Click empty space to add | ✅ Auto-sync enabled")
    
    from components.panel_editor import render_react_panel_editor
    
    render_react_panel_editor(
        img, 
        page_panels, 
        page_idx,
        react_app_url="http://localhost:5173"
    )
    
    # Sync button (fallback)
    import queue
    queue_size = panel_update_queue.qsize()
    st.write(f"DEBUG: Queue size: {queue_size}")
    
    if st.button("🔄 Sync from Editor", type="secondary"):
        st.write(f"DEBUG: Button clicked, checking queue...")
        if not panel_update_queue.empty():
            try:
                data = panel_update_queue.get_nowait()
                st.write(f"DEBUG: Received data: {data}")
                if data.get('panels'):
                    from core.panel_detector import Panel
                    new_panels = []
                    for p_data in data['panels']:
                        panel = Panel(p_data['x'], p_data['y'], p_data['width'], p_data['height'])
                        panel.original_image = img.copy()
                        panel.page_index = page_idx
                        new_panels.append(panel)
                    
                    # Update session state
                    if st.session_state.detected_panels:
                        other_panels = [p for p in st.session_state.detected_panels if getattr(p, 'page_index', 0) != page_idx]
                        st.session_state.detected_panels = other_panels + new_panels
                    else:
                        other_panels = [p for p in st.session_state.manual_panels if getattr(p, 'page_index', 0) != page_idx]
                        st.session_state.manual_panels = other_panels + new_panels
                    
                    st.success(f"✅ Synced {len(new_panels)} panels from editor!")
                    st.rerun()
                else:
                    st.info("ℹ️ No panels in data")
            except Exception as e:
                st.error(f"Sync error: {e}")
                import traceback
                st.code(traceback.format_exc())
        else:
            st.info("ℹ️ Queue is empty - no updates from editor")
    
    # Also show simple editor for precise adjustments
    st.markdown("### Fine-tune Positions")
    
    if page_panels:
        img_h, img_w = img.shape[:2]
        
        for i, panel in enumerate(page_panels):
            with st.expander(f"Panel {i+1}: ({panel.x}, {panel.y}) {panel.width}x{panel.height}", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    new_x = st.number_input(f"X", 0, img_w, int(panel.x), key=f"x_{page_idx}_{i}")
                    new_y = st.number_input(f"Y", 0, img_h, int(panel.y), key=f"y_{page_idx}_{i}")
                with col2:
                    new_w = st.number_input(f"Width", 10, img_w, int(panel.width), key=f"w_{page_idx}_{i}")
                    new_h = st.number_input(f"Height", 10, img_h, int(panel.height), key=f"h_{page_idx}_{i}")
                
                if (new_x != panel.x or new_y != panel.y or new_w != panel.width or new_h != panel.height):
                    panel.x = new_x
                    panel.y = new_y
                    panel.width = new_w
                    panel.height = new_h
                    st.rerun()
                
                if st.button("🗑️ Delete", key=f"del_{page_idx}_{i}"):
                    if st.session_state.detected_panels:
                        st.session_state.detected_panels.remove(panel)
                    else:
                        st.session_state.manual_panels.remove(panel)
                    st.rerun()
    
    # Add new panel button (adds to editor)
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Add Panel", type="secondary", use_container_width=True):
            from core.panel_detector import Panel
            img_h, img_w = img.shape[:2]
            new_w, new_h = img_w // 3, img_h // 3
            panel = Panel(
                (img_w - new_w) // 2,
                (img_h - new_h) // 2,
                new_w, new_h
            )
            panel.original_image = img.copy()
            panel.page_index = page_idx
            if st.session_state.detected_panels:
                st.session_state.detected_panels.append(panel)
            else:
                st.session_state.manual_panels.append(panel)
            st.rerun()
    
    with col_btn2:
        if page_panels and st.button("🔄 Refresh Editor", type="secondary", use_container_width=True):
            st.rerun()


def step_4_render():
    """Step 4: Render video."""
    st.markdown('<p class="main-header">🎬 Render Video</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Step 4: Configure and generate your video</p>', unsafe_allow_html=True)
    
    # Navigation
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⬅️ Back to Edit", use_container_width=True):
            st.session_state.step = 3
            st.rerun()
    
    # Get panels to render
    panels = st.session_state.detected_panels if st.session_state.detected_panels else st.session_state.manual_panels
    
    if not panels:
        st.error("❌ No panels to render! Go back and add panels.")
        return
    
    st.success(f"✅ Ready to render {len(panels)} panels")
    
    # Settings sidebar
    with st.sidebar:
        st.header("⚙️ Render Settings")
        
        transition_type = st.selectbox(
            "Transition Type",
            ["Ken Burns", "Crossfade", "Slide", "Zoom"]
        )
        
        transition_duration = st.slider("Transition Duration (sec)", 0.5, 3.0, 1.0, 0.1)
        panel_duration = st.slider("Panel Duration (sec)", 1.0, 5.0, 2.0, 0.5)
        
        fps = st.slider("FPS", 12, 60, 24)
        resolution = st.selectbox(
            "Resolution",
            ["1920x1080 (Full HD)", "1280x720 (HD)", "854x480 (SD)"],
            index=1
        )
    
    # Output filename
    output_filename = st.text_input(
        "Output filename",
        value="my_comic_animation.mp4"
    )
    
    if st.button("🎥 Render Video", type="primary", use_container_width=True):
        # Parse resolution
        res_map = {
            "1920x1080 (Full HD)": (1920, 1080),
            "1280x720 (HD)": (1280, 720),
            "854x480 (SD)": (854, 480)
        }
        
        strategy_map = {
            "Ken Burns": MorphStrategy.KEN_BURNS,
            "Crossfade": MorphStrategy.CROSSFADE,
            "Slide": MorphStrategy.SLIDE,
            "Zoom": MorphStrategy.ZOOM
        }
        
        config = RenderConfig(
            fps=fps,
            resolution=res_map.get(resolution, (1280, 720)),
            panel_duration_frames=int(panel_duration * fps),
            transition_duration_frames=int(transition_duration * fps),
            transition_strategy=strategy_map.get(transition_type, MorphStrategy.KEN_BURNS),
            output_path=str(Path(st.session_state.temp_dir) / output_filename)
        )
        
        progress_placeholder = st.empty()
        
        with st.spinner("Rendering video..."):
            renderer = Renderer(config)
            
            def progress_callback(progress: float, message: str):
                progress_placeholder.progress(min(progress, 0.99), text=message)
            
            config.progress_callback = progress_callback
            
            try:
                result_path = renderer.render(panels)
                progress_placeholder.progress(1.0, text="Done!")
                
                if result_path and Path(result_path).exists():
                    st.session_state.rendered_video_path = result_path
                    st.success(f"✅ Video saved: {output_filename}")
                
            except Exception as e:
                st.error(f"Rendering failed: {e}")
    
    # Show rendered video if available
    if st.session_state.rendered_video_path and Path(st.session_state.rendered_video_path).exists():
        st.markdown("### 📼 Result")
        
        with open(st.session_state.rendered_video_path, 'rb') as f:
            video_bytes = f.read()
            st.download_button(
                label="⬇️ Download Video",
                data=video_bytes,
                file_name=output_filename,
                mime="video/mp4",
                use_container_width=True
            )
        
        st.video(st.session_state.rendered_video_path)


def main():
    """Main Streamlit application with wizard interface."""
    init_session_state()
    
    # Render step indicator
    render_step_indicator(st.session_state.step)
    
    # Render current step
    if st.session_state.step == 1:
        step_1_upload()
    elif st.session_state.step == 2:
        step_2_panels()
    elif st.session_state.step == 3:
        step_3_edit()
    elif st.session_state.step == 4:
        step_4_render()
    
    # Footer
    st.markdown("---")
    st.markdown("Made with ❤️ using MoFrame")


if __name__ == "__main__":
    main()
