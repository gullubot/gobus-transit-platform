import { useState, useEffect } from 'react';

interface LocationState {
  lat: number | null;
  lng: number | null;
  error: string | null;
  loading: boolean;
}

export function useGeolocation() {
  const [state, setState] = useState<LocationState>({
    lat: null,
    lng: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    if (!navigator.geolocation) {
      setState((s) => ({ ...s, error: 'Geolocation not supported', loading: false }));
      return;
    }

    const options = {
      enableHighAccuracy: false, // Fast, sufficient for nearest stop
      timeout: 5000,
      maximumAge: 60000, // 1 min cache is fine
    };

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setState({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          error: null,
          loading: false,
        });
      },
      (err) => {
        let errorMsg = 'Failed to get location';
        if (err.code === err.PERMISSION_DENIED) errorMsg = 'Permission denied';
        else if (err.code === err.TIMEOUT) errorMsg = 'Timeout';
        
        setState((s) => ({ ...s, error: errorMsg, loading: false }));
      },
      options
    );
  }, []);

  return state;
}
