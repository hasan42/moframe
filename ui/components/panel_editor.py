import streamlit as st
import streamlit.components.v1 as components
import base64
import json
import numpy as np
from PIL import Image
import io


def render_react_panel_editor(image: np.ndarray, panels: list, page_idx: int, react_app_url: str = "http://localhost:3000"):
    """
    Render React panel editor with Apply button.
    Returns updated panels dict or None.
    """
    
    # Convert image to base64
    if len(image.shape) == 3:
        if image.shape[2] == 3:
            img_rgb = image[:, :, ::-1]  # BGR to RGB
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
    
    storage_key = f"panel_editor_{page_idx}"
    
    # Create two columns: editor and controls
    col_editor, col_controls = st.columns([4, 1])
    
    with col_editor:
        # HTML with iframe for React editor
        html = f"""
        <div>
            <iframe id="frame_{page_idx}" src="{react_app_url}" width="100%" height="850" frameborder="0"></iframe>
            
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
                    
                    window.addEventListener('message', (e) => {{
                        if (e.data.type === 'PANELS_APPLY') {{
                            localStorage.setItem('{storage_key}', JSON.stringify(e.data.panels));
                            // Show visual notification
                            const notif = document.createElement('div');
                            notif.textContent = '✓ Changes saved! Click "Load" button.';
                            notif.style.cssText = 'position:fixed;top:20px;right:20px;background:#4CAF50;color:white;padding:12px 20px;border-radius:5px;z-index:9999;font-weight:bold;box-shadow:0 2px 10px rgba(0,0,0,0.3);';
                            document.body.appendChild(notif);
                            setTimeout(() => notif.remove(), 4000);
                        }}
                    }});
                }})();
            </script>
        </div>
        """
        
        components.html(html, height=900)
    
    with col_controls:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Button to load updated panels from localStorage
        if st.button("🔄 Load Changes", key=f"load_{page_idx}", type="primary"):
            # JavaScript to extract from localStorage and update query params
            load_html = f"""
            <script>
                (function() {{
                    const data = localStorage.getItem('{storage_key}');
                    if (data) {{
                        // Update URL with panels data
                        const url = new URL(window.location);
                        url.searchParams.set('panels_{page_idx}', data);
                        window.history.replaceState({{}}, '', url);
                        localStorage.removeItem('{storage_key}');
                    }}
                }})();
            </script>
            """
            components.html(load_html, height=0)
            st.rerun()
    
    # Check for updated panels in query params
    query_key = f'panels_{page_idx}'
    if query_key in st.query_params:
        try:
            updated_data = json.loads(st.query_params[query_key])
            # Clear from query params
            del st.query_params[query_key]
            return updated_data
        except:
            pass
    
    return None
