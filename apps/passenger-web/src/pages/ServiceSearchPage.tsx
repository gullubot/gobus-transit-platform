import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Search, Bus, AlertCircle } from 'lucide-react';
import { api, ApiError } from '../api/client';

interface ServiceSummary {
  id: string;
  organization_id: string;
  service_code: string;
  service_name: string;
  route_id: string;
}

export default function ServiceSearchPage() {
  const navigate = useNavigate();
  
  const [query, setQuery] = useState('');
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    
    async function loadServices() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.getServices();
        if (mounted) {
          setServices(data);
        }
      } catch (err) {
        if (mounted) {
          const message = err instanceof ApiError ? err.detail : 'Unable to load services. Please try again.';
          setError(message);
        }
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }
    
    loadServices();
    
    return () => {
      mounted = false;
    };
  }, []);

  const filteredServices = useMemo(() => {
    const trimmedQuery = query.trim().toLowerCase();
    if (!trimmedQuery) return [];
    
    return services.filter(s => 
      s.service_code.toLowerCase().includes(trimmedQuery) ||
      s.service_name.toLowerCase().includes(trimmedQuery)
    );
  }, [query, services]);

  return (
    <div className="app-layout">
      <header className="top-app-bar">
        <button className="top-app-bar__action" onClick={() => navigate(-1)} title="Back">
          <ChevronLeft size={24} />
        </button>
        <div className="top-app-bar__title">Search Bus / Service</div>
        <div className="top-app-bar__action" style={{ visibility: 'hidden' }}>
          <ChevronLeft size={24} />
        </div>
      </header>

      <main className="main-content">
        <div className="search-page-header">
          <div className="search-input-container">
            <Search size={20} className="search-input-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Search bus or service"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
          </div>
          <div className="search-hint">
            Enter a service name or code (e.g., AC4B)
          </div>
        </div>

        <div className="search-results-container">
          {isLoading && (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Loading services...</p>
            </div>
          )}

          {!isLoading && error && (
            <div className="error-state">
              <AlertCircle size={32} className="error-icon" />
              <p>{error}</p>
            </div>
          )}

          {!isLoading && !error && query.trim() === '' && (
            <div className="empty-state">
              <Bus size={48} className="empty-icon" />
              <p>Search for a bus or service to see its route and schedule.</p>
            </div>
          )}

          {!isLoading && !error && query.trim() !== '' && filteredServices.length === 0 && (
            <div className="empty-state">
              <AlertCircle size={48} className="empty-icon text-muted" />
              <p>No bus or service found.</p>
            </div>
          )}

          {!isLoading && !error && filteredServices.length > 0 && (
            <div className="service-result-list">
              {filteredServices.map(service => (
                <button
                  key={service.id}
                  className="service-search-result-card"
                  onClick={() => navigate(`/service/${service.id}`)}
                >
                  <div className="service-search-result-card__header">
                    <div className="service-search-result-card__badge">
                      <Bus size={14} />
                      {service.service_code}
                    </div>
                  </div>
                  <div className="service-search-result-card__name">
                    {service.service_name}
                  </div>
                  <div className="service-search-result-card__action">
                    View service details
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
