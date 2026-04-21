import streamlit as st
import streamlit.components.v1 as components
import base64
import json
import numpy as np
from PIL import Image


def render_react_panel_editor(image: np.ndarray, panels: list, key: str = "panel_editor"):
    """
    Render React panel editor in Streamlit.
    Returns updated panels when Apply is clicked.
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
    import io
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    # Convert panels to dict format
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
    
    # Store panels in session state for this key
    session_key = f"react_editor_{key}"
    if session_key not in st.session_state:
        st.session_state[session_key] = {
            'image_url': f"data:image/png;base64,{img_b64}",
            'panels': panels_data,
            'applied': False
        }
    
    # Update image if changed
    st.session_state[session_key]['image_url'] = f"data:image/png;base64,{img_b64}"
    
    # HTML wrapper with React app
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
                overflow: hidden;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }}
        </style>
    </head>
    <body>
        <div id="root"></div>
        <script type="module">
            // Panel Editor React Component as vanilla JS
            const {{ useRef, useState, useEffect, useCallback }} = React;
            
            const HANDLE_SIZE = 10;
            const MIN_SIZE = 30;
            
            function PanelEditor({{ imageUrl, initialPanels }}) {{
                const canvasRef = useRef(null);
                const [image, setImage] = useState(null);
                const [panels, setPanels] = useState(initialPanels);
                const [dragState, setDragState] = useState({{
                    panelId: null,
                    action: null,
                    handle: null,
                    startX: 0,
                    startY: 0,
                    startPanel: null
                }});
                const [hoveredPanel, setHoveredPanel] = useState(null);
                
                // Load image
                useEffect(() => {{
                    const img = new Image();
                    img.src = imageUrl;
                    img.onload = () => setImage(img);
                }}, [imageUrl]);
                
                // Draw canvas
                const draw = useCallback(() => {{
                    const canvas = canvasRef.current;
                    if (!canvas || !image) return;
                    
                    const ctx = canvas.getContext('2d');
                    if (!ctx) return;
                    
                    canvas.width = image.width;
                    canvas.height = image.height;
                    
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(image, 0, 0);
                    
                    const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff'];
                    
                    panels.forEach((panel, i) => {{
                        const color = colors[i % colors.length];
                        const isHovered = panel.id === hoveredPanel;
                        const isSelected = panel.id === dragState.panelId;
                        
                        ctx.strokeStyle = color;
                        ctx.lineWidth = isHovered || isSelected ? 4 : 2;
                        ctx.strokeRect(panel.x, panel.y, panel.width, panel.height);
                        
                        ctx.fillStyle = color + '1A';
                        ctx.fillRect(panel.x, panel.y, panel.width, panel.height);
                        
                        ctx.fillStyle = color;
                        ctx.font = 'bold 16px Arial';
                        ctx.fillText(String(i + 1), panel.x + 5, panel.y + 20);
                        
                        if (isHovered || isSelected) {{
                            ctx.fillStyle = '#fff';
                            ctx.strokeStyle = '#000';
                            ctx.lineWidth = 1;
                            
                            const corners = [
                                [panel.x, panel.y],
                                [panel.x + panel.width, panel.y],
                                [panel.x, panel.y + panel.height],
                                [panel.x + panel.width, panel.y + panel.height]
                            ];
                            
                            corners.forEach(([cx, cy]) => {{
                                ctx.fillRect(cx - HANDLE_SIZE/2, cy - HANDLE_SIZE/2, HANDLE_SIZE, HANDLE_SIZE);
                                ctx.strokeRect(cx - HANDLE_SIZE/2, cy - HANDLE_SIZE/2, HANDLE_SIZE, HANDLE_SIZE);
                            }});
                        }}
                    }});
                }}, [image, panels, hoveredPanel, dragState.panelId]);
                
                useEffect(() => {{
                    draw();
                }}, [draw]);
                
                const getCanvasPos = (e) => {{
                    const canvas = canvasRef.current;
                    if (!canvas) return {{ x: 0, y: 0 }};
                    const rect = canvas.getBoundingClientRect();
                    const scaleX = canvas.width / rect.width;
                    const scaleY = canvas.height / rect.height;
                    return {{
                        x: (e.clientX - rect.left) * scaleX,
                        y: (e.clientY - rect.top) * scaleY
                    }};
                }};
                
                const getHandle = (x, y, panel) => {{
                    const corners = [
                        [panel.x, panel.y, 'nw'],
                        [panel.x + panel.width, panel.y, 'ne'],
                        [panel.x, panel.y + panel.height, 'sw'],
                        [panel.x + panel.width, panel.y + panel.height, 'se']
                    ];
                    for (const [cx, cy, type] of corners) {{
                        if (Math.abs(x - cx) < HANDLE_SIZE && Math.abs(y - cy) < HANDLE_SIZE) {{
                            return type;
                        }}
                    }}
                    return null;
                }};
                
                const isInsidePanel = (x, y, panel) => {{
                    return x >= panel.x && x <= panel.x + panel.width && y >= panel.y && y <= panel.y + panel.height;
                }};
                
                const handleMouseDown = (e) => {{
                    const {{ x, y }} = getCanvasPos(e);
                    
                    for (let i = panels.length - 1; i >= 0; i--) {{
                        const panel = panels[i];
                        const handle = getHandle(x, y, panel);
                        
                        if (handle) {{
                            setDragState({{
                                panelId: panel.id,
                                action: 'resize',
                                handle,
                                startX: x,
                                startY: y,
                                startPanel: {{ ...panel }}
                            }});
                            return;
                        }}
                        
                        if (isInsidePanel(x, y, panel)) {{
                            setDragState({{
                                panelId: panel.id,
                                action: 'move',
                                handle: null,
                                startX: x,
                                startY: y,
                                startPanel: {{ ...panel }}
                            }});
                            return;
                        }}
                    }}
                    
                    // Create new panel
                    const newPanel = {{
                        id: `panel_${{Date.now()}}`,
                        x: x - 50,
                        y: y - 50,
                        width: 100,
                        height: 100
                    }};
                    setPanels([...panels, newPanel]);
                }};
                
                const handleMouseMove = (e) => {{
                    const {{ x, y }} = getCanvasPos(e);
                    
                    if (!dragState.panelId || !dragState.startPanel) {{
                        for (let i = panels.length - 1; i >= 0; i--) {{
                            const panel = panels[i];
                            if (isInsidePanel(x, y, panel) || getHandle(x, y, panel)) {{
                                setHoveredPanel(panel.id);
                                return;
                            }}
                        }}
                        setHoveredPanel(null);
                        return;
                    }}
                    
                    const dx = x - dragState.startX;
                    const dy = y - dragState.startY;
                    const startPanel = dragState.startPanel;
                    const canvas = canvasRef.current;
                    
                    const newPanels = panels.map(p => {{
                        if (p.id !== dragState.panelId) return p;
                        
                        if (dragState.action === 'move') {{
                            return {{
                                ...p,
                                x: Math.max(0, Math.min(canvas.width - p.width, startPanel.x + dx)),
                                y: Math.max(0, Math.min(canvas.height - p.height, startPanel.y + dy))
                            }};
                        }}
                        
                        if (dragState.action === 'resize' && dragState.handle) {{
                            let newP = {{ ...p }};
                            if (dragState.handle.includes('e')) newP.width = Math.max(MIN_SIZE, startPanel.width + dx);
                            if (dragState.handle.includes('w')) {{
                                const nw = Math.max(MIN_SIZE, startPanel.width - dx);
                                newP.x = startPanel.x + (startPanel.width - nw);
                                newP.width = nw;
                            }}
                            if (dragState.handle.includes('s')) newP.height = Math.max(MIN_SIZE, startPanel.height + dy);
                            if (dragState.handle.includes('n')) {{
                                const nh = Math.max(MIN_SIZE, startPanel.height - dy);
                                newP.y = startPanel.y + (startPanel.height - nh);
                                newP.height = nh;
                            }}
                            return newP;
                        }}
                        
                        return p;
                    }});
                    
                    setPanels(newPanels);
                }};
                
                const handleMouseUp = () => {{
                    setDragState({{ panelId: null, action: null, handle: null, startX: 0, startY: 0, startPanel: null }});
                }};
                
                const handleDoubleClick = (e) => {{
                    const {{ x, y }} = getCanvasPos(e);
                    for (let i = panels.length - 1; i >= 0; i--) {{
                        const panel = panels[i];
                        if (isInsidePanel(x, y, panel)) {{
                            setPanels(panels.filter(p => p.id !== panel.id));
                            return;
                        }}
                    }}
                }};
                
                const handleApply = () => {{
                    window.parent.postMessage({{
                        type: 'PANELS_UPDATED',
                        key: '{key}',
                        panels: panels
                    }}, '*');
                }};
                
                if (!image) return React.createElement('div', null, 'Loading...');
                
                return React.createElement('div', {{ style: {{ display: 'inline-block' }} }},
                    React.createElement('canvas', {{
                        ref: canvasRef,
                        style: {{
                            border: '2px solid #333',
                            cursor: dragState.panelId ? 'grabbing' : hoveredPanel ? 'grab' : 'crosshair',
                            maxWidth: '100%',
                            height: 'auto'
                        }},
                        onMouseDown: handleMouseDown,
                        onMouseMove: handleMouseMove,
                        onMouseUp: handleMouseUp,
                        onMouseLeave: handleMouseUp,
                        onDoubleClick: handleDoubleClick
                    }}),
                    React.createElement('div', {{ style: {{ marginTop: '8px', fontSize: '13px', color: '#666' }} }},
                        '🖱️ Drag to move | Drag corners to resize | Double-click to delete | Click empty space to add'
                    ),
                    React.createElement('div', {{ style: {{ marginTop: '16px' }} }},
                        React.createElement('button', {{
                            onClick: handleApply,
                            style: {{
                                padding: '10px 24px',
                                fontSize: '16px',
                                backgroundColor: '#4CAF50',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontWeight: 'bold'
                            }}
                        }}, '✅ Apply Changes'),
                        React.createElement('span', {{ style: {{ marginLeft: '12px', color: '#666', fontSize: '14px' }} }},
                            panels.length + ' panels'
                        )
                    )
                );
            }}
            
            // Render app
            const root = ReactDOM.createRoot(document.getElementById('root'));
            root.render(React.createElement(PanelEditor, {{
                imageUrl: '{st.session_state[session_key]["image_url"]}',
                initialPanels: {json.dumps(st.session_state[session_key]['panels'])}
            }}));
        </script>
        <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
        <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
        <script>
            // Listen for messages from iframe
            window.addEventListener('message', function(e) {{
                if (e.data.type === 'PANELS_UPDATED' && e.data.key === '{key}') {{
                    // Store in sessionStorage for Streamlit to read
                    sessionStorage.setItem('panels_{key}', JSON.stringify(e.data.panels));
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    # Render component
    result = components.html(html, height=900, key=key)
    
    # Check if we have updated panels from sessionStorage via JavaScript
    # This requires a second component to read the result
    return None  # Will be handled by separate callback


def get_updated_panels(key: str = "panel_editor") -> list:
    """Get updated panels from React editor (call after render)."""
    # This would require a custom Streamlit component
    # For now, we'll use a workaround with session state
    session_key = f"react_editor_{key}"
    if session_key in st.session_state and st.session_state[session_key].get('applied'):
        panels_data = st.session_state[session_key]['panels']
        # Convert back to Panel objects
        from core.panel_detector import Panel
        return [
            Panel(p['x'], p['y'], p['width'], p['height'])
            for p in panels_data
        ]
    return None
