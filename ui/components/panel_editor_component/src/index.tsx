import React, { useEffect, useRef, useState, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { Streamlit, withStreamlitConnection } from 'streamlit-component-lib';

interface Panel {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface ComponentProps {
  args: {
    imageUrl: string;
    panels: Panel[];
    pageIdx: number;
  };
}

const HANDLE_SIZE = 10;
const MIN_SIZE = 30;

const PanelEditor: React.FC<ComponentProps> = (props) => {
  const { args } = props;
  const imageUrl = args.imageUrl;
  const initialPanels = args.panels || [];
  const pageIdx = args.pageIdx;

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [localPanels, setLocalPanels] = useState<Panel[]>(initialPanels);
  const [dragState, setDragState] = useState<any>(null);
  const [hoveredPanel, setHoveredPanel] = useState<string | null>(null);

  useEffect(() => {
    setLocalPanels(initialPanels);
  }, [initialPanels]);

  useEffect(() => {
    if (imageUrl) {
      const img = new Image();
      img.src = imageUrl;
      img.onload = () => setImage(img);
    }
  }, [imageUrl]);

  useEffect(() => {
    Streamlit.setFrameHeight();
  }, []);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = image.width;
    canvas.height = image.height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0);

    const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff'];
    localPanels.forEach((panel, i) => {
      const color = colors[i % colors.length];
      const isHovered = panel.id === hoveredPanel;
      const isSelected = dragState?.panelId === panel.id;

      ctx.strokeStyle = color;
      ctx.lineWidth = isHovered || isSelected ? 4 : 2;
      ctx.strokeRect(panel.x, panel.y, panel.width, panel.height);
      ctx.fillStyle = color + '1A';
      ctx.fillRect(panel.x, panel.y, panel.width, panel.height);
      ctx.fillStyle = color;
      ctx.font = 'bold 16px Arial';
      ctx.fillText(String(i + 1), panel.x + 5, panel.y + 20);

      if (isHovered || isSelected) {
        ctx.fillStyle = '#fff';
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 1;
        const corners = [
          [panel.x, panel.y],
          [panel.x + panel.width, panel.y],
          [panel.x, panel.y + panel.height],
          [panel.x + panel.width, panel.y + panel.height]
        ];
        corners.forEach(([cx, cy]) => {
          ctx.fillRect(cx - HANDLE_SIZE / 2, cy - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
          ctx.strokeRect(cx - HANDLE_SIZE / 2, cy - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
        });
      }
    });
  }, [image, localPanels, hoveredPanel, dragState]);

  useEffect(() => { draw(); }, [draw]);

  const getCanvasPos = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY
    };
  };

  const getHandle = (x: number, y: number, panel: Panel) => {
    const corners: [number, number, string][] = [
      [panel.x, panel.y, 'nw'],
      [panel.x + panel.width, panel.y, 'ne'],
      [panel.x, panel.y + panel.height, 'sw'],
      [panel.x + panel.width, panel.y + panel.height, 'se']
    ];
    for (const [cx, cy, type] of corners) {
      if (Math.abs(x - cx) < HANDLE_SIZE && Math.abs(y - cy) < HANDLE_SIZE) return type;
    }
    return null;
  };

  const isInsidePanel = (x: number, y: number, panel: Panel) => {
    return x >= panel.x && x <= panel.x + panel.width && y >= panel.y && y <= panel.y + panel.height;
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    const { x, y } = getCanvasPos(e);
    for (let i = localPanels.length - 1; i >= 0; i--) {
      const panel = localPanels[i];
      const handle = getHandle(x, y, panel);
      if (handle) {
        setDragState({ panelId: panel.id, action: 'resize', handle, startX: x, startY: y, startPanel: { ...panel } });
        return;
      }
      if (isInsidePanel(x, y, panel)) {
        setDragState({ panelId: panel.id, action: 'move', handle: null, startX: x, startY: y, startPanel: { ...panel } });
        return;
      }
    }
    const newPanel: Panel = { id: `panel_${Date.now()}`, x: x - 50, y: y - 50, width: 100, height: 100 };
    setLocalPanels([...localPanels, newPanel]);
    Streamlit.setComponentValue({ pageIdx, panels: [...localPanels, newPanel], action: 'add' });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const { x, y } = getCanvasPos(e);
    if (!dragState?.panelId || !dragState?.startPanel) {
      for (let i = localPanels.length - 1; i >= 0; i--) {
        const panel = localPanels[i];
        if (isInsidePanel(x, y, panel) || getHandle(x, y, panel)) {
          setHoveredPanel(panel.id);
          return;
        }
      }
      setHoveredPanel(null);
      return;
    }

    const dx = x - dragState.startX;
    const dy = y - dragState.startY;
    const startPanel = dragState.startPanel;
    const canvas = canvasRef.current;

    const newPanels = localPanels.map((p) => {
      if (p.id !== dragState.panelId) return p;
      if (dragState.action === 'move') {
        return {
          ...p,
          x: Math.max(0, Math.min((canvas?.width || 0) - p.width, startPanel.x + dx)),
          y: Math.max(0, Math.min((canvas?.height || 0) - p.height, startPanel.y + dy))
        };
      }
      if (dragState.action === 'resize' && dragState.handle) {
        let newPanel = { ...p };
        if (dragState.handle.includes('e')) newPanel.width = Math.max(MIN_SIZE, startPanel.width + dx);
        if (dragState.handle.includes('w')) {
          const nw = Math.max(MIN_SIZE, startPanel.width - dx);
          newPanel.x = startPanel.x + (startPanel.width - nw);
          newPanel.width = nw;
        }
        if (dragState.handle.includes('s')) newPanel.height = Math.max(MIN_SIZE, startPanel.height + dy);
        if (dragState.handle.includes('n')) {
          const nh = Math.max(MIN_SIZE, startPanel.height - dy);
          newPanel.y = startPanel.y + (startPanel.height - nh);
          newPanel.height = nh;
        }
        return newPanel;
      }
      return p;
    });
    setLocalPanels(newPanels);
  };

  const handleMouseUp = () => {
    setDragState(null);
    Streamlit.setComponentValue({ pageIdx, panels: localPanels, action: 'update' });
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    const { x, y } = getCanvasPos(e);
    for (let i = localPanels.length - 1; i >= 0; i--) {
      const panel = localPanels[i];
      if (isInsidePanel(x, y, panel)) {
        const newPanels = localPanels.filter((p) => p.id !== panel.id);
        setLocalPanels(newPanels);
        Streamlit.setComponentValue({ pageIdx, panels: newPanels, action: 'delete' });
        return;
      }
    }
  };

  if (!image) return <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>Loading...</div>;

  return (
    <div style={{ display: 'inline-block' }}>
      <canvas
        ref={canvasRef}
        style={{
          border: '2px solid #333',
          cursor: dragState?.panelId ? 'grabbing' : hoveredPanel ? 'grab' : 'crosshair',
          maxWidth: '100%',
          height: 'auto'
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onDoubleClick={handleDoubleClick}
      />
      <div style={{ marginTop: '8px', fontSize: '13px', color: '#666' }}>
        🖱️ Drag to move | Drag corners to resize | Double-click to delete | Click empty space to add
      </div>
      <div style={{ marginTop: '8px', fontSize: '14px', color: '#4CAF50' }}>
        ✅ Auto-sync enabled — changes saved automatically
      </div>
    </div>
  );
};

const App = withStreamlitConnection(PanelEditor);
ReactDOM.render(<App />, document.getElementById('root'));
