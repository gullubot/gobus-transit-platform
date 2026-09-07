import { Bus, Clock, Users } from 'lucide-react';

interface ServiceResultCardProps {
  service: {
    service_id: string;
    service_name: string;
    direction: string;
    nearest_bus: {
      vehicle_id: string;
      eta_seconds: number | null;
      eta_status: string | null;
      crowd_level: string;
    } | null;
    active_buses_count: number;
  };
  onClick?: () => void;
}

export default function ServiceResultCard({ service, onClick }: ServiceResultCardProps) {
  // Format ETA
  let etaText = 'Unavailable';
  let etaClass = '';
  
  if (service.nearest_bus?.eta_seconds !== null && service.nearest_bus?.eta_seconds !== undefined) {
    const mins = Math.round(service.nearest_bus.eta_seconds / 60);
    if (mins <= 0) etaText = 'Due now';
    else etaText = `Arriving in ${mins} min`;

    if (service.nearest_bus.eta_status === 'DEGRADED') {
      etaText += ' (Estimated)';
      etaClass = 'text-warning';
    } else if (service.nearest_bus.eta_status === 'STALE') {
      etaText = `Arriving in ${mins} min (Stale)`;
      etaClass = 'text-danger';
    }
  }

  // Format Crowd
  let crowdText = 'Unknown crowding';
  if (service.nearest_bus?.crowd_level === 'LOW') crowdText = 'Low crowding';
  if (service.nearest_bus?.crowd_level === 'MEDIUM') crowdText = 'Medium crowding';
  if (service.nearest_bus?.crowd_level === 'HIGH') crowdText = 'High crowding';
  if (service.nearest_bus?.crowd_level === 'CRUSH') crowdText = 'Crush load';

  return (
    <div className="card service-result-card" onClick={onClick}>
      <div className="card__body">
        <div className="service-result-card__header">
          <div className="service-badge">
            <Bus size={16} />
            <span>{service.service_name}</span>
          </div>
          <div className="service-direction">Towards {service.direction}</div>
        </div>

        {service.nearest_bus ? (
          <div className="service-result-card__bus-info">
            <div className={`service-eta ${etaClass}`}>
              <Clock size={16} />
              <span>{etaText}</span>
            </div>
            <div className="service-crowd">
              <span className="dot">●</span>
              <span>{crowdText}</span>
            </div>
          </div>
        ) : (
          <div className="service-result-card__bus-info">
            <div className="service-eta text-subtle">
              <Clock size={16} />
              <span>No active buses tracked</span>
            </div>
          </div>
        )}

        <div className="service-result-card__footer">
          <div className="active-count">
            <Users size={14} />
            <span>{service.active_buses_count} {service.active_buses_count === 1 ? 'bus' : 'buses'} on route</span>
          </div>
        </div>
      </div>
    </div>
  );
}
