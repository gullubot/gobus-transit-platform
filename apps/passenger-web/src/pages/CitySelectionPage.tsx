import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, Loader2 } from 'lucide-react';
import { api } from '../api/client';
import { useCity } from '../contexts/CityContext';

interface City {
  id: string;
  name: string;
}

export default function CitySelectionPage() {
  const [cities, setCities] = useState<City[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const { selectCity } = useCity();
  const navigate = useNavigate();

  useEffect(() => {
    async function fetchCities() {
      try {
        const data = await api.getCities();
        setCities(data);
      } catch {
        setError('Unable to load cities. Please try again.');
      } finally {
        setLoading(false);
      }
    }
    fetchCities();
  }, []);

  function handleSelect(city: City) {
    selectCity(city.id, city.name);
    navigate('/home', { replace: true });
  }

  return (
    <div className="city-page">
      <div className="city-page__header">
        <h1 className="city-page__title">Select Your City</h1>
        <p className="city-page__subtitle">Choose the city you want to track buses in</p>
      </div>

      <div className="city-page__list">
        {loading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
            <Loader2 size={32} className="spin" style={{ color: 'var(--gb-primary)' }} />
          </div>
        )}

        {error && (
          <div className="error-state">
            <div className="error-state__title">Something went wrong</div>
            <div className="error-state__text">{error}</div>
            <button className="btn btn--primary btn--sm" onClick={() => window.location.reload()}>
              Retry
            </button>
          </div>
        )}

        {!loading && !error && cities.map((city) => (
          <button
            key={city.id}
            className="city-card"
            onClick={() => handleSelect(city)}
          >
            <div className="city-card__icon">
              <Building2 size={24} />
            </div>
            <div className="city-card__name">{city.name}</div>
          </button>
        ))}

        {!loading && !error && cities.length === 0 && (
          <div className="empty-state">
            <div className="empty-state__title">No cities available</div>
            <div className="empty-state__text">No transit organizations have been set up yet.</div>
          </div>
        )}
      </div>
    </div>
  );
}
