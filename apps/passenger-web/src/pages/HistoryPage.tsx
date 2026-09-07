import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { History, Trash2, ArrowRight, Bus, Search, MapPin } from 'lucide-react';
import { getSearchHistory, clearSearchHistory } from '../utils/history';
import type { JourneySearch } from '../utils/history';

export default function HistoryPage() {
  const navigate = useNavigate();
  const [history, setHistory] = useState<JourneySearch[]>([]);

  useEffect(() => {
    setHistory(getSearchHistory());
  }, []);

  function handleClear() {
    clearSearchHistory();
    setHistory([]);
  }

  function handleSelect(journey: JourneySearch) {
    navigate('/home', {
      state: {
        openSearch: true,
        initialFrom: journey.from,
        initialTo: journey.to
      }
    });
  }

  return (
    <div className="app-shell">
      <header className="top-app-bar">
        <div className="top-app-bar__title">Recent Journeys</div>
        {history.length > 0 && (
          <button className="top-app-bar__action" onClick={handleClear} title="Clear history">
            <Trash2 size={18} />
          </button>
        )}
      </header>

      <div className="page-content history-page-content">
        {history.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state__icon">
              <History size={32} />
            </div>
            <p>No recent journeys found.</p>
          </div>
        ) : (
          <div className="history-list">
            {history.map((journey, idx) => (
              <button 
                key={idx} 
                className="history-card" 
                onClick={() => handleSelect(journey)}
              >
                <div className="history-card__route">
                  <div className="history-card__stop">
                    <span className="dot dot--blue"></span>
                    <span>{journey.from.name}</span>
                  </div>
                  <div className="history-card__separator">
                    <ArrowRight size={14} className="text-subtle" />
                  </div>
                  <div className="history-card__stop">
                    <span className="dot dot--green"></span>
                    <span>{journey.to.name}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <BottomNav />
    </div>
  );
}

function BottomNav() {
  const navigate = useNavigate();
  const path = window.location.pathname;

  return (
    <nav className="bottom-nav">
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
