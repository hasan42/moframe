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
    if 'temp_dir' not in st.session_state:
        st.session_state.temp_dir = tempfile.mkdtemp()
    if 'rendering' not in st.session_state:
        st.session_state.rendering = False


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
    return all_panels


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
        
        # Detect panels button
        st.header("🔍 Detect Panels")
        
        if st.button("🔎 Detect Panels", type="primary"):
            with st.spinner("Analyzing pages..."):
                st.session_state.detected_panels = detect_panels(
                    st.session_state.loaded_images,
                    reading_order
                )
            
            if st.session_state.detected_panels:
                st.success(f"Found {len(st.session_state.detected_panels)} panels")
    
    # Display detected panels
    if st.session_state.detected_panels:
        st.header(f"🎨 Detected Panels ({len(st.session_state.detected_panels)})")
        
        # Show panel thumbnails
        cols = st.columns(4)
        for i, panel in enumerate(st.session_state.detected_panels[:12]):
            with cols[i % 4]:
                try:
                    panel_img = panel.extract_from_original()
                    panel_img = cv2.resize(panel_img, (200, 150))
                    st.image(panel_img, caption=f"Panel {i+1}")
                except Exception as e:
                    st.error(f"Error displaying panel {i+1}")
        
        if len(st.session_state.detected_panels) > 12:
            st.info(f"... and {len(st.session_state.detected_panels) - 12} more panels")
        
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
                    st.session_state.detected_panels,
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
