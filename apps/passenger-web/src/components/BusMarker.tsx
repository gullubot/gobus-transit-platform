import { Marker } from 'react-leaflet';
import L from 'leaflet';
import { renderToStaticMarkup } from 'react-dom/server';
import { Bus } from 'lucide-react';

interface BusMarkerProps {
  position: [number, number];
  isSelected: boolean;
  onClick: () => void;
}

export default function BusMarker({ position, isSelected, onClick }: BusMarkerProps) {
  const iconHtml = renderToStaticMarkup(
    <div className={`bus-marker-icon ${isSelected ? 'bus-marker-icon--selected' : ''}`}>
      <div className="bus-marker-icon__inner">
        <Bus size={isSelected ? 18 : 14} color="#ffffff" />
      </div>
    </div>
  );

  const icon = L.divIcon({
    html: iconHtml,
    className: '', // Clear default leaflet class to avoid styling conflicts
    iconSize: isSelected ? [36, 36] : [28, 28],
    iconAnchor: isSelected ? [18, 18] : [14, 14],
  });

  return (
    <Marker 
      position={position} 
      icon={icon} 
      eventHandlers={{ click: onClick }}
      zIndexOffset={isSelected ? 1000 : 100} // Ensure selected marker is on top
    />
  );
}
