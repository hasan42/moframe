"""
Interactive panel editor using HTML Canvas with drag-drop and resize.
"""

import streamlit as st
import json
import base64
import numpy as np

def panel_editor(image: np.ndarray, panels: list, key: str = "panel_editor"):
    """
    Render interactive canvas for panel editing.
    
    Args:
        image: numpy array (H, W, 3)
        panels: list of dicts with 'x', 'y', 'width', 'height', 'label'
        key: unique key for component
        
    Returns:
        Updated panels list or None if no change
    """
    img_h, img_w = image.shape[:2]
    
    # Convert image to base64
    from PIL import Image
    import io
    pil_img = Image.fromarray(image)
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    # Panels as JSON
    panels_json = json.dumps(panels)
    
    # HTML/JS component
    html = f"""
    <style>
        #canvas-container-{{key}} {{
            position: relative;
            display: inline-block;
            border: 2px solid #333;
        }}
        #panel-canvas-{{key}} {{
            cursor: crosshair;
            display: block;
        }}
        .panel-label {{
            position: absolute;
            background: rgba(255,255,255,0.8);
            padding: 2px 6px;
            font-size: 12px;
            border-radius: 3px;
            pointer-events: none;
            font-weight: bold;
        }}
    </style>
    <div id="canvas-container-{{key}}">
        <canvas id="panel-canvas-{{key}}" width="{img_w}" height="{img_h}"></canvas>
    </div>
    <div style="margin-top: 10px; font-size: 14px;">
        <b>Controls:</b> Drag center to move | Drag corners/sides to resize | Double-click to delete
    </div>
    <input type="hidden" id="panels-data-{{key}}" value='{panels_json}'>
    <input type="hidden" id="output-data-{{key}}" name="output_{{key}}">
    
    <script>
        (function() {{
            const canvas = document.getElementById('panel-canvas-{{key}}');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            img.src = 'data:image/png;base64,{img_b64}';
            
            let panels = JSON.parse(document.getElementById('panels-data-{{key}}').value);
            let selectedPanel = null;
            let resizeHandle = null;  // 'nw', 'ne', 'sw', 'se', 'n', 's', 'e', 'w', 'move'
            let startX, startY;
            let startPanel = null;
            
            const HANDLE_SIZE = 8;
            const MIN_SIZE = 20;
            
            const colors = [
                '#FF0000', '#00FF00', '#0000FF', '#FFFF00', 
                '#FF00FF', '#00FFFF', '#800080', '#FFA500'
            ];
            
            img.onload = function() {{
                draw();
            }};
            
            function draw() {{
                // Clear and draw image
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0);
                
                // Draw panels
                panels.forEach((panel, idx) => {{
                    const color = colors[idx % colors.length];
                    ctx.strokeStyle = color;
                    ctx.lineWidth = 3;
                    ctx.strokeRect(panel.x, panel.y, panel.width, panel.height);
                    
                    // Draw label
                    ctx.fillStyle = color;
                    ctx.font = 'bold 16px Arial';
                    ctx.fillText(panel.label || String(idx + 1), panel.x + 5, panel.y + 20);
                    
                    // Draw resize handles if selected
                    if (panel === selectedPanel) {{
                        ctx.fillStyle = '#fff';
                        ctx.strokeStyle = '#000';
                        ctx.lineWidth = 1;
                        
                        // Corner handles
                        const handles = [
                            {{x: panel.x, y: panel.y, type: 'nw'}},
                            {{x: panel.x + panel.width, y: panel.y, type: 'ne'}},
                            {{x: panel.x, y: panel.y + panel.height, type: 'sw'}},
                            {{x: panel.x + panel.width, y: panel.y + panel.height, type: 'se'}}
                        ];
                        
                        handles.forEach(h => {{
                            ctx.fillRect(h.x - HANDLE_SIZE/2, h.y - HANDLE_SIZE/2, HANDLE_SIZE, HANDLE_SIZE);
                            ctx.strokeRect(h.x - HANDLE_SIZE/2, h.y - HANDLE_SIZE/2, HANDLE_SIZE, HANDLE_SIZE);
                        }});
                    }}
                }});
            }}
            
            function getHandleAt(x, y, panel) {{
                const handles = [
                    {{x: panel.x, y: panel.y, type: 'nw'}},
                    {{x: panel.x + panel.width, y: panel.y, type: 'ne'}},
                    {{x: panel.x, y: panel.y + panel.height, type: 'sw'}},
                    {{x: panel.x + panel.width, y: panel.y + panel.height, type: 'se'}}
                ];
                
                for (let h of handles) {{
                    if (Math.abs(x - h.x) <= HANDLE_SIZE && Math.abs(y - h.y) <= HANDLE_SIZE) {{
                        return h.type;
                    }}
                }}
                
                // Check if inside panel (for move)
                if (x >= panel.x && x <= panel.x + panel.width &&
                    y >= panel.y && y <= panel.y + panel.height) {{
                    return 'move';
                }}
                
                return null;
            }}
            
            canvas.addEventListener('mousedown', function(e) {{
                const rect = canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) * (canvas.width / rect.width);
                const y = (e.clientY - rect.top) * (canvas.height / rect.height);
                
                // Check panels in reverse order (top first)
                for (let i = panels.length - 1; i >= 0; i--) {{
                    const handle = getHandleAt(x, y, panels[i]);
                    if (handle) {{
                        selectedPanel = panels[i];
                        resizeHandle = handle;
                        startX = x;
                        startY = y;
                        startPanel = {{...panels[i]}};
                        draw();
                        return;
                    }}
                }}
                
                selectedPanel = null;
                draw();
            }});
            
            canvas.addEventListener('mousemove', function(e) {{
                if (!selectedPanel || !resizeHandle) return;
                
                const rect = canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) * (canvas.width / rect.width);
                const y = (e.clientY - rect.top) * (canvas.height / rect.height);
                
                const dx = x - startX;
                const dy = y - startY;
                
                if (resizeHandle === 'move') {{
                    selectedPanel.x = Math.max(0, Math.min(canvas.width - selectedPanel.width, startPanel.x + dx));
                    selectedPanel.y = Math.max(0, Math.min(canvas.height - selectedPanel.height, startPanel.y + dy));
                }} else {{
                    // Resize
                    if (resizeHandle.includes('e')) {{
                        selectedPanel.width = Math.max(MIN_SIZE, startPanel.width + dx);
                    }}
                    if (resizeHandle.includes('w')) {{
                        const newWidth = Math.max(MIN_SIZE, startPanel.width - dx);
                        const widthDiff = selectedPanel.width - newWidth;
                        selectedPanel.width = newWidth;
                        selectedPanel.x = startPanel.x + widthDiff;
                    }}
                    if (resizeHandle.includes('s')) {{
                        selectedPanel.height = Math.max(MIN_SIZE, startPanel.height + dy);
                    }}
                    if (resizeHandle.includes('n')) {{
                        const newHeight = Math.max(MIN_SIZE, startPanel.height - dy);
                        const heightDiff = selectedPanel.height - newHeight;
                        selectedPanel.height = newHeight;
                        selectedPanel.y = startPanel.y + heightDiff;
                    }}
                }}
                
                draw();
            }});
            
            canvas.addEventListener('mouseup', function() {{
                if (selectedPanel) {{
                    // Send data back to Streamlit
                    document.getElementById('output-data-{{key}}').value = JSON.stringify(panels);
                }}
                resizeHandle = null;
            }});
            
            canvas.addEventListener('dblclick', function(e) {{
                const rect = canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left) * (canvas.width / rect.width);
                const y = (e.clientY - rect.top) * (canvas.height / rect.height);
                
                // Find and delete panel
                for (let i = panels.length - 1; i >= 0; i--) {{
                    const p = panels[i];
                    if (x >= p.x && x <= p.x + p.width && y >= p.y && y <= p.y + p.height) {{
                        panels.splice(i, 1);
                        selectedPanel = null;
                        draw();
                        document.getElementById('output-data-{{key}}').value = JSON.stringify(panels);
                        return;
                    }}
                }}
            }});
            
            // Initial draw
            img.onload();
        }})();
    </script>
    """
    
    # Replace key placeholder
    html = html.replace('{{key}}', key.replace('-', '_'))
    
    # Render component
    import streamlit.components.v1 as components
    components.html(html, height=img_h + 60, scrolling=False)
    
    # Return panels (in real implementation would get from JS via session state)
    return None
