"""
MoFrame Panel Editor - Streamlit Custom Component
Interactive canvas editor for comic panels with auto-sync.
"""

import os
import streamlit.components.v1 as components
import base64
import json
import numpy as np
from PIL import Image
import io
import streamlit as st

# Build paths
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.join(_BASE_DIR, 'build')

# Check if build exists
_build_exists = os.path.exists(os.path.join(_BUILD_DIR, 'static', 'js', 'main.js'))

# Declare component once at module level (only if build exists)
_component_func = None
if _build_exists:
    try:
        _component_func = components.declare_component(
            "moframe_panel_editor",
            path=_BUILD_DIR
        )
    except Exception as e:
        st.error(f"Failed to declare component: {e}")
        _component_func = None


def panel_editor_component(image: np.ndarray, panels: list, page_idx: int, key: str = None):
    """Render the MoFrame Panel Editor component."""
    
    # Use fallback if component not available
    if _component_func is None:
        return _render_fallback_editor(image, panels, page_idx, key)
    
    # Convert image to base64
    if len(image.shape) == 3:
        img_rgb = image[:, :, ::-1] if image.shape[2] in [3, 4] else image
    else:
        img_rgb = np.stack([image] * 3, axis=-1) if len(image.shape) == 2 else image
    
    pil_img = Image.fromarray(img_rgb)
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    # Prepare panels data
    panels_data = [
        {
            'id': f'panel_{i}_{hash(str(panel.x) + str(panel.y))}',
            'x': int(panel.x),
            'y': int(panel.y),
            'width': int(panel.width),
            'height': int(panel.height)
        }
        for i, panel in enumerate(panels)
    ]
    
    component_args = {
        'imageUrl': f'data:image/png;base64,{img_b64}',
        'panels': panels_data,
        'pageIdx': page_idx
    }
    
    # Call component
    result = _component_func(**component_args, key=key, default=None)
    
    if result and isinstance(result, dict) and 'panels' in result:
        return result['panels']
    return None


def _render_fallback_editor(image, panels, page_idx, key):
    """Fallback when component build is not available."""
    st.warning("⚠️ Panel Editor component not available. Using fallback editor.")
    
    img_h, img_w = image.shape[:2]
    updated = False
    
    for i, panel in enumerate(panels):
        cols = st.columns(4)
        with cols[0]:
            new_x = st.number_input(f"X", 0, img_w, int(panel.x), key=f"x_fb_{page_idx}_{i}")
        with cols[1]:
            new_y = st.number_input(f"Y", 0, img_h, int(panel.y), key=f"y_fb_{page_idx}_{i}")
        with cols[2]:
            new_w = st.number_input(f"W", 10, img_w, int(panel.width), key=f"w_fb_{page_idx}_{i}")
        with cols[3]:
            new_h = st.number_input(f"H", 10, img_h, int(panel.height), key=f"h_fb_{page_idx}_{i}")
        
        if any([new_x != panel.x, new_y != panel.y, new_w != panel.width, new_h != panel.height]):
            panel.x, panel.y, panel.width, panel.height = new_x, new_y, new_w, new_h
            updated = True
    
    return panels if updated else None


def render_panel_editor(image, panels, page_idx, key=None):
    """Render the panel editor and return updated panels."""
    result = panel_editor_component(image, panels, page_idx, key=key)
    if result is not None:
        return result
    return panels
