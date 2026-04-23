import streamlit as st
import streamlit.components.v1 as components
import base64
import json
import numpy as np
from PIL import Image
import io


def render_react_panel_editor(image: np.ndarray, panels: list, page_idx: int, react_app_url: str = "http://localhost:5173"):
    """
    Render React panel editor with auto-sync via HTTP.
    """
    
    # Convert image to base64
    if len(image.shape) == 3:
        if image.shape[2] == 3:
            img_rgb = image[:, :, ::-1]
        elif image.shape[2] == 4:
            img_rgb = image[:, :, ::-1]
        else:
            img_rgb = image
    else:
        img_rgb = image
        if len(img_rgb.shape) == 2:
            img_rgb = np.stack([img_rgb] * 3, axis=-1)
    
    pil_img = Image.fromarray(img_rgb)
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    # Current panels as JSON
    panels_data = [
        {'id': f'panel_{i}', 'x': int(panel.x), 'y': int(panel.y), 
         'width': int(panel.width), 'height': int(panel.height)}
        for i, panel in enumerate(panels)
    ]
    
    # HTML with iframe for React editor
    html = f"""
    <div>
        <iframe id="frame_{page_idx}" src="{react_app_url}" width="100%" height="600" frameborder="0"></iframe>
        
        <script>
            (function() {{
                const frame = document.getElementById('frame_{page_idx}');
                
                const initData = {{
                    type: 'INIT',
                    imageUrl: 'data:image/png;base64,{img_b64}',
                    panels: {json.dumps(panels_data)}
                }};
                
                frame.onload = () => {{
                    frame.contentWindow.postMessage(initData, '*');
                }};
                
                setTimeout(() => {{
                    if (frame.contentWindow) {{
                        frame.contentWindow.postMessage(initData, '*');
                    }}
                }}, 500);
            }})();
        </script>
    </div>
    """
    
    components.html(html, height=650)
    
    return None
