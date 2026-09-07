import { Route } from 'lucide-react';

export default function PlanTripPage() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-page__icon">
        <Route size={64} />
      </div>
      <div className="placeholder-page__title">Plan a Trip</div>
      <div className="placeholder-page__text">
        Search scheduled bus services between any two stops in your city.
      </div>
    </div>
  );
}
