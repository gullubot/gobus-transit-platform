import { useState, useEffect } from 'react';
import { Search, X, MapPin } from 'lucide-react';
import { api } from '../api/client';
import type { Stop } from '../utils/history';

interface StopSearchOverlayProps {
  onClose: () => void;
  onSelect: (stop: Stop) => void;
  placeholder?: string;
  autoFocus?: boolean;
}

export default function StopSearchOverlay({ onClose, onSelect, placeholder = 'Search stops', autoFocus = true }: StopSearchOverlayProps) {
  const [query, setQuery] = useState('');
  const [stops, setStops] = useState<Stop[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounced search
  useEffect(() => {
    if (!query.trim()) {
      setStops([]);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    const timer = setTimeout(async () => {
      try {
        const results = await api.getStops(query.trim());
        setStops(results.map(r => ({ id: r.id, name: r.name, stop_code: r.stop_code })));
      } catch (err: any) {
        setError('Unable to fetch stops');
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div className="stop-search-overlay">
      <div className="stop-search-overlay__header">
        <div className="input-group">
          <Search size={18} className="input-icon" />
          <input
            type="text"
            className="input"
            placeholder={placeholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus={autoFocus}
          />
          {query && (
            <button className="btn-clear" onClick={() => setQuery('')}>
              <X size={16} />
            </button>
          )}
        </div>
        <button className="btn-cancel" onClick={onClose}>Cancel</button>
      </div>

      <div className="stop-search-overlay__results page-content">
        {loading && (
          <div className="stop-search-overlay__loading">
            <div className="skeleton skeleton-text"></div>
            <div className="skeleton skeleton-text"></div>
            <div className="skeleton skeleton-text"></div>
          </div>
        )}

        {error && !loading && (
          <div className="error-state">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && query.trim() && stops.length === 0 && (
          <div className="empty-state">
            <p>No stops found for "{query}"</p>
          </div>
        )}

        {!loading && !error && stops.map(stop => (
          <button
            key={stop.id}
            className="stop-result-item"
            onClick={() => onSelect(stop)}
          >
            <div className="stop-result-item__icon">
              <MapPin size={18} />
            </div>
            <div className="stop-result-item__content">
              <div className="stop-result-item__name">{stop.name}</div>
              <div className="stop-result-item__code">{stop.stop_code}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
