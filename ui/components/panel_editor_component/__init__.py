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

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_BUILD_DIR = os.path.join(_BASE_DIR, 'build')


def panel_editor_component(image: np.ndarray, panels: list, page_idx: int, key: str = None):
    """Render the MoFrame Panel Editor component."""
    
    if len(image.shape) == 3:
        img_rgb = image[:, :, ::-1] if image.shape[2] in [3, 4] else image
    else:
        img_rgb = np.stack([image] * 3, axis=-1) if len(image.shape) == 2 else image
    
    pil_img = Image.fromarray(img_rgb)
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    panels_data = [
        {'id': f'panel_{i}_{id(panel)}', 'x': int(panel.x), 'y': int(panel.y), 'width': int(panel.width), 'height': int(panel.height)}
        for i, panel in enumerate(panels)
    ]
    
    component_args = {'imageUrl': f'data:image/png;base64,{img_b64}', 'panels': panels_data, 'pageIdx': page_idx}
    
    if not os.path.exists(os.path.join(_BUILD_DIR, 'static', 'js', 'main.js')):
        return _render_fallback_editor(image, panels, page_idx, key)
    
    _component_func = components.declare_component('moframe_panel_editor', path=_BUILD_DIR)
    result = _component_func(**component_args, key=key, default=None)
    
    if result and isinstance(result, dict) and 'panels' in result:
        return result['panels']
    return None


def _render_fallback_editor(image, panels, page_idx, key):
    """Fallback when component build is not available."""
    import streamlit as st
    st.warning("⚠️ Panel Editor component not built. Run `npm install && npm run build` in component directory.")
    img_h, img_w = image.shape[:2]
    for i, panel in enumerate(panels):
        col1, col2 = st.columns(2)
        with col1:
            new_x = st.number_input(f"X{i}", 0, img_w, int(panel.x), key=f"x_fb_{page_idx}_{i}")
            new_y = st.number_input(f"Y{i}", 0, img_h, int(panel.y), key=f"y_fb_{page_idx}_{i}")
        with col2:
            new_w = st.number_input(f"W{i}", 10, img_w, int(panel.width), key=f"w_fb_{page_idx}_{i}")
            new_h = st.number_input(f"H{i}", 10, img_h, int(panel.height), key=f"h_fb_{page_idx}_{i}")
        if any([new_x != panel.x, new_y != panel.y, new_w != panel.width, new_h != panel.height]):
            panel.x, panel.y, panel.width, panel.height = new_x, new_y, new_w, new_h
    return None


def render_panel_editor(image, panels, page_idx, key=None):
    """Render the panel editor and return updated panels."""
    return panel_editor_component(image, panels, page_idx, key=key)
