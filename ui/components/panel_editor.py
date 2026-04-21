import streamlit as st
import streamlit.components.v1 as components
import base64
import json
import numpy as np
from PIL import Image


def render_react_panel_editor(image: np.ndarray, panels: list, page_idx: int, react_app_url: str = "http://localhost:3000"):
    """
    Render React panel editor.
    Returns list of panels or None if not updated yet.
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
    import io
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    panels_data = [
        {'id': f'panel_{i}', 'x': int(panel.x), 'y': int(panel.y), 
         'width': int(panel.width), 'height': int(panel.height)}
        for i, panel in enumerate(panels)
    ]
    
    editor_key = f"editor_{page_idx}"
    storage_key = f"panel_editor_{page_idx}"
    
    # JavaScript to read from localStorage and send back
    html = f"""
    <div>
        <iframe id="frame_{page_idx}" src="{react_app_url}" width="100%" height="850" frameborder="0"></iframe>
        
        <script>
            // Send init data to iframe
            const frame = document.getElementById('frame_{page_idx}');
            const initData = {{
                type: 'INIT',
                imageUrl: 'data:image/png;base64,{img_b64}',
                panels: {json.dumps(panels_data)}
            }};
            
            frame.onload = () => {{
                frame.contentWindow.postMessage(initData, '*');
            }};
            
            // Retry after delay
            setTimeout(() => {{
                frame.contentWindow.postMessage(initData, '*');
            }}, 1000);
            
            // Listen for Apply
            window.addEventListener('message', (e) => {{
                if (e.data.type === 'PANELS_APPLY') {{
                    localStorage.setItem('{storage_key}', JSON.stringify(e.data.panels));
                    // Force reload to pick up changes
                    window.location.reload();
                }}
            }});
        </script>
        
        <script>
            // Read from localStorage and update Streamlit
            const stored = localStorage.getItem('{storage_key}');
            if (stored) {{
                // Send to Streamlit
                window.parent.postMessage({{
                    type: 'streamlit:setComponentValue',
                    value: JSON.stringify({{
                        key: '{editor_key}',
                        data: JSON.parse(stored)
                    }})
                }}, '*');
                // Clear storage
                localStorage.removeItem('{storage_key}');
            }}
        </script>
    </div>
    """
    
    components.html(html, height=900, key=editor_key)
    
    # Check session state for result
    result_key = f"{editor_key}_panels"
    if result_key in st.session_state:
        result = st.session_state[result_key]
        del st.session_state[result_key]
        return result
    
    return None
