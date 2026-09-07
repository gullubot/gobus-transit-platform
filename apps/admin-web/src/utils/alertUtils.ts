export const ALERT_TYPE_LABELS: Record<string, string> = {
  VEHICLE_OFFLINE_SCHEDULED: "Vehicle Offline While Scheduled",
  UNEXPECTED_MAINTENANCE: "Unexpected Maintenance",
  VEHICLE_TRACKING_STALE: "Vehicle Tracking Stale",
  LOW_TRACKING_CONFIDENCE: "Low Tracking Confidence",
  SERVICE_CROWDING_PATTERN: "Recurring Crowding Pattern",
};

export function formatAlertType(type: string): string {
  if (!type) return "Operational Incident";
  if (ALERT_TYPE_LABELS[type]) return ALERT_TYPE_LABELS[type];
  return type
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function formatGoBusDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "—";
    const day = String(d.getDate()).padStart(2, "0");
    const month = d.toLocaleString("en-US", { month: "short" });
    const year = d.getFullYear();
    let hours = d.getHours();
    const minutes = String(d.getMinutes()).padStart(2, "0");
    const ampm = hours >= 12 ? "PM" : "AM";
    hours = hours % 12;
    hours = hours ? hours : 12;
    const formattedHours = String(hours).padStart(2, "0");
    return `${day} ${month} ${year} · ${formattedHours}:${minutes} ${ampm}`;
  } catch {
    return "—";
  }
}
