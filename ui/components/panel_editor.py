import streamlit as st
import streamlit.components.v1 as components
import base64
import json
import numpy as np
from PIL import Image
import io


def render_react_panel_editor(image: np.ndarray, panels: list, page_idx: int, react_app_url: str = "http://localhost:3000"):
    """
    Render React panel editor.
    Uses a simple approach: React editor shows JSON, user copies it to text area.
    """
    
    # Session state key for result
    result_key = f"panel_editor_result_{page_idx}"
    
    # Check if we have pasted data
    if result_key in st.session_state and st.session_state[result_key]:
        try:
            data = json.loads(st.session_state[result_key])
            # Clear it
            st.session_state[result_key] = ""
            return data
        except:
            pass
    
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
    
    # Create columns
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
                }})();
            </script>
        </div>
        """
        
        components.html(html, height=900)
    
    with col_controls:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Instructions
        st.info("1️⃣ Edit panels in canvas\\n2️⃣ Click '📋 Copy JSON' in canvas\\n3️⃣ Paste below and click 'Apply'")
        
        # Text area for pasted JSON
        pasted_data = st.text_area(
            "Paste panel JSON here:",
            key=f"panel_paste_{page_idx}",
            height=100,
            placeholder='[{\"id\": \"panel_0\", \"x\": 100, \"y\": 100, \"width\": 200, \"height\": 300}, ...]'
        )
        
        if st.button("✅ Apply Changes", key=f"apply_{page_idx}", type="primary", use_container_width=True):
            if pasted_data:
                try:
                    data = json.loads(pasted_data)
                    st.session_state[result_key] = pasted_data
                    st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")
            else:
                st.warning("Please paste the JSON data from the canvas editor")
    
    return None
