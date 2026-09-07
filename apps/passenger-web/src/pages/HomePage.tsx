import { useState, useEffect } from 'react';
import { MapPin, Search, Bus, Landmark, LogOut, ChevronDown, WifiOff } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useCity } from '../contexts/CityContext';
import { api } from '../api/client';
import { saveSearchJourney } from '../utils/history';
import type { Stop } from '../utils/history';
import Map from '../components/Map';
import TripSearchCard from '../components/TripSearchCard';
import ServiceResultsList from '../components/ServiceResultsList';

export default function HomePage() {
  const { user, logout } = useAuth();
  const { cityName } = useCity();
  const navigate = useNavigate();
  const location = useLocation();
  
  const [isSearchOpen, setIsSearchOpen] = useState(location.state?.openSearch || false);
  const [mapCenter, setMapCenter] = useState<[number, number]>([22.5726, 88.3639]);
  
  // Search state
  const [initialFrom, setInitialFrom] = useState<Stop | null>(location.state?.initialFrom || null);
  const [initialTo, setInitialTo] = useState<Stop | null>(location.state?.initialTo || null);
  
  const [searchResults, setSearchResults] = useState<any[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    async function loadCityCenter() {
      try {
        const stops = await api.getStops();
        const validStops = stops.filter(s => s.latitude && s.longitude);
        if (validStops.length > 0) {
          const sumLat = validStops.reduce((sum, s) => sum + s.latitude!, 0);
          const sumLng = validStops.reduce((sum, s) => sum + s.longitude!, 0);
          setMapCenter([sumLat / validStops.length, sumLng / validStops.length]);
        }
      } catch (err) {
        console.error('Failed to load stops for center calculation', err);
      }
    }
    if (cityName) {
      loadCityCenter();
    }
  }, [cityName]);

  useEffect(() => {
    function handleOnline() { setIsOffline(false); }
    function handleOffline() { setIsOffline(true); }
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    }
  }, []);

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  async function handleSearch(from: Stop, to: Stop) {
    if (isOffline) {
      setSearchError('Live search unavailable while offline.');
      return;
    }
    
    setIsSearching(true);
    setSearchError(null);
    setSearchResults(null);
    
    try {
      const results = await api.searchServices(from.id, to.id);
      setSearchResults(results);
      saveSearchJourney(from, to);
    } catch (err: any) {
      setSearchError('Unable to fetch live data right now.');
    } finally {
      setIsSearching(false);
    }
  }

  function handleServiceSelect(service: any) {
    navigate(`/service/${service.service_id}/live`);
  }

  return (
    <div className="app-shell home-shell">
      {/* Map Background */}
      <div className="home-map-container">
        <Map center={mapCenter} zoom={13} />
      </div>

      {/* Floating Glassmorphism Header */}
      <header className="top-app-bar top-app-bar--floating">
        <div className="top-app-bar__title">GoBus</div>
        <button
          className="city-selector-btn"
          onClick={() => navigate('/select-city')}
        >
          <MapPin size={14} />
          {cityName || 'Select City'}
          <ChevronDown size={14} />
        </button>
        <button className="top-app-bar__action" onClick={handleLogout} title="Logout">
          <LogOut size={18} />
        </button>
      </header>

      {isOffline && (
        <div className="offline-banner">
          <WifiOff size={16} />
          <span>You are offline. Live bus search is unavailable.</span>
        </div>
      )}

      {/* Floating Bottom UI */}
      <div className={`home-floating-ui ${isSearchOpen ? 'home-floating-ui--expanded' : ''}`}>
        {!isSearchOpen ? (
          <>
            {/* Quick Actions (Floating above search) */}
            <div className="home-floating-actions">
              <button className="home-floating-action-btn" onClick={() => navigate('/service-search')}>
                <Search size={18} className="icon-blue" />
                <span>Search Bus</span>
              </button>
              <button className="home-floating-action-btn">
                <Landmark size={18} className="icon-amber" />
                <span>Depots</span>
              </button>
            </div>

            {/* Destination Search Hero */}
            <div className="home-search-prompt" onClick={() => setIsSearchOpen(true)}>
              <div className="home-search-prompt__greeting">Hello, {user?.name || 'Passenger'}</div>
              <button className="home-search-card">
                <div className="home-search-card__icon">
                  <Search size={18} />
                </div>
                <div className="home-search-card__text">Where do you want to go?</div>
              </button>
            </div>
          </>
        ) : (
          <div className="home-search-expanded-container">
            <TripSearchCard 
              initialFrom={initialFrom}
              initialTo={initialTo}
              onClose={() => {
                setIsSearchOpen(false);
                setSearchResults(null);
                setSearchError(null);
                setInitialFrom(null);
                setInitialTo(null);
                // Clear router state
                navigate('.', { replace: true, state: {} });
              }} 
              onSearch={handleSearch}
            />

            {(isSearching || searchError || searchResults) && (
              <div className="home-search-results">
                <ServiceResultsList
                  loading={isSearching}
                  error={searchError}
                  results={searchResults || []}
                  onSelect={handleServiceSelect}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom Navigation */}
      <BottomNav />
    </div>
  );
}

function BottomNav() {
  const navigate = useNavigate();
  const path = window.location.pathname;

  return (
    <nav className="bottom-nav bottom-nav--floating">
      <button
        className={`bottom-nav__item ${path === '/home' ? 'bottom-nav__item--active' : ''}`}
        onClick={() => navigate('/home')}
      >
        <Bus size={22} />
        <span>Home</span>
      </button>
      <button
        className={`bottom-nav__item ${path === '/history' ? 'bottom-nav__item--active' : ''}`}
        onClick={() => navigate('/history')}
      >
        <Search size={22} />
        <span>History</span>
      </button>
      <button
        className={`bottom-nav__item ${path === '/plan' ? 'bottom-nav__item--active' : ''}`}
        onClick={() => navigate('/plan')}
      >
        <MapPin size={22} />
        <span>Plan Trip</span>
      </button>
    </nav>
  );
}
