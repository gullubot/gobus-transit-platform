import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bus } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await api.login(phone, name);
      login(result.access_token, {
        userId: result.user_id,
        name: result.name,
        role: result.role,
        phone: result.phone,
      });
      navigate('/select-city', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError('Unable to connect. Please check your connection.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-page__logo">
        <div className="login-page__logo-icon">
          <Bus size={32} />
        </div>
        <div className="login-page__logo-text">GoBus</div>
        <div className="login-page__tagline">Your city transit, simplified</div>
      </div>

      <div className="login-card">
        <h1 className="login-card__title">Sign In</h1>
        <form className="login-card__form" onSubmit={handleSubmit}>
          {error && <div className="login-card__error">{error}</div>}

          <div className="input-group">
            <label className="input-group__label" htmlFor="login-phone">Phone Number</label>
            <input
              id="login-phone"
              className="input"
              type="tel"
              placeholder="e.g. +1234567890"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoComplete="tel"
              required
            />
          </div>

          <div className="input-group">
            <label className="input-group__label" htmlFor="login-name">Full Name</label>
            <input
              id="login-name"
              className="input"
              type="text"
              placeholder="Enter your name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn--primary btn--full"
            disabled={loading || !phone || !name}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
