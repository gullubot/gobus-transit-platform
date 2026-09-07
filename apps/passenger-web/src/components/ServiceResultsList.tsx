import ServiceResultCard from './ServiceResultCard';

interface ServiceResultsListProps {
  loading: boolean;
  error: string | null;
  results: any[];
  onSelect: (service: any) => void;
}

export default function ServiceResultsList({ loading, error, results, onSelect }: ServiceResultsListProps) {
  if (loading) {
    return (
      <div className="service-results-list">
        <div className="card service-result-card">
          <div className="card__body">
            <div className="skeleton skeleton-text" style={{ width: '40%' }}></div>
            <div className="skeleton skeleton-text" style={{ width: '60%' }}></div>
            <div className="skeleton skeleton-text" style={{ width: '30%', marginTop: '16px' }}></div>
          </div>
        </div>
        <div className="card service-result-card">
          <div className="card__body">
            <div className="skeleton skeleton-text" style={{ width: '50%' }}></div>
            <div className="skeleton skeleton-text" style={{ width: '70%' }}></div>
            <div className="skeleton skeleton-text" style={{ width: '40%', marginTop: '16px' }}></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="service-results-list">
        <div className="error-state card">
          <div className="card__body">
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="service-results-list">
        <div className="empty-state card">
          <div className="card__body">
            <p>No services match this journey.</p>
          </div>
        </div>
      </div>
    );
  }

  const activeBusesCount = results.reduce((acc, curr) => acc + curr.active_buses_count, 0);

  if (activeBusesCount === 0) {
    return (
      <div className="service-results-list">
        <div className="empty-state card">
          <div className="card__body">
            <p>No buses currently available for this journey.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="service-results-list">
      {results.map((service, idx) => (
        <ServiceResultCard 
          key={`${service.service_id}-${idx}`} 
          service={service} 
          onClick={() => onSelect(service)}
        />
      ))}
    </div>
  );
}
