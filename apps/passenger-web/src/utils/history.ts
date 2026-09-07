export interface Stop {
  id: string;
  name: string;
  stop_code: string;
}

export interface JourneySearch {
  from: Stop;
  to: Stop;
  timestamp: number;
}

const HISTORY_KEY = 'gobus_search_history';
const MAX_HISTORY = 10;

export function getSearchHistory(): JourneySearch[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch (err) {
    console.error('Failed to parse search history', err);
    return [];
  }
}

export function saveSearchJourney(from: Stop, to: Stop) {
  const history = getSearchHistory();
  
  // Create new journey
  const newJourney: JourneySearch = {
    from,
    to,
    timestamp: Date.now(),
  };

  // Remove exact duplicates (same from and to)
  const filtered = history.filter(
    (journey) => !(journey.from.id === from.id && journey.to.id === to.id)
  );

  // Add to front
  filtered.unshift(newJourney);

  // Cap size
  const capped = filtered.slice(0, MAX_HISTORY);

  localStorage.setItem(HISTORY_KEY, JSON.stringify(capped));
}

export function clearSearchHistory() {
  localStorage.removeItem(HISTORY_KEY);
}
