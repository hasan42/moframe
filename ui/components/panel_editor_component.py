"""
Streamlit component that embeds the React panel editor.
Communicates via iframe postMessage.
"""

import streamlit as st
import streamlit.components.v1 as components
import base64
import json
import numpy as np
from PIL import Image
from pathlib import Path


class PanelEditorComponent:
    """Embeds React panel editor in Streamlit."""
    
    def __init__(self, react_app_url: str = "http://localhost:3000"):
        self.react_app_url = react_app_url
    
    def render(self, image: np.ndarray, panels: list, key: str = "panel_editor"):
        """Render the panel editor and return updated panels."""
        
        # Convert image to base64
        if len(image.shape) == 3:
            if image.shape[2] == 3:
                # BGR to RGB
                img_rgb = image[:, :, ::-1]
            elif image.shape[2] == 4:
                # BGRA to RGBA
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
        
        # Convert panels to dict format for React
        panels_data = [
            {
                'id': f'panel_{i}_{id(panel)}',
                'x': panel.x,
                'y': panel.y,
                'width': panel.width,
                'height': panel.height
            }
            for i, panel in enumerate(panels)
        ]
        
        # Create HTML wrapper that loads React app and communicates via postMessage
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body, html {{
                    margin: 0;
                    padding: 0;
                    height: 100%;
                    overflow: hidden;
                }}
                #root {{
                    height: 100%;
                }}
                iframe {{
                    width: 100%;
                    height: 100%;
                    border: none;
                }}
            </style>
        </head>
        <body>
            <iframe id="editor-frame" src="{self.react_app_url}"></iframe>
            <script>
                // Store current panels
                window.currentPanels = {json.dumps(panels_data)};
                
                // Wait for iframe to load
                const iframe = document.getElementById('editor-frame');
                
                iframe.onload = function() {{
                    // Send init message to React
                    iframe.contentWindow.postMessage({{
                        type: 'INIT',
                        imageUrl: 'data:image/png;base64,{img_b64}',
                        panels: window.currentPanels
                    }}, '*');
                }};
                
                // Listen for messages from React
                window.addEventListener('message', function(e) {{
                    if (e.data.type === 'PANELS_UPDATED') {{
                        // Store updated panels
                        window.currentPanels = e.data.panels;
                        
                        // Send to Streamlit via Streamlit's API
                        if (window.parent && window.parent.postMessage) {{
                            window.parent.postMessage({{
                                type: 'streamlit:component:message',
                                key: '{key}',
                                data: {{
                                    panels: e.data.panels
                                }}
                            }}, '*');
                        }}
                    }} else if (e.data.type === 'EDITOR_READY') {{
                        // Resend init data if needed
                        if (window.currentPanels) {{
                            iframe.contentWindow.postMessage({{
                                type: 'INIT',
                                imageUrl: 'data:image/png;base64,{img_b64}',
                                panels: window.currentPanels
                            }}, '*');
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        # Render component
        components.html(html, height=800, key=key)
        
        # For now, return original panels (synchronous update)
        # In a full implementation, we'd use a callback or session state
        return panels


# Create singleton instance
panel_editor = PanelEditorComponent()


def render_panel_editor(image: np.ndarray, panels: list, key: str = "panel_editor"):
    """Render panel editor and return panels."""
    return panel_editor.render(image, panels, key)
