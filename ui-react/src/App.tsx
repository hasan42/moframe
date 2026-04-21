import { useState, useEffect } from 'react';
import { PanelEditor } from './PanelEditor';

interface Panel {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

function App() {
  const [imageUrl, setImageUrl] = useState<string>('');
  const [panels, setPanels] = useState<Panel[]>([]);
  const [isReady, setIsReady] = useState(false);

  // Listen for messages from parent (Streamlit)
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data.type === 'INIT') {
        setImageUrl(event.data.imageUrl);
        setPanels(event.data.panels || []);
        setIsReady(true);
      }
    };

    window.addEventListener('message', handleMessage);
    
    // Notify parent that we're ready
    window.parent.postMessage({ type: 'EDITOR_READY' }, '*');

    return () => window.removeEventListener('message', handleMessage);
  }, []);

  // Send updates to parent
  const handlePanelsChange = (newPanels: Panel[]) => {
    setPanels(newPanels);
    window.parent.postMessage({
      type: 'PANELS_UPDATED',
      panels: newPanels
    }, '*');
  };

  if (!isReady) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        fontFamily: 'sans-serif'
      }}>
        <div>Loading editor...</div>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <PanelEditor 
        imageUrl={imageUrl} 
        panels={panels} 
        onPanelsChange={handlePanelsChange} 
      />
    </div>
  );
}

export default App;