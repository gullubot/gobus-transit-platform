import { useState, useEffect } from 'react';
import { MapPin, Search, ArrowDownUp } from 'lucide-react';
import { useGeolocation } from '../hooks/useGeolocation';
import { api } from '../api/client';
import { calculateDistance } from '../utils/location';
import type { Stop } from '../utils/history';
import StopSearchOverlay from './StopSearchOverlay';

interface TripSearchCardProps {
  initialTo?: Stop | null;
  initialFrom?: Stop | null;
  onClose?: () => void;
  onSearch?: (from: Stop, to: Stop) => void;
}

export default function TripSearchCard({ initialTo, initialFrom, onClose, onSearch }: TripSearchCardProps) {
  const [from, setFrom] = useState<Stop | null>(initialFrom || null);
  const [to, setTo] = useState<Stop | null>(initialTo || null);
  const [activeInput, setActiveInput] = useState<'from' | 'to' | null>(null);

  const { lat, lng, loading: geoLoading, error: geoError } = useGeolocation();

  // On mount, if no initialFrom, try to find nearest stop
  useEffect(() => {
    if (initialFrom) return;
    if (geoLoading || geoError || lat === null || lng === null) return;

    async function findNearest() {
      try {
        const stops = await api.getStops();
        let nearest: Stop | null = null;
        let minDist = Infinity;
        
        for (const stop of stops) {
          if (stop.latitude && stop.longitude) {
            const dist = calculateDistance(lat!, lng!, stop.latitude, stop.longitude);
            if (dist < minDist) {
              minDist = dist;
              nearest = { id: stop.id, name: stop.name, stop_code: stop.stop_code };
            }
          }
        }
        
        if (nearest && !from) {
          setFrom(nearest);
        }
      } catch (err) {
        console.error('Failed to get nearest stop', err);
      }
    }
    
    findNearest();
  }, [lat, lng, geoLoading, geoError, initialFrom, from]);

  function handleSwap() {
    setFrom(to);
    setTo(from);
  }

  function handleSearchClick() {
    if (from && to && onSearch) {
      onSearch(from, to);
    }
  }

  function handleStopSelect(stop: Stop) {
    if (activeInput === 'from') setFrom(stop);
    if (activeInput === 'to') setTo(stop);
    setActiveInput(null);
  }

  return (
    <>
      <div className="trip-search-card">
        <div className="trip-search-card__header">
          <h3>Plan your trip</h3>
          {onClose && (
            <button className="btn-close" onClick={onClose} aria-label="Close search">
              &times;
            </button>
          )}
        </div>

        <div className="trip-search-card__inputs">
          <div className="input-group" onClick={() => setActiveInput('from')}>
            <MapPin size={18} className="input-icon" />
            <input 
              type="text" 
              className="input" 
              placeholder={geoLoading && !from ? "Locating..." : "Your Location"} 
              value={from ? from.name : ''}
              readOnly 
            />
          </div>
          
          <button className="trip-search-card__swap" onClick={handleSwap} aria-label="Swap locations">
            <ArrowDownUp size={16} />
          </button>

          <div className="input-group" onClick={() => setActiveInput('to')}>
            <Search size={18} className="input-icon" />
            <input 
              type="text" 
              className="input" 
              placeholder="Destination" 
              value={to ? to.name : ''}
              readOnly 
            />
          </div>
        </div>

        <div className="trip-search-card__actions">
          <button 
            className="btn btn--primary" 
            onClick={handleSearchClick}
            disabled={!from || !to}
          >
            Search Nearby Buses
          </button>
        </div>
      </div>

      {activeInput && (
        <StopSearchOverlay
          placeholder={activeInput === 'from' ? 'Where are you starting?' : 'Where do you want to go?'}
          onClose={() => setActiveInput(null)}
          onSelect={handleStopSelect}
        />
      )}
    </>
  );
}
