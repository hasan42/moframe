"""
MoFrame - Streamlit UI
Web interface for converting comics to animated videos.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional
import json
import base64
import io

import streamlit as st
import streamlit.components.v1 as components
from streamlit_drawable_canvas import st_canvas
import numpy as np
from PIL import Image
import cv2

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
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .panel-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        margin: 5px;
    }
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize Streamlit session state."""
    if 'loaded_images' not in st.session_state:
        st.session_state.loaded_images = []
    if 'detected_panels' not in st.session_state:
        st.session_state.detected_panels = []
    if 'panel_order' not in st.session_state:
        st.session_state.panel_order = []
    if 'preview_frames' not in st.session_state:
        st.session_state.preview_frames = []
    if 'temp_dir' not in st.session_state:
        st.session_state.temp_dir = tempfile.mkdtemp()
    if 'rendering' not in st.session_state:
        st.session_state.rendering = False
    if 'show_reorder_ui' not in st.session_state:
        st.session_state.show_reorder_ui = False
    if 'detection_mode' not in st.session_state:
        st.session_state.detection_mode = "Auto"
    if 'manual_panels' not in st.session_state:
        st.session_state.manual_panels = []  # [(x, y, w, h), ...]
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    if 'editing_panel_idx' not in st.session_state:
        st.session_state.editing_panel_idx = None
    if 'edit_values' not in st.session_state:
        st.session_state.edit_values = {'x': 0, 'y': 0, 'w': 200, 'h': 300}
    if 'canvas_panels' not in st.session_state:
        st.session_state.canvas_panels = []


def render_drawable_canvas(image: np.ndarray, panels: list, key: str):
    """Render interactive canvas using streamlit-drawable-canvas."""
    from PIL import Image
    
    # Convert to PIL Image
    if len(image.shape) == 3 and image.shape[2] == 3:
        # BGR to RGB
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        img_rgb = image
    
    pil_img = Image.fromarray(img_rgb)
    
    # Create initial drawing data from panels
    initial_drawing = {"version": "4.2", "objects": []}
    
    for i, panel in enumerate(panels):
        rect = {
            "type": "rect",
            "version": "4.2",
            "originX": "left",
            "originY": "top",
            "left": panel.x,
            "top": panel.y,
            "width": panel.width,
            "height": panel.height,
            "fill": "rgba(255, 0, 0, 0.1)",
            "stroke": ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff"][i % 6],
            "strokeWidth": 3,
            "strokeDashArray": None,
            "strokeLineCap": "butt",
            "strokeDashOffset": 0,
            "strokeLineJoin": "miter",
            "strokeUniform": False,
            "strokeMiterLimit": 4,
            "scaleX": 1,
            "scaleY": 1,
            "angle": 0,
            "flipX": False,
            "flipY": False,
            "opacity": 1,
            "shadow": None,
            "visible": True,
            "backgroundColor": "",
            "fillRule": "nonzero",
            "paintFirst": "fill",
            "globalCompositeOperation": "source-over",
            "skewX": 0,
            "skewY": 0,
            "rx": 0,
            "ry": 0,
            "name": f"panel_{i}"
        }
        initial_drawing["objects"].append(rect)
    
    # Render canvas
    canvas_result = st_canvas(
        fill_color="rgba(255, 0, 0, 0.1)",
        stroke_width=3,
        stroke_color="#ff0000",
        background_image=pil_img,
        drawing_mode="transform" if panels else "rect",  # Allow move/resize or draw new
        initial_drawing=initial_drawing if panels else None,
        height=pil_img.height,
        width=pil_img.width,
        key=key,
    )
    
    # Return canvas result for processing
    return canvas_result


# Keep old function for compatibility (not used)
def render_canvas_editor(image: np.ndarray, panels: list, key: str):
    """Deprecated: Use render_drawable_canvas instead."""
    pass
    """Render interactive HTML5 canvas with drag-drop and resize."""
    img_h, img_w = image.shape[:2]
    
    # Convert image to base64
    pil_img = Image.fromarray(image)
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    # Panels JSON
    panels_data = [{'x': p.x, 'y': p.y, 'w': p.width, 'h': p.height, 'label': str(i+1)} 
                   for i, p in enumerate(panels)]
    panels_json = json.dumps(panels_data)
    
    # HTML/JS
    html = f"""
    <div id="editor-{key}" style="position: relative; display: inline-block;">
        <canvas id="canvas-{key}" width="{img_w}" height="{img_h}" 
                style="border: 2px solid #333; cursor: crosshair; max-width: 100%; height: auto;"></canvas>
    </div>
    <div style="margin-top: 8px; font-size: 13px; color: #666;">
        💡 Drag inside to move | Drag corners to resize | Double-click to delete
    </div>
    
    <script>
    (function() {{
        const canvas = document.getElementById('canvas-{key}');
        const ctx = canvas.getContext('2d');
        const img = new Image();
        img.src = 'data:image/png;base64,{img_b64}';
        
        let panels = {panels_json};
        let selected = null;
        let dragging = false;
        let resizing = false;
        let resizeCorner = '';
        let startX, startY, startPanel;
        
        const HANDLE = 10;
        const MIN = 30;
        const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff', '#800080', '#ffa500'];
        
        function draw() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);
            
            panels.forEach((p, i) => {{
                const c = colors[i % colors.length];
                ctx.strokeStyle = c;
                ctx.lineWidth = 3;
                ctx.strokeRect(p.x, p.y, p.w, p.h);
                
                // Label
                ctx.fillStyle = c;
                ctx.font = 'bold 16px Arial';
                ctx.fillText(p.label, p.x + 5, p.y + 20);
                
                // Handles if selected
                if (p === selected) {{
                    ctx.fillStyle = '#fff';
                    ctx.strokeStyle = '#000';
                    ctx.lineWidth = 1;
                    
                    // Corner handles
                    const corners = [
                        [p.x, p.y], [p.x + p.w, p.y],
                        [p.x, p.y + p.h], [p.x + p.w, p.y + p.h]
                    ];
                    corners.forEach(([cx, cy]) => {{
                        ctx.fillRect(cx - HANDLE/2, cy - HANDLE/2, HANDLE, HANDLE);
                        ctx.strokeRect(cx - HANDLE/2, cy - HANDLE/2, HANDLE, HANDLE);
                    }});
                }}
            }});
        }}
        
        function getCursor(x, y, p) {{
            const corners = [
                [p.x, p.y, 'nw'], [p.x + p.w, p.y, 'ne'],
                [p.x, p.y + p.h, 'sw'], [p.x + p.w, p.y + p.h, 'se']
            ];
            for (let [cx, cy, type] of corners) {{
                if (Math.abs(x - cx) < HANDLE && Math.abs(y - cy) < HANDLE) return type;
            }}
            if (x >= p.x && x <= p.x + p.w && y >= p.y && y <= p.y + p.h) return 'move';
            return null;
        }}
        
        canvas.addEventListener('mousedown', e => {{
            const r = canvas.getBoundingClientRect();
            const scaleX = canvas.width / r.width;
            const scaleY = canvas.height / r.height;
            const x = (e.clientX - r.left) * scaleX;
            const y = (e.clientY - r.top) * scaleY;
            
            selected = null;
            for (let i = panels.length - 1; i >= 0; i--) {{
                const hit = getCursor(x, y, panels[i]);
                if (hit) {{
                    selected = panels[i];
                    startX = x; startY = y;
                    startPanel = {{...selected}};
                    if (hit === 'move') dragging = true;
                    else {{ resizing = true; resizeCorner = hit; }}
                    draw();
                    return;
                }}
            }}
            draw();
        }});
        
        canvas.addEventListener('mousemove', e => {{
            if (!selected || (!dragging && !resizing)) return;
            
            const r = canvas.getBoundingClientRect();
            const x = (e.clientX - r.left) * (canvas.width / r.width);
            const y = (e.clientY - r.top) * (canvas.height / r.height);
            
            const dx = x - startX;
            const dy = y - startY;
            
            if (dragging) {{
                selected.x = Math.max(0, Math.min(canvas.width - selected.w, startPanel.x + dx));
                selected.y = Math.max(0, Math.min(canvas.height - selected.h, startPanel.y + dy));
            }} else {{
                if (resizeCorner.includes('e')) selected.w = Math.max(MIN, startPanel.w + dx);
                if (resizeCorner.includes('w')) {{
                    const nw = Math.max(MIN, startPanel.w - dx);
                    selected.x = startPanel.x + (startPanel.w - nw);
                    selected.w = nw;
                }}
                if (resizeCorner.includes('s')) selected.h = Math.max(MIN, startPanel.h + dy);
                if (resizeCorner.includes('n')) {{
                    const nh = Math.max(MIN, startPanel.h - dy);
                    selected.y = startPanel.y + (startPanel.h - nh);
                    selected.h = nh;
                }}
            }}
            draw();
        }});
        
        canvas.addEventListener('mouseup', () => {{
            dragging = false;
            resizing = false;
            resizeCorner = '';
        }});
        
        canvas.addEventListener('dblclick', e => {{
            const r = canvas.getBoundingClientRect();
            const x = (e.clientX - r.left) * (canvas.width / r.width);
            const y = (e.clientY - r.top) * (canvas.height / r.height);
            
            for (let i = panels.length - 1; i >= 0; i--) {{
                const p = panels[i];
                if (x >= p.x && x <= p.x + p.w && y >= p.y && y <= p.y + p.h) {{
                    panels.splice(i, 1);
                    selected = null;
                    draw();
                    return;
                }}
            }}
        }});
        
        // Expose for Streamlit
        window.getPanels_{key} = () => JSON.stringify(panels);
        window.addPanel_{key} = () => {{
            const w = Math.floor(canvas.width / 3);
            const h = Math.floor(canvas.height / 3);
            panels.push({{
                x: Math.floor((canvas.width - w) / 2),
                y: Math.floor((canvas.height - h) / 2),
                w: w, h: h,
                label: String(panels.length + 1)
            }});
            draw();
        }};
        
        img.onload = draw;
    }})();
    </script>
    """
    
    components.html(html, height=img_h + 50, scrolling=False)



def load_comic_file(uploaded_file, temp_dir):
    """Load comic from uploaded file."""
    if uploaded_file is None:
        return []
    
    # Save uploaded file to temp directory
    file_path = Path(temp_dir) / uploaded_file.name
    with open(file_path, 'wb') as f:
        f.write(uploaded_file.getvalue())
    
    try:
        images = load_comic(file_path)
        return images
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return []


def detect_panels(images: List[np.ndarray], reading_order: str) -> List:
    """Detect panels in loaded images."""
    order_map = {
        "Left to Right": ReadingOrder.LEFT_TO_RIGHT,
        "Right to Left (Manga)": ReadingOrder.RIGHT_TO_LEFT
    }
    
    detector = PanelDetector(reading_order=order_map.get(reading_order, ReadingOrder.LEFT_TO_RIGHT))
    all_panels = []
    
    progress_bar = st.progress(0)
    for i, img in enumerate(images):
        panels = detector.detect(img, page_index=i)
        all_panels.extend(panels)
        progress_bar.progress((i + 1) / len(images))
    
    progress_bar.empty()
    
    # Initialize custom order to default order
    st.session_state.panel_order = list(range(len(all_panels)))
    
    return all_panels


def reorder_panels(detected_panels: List, order_indices: List[int]) -> List:
    """Reorder panels based on custom indices."""
    return [detected_panels[i] for i in order_indices]


def move_panel(order: List[int], index: int, direction: int) -> List[int]:
    """Move panel at index in direction (-1 for up, +1 for down)."""
    new_order = order.copy()
    new_pos = index + direction
    
    if 0 <= new_pos < len(new_order):
        # Swap
        new_order[index], new_order[new_pos] = new_order[new_pos], new_order[index]
    
    return new_order


def remove_panel(order: List[int], index: int) -> List[int]:
    """Remove panel at index from order."""
    new_order = order.copy()
    del new_order[index]
    return new_order


def reset_order(num_panels: int) -> List[int]:
    """Reset order to default."""
    return list(range(num_panels))


def render_video(panels: List, config: RenderConfig, progress_placeholder):
    """Render video with progress updates."""
    renderer = Renderer(config)
    
    def progress_callback(progress: float, message: str):
        progress_placeholder.progress(min(progress, 0.99), text=message)
    
    config.progress_callback = progress_callback
    
    try:
        result_path = renderer.render(panels)
        progress_placeholder.progress(1.0, text="Done!")
        return result_path
    except Exception as e:
        progress_placeholder.error(f"Rendering failed: {e}")
        return None


def generate_preview(panels: List, config: RenderConfig) -> List:
    """Generate preview frames for first transition."""
    if len(panels) < 2:
        return []
    
    renderer = Renderer(config)
    
    try:
        # Generate preview for transition between first two panels
        preview_frames = renderer.preview_transition(
            panels[0], panels[1], num_samples=5
        )
        return preview_frames
    except Exception as e:
        st.error(f"Preview generation failed: {e}")
        return []


def main():
    """Main Streamlit application."""
    init_session_state()
    
    # Header
    st.markdown('<p class="main-header">🎬 MoFrame</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Transform your comics into animated videos</p>', unsafe_allow_html=True)
    
    # Sidebar - Settings
    st.sidebar.header("⚙️ Settings")
    
    # Reading order
    reading_order = st.sidebar.selectbox(
        "Reading Order",
        ["Left to Right", "Right to Left (Manga)"],
        help="Direction for panel sequence"
    )
    
    # Transition settings
    st.sidebar.subheader("Transition")
    transition_type = st.sidebar.selectbox(
        "Type",
        ["Ken Burns", "Crossfade", "Slide", "Zoom", "Feature Morph"],
        help="Animation style between panels"
    )
    
    transition_duration = st.sidebar.slider(
        "Duration (seconds)",
        min_value=0.5,
        max_value=3.0,
        value=1.0,
        step=0.1
    )
    
    # Panel settings
    st.sidebar.subheader("Panel Display")
    panel_duration = st.sidebar.slider(
        "Duration (seconds)",
        min_value=1.0,
        max_value=5.0,
        value=2.0,
        step=0.5
    )
    
    # Video settings
    st.sidebar.subheader("Video Output")
    fps = st.sidebar.slider(
        "FPS",
        min_value=12,
        max_value=60,
        value=24,
        step=1
    )
    
    resolution = st.sidebar.selectbox(
        "Resolution",
        ["1920x1080 (Full HD)", "1280x720 (HD)", "854x480 (SD)", "640x360"],
        index=1
    )
    
    # Main content - File upload
    st.header("📁 Upload Comic")
    
    uploaded_file = st.file_uploader(
        "Drop your comic file here",
        type=['cbz', 'cbr', 'pdf', 'zip', 'rar', 'jpg', 'jpeg', 'png', 'webp'],
        help="Supported formats: CBZ, CBR, PDF, ZIP, RAR, and image files"
    )
    
    # Load button
    if uploaded_file and st.button("📂 Load Comic", type="primary"):
        with st.spinner("Loading comic..."):
            st.session_state.loaded_images = load_comic_file(
                uploaded_file, 
                st.session_state.temp_dir
            )
            st.session_state.detected_panels = []
        
        if st.session_state.loaded_images:
            st.success(f"Loaded {len(st.session_state.loaded_images)} pages")
    
    # Display loaded images
    if st.session_state.loaded_images:
        st.header("📄 Pages")
        
        cols = st.columns(min(4, len(st.session_state.loaded_images)))
        for i, img in enumerate(st.session_state.loaded_images[:8]):  # Show first 8
            with cols[i % len(cols)]:
                st.image(img, caption=f"Page {i+1}", use_container_width=True)
        
        if len(st.session_state.loaded_images) > 8:
            st.info(f"... and {len(st.session_state.loaded_images) - 8} more pages")
        
        # Detect panels section
        st.header("🔍 Detect Panels")
        
        # Mode selection
        detection_mode = st.radio(
            "Detection Mode",
            ["Auto Detect", "Manual Draw"],
            help="Auto: automatic panel detection. Manual: draw panel regions yourself"
        )
        
        if detection_mode == "Auto Detect":
            if st.button("🔎 Detect Panels", type="primary"):
                with st.spinner("Analyzing pages..."):
                    st.session_state.detected_panels = detect_panels(
                        st.session_state.loaded_images,
                        reading_order
                    )
                
                if st.session_state.detected_panels:
                    st.success(f"Found {len(st.session_state.detected_panels)} panels")
                    st.session_state.panel_order = list(range(len(st.session_state.detected_panels)))
        
        else:  # Manual Draw mode with HTML5 Canvas
            st.info("Manual mode: Drag panels to move, drag corners to resize, double-click to delete")
            
            # Page selector
            page_options = [f"Page {i+1}" for i in range(len(st.session_state.loaded_images))]
            selected_page = st.selectbox("Select page", page_options, key="manual_page")
            page_idx = page_options.index(selected_page)
            
            st.session_state.current_page = page_idx
            img = st.session_state.loaded_images[page_idx]
            
            # Filter panels for current page
            page_panels = [p for p in st.session_state.manual_panels if p.page_index == page_idx]
            
            # Control buttons
            btn_cols = st.columns([1, 1, 1, 1])
            with btn_cols[0]:
                if st.button("➕ Add Panel", type="primary", key="add_panel_btn"):
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
                    st.session_state.manual_panels.append(panel)
                    st.rerun()
            
            with btn_cols[1]:
                if st.button("🗑️ Clear This Page", key="clear_page_btn"):
                    st.session_state.manual_panels = [
                        p for p in st.session_state.manual_panels if p.page_index != page_idx
                    ]
                    st.rerun()
            
            with btn_cols[2]:
                if st.button("🗑️ Clear All", key="clear_all_btn"):
                    st.session_state.manual_panels = []
                    st.rerun()
            
            with btn_cols[3]:
                if st.button("✅ Use Panels", type="primary", key="use_panels_btn") and st.session_state.manual_panels:
                    st.session_state.detected_panels = st.session_state.manual_panels.copy()
                    st.session_state.panel_order = list(range(len(st.session_state.manual_panels)))
                    st.success(f"Using {len(st.session_state.detected_panels)} panels")
            
            # Canvas editor using streamlit-drawable-canvas
            st.markdown("**Interactive Canvas:**")
            st.info("🖱️ Drag to move | Drag corners to resize | Draw new rectangle to add panel")
            
            canvas_result = render_drawable_canvas(img, page_panels, key=f"editor_{page_idx}")
            
            # Sync canvas changes back to panels
            if canvas_result.json_data is not None:
                objects = canvas_result.json_data.get("objects", [])
                # Filter only rectangles (panels)
                rects = [obj for obj in objects if obj.get("type") == "rect"]
                
                # Update panel positions
                for i, obj in enumerate(rects):
                    if i < len(page_panels):
                        page_panels[i].x = int(obj.get("left", 0))
                        page_panels[i].y = int(obj.get("top", 0))
                        page_panels[i].width = int(obj.get("width", 100))
                        page_panels[i].height = int(obj.get("height", 100))
                
                # Check for new panels (drawn by user)
                if len(rects) > len(page_panels):
                    # New rectangles were drawn
                    for i in range(len(page_panels), len(rects)):
                        obj = rects[i]
                        from core.panel_detector import Panel
                        new_panel = Panel(
                            int(obj.get("left", 0)),
                            int(obj.get("top", 0)),
                            int(obj.get("width", 100)),
                            int(obj.get("height", 100))
                        )
                        new_panel.original_image = img.copy()
                        new_panel.page_index = page_idx
                        st.session_state.manual_panels.append(new_panel)
                    st.rerun()
    
    # Display detected panels
    if st.session_state.detected_panels:
        st.header(f"🎨 Detected Panels ({len(st.session_state.detected_panels)})")
        
        # Toggle reorder UI
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔀 Reorder Panels", type="secondary"):
                st.session_state.show_reorder_ui = not st.session_state.show_reorder_ui
        
        # Reorder UI
        if st.session_state.show_reorder_ui:
            st.info("Use ↑ ↓ to reorder, 🗑️ to remove panel, 🔄 to reset")
            
            # Show all panels with reorder controls
            num_panels = len(st.session_state.detected_panels)
            current_order = st.session_state.panel_order
            
            for display_idx, original_idx in enumerate(current_order):
                panel = st.session_state.detected_panels[original_idx]
                
                col_img, col_controls = st.columns([1, 4])
                
                with col_img:
                    try:
                        panel_img = panel.extract_from_original()
                        panel_img = cv2.resize(panel_img, (120, 90))
                        st.image(panel_img, caption=f"#{display_idx+1}")
                    except:
                        st.error("Error")
                
                with col_controls:
                    btn_cols = st.columns([1, 1, 1, 1, 8])
                    
                    with btn_cols[0]:
                        if st.button("↑", key=f"up_{display_idx}", disabled=display_idx == 0):
                            st.session_state.panel_order = move_panel(
                                current_order, display_idx, -1
                            )
                            st.rerun()
                    
                    with btn_cols[1]:
                        if st.button("↓", key=f"down_{display_idx}", disabled=display_idx == len(current_order) - 1):
                            st.session_state.panel_order = move_panel(
                                current_order, display_idx, 1
                            )
                            st.rerun()
                    
                    with btn_cols[2]:
                        if st.button("🗑️", key=f"del_{display_idx}"):
                            st.session_state.panel_order = remove_panel(
                                current_order, display_idx
                            )
                            st.rerun()
                    
                    with btn_cols[3]:
                        if st.button("🔄", key=f"reset_{display_idx}"):
                            st.session_state.panel_order = reset_order(num_panels)
                            st.rerun()
                    
                    with btn_cols[4]:
                        st.caption(f"Original: #{original_idx+1} | Page: {panel.page_index+1}")
            
            st.divider()
        
        # Get panels in current order
        ordered_panels = reorder_panels(
            st.session_state.detected_panels,
            st.session_state.panel_order
        )
        
        # Show current order preview (first 8)
        st.subheader(f"Current Sequence ({len(ordered_panels)} panels)")
        
        preview_cols = st.columns(min(8, len(ordered_panels)))
        for i, panel in enumerate(ordered_panels[:8]):
            with preview_cols[i % len(preview_cols)]:
                try:
                    panel_img = panel.extract_from_original()
                    panel_img = cv2.resize(panel_img, (100, 75))
                    st.image(panel_img, caption=f"#{i+1}")
                except:
                    st.error("Err")
        
        if len(ordered_panels) > 8:
            st.caption(f"... and {len(ordered_panels) - 8} more")
        
        # Preview Section
        st.header("👁️ Preview Transition")
        
        col_preview1, col_preview2, col_preview3 = st.columns([1, 2, 1])
        
        with col_preview2:
            if st.button("🔍 Generate Preview", type="secondary"):
                with st.spinner("Generating preview..."):
                    # Create preview config (low res for speed)
                    preview_res_map = {
                        "1920x1080 (Full HD)": (640, 360),
                        "1280x720 (HD)": (427, 240),
                        "854x480 (SD)": (320, 180),
                        "640x360": (320, 180)
                    }
                    
                    strategy_map = {
                        "Ken Burns": MorphStrategy.KEN_BURNS,
                        "Crossfade": MorphStrategy.CROSSFADE,
                        "Slide": MorphStrategy.SLIDE,
                        "Zoom": MorphStrategy.ZOOM,
                        "Feature Morph": MorphStrategy.FEATURE_MORPH
                    }
                    
                    preview_config = RenderConfig(
                        fps=fps,
                        resolution=preview_res_map.get(resolution, (427, 240)),
                        panel_duration_frames=int(panel_duration * fps),
                        transition_duration_frames=int(transition_duration * fps),
                        transition_strategy=strategy_map.get(transition_type, MorphStrategy.KEN_BURNS)
                    )
                    
                    preview_frames = generate_preview(ordered_panels, preview_config)
                    
                    if preview_frames:
                        st.session_state.preview_frames = preview_frames
                        st.success(f"Preview ready! {len(preview_frames)} frames")
                    else:
                        st.error("Could not generate preview")
        
        # Display preview if available
        if 'preview_frames' in st.session_state and st.session_state.preview_frames:
            st.subheader("Preview Frames")
            preview_cols = st.columns(len(st.session_state.preview_frames))
            
            for i, (col, frame) in enumerate(zip(preview_cols, st.session_state.preview_frames)):
                with col:
                    st.image(frame, caption=f"Frame {i+1}")
            
            # Create animation from frames
            st.caption("💡 Tip: If preview looks good, proceed to render full video")
        
        # Render section
        st.header("🎬 Generate Video")
        
        # Output filename
        output_filename = st.text_input(
            "Output filename",
            value="my_comic_animation.mp4"
        )
        
        if st.button("🎥 Render Video", type="primary"):
            # Parse resolution
            res_map = {
                "1920x1080 (Full HD)": (1920, 1080),
                "1280x720 (HD)": (1280, 720),
                "854x480 (SD)": (854, 480),
                "640x360": (640, 360)
            }
            
            strategy_map = {
                "Ken Burns": MorphStrategy.KEN_BURNS,
                "Crossfade": MorphStrategy.CROSSFADE,
                "Slide": MorphStrategy.SLIDE,
                "Zoom": MorphStrategy.ZOOM,
                "Feature Morph": MorphStrategy.FEATURE_MORPH
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
                result_path = render_video(
                    ordered_panels,  # Use ordered panels
                    config,
                    progress_placeholder
                )
            
            if result_path and Path(result_path).exists():
                st.success(f"Video saved: {output_filename}")
                
                # Provide download button
                with open(result_path, 'rb') as f:
                    st.download_button(
                        label="⬇️ Download Video",
                        data=f,
                        file_name=output_filename,
                        mime="video/mp4"
                    )
                
                # Show video preview
                st.video(result_path)
    
    # Footer
    st.markdown("---")
    st.markdown("Made with ❤️ using MoFrame")


if __name__ == "__main__":
    main()
