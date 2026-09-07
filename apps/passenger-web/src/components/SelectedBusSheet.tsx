import { Clock, Navigation, X, RefreshCw } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface SelectedBusSheetProps {
  bus: {
    vehicle_id: string;
    eta_seconds: number | null;
    eta_status: string | null;
    crowd_level: string;
    state: string;
    last_updated_at: string | null;
  };
  serviceName: string;
  direction: string;
  onClose: () => void;
}

export default function SelectedBusSheet({ bus, serviceName, direction, onClose }: SelectedBusSheetProps) {
  let etaText = 'ETA Unknown';
  let etaClass = '';
  if (bus.eta_seconds !== null) {
    const mins = Math.round(bus.eta_seconds / 60);
    if (mins <= 0) etaText = 'Due now';
    else etaText = `Arriving in ${mins} min`;
    
    if (bus.eta_status === 'DEGRADED') {
      etaText += ' (Est)';
      etaClass = 'text-warning';
    } else if (bus.eta_status === 'STALE') {
      etaText += ' (Stale)';
      etaClass = 'text-danger';
    }
  }

  let crowdText = 'Unknown crowding';
  if (bus.crowd_level === 'LOW') crowdText = 'Low crowding';
  if (bus.crowd_level === 'MEDIUM') crowdText = 'Medium crowding';
  if (bus.crowd_level === 'HIGH') crowdText = 'High crowding';
  if (bus.crowd_level === 'CRUSH') crowdText = 'Crush load';

  let updatedText = 'Unknown';
  if (bus.last_updated_at) {
    try {
      updatedText = 'Updated ' + formatDistanceToNow(new Date(bus.last_updated_at)) + ' ago';
    } catch {
      updatedText = 'Updated recently';
    }
  }

  return (
    <div className="selected-bus-sheet">
      <div className="selected-bus-sheet__header">
        <div className="selected-bus-sheet__title">
          <Navigation size={18} className="icon-blue" />
          <span>BUS {bus.vehicle_id.substring(0, 4)}</span>
          <span className={`badge badge--${bus.state.toLowerCase()}`}>
            {bus.state.replace('_', ' ')}
          </span>
        </div>
        <button className="icon-button" onClick={onClose} title="Close">
          <X size={20} />
        </button>
      </div>

      <div className="selected-bus-sheet__content">
        <div className={`bus-eta-large ${etaClass}`}>
          <Clock size={20} />
          <span>{etaText}</span>
        </div>
        
        <div className="bus-crowding-large">
          <span className="dot">●</span>
          <span>{crowdText}</span>
        </div>

        <div className="selected-bus-sheet__service">
          <div className="service-badge-small">{serviceName}</div>
          <span className="text-subtle">Towards {direction}</span>
        </div>
      </div>

      <div className="selected-bus-sheet__footer text-subtle">
        <RefreshCw size={12} />
        <span>{updatedText}</span>
      </div>
    </div>
  );
}
