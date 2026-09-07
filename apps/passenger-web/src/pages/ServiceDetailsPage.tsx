import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChevronLeft, Map as MapIcon, ArrowRightLeft, Bus, AlertCircle } from 'lucide-react';
import { api, ApiError } from '../api/client';

type ServiceDetail = Awaited<ReturnType<typeof api.getServiceDetail>>;
type StopDeparture = Awaited<ReturnType<typeof api.getStopDepartures>>[0];

export default function ServiceDetailsPage() {
  const { serviceId } = useParams<{ serviceId: string }>();
  const navigate = useNavigate();

  const [service, setService] = useState<ServiceDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [direction, setDirection] = useState<'A_TO_B' | 'B_TO_A'>('A_TO_B');
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);

  const [departures, setDepartures] = useState<StopDeparture[]>([]);
  const [isDeparturesLoading, setIsDeparturesLoading] = useState(false);

  // 1. Fetch Service Details
  useEffect(() => {
    if (!serviceId) return;

    let mounted = true;
    async function fetchService() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.getServiceDetail(serviceId!);
        if (mounted) {
          setService(data);
          
          // Automatically pick first stop of A_TO_B as default
          if (data.stops.length > 0) {
            setSelectedStopId(data.stops[0].stop_id);
          }
          
          // Auto-switch direction if only B_TO_A operates
          const hasAToB = data.schedules.some(s => s.direction === 'A_TO_B');
          const hasBToA = data.schedules.some(s => s.direction === 'B_TO_A');
          if (!hasAToB && hasBToA) {
            setDirection('B_TO_A');
            if (data.stops.length > 0) {
              setSelectedStopId(data.stops[data.stops.length - 1].stop_id);
            }
          }
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof ApiError ? err.detail : 'Failed to load service details.');
        }
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    fetchService();
    return () => { mounted = false; };
  }, [serviceId]);

  // 2. Fetch Departures when stop or direction changes
  useEffect(() => {
    if (!serviceId || !selectedStopId) return;

    let mounted = true;
    async function fetchDepartures() {
      setIsDeparturesLoading(true);
      try {
        const data = await api.getStopDepartures(selectedStopId!, serviceId!, direction);
        if (mounted) {
          setDepartures(data);
        }
      } catch (err) {
        if (mounted) setDepartures([]);
      } finally {
        if (mounted) setIsDeparturesLoading(false);
      }
    }

    fetchDepartures();
    const interval = setInterval(fetchDepartures, 15000); // refresh every 15s

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [serviceId, selectedStopId, direction]);

  // Derived state for the UI
  const orderedStops = useMemo(() => {
    if (!service) return [];
    // Stops are canonical A_TO_B
    return direction === 'A_TO_B' ? [...service.stops] : [...service.stops].reverse();
  }, [service, direction]);

  const originName = orderedStops.length > 0 ? orderedStops[0].stop_name : '';
  const destName = orderedStops.length > 0 ? orderedStops[orderedStops.length - 1].stop_name : '';

  const activeSchedule = useMemo(() => {
    if (!service) return null;
    return service.schedules.find(s => s.direction === direction) || null;
  }, [service, direction]);

  const handleSwitchDirection = () => {
    setDirection(prev => prev === 'A_TO_B' ? 'B_TO_A' : 'A_TO_B');
    // Also reset selected stop to the new origin
    if (service && service.stops.length > 0) {
      if (direction === 'A_TO_B') {
        setSelectedStopId(service.stops[service.stops.length - 1].stop_id);
      } else {
        setSelectedStopId(service.stops[0].stop_id);
      }
    }
  };

  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return '—';
    // If it's a simple HH:MM:SS string from schedule
    if (timeStr.length === 8 && timeStr.includes(':')) {
      const [h, m] = timeStr.split(':');
      const hour = parseInt(h, 10);
      const ampm = hour >= 12 ? 'PM' : 'AM';
      const formattedHour = hour % 12 || 12;
      return `${formattedHour}:${m} ${ampm}`;
    }
    // If it's an ISO string
    try {
      const d = new Date(timeStr);
      if (isNaN(d.getTime())) return timeStr;
      return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch {
      return timeStr;
    }
  };

  if (isLoading) {
    return (
      <div className="app-layout">
        <header className="top-app-bar"><div className="top-app-bar__title">Loading...</div></header>
        <div className="loading-state"><div className="spinner"></div></div>
      </div>
    );
  }

  if (error || !service) {
    return (
      <div className="app-layout">
        <header className="top-app-bar">
          <button className="top-app-bar__action" onClick={() => navigate(-1)}><ChevronLeft size={24} /></button>
          <div className="top-app-bar__title">Error</div>
        </header>
        <div className="error-state"><AlertCircle size={32} /><p>{error || 'Service not found.'}</p></div>
      </div>
    );
  }

  return (
    <div className="app-layout service-details-page">
      <header className="top-app-bar">
        <button className="top-app-bar__action" onClick={() => navigate(-1)} title="Back">
          <ChevronLeft size={24} />
        </button>
        <div className="top-app-bar__title">Service details</div>
        <div className="top-app-bar__action" style={{ visibility: 'hidden' }}><ChevronLeft size={24} /></div>
      </header>

      <main className="main-content" style={{ paddingBottom: '80px' }}>
        {/* Main Header Card */}
        <section className="service-details-header">
          <div className="service-details-badge">
            <Bus size={20} />
            <h2>{service.service_code}</h2>
          </div>
          <h1 className="service-details-name">{service.service_name}</h1>
          
          <div className="service-direction-card">
            <div className="service-direction-text">
              <span className="origin">{originName}</span>
              <ArrowRightLeft size={16} className="direction-icon-subtle" />
              <span className="destination">{destName}</span>
            </div>
            <button className="direction-switch-btn" onClick={handleSwitchDirection}>
              <ArrowRightLeft size={16} />
              Switch
            </button>
          </div>
        </section>

        {/* Schedule Info */}
        <section className="service-schedule-info">
          {activeSchedule ? (
            <div className="schedule-info-grid">
              <div className="schedule-info-item">
                <span className="schedule-label">First bus</span>
                <span className="schedule-value">{formatTime(activeSchedule.start_time)}</span>
              </div>
              <div className="schedule-info-item">
                <span className="schedule-label">Last bus</span>
                <span className="schedule-value">{formatTime(activeSchedule.end_time)}</span>
              </div>
              <div className="schedule-info-item">
                <span className="schedule-label">Every</span>
                <span className="schedule-value">{activeSchedule.typical_interval_minutes} min</span>
              </div>
            </div>
          ) : (
            <div className="schedule-no-data text-muted">
              No schedule available for this direction.
            </div>
          )}
        </section>

        {/* Departure Board */}
        <section className="service-departure-board">
          <h3 className="section-title">Departures</h3>
          <div className="departure-stop-selector">
            <label>At Stop:</label>
            <select 
              value={selectedStopId || ''} 
              onChange={(e) => setSelectedStopId(e.target.value)}
              className="stop-select"
            >
              {orderedStops.map((stop) => (
                <option key={stop.stop_id} value={stop.stop_id}>
                  {stop.stop_name}
                </option>
              ))}
            </select>
          </div>
          
          <div className="departure-board-table">
            <div className="departure-board-header">
              <div>Scheduled</div>
              <div>Expected</div>
              <div style={{ textAlign: 'right' }}>Status</div>
            </div>
            
            {isDeparturesLoading && departures.length === 0 ? (
              <div className="departure-board-empty">Loading...</div>
            ) : departures.length > 0 ? (
              departures.map((dep, idx) => (
                <div key={idx} className="departure-board-row">
                  <div className="time-scheduled">{formatTime(dep.scheduled_time)}</div>
                  <div className={`time-expected ${dep.status === 'DELAYED' ? 'text-amber' : 'text-green'}`}>
                    {formatTime(dep.expected_time)}
                  </div>
                  <div className={`status-badge status-${dep.status.toLowerCase()}`}>
                    {dep.status.replace('_', ' ')}
                  </div>
                </div>
              ))
            ) : (
              <div className="departure-board-empty text-muted">
                No upcoming departures.
              </div>
            )}
          </div>
        </section>

        {/* Route Stops Line */}
        <section className="service-stops-progression">
          <h3 className="section-title">Route stops</h3>
          <div className="stops-timeline">
            {orderedStops.map((stop, idx) => {
              const isLast = idx === orderedStops.length - 1;
              const isSelected = stop.stop_id === selectedStopId;
              
              return (
                <div 
                  key={stop.stop_id} 
                  className={`timeline-item ${isSelected ? 'timeline-item--selected' : ''}`}
                  onClick={() => setSelectedStopId(stop.stop_id)}
                >
                  <div className="timeline-node-container">
                    <div className="timeline-node"></div>
                    {!isLast && <div className="timeline-line"></div>}
                  </div>
                  <div className="timeline-content">
                    {stop.stop_name}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </main>

      {/* Floating CTA */}
      <div className="service-live-cta-container">
        <button 
          className="btn btn-primary btn-block service-live-cta"
          onClick={() => navigate(`/service/${service.id}/live`)}
        >
          <MapIcon size={20} />
          View buses live
        </button>
      </div>
    </div>
  );
}
