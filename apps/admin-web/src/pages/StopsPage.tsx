import { useState, useEffect } from "react";
import { apiFetch, apiFetchResponse } from "../api/api";
import { Plus, Search, MapPin, Edit2, Trash2, AlertTriangle, X, Tag, ArrowLeft } from "lucide-react";
import { StopDetailModal } from "../components/StopDetailModal";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";

interface Stop {
  id: string;
  stop_code: string;
  name: string;
  latitude: number;
  longitude: number;
  status: string;
  aliases?: string[];
}

export default function StopsPage() {
  const [stops, setStops] = useState<Stop[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [detailModalStopId, setDetailModalStopId] = useState<string | null>(null);
  const [formData, setFormData] = useState({ stop_code: "", name: "", latitude: "", longitude: "", status: "ACTIVE" });
  const [aliases, setAliases] = useState<string[]>([]);
  const [aliasInput, setAliasInput] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [coordWarning, setCoordWarning] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const returnTo = (location.state as any)?.returnTo || searchParams.get("returnTo");
  const returnLabel = (location.state as any)?.returnLabel || "Alerts & Triage";

  useEffect(() => {
    loadStops();
  }, []);

  useEffect(() => {
    const urlStopId = searchParams.get("stopId");
    if (urlStopId) {
      setDetailModalStopId(urlStopId);
    } else {
      setDetailModalStopId(null);
    }
  }, [searchParams]);

  const openStopDetail = (stopId: string) => {
    setDetailModalStopId(stopId);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("stopId", stopId);
      return next;
    }, { replace: true });
  };

  const closeStopDetail = () => {
    setDetailModalStopId(null);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("stopId");
      return next;
    }, { replace: true });
  };

  const loadStops = async () => {
    try {
      const data = await apiFetch("/admin/stops");
      setStops(data);
    } catch (err) {
      console.error("Failed to load stops", err);
    } finally {
      setLoading(false);
    }
  };

  // Check coordinates against existing stops and geography whenever lat/lng changes
  const checkCoordinateCollision = (latStr: string, lonStr: string) => {
    const lat = parseFloat(latStr);
    const lon = parseFloat(lonStr);
    if (isNaN(lat) || isNaN(lon)) {
      setCoordWarning(null);
      return;
    }

    if (Math.abs(lat) > 90 || Math.abs(lon) > 180) {
      setCoordWarning("Invalid coordinates: Latitude must be between -90 and 90, Longitude between -180 and 180. Check for missing decimal points.");
      return;
    }

    if (lat > 30 || lat < 20 || lon < 85 || lon > 92) {
      setCoordWarning(`Suspect location: (${lat.toFixed(4)}, ${lon.toFixed(4)}) is outside the Kolkata metropolitan transit region (~22.5° N, ~88.3° E). Check if Latitude and Longitude are swapped.`);
      return;
    }

    const collision = stops.find(
      s => (!editingId || s.id !== editingId) &&
           Math.abs(s.latitude - lat) < 0.00001 &&
           Math.abs(s.longitude - lon) < 0.00001
    );

    if (collision) {
      setCoordWarning(`Another Stop (${collision.stop_code} — ${collision.name}) exists at this location. Review before continuing.`);
    } else {
      setCoordWarning(null);
    }
  };

  const handleAddAlias = (e?: React.KeyboardEvent | React.MouseEvent) => {
    if (e && 'key' in e && e.key !== 'Enter') return;
    if (e) e.preventDefault();
    const clean = aliasInput.trim();
    if (clean && !aliases.includes(clean)) {
      setAliases([...aliases, clean]);
      setAliasInput("");
    }
  };

  const handleRemoveAlias = (aliasToRemove: string) => {
    setAliases(aliases.filter(a => a !== aliasToRemove));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const lat = parseFloat(formData.latitude);
    const lon = parseFloat(formData.longitude);

    if (isNaN(lat) || isNaN(lon)) {
      setErrorMsg("Latitude and Longitude must be valid decimal numbers.");
      return;
    }

    if (Math.abs(lat) > 90 || Math.abs(lon) > 180) {
      setErrorMsg("Coordinates out of range: Latitude must be in [-90, 90] and Longitude in [-180, 180]. Please verify decimal points.");
      return;
    }

    // Check duplicate stop code
    const cleanCode = formData.stop_code.trim().toUpperCase();
    const dupCode = stops.find(s => (!editingId || s.id !== editingId) && s.stop_code.toUpperCase() === cleanCode);
    if (dupCode) {
      setErrorMsg(`Stop code '${cleanCode}' is already used by '${dupCode.name}'. Every stop must have a unique code.`);
      return;
    }

    setSubmitting(true);

    try {
      const url = editingId ? `/admin/stops/${editingId}` : "/admin/stops";
      const method = editingId ? "PUT" : "POST";
      
      const { headers } = await apiFetchResponse(url, {
        method,
        body: JSON.stringify({
          ...formData,
          stop_code: cleanCode,
          latitude: lat,
          longitude: lon,
          aliases,
        })
      });

      const warningHeader = headers.get("X-Data-Quality-Warning");
      if (warningHeader) {
        console.warn("Data Quality Warning:", warningHeader);
      }

      setShowModal(false);
      setEditingId(null);
      loadStops();
      setFormData({ stop_code: "", name: "", latitude: "", longitude: "", status: "ACTIVE" });
      setAliases([]);
      setAliasInput("");
      setCoordWarning(null);
    } catch (err: any) {
      setErrorMsg(err.message || `Failed to ${editingId ? "update" : "create"} stop`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (stop: Stop) => {
    setFormData({
      stop_code: stop.stop_code,
      name: stop.name,
      latitude: stop.latitude.toString(),
      longitude: stop.longitude.toString(),
      status: stop.status
    });
    setAliases(stop.aliases || []);
    setAliasInput("");
    setErrorMsg(null);
    setCoordWarning(null);
    setEditingId(stop.id);
    setShowModal(true);
  };

  const handleDelete = async (stop: Stop) => {
    if (!confirm(`Are you sure you want to delete Stop ${stop.stop_code} — "${stop.name}"?\n\nThis action cannot be undone.`)) return;
    try {
      await apiFetch(`/admin/stops/${stop.id}`, { method: "DELETE" });
      loadStops();
    } catch (err: any) {
      alert(err.message || "Failed to delete stop");
    }
  };

  const filteredStops = stops.filter(s => 
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    s.stop_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (s.aliases && s.aliases.some(a => a.toLowerCase().includes(searchQuery.toLowerCase())))
  );

  return (
    <div className="page-container">
      {returnTo && (
        <div style={{ marginBottom: "1rem" }}>
          <button
            type="button"
            onClick={() => navigate(returnTo, { state: location.state })}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: "pointer",
              padding: "4px 0",
              transition: "color 0.15s ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#f8fafc")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
          >
            <ArrowLeft size={16} /> Back to {returnLabel}
          </button>
        </div>
      )}
      <div className="page-header">
        <div>
          <h1 className="page-title">Stops Management</h1>
          <p className="page-subtitle">Manage all physical bus stops and searchable local names in your network.</p>
        </div>
        <button className="btn-primary" onClick={() => {
          setEditingId(null);
          setFormData({ stop_code: "", name: "", latitude: "", longitude: "", status: "ACTIVE" });
          setAliases([]);
          setAliasInput("");
          setErrorMsg(null);
          setCoordWarning(null);
          setShowModal(true);
        }}>
          <Plus size={18} /> Add New Stop
        </button>
      </div>

      <div className="data-table-card">
        <div className="table-toolbar">
          <div className="search-box">
            <Search size={16} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search by stop name, code, or alias..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {loading ? (
          <div className="loading-state">Loading stops...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name & Aliases</th>
                <th>Location</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredStops.map(stop => (
                <tr 
                  key={stop.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => openStopDetail(stop.id)}
                >
                  <td><span className="code-badge">{stop.stop_code}</span></td>
                  <td>
                    <div className="font-medium">{stop.name}</div>
                    {stop.aliases && stop.aliases.length > 0 && (
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
                        {stop.aliases.map((alias, idx) => (
                          <span key={idx} style={{ 
                            fontSize: '0.75rem', 
                            background: '#f1f5f9', 
                            color: '#475569', 
                            padding: '2px 6px', 
                            borderRadius: '4px',
                            border: '1px solid #e2e8f0' 
                          }}>
                            {alias}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="location-cell">
                      <MapPin size={14} className="text-muted" />
                      <span>
                        {stop.latitude != null && !isNaN(Number(stop.latitude)) && stop.longitude != null && !isNaN(Number(stop.longitude))
                          ? `${Number(stop.latitude).toFixed(4)}, ${Number(stop.longitude).toFixed(4)}`
                          : "—"}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className={`status-badge ${stop.status.toLowerCase()}`}>
                      {stop.status}
                    </span>
                  </td>
                  <td className="text-right">
                    <button className="action-btn" title="Edit" onClick={(e) => { e.stopPropagation(); handleEdit(stop); }}><Edit2 size={16} /></button>
                    <button className="action-btn text-danger" title="Delete" onClick={(e) => { e.stopPropagation(); handleDelete(stop); }}><Trash2 size={16} /></button>
                  </td>
                </tr>
              ))}
              {filteredStops.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-state">No stops found in your organization.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '560px' }}>
            <div className="modal-header">
              <h2>{editingId ? "Edit Stop" : "Create New Stop"}</h2>
              <button className="close-btn" onClick={() => setShowModal(false)}>×</button>
            </div>
            
            {errorMsg && (
              <div style={{ 
                margin: '16px 24px 0', 
                padding: '12px 16px', 
                background: '#fef2f2', 
                border: '1px solid #fecaca', 
                borderRadius: '8px', 
                color: '#dc2626', 
                fontSize: '0.875rem' 
              }}>
                {errorMsg}
              </div>
            )}

            {coordWarning && (
              <div style={{ 
                margin: '16px 24px 0', 
                padding: '12px 16px', 
                background: '#fffbeb', 
                border: '1px solid #fde68a', 
                borderRadius: '8px', 
                color: '#b45309', 
                fontSize: '0.875rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px'
              }}>
                <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <strong>Data Quality Notice:</strong> {coordWarning}
                  <div style={{ fontSize: '0.75rem', marginTop: '4px', color: '#92400e' }}>
                    This will NOT prevent saving. You may continue as a new stop if intended.
                  </div>
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="modal-form">
              <div className="form-row">
                <div className="input-group">
                  <label>Stop Code (Required, Unique)</label>
                  <input 
                    required 
                    value={formData.stop_code} 
                    onChange={e => setFormData({...formData, stop_code: e.target.value})} 
                    placeholder="e.g. STP001" 
                  />
                </div>
                <div className="input-group">
                  <label>Primary Name (Required)</label>
                  <input 
                    required 
                    value={formData.name} 
                    onChange={e => setFormData({...formData, name: e.target.value})} 
                    placeholder="e.g. Shivaji Nagar Bus Stop" 
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="input-group">
                  <label>Latitude</label>
                  <input 
                    type="number" 
                    step="any" 
                    required 
                    value={formData.latitude} 
                    onChange={e => {
                      setFormData({...formData, latitude: e.target.value});
                      checkCoordinateCollision(e.target.value, formData.longitude);
                    }} 
                    placeholder="22.5726" 
                  />
                </div>
                <div className="input-group">
                  <label>Longitude</label>
                  <input 
                    type="number" 
                    step="any" 
                    required 
                    value={formData.longitude} 
                    onChange={e => {
                      setFormData({...formData, longitude: e.target.value});
                      checkCoordinateCollision(formData.latitude, e.target.value);
                    }} 
                    placeholder="88.3639" 
                  />
                </div>
              </div>

              {/* Aliases Section */}
              <div className="input-group" style={{ marginBottom: '16px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Tag size={14} /> Searchable Local Names / Aliases (Optional)
                </label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input 
                    type="text" 
                    value={aliasInput} 
                    onChange={e => setAliasInput(e.target.value)} 
                    onKeyDown={handleAddAlias}
                    placeholder="e.g. Hanuman Mandir, Mandir Stop..." 
                  />
                  <button 
                    type="button" 
                    className="btn-secondary" 
                    onClick={handleAddAlias}
                    style={{ whiteSpace: 'nowrap' }}
                  >
                    Add Alias
                  </button>
                </div>

                {aliases.length > 0 && (
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '8px' }}>
                    {aliases.map((a, idx) => (
                      <span key={idx} style={{ 
                        display: 'inline-flex', 
                        alignItems: 'center', 
                        gap: '4px',
                        background: '#eff6ff', 
                        color: '#1d4ed8', 
                        padding: '4px 8px', 
                        borderRadius: '6px', 
                        fontSize: '0.8125rem',
                        border: '1px solid #bfdbfe' 
                      }}>
                        {a}
                        <X 
                          size={13} 
                          style={{ cursor: 'pointer' }} 
                          onClick={() => handleRemoveAlias(a)} 
                        />
                      </span>
                    ))}
                  </div>
                )}
                <span style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>
                  Passengers can discover this Stop using either its primary name or any alias.
                </span>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={submitting}>
                  {submitting ? "Saving..." : (editingId ? "Save Changes" : "Create Stop")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {detailModalStopId && (
        <StopDetailModal
          stopId={detailModalStopId}
          onClose={closeStopDetail}
          onRouteClick={(routeId) => {
            const currentStop = stops.find((s) => s.id === detailModalStopId);
            const stopCode = currentStop?.stop_code || "";
            navigate(`/routes/${routeId}`, {
              state: {
                returnTo: `/stops?stopId=${detailModalStopId}`,
                returnLabel: stopCode ? `Stop ${stopCode}` : "Stops",
              },
            });
          }}
        />
      )}
    </div>
  );
}
