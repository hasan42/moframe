"""
MoFrame - Streamlit UI
Web interface for converting comics to animated videos.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional

import streamlit as st
import numpy as np
from PIL import Image
import cv2
import plotly.graph_objects as go

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


def load_comic_file(uploaded_file, temp_dir: str) -> List[np.ndarray]:
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
                st.image(img, caption=f"Page {i+1}", use_column_width=True)
        
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
        
        else:  # Manual Draw mode
            st.info("Manual mode: Click on image to create panel, then adjust with sliders")
            
            # Page selector
            page_options = [f"Page {i+1}" for i in range(len(st.session_state.loaded_images))]
            selected_page = st.selectbox("Select page", page_options, key="manual_page")
            page_idx = page_options.index(selected_page)
            
            st.session_state.current_page = page_idx
            img = st.session_state.loaded_images[page_idx]
            img_h, img_w = img.shape[:2]
            
            # Initialize click position
            if 'click_x' not in st.session_state:
                st.session_state.click_x = img_w // 2
                st.session_state.click_y = img_h // 2
            
            # Two-column layout: image left, controls right
            col_img, col_ctrl = st.columns([3, 2])
            
            with col_img:
                st.markdown("**Click to set panel position:**")
                # Display image with click handler
                import streamlit.components.v1 as components
                
                # Simple click detection using st.image with experimental feature
                clicked = st.image(img, use_column_width=True)
                
                # Alternative: use st.slider for position after visual selection
                st.markdown("*Or set position manually:*")
            
            with col_ctrl:
                st.markdown("**Panel settings:**")
                
                # Position inputs
                new_x = st.number_input("X (left)", 0, img_w, st.session_state.click_x)
                new_y = st.number_input("Y (top)", 0, img_h, st.session_state.click_y)
                new_w = st.number_input("Width", 10, img_w, 300)
                new_h = st.number_input("Height", 10, img_h, 400)
                
                # Preview checkbox
                show_preview = st.checkbox("Show preview", value=True)
                
                # Add button
                if st.button("➕ Add Panel", type="primary"):
                    from core.panel_detector import Panel
                    panel = Panel(new_x, new_y, new_w, new_h)
                    panel.original_image = img.copy()
                    panel.page_index = page_idx
                    panel.panel_index = len(st.session_state.manual_panels)
                    st.session_state.manual_panels.append(panel)
                    st.session_state.click_x = new_x
                    st.session_state.click_y = new_y
                    st.success(f"Panel {len(st.session_state.manual_panels)} added!")
                    st.rerun()
            
            # Preview section below
            if show_preview or st.session_state.manual_panels:
                st.markdown("**Preview:**")
                viz_img = img.copy()
                colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), 
                          (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 165, 0)]
                
                # Draw existing panels
                page_panels = [(i, p) for i, p in enumerate(st.session_state.manual_panels) if p.page_index == page_idx]
                for list_idx, (panel_idx, panel) in enumerate(page_panels):
                    color = colors[panel_idx % len(colors)]
                    cv2.rectangle(viz_img, (panel.x, panel.y),
                                 (panel.x + panel.width, panel.y + panel.height),
                                 color, 3)
                    cv2.putText(viz_img, str(panel_idx + 1), (panel.x + 5, panel.y + 25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                
                # Draw preview of new panel
                if show_preview:
                    cv2.rectangle(viz_img, (new_x, new_y),
                                 (new_x + new_w, new_y + new_h), (0, 255, 0), 2)
                    cv2.putText(viz_img, "NEW", (new_x + 5, new_y + 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                st.image(viz_img, use_column_width=True)
            
            # Panel management section
            if st.session_state.manual_panels:
                st.markdown("**Manage panels:**")
                
                # Select panel to edit
                page_panel_indices = [i for i, p in enumerate(st.session_state.manual_panels) if p.page_index == page_idx]
                
                if page_panel_indices:
                    edit_options = [f"Panel {i+1}" for i in page_panel_indices]
                    selected_edit = st.selectbox("Select panel to edit", ["None"] + edit_options)
                    
                    if selected_edit != "None":
                        edit_idx = int(selected_edit.split()[1]) - 1
                        panel = st.session_state.manual_panels[edit_idx]
                        
                        st.markdown(f"**Editing Panel {edit_idx + 1}:**")
                        
                        edit_x = st.slider("X", 0, img_w, panel.x, key=f"edit_x_{edit_idx}")
                        edit_y = st.slider("Y", 0, img_h, panel.y, key=f"edit_y_{edit_idx}")
                        edit_w = st.slider("Width", 10, img_w, panel.width, key=f"edit_w_{edit_idx}")
                        edit_h = st.slider("Height", 10, img_h, panel.height, key=f"edit_h_{edit_idx}")
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("💾 Save", key=f"save_{edit_idx}"):
                                panel.x = edit_x
                                panel.y = edit_y
                                panel.width = edit_w
                                panel.height = edit_h
                                st.success("Updated!")
                                st.rerun()
                        with c2:
                            if st.button("🗑️ Delete", key=f"del_{edit_idx}"):
                                st.session_state.manual_panels.pop(edit_idx)
                                # Reindex
                                for i, p in enumerate(st.session_state.manual_panels):
                                    p.panel_index = i
                                st.rerun()
            
            # Global controls
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🗑️ Clear All Pages"):
                    st.session_state.manual_panels = []
                    st.success("All panels cleared")
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear This Page"):
                    st.session_state.manual_panels = [p for p in st.session_state.manual_panels if p.page_index != page_idx]
                    for i, p in enumerate(st.session_state.manual_panels):
                        p.panel_index = i
                    st.rerun()
            with col3:
                if st.button("✅ Use Manual Panels", type="primary") and st.session_state.manual_panels:
                    st.session_state.detected_panels = st.session_state.manual_panels.copy()
                    st.session_state.panel_order = list(range(len(st.session_state.manual_panels)))
                    st.success(f"Using {len(st.session_state.detected_panels)} panels")
            
            # List all panels
            if st.session_state.manual_panels:
                st.markdown("**All panels:**")
                for i, panel in enumerate(st.session_state.manual_panels):
                    page_str = f"Page {panel.page_index + 1}" if panel.page_index is not None else "Unknown"
                    st.markdown(f"{i+1}. ({panel.x}, {panel.y}) {panel.width}x{panel.height} — {page_str}")
    
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
