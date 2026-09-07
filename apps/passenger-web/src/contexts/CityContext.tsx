import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

interface CityContextValue {
  cityId: string | null;
  cityName: string | null;
  hasCity: boolean;
  selectCity: (id: string, name: string) => void;
  clearCity: () => void;
}

const STORAGE_KEY_CITY_ID = 'gobus_city_id';
const STORAGE_KEY_CITY_NAME = 'gobus_city_name';

function restoreCity(): { id: string | null; name: string | null } {
  const storedId = localStorage.getItem(STORAGE_KEY_CITY_ID);
  const storedName = localStorage.getItem(STORAGE_KEY_CITY_NAME);
  return { id: storedId, name: storedName };
}

const CityContext = createContext<CityContextValue | null>(null);

export function CityProvider({ children }: { children: ReactNode }) {
  const initial = restoreCity();
  const [cityId, setCityId] = useState<string | null>(initial.id);
  const [cityName, setCityName] = useState<string | null>(initial.name);

  const selectCity = useCallback((id: string, name: string) => {
    localStorage.setItem(STORAGE_KEY_CITY_ID, id);
    localStorage.setItem(STORAGE_KEY_CITY_NAME, name);
    setCityId(id);
    setCityName(name);
  }, []);

  const clearCity = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY_CITY_ID);
    localStorage.removeItem(STORAGE_KEY_CITY_NAME);
    setCityId(null);
    setCityName(null);
  }, []);

  return (
    <CityContext.Provider value={{
      cityId,
      cityName,
      hasCity: cityId !== null,
      selectCity,
      clearCity,
    }}>
      {children}
    </CityContext.Provider>
  );
}

export function useCity() {
  const context = useContext(CityContext);
  if (!context) {
    throw new Error('useCity must be used within a CityProvider');
  }
  return context;
}
