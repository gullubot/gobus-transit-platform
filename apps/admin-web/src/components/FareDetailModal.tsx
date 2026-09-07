import React, { useEffect, useState } from "react";
import {
  X,
  Banknote,
  Calendar,
  Edit2,
  Plus,
  Trash2,
  AlertCircle,
  Save,
  CheckCircle2,
  Layers,
  ArrowRight,
  Bus,
  Loader2,
} from "lucide-react";
import {
  getFareConfiguration,
  updateFareConfiguration,
  safeNumber,
  type FareConfigurationItem,
  type FareSlabItem,
} from "../api/api";

interface FareDetailModalProps {
  fareId: string;
  initialEdit?: boolean;
  onClose: () => void;
  onFareUpdated?: (updated: FareConfigurationItem) => void;
}

// Consistent date formatting helper
const formatDate = (isoStr: string | null | undefined): string => {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }); // e.g. "04 Sep 2026"
  } catch {
    return isoStr;
  }
};

export const FareDetailModal: React.FC<FareDetailModalProps> = ({
  fareId,
  initialEdit = false,
  onClose,
  onFareUpdated,
}) => {
  const [fare, setFare] = useState<FareConfigurationItem | null>(null);
  const [mode, setMode] = useState<"view" | "edit">(initialEdit ? "edit" : "view");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Edit form state
  const [name, setName] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [effectiveUntil, setEffectiveUntil] = useState("");
  const [slabs, setSlabs] = useState<FareSlabItem[]>([]);

  // Split Open-Ended Slab Safety State (Amendment 1)
  const [showSplitPrompt, setShowSplitPrompt] = useState(false);
  const [splitBoundaryInput, setSplitBoundaryInput] = useState("");
  const [splitError, setSplitError] = useState<string | null>(null);

  const populateForm = (data: FareConfigurationItem) => {
    setName(data.name || "");
    setEffectiveFrom(data.effective_from || "");
    setEffectiveUntil(data.effective_until || "");
    setSlabs(
      data.slabs.map((s) => ({
        id: s.id,
        min_distance_km: s.min_distance_km,
        max_distance_km: s.max_distance_km,
        fare_amount: s.fare_amount,
      }))
    );
  };

  // Fetch fare details whenever fareId changes
  useEffect(() => {
    let isMounted = true;

    async function fetchDetails() {
      try {
        setLoading(true);
        setError(null);
        setFormError(null);
        setRowErrors({});
        setSuccessMsg(null);
        setShowSplitPrompt(false);
        setMode(initialEdit ? "edit" : "view");

        const data = await getFareConfiguration(fareId);
        if (!isMounted) return;

        setFare(data);
        populateForm(data);
      } catch (err: any) {
        if (!isMounted) return;
        setError(err.message || "Failed to load fare configuration details.");
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchDetails();

    return () => {
      isMounted = false;
    };
  }, [fareId, initialEdit]);

  const switchToEdit = () => {
    if (!fare) return;
    populateForm(fare);
    setFormError(null);
    setRowErrors({});
    setSuccessMsg(null);
    setShowSplitPrompt(false);
    setMode("edit");
  };

  const cancelEdit = () => {
    if (!fare) return;
    populateForm(fare);
    setFormError(null);
    setRowErrors({});
    setShowSplitPrompt(false);
    setMode("view");
  };

  // Safe formatting helpers that NEVER call .toFixed on unvalidated types
  const formatKm = (val: unknown): string => {
    const num = safeNumber(val);
    if (num === null) return "—";
    return `${num.toFixed(2)} km`;
  };

  const formatPrice = (val: unknown, currency = "INR"): string => {
    const num = safeNumber(val);
    if (num === null) return "—";
    const symbol = currency === "INR" ? "₹" : `${currency} `;
    return `${symbol}${num.toFixed(2)}`;
  };

  // Slabs editor handlers
  const handleAddSlabClick = () => {
    if (slabs.length === 0) {
      setSlabs([
        {
          min_distance_km: 0,
          max_distance_km: null,
          fare_amount: 10,
        },
      ]);
      return;
    }

    const lastSlab = slabs[slabs.length - 1];
    const prevMax = safeNumber(lastSlab.max_distance_km);

    // If last slab already has a finite max distance: normal contiguous addition
    if (prevMax !== null) {
      const nextFare = (safeNumber(lastSlab.fare_amount) ?? 10) + 5;
      setSlabs([
        ...slabs,
        {
          min_distance_km: prevMax,
          max_distance_km: null, // open-ended final slab
          fare_amount: nextFare,
        },
      ]);
      setShowSplitPrompt(false);
      return;
    }

    // Amendment 1: Current final slab is open-ended.
    // DO NOT silently invent a new boundary. Require the Admin to provide the split boundary.
    setSplitBoundaryInput("");
    setSplitError(null);
    setShowSplitPrompt(true);
  };

  const handleConfirmSplit = () => {
    if (slabs.length === 0) return;
    const lastIdx = slabs.length - 1;
    const lastSlab = slabs[lastIdx];
    const prevMin = safeNumber(lastSlab.min_distance_km) ?? 0;

    const boundaryNum = Number(splitBoundaryInput);
    if (!splitBoundaryInput.trim() || isNaN(boundaryNum)) {
      setSplitError("Please enter a valid numeric distance.");
      return;
    }

    if (boundaryNum <= prevMin) {
      setSplitError(`Split boundary (${boundaryNum} km) must be greater than current slab start (${prevMin} km).`);
      return;
    }

    // Transform: 15 km → Open into 15 km → [new boundary] and [new boundary] → Open
    const updatedSlabs = [...slabs];
    updatedSlabs[lastIdx] = {
      ...lastSlab,
      max_distance_km: boundaryNum,
    };

    const nextFare = (safeNumber(lastSlab.fare_amount) ?? 10) + 5;
    updatedSlabs.push({
      min_distance_km: boundaryNum,
      max_distance_km: null, // the final slab remains the only open-ended slab
      fare_amount: nextFare,
    });

    setSlabs(updatedSlabs);
    setShowSplitPrompt(false);
    setSplitBoundaryInput("");
    setSplitError(null);
  };

  const handleRemoveSlab = (index: number) => {
    if (slabs.length <= 1) return;
    const newSlabs = [...slabs];
    newSlabs.splice(index, 1);
    setSlabs(newSlabs);
    // Clear any row errors
    setRowErrors({});
    setFormError(null);
  };

  const handleSlabChange = (
    index: number,
    field: keyof FareSlabItem,
    rawVal: string
  ) => {
    const newSlabs = [...slabs];
    let parsed: number | null = null;
    if (rawVal.trim() !== "") {
      const n = Number(rawVal);
      parsed = isNaN(n) ? 0 : n;
    }

    if (field === "max_distance_km") {
      newSlabs[index] = { ...newSlabs[index], max_distance_km: parsed };
    } else if (field === "min_distance_km") {
      newSlabs[index] = {
        ...newSlabs[index],
        min_distance_km: parsed !== null ? parsed : 0,
      };
    } else if (field === "fare_amount") {
      newSlabs[index] = {
        ...newSlabs[index],
        fare_amount: parsed !== null ? parsed : 0,
      };
    }

    setSlabs(newSlabs);
    // Clear error for this row when changed
    if (rowErrors[index]) {
      const updatedErrors = { ...rowErrors };
      delete updatedErrors[index];
      setRowErrors(updatedErrors);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fare) return;

    setFormError(null);
    setRowErrors({});
    setSuccessMsg(null);

    // Client-side validation mirroring backend rules precisely
    if (!name.trim()) {
      setFormError("Fare configuration name cannot be empty.");
      return;
    }

    if (slabs.length === 0) {
      setFormError("Fare configuration must have at least one slab.");
      return;
    }

    const firstMin = safeNumber(slabs[0].min_distance_km);
    if (firstMin !== 0) {
      const msg = "The first fare slab must start at 0.0 km.";
      setFormError(msg);
      setRowErrors({ 0: msg });
      return;
    }

    const newRowErrors: Record<number, string> = {};
    let firstError: string | null = null;

    for (let i = 0; i < slabs.length; i++) {
      const s = slabs[i];
      const minD = safeNumber(s.min_distance_km);
      const maxD = safeNumber(s.max_distance_km);
      const amt = safeNumber(s.fare_amount);

      if (minD === null || minD < 0) {
        const msg = `Slab ${i + 1}: Min distance cannot be negative or empty.`;
        if (!firstError) firstError = msg;
        newRowErrors[i] = msg;
        break;
      }

      if (amt === null || amt < 0) {
        const msg = `Slab ${i + 1}: Fare amount cannot be negative.`;
        if (!firstError) firstError = msg;
        newRowErrors[i] = msg;
        break;
      }

      if (maxD !== null) {
        if (maxD <= minD) {
          const msg = `Slab ${i + 1}: Max distance (${maxD} km) must be greater than Min distance (${minD} km).`;
          if (!firstError) firstError = msg;
          newRowErrors[i] = msg;
          break;
        }
      } else if (i !== slabs.length - 1) {
        const msg = `Slab ${i + 1}: Only the final slab may be open-ended (leave Max Distance empty).`;
        if (!firstError) firstError = msg;
        newRowErrors[i] = msg;
        break;
      }

      // Check continuity with next slab
      if (i < slabs.length - 1) {
        const nextMin = safeNumber(slabs[i + 1].min_distance_km);
        if (maxD === null) {
          const msg = `Slab ${i + 1}: Cannot have subsequent slabs after an open-ended slab.`;
          if (!firstError) firstError = msg;
          newRowErrors[i] = msg;
          break;
        }
        if (nextMin !== maxD) {
          const msg = `Slabs must remain continuous: Slab ${i + 1} ends at ${maxD} km, but Slab ${i + 2} starts at ${nextMin} km.`;
          if (!firstError) firstError = msg;
          newRowErrors[i + 1] = msg;
          break;
        }
      }
    }

    if (firstError) {
      setFormError(firstError);
      setRowErrors(newRowErrors);
      return;
    }

    try {
      setSubmitting(true);
      const payload = {
        name: name.trim(),
        currency: fare.currency || "INR",
        effective_from: effectiveFrom,
        effective_until: effectiveUntil || null,
        slabs: slabs.map((s) => ({
          min_distance_km: safeNumber(s.min_distance_km) ?? 0,
          max_distance_km: safeNumber(s.max_distance_km),
          fare_amount: safeNumber(s.fare_amount) ?? 0,
        })),
      };

      const updated = await updateFareConfiguration(fare.id, payload);
      setFare(updated);
      populateForm(updated);
      setMode("view");
      setSuccessMsg("Fare configuration and rate chart updated successfully.");
      onFareUpdated?.(updated);
    } catch (err: any) {
      setFormError(err.message || "Failed to update fare configuration.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10000,
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: "#161922",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          borderRadius: "14px",
          width: "100%",
          maxWidth: "780px",
          maxHeight: "90vh",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          color: "#f8fafc",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header: Answers "What Fare is this?", "What Service does it belong to?", "Is it active?" */}
        <div
          style={{
            padding: "18px 24px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            backgroundColor: "rgba(255, 255, 255, 0.02)",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px", minWidth: 0 }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "10px",
                backgroundColor: "rgba(99, 102, 241, 0.15)",
                border: "1px solid rgba(99, 102, 241, 0.3)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Banknote size={22} style={{ color: "#818cf8" }} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <h3
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    margin: 0,
                    color: "#f8fafc",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {loading
                    ? "Loading Fare..."
                    : mode === "edit"
                    ? "Edit Fare Configuration"
                    : fare?.name || "Fare Details"}
                </h3>
                {fare?.is_active !== undefined && (
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor: fare.is_active
                        ? "rgba(34, 197, 94, 0.12)"
                        : "rgba(148, 163, 184, 0.12)",
                      color: fare.is_active ? "#4ade80" : "#94a3b8",
                      border: fare.is_active
                        ? "1px solid rgba(34, 197, 94, 0.25)"
                        : "1px solid rgba(148, 163, 184, 0.2)",
                    }}
                  >
                    {fare.is_active ? "Active" : "Inactive"}
                  </span>
                )}
              </div>

              {/* Service Context Subtitle */}
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                <Bus size={13} style={{ color: "#818cf8" }} />
                <span style={{ fontSize: "12px", color: "#cbd5e1", fontWeight: 500 }}>
                  Attached Service:
                </span>
                {fare?.service_code ? (
                  <span
                    style={{
                      fontSize: "12px",
                      color: "#c7d2fe",
                      backgroundColor: "rgba(99, 102, 241, 0.14)",
                      border: "1px solid rgba(99, 102, 241, 0.25)",
                      padding: "1px 6px",
                      borderRadius: "4px",
                      fontWeight: 600,
                    }}
                  >
                    {fare.service_name ? `${fare.service_name} · ${fare.service_code}` : fare.service_code}
                  </span>
                ) : (
                  <span style={{ fontSize: "12px", color: "#64748b", fontStyle: "italic" }}>
                    Unassigned
                  </span>
                )}
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            title="Close dialog"
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              padding: "6px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#f8fafc";
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.06)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "#94a3b8";
              e.currentTarget.style.backgroundColor = "transparent";
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body with Internal Scrolling */}
        <div style={{ padding: "24px", overflowY: "auto", flex: 1 }}>
          {loading ? (
            <div
              style={{
                padding: "60px 20px",
                textAlign: "center",
                color: "#94a3b8",
                fontSize: "14px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "12px",
              }}
            >
              <Loader2 size={24} className="animate-spin" style={{ color: "#818cf8" }} />
              <span>Loading fare configuration details...</span>
            </div>
          ) : error || !fare ? (
            <div
              style={{
                padding: "20px",
                borderRadius: "8px",
                backgroundColor: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                color: "#f87171",
                fontSize: "14px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <AlertCircle size={18} />
              <span>{error || "Fare configuration not found."}</span>
            </div>
          ) : mode === "view" ? (
            /* VIEW MODE: High-clarity Operational Fare Details + Rate Chart */
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              {successMsg && (
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "6px",
                    backgroundColor: "rgba(34, 197, 94, 0.12)",
                    border: "1px solid rgba(34, 197, 94, 0.3)",
                    color: "#4ade80",
                    fontSize: "13px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <CheckCircle2 size={16} />
                  <span>{successMsg}</span>
                </div>
              )}

              {/* Top Operational Metadata Strip */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                  gap: "12px",
                }}
              >
                {/* Service Card */}
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                  }}
                >
                  <span
                    style={{
                      fontSize: "11px",
                      color: "#64748b",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      fontWeight: 600,
                    }}
                  >
                    Attached Service
                  </span>
                  <div
                    style={{
                      fontWeight: 700,
                      color: "#f8fafc",
                      fontSize: "13px",
                      marginTop: "4px",
                    }}
                  >
                    {fare.service_name ? `${fare.service_name} · ${fare.service_code}` : fare.service_code || "—"}
                  </div>
                </div>

                {/* Status Card */}
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                  }}
                >
                  <span
                    style={{
                      fontSize: "11px",
                      color: "#64748b",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      fontWeight: 600,
                    }}
                  >
                    Status
                  </span>
                  <div style={{ marginTop: "4px" }}>
                    <span
                      style={{
                        fontSize: "12px",
                        fontWeight: 600,
                        padding: "2px 8px",
                        borderRadius: "4px",
                        backgroundColor: fare.is_active
                          ? "rgba(34, 197, 94, 0.12)"
                          : "rgba(148, 163, 184, 0.12)",
                        color: fare.is_active ? "#4ade80" : "#94a3b8",
                        border: fare.is_active
                          ? "1px solid rgba(34, 197, 94, 0.25)"
                          : "1px solid rgba(148, 163, 184, 0.2)",
                        display: "inline-block",
                      }}
                    >
                      {fare.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                </div>

                {/* Effective From Card */}
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                  }}
                >
                  <span
                    style={{
                      fontSize: "11px",
                      color: "#64748b",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      fontWeight: 600,
                    }}
                  >
                    Effective From
                  </span>
                  <div
                    style={{
                      fontWeight: 600,
                      color: "#f8fafc",
                      fontSize: "13px",
                      marginTop: "4px",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <Calendar size={13} style={{ color: "#818cf8" }} />
                    <span>{formatDate(fare.effective_from)}</span>
                  </div>
                  {fare.effective_until && (
                    <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                      Until: {formatDate(fare.effective_until)}
                    </div>
                  )}
                </div>

                {/* Slabs Count Card */}
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                  }}
                >
                  <span
                    style={{
                      fontSize: "11px",
                      color: "#64748b",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                      fontWeight: 600,
                    }}
                  >
                    Configured Slabs
                  </span>
                  <div
                    style={{
                      fontWeight: 700,
                      color: "#818cf8",
                      fontSize: "13px",
                      marginTop: "4px",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <Layers size={13} />
                    <span>{fare.slabs.length} {fare.slabs.length === 1 ? "slab" : "slabs"}</span>
                  </div>
                </div>
              </div>

              {/* Complete Operational Rate Chart */}
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "10px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Layers size={15} style={{ color: "#818cf8" }} />
                    <h4
                      style={{
                        fontSize: "13px",
                        fontWeight: 700,
                        color: "#f8fafc",
                        margin: 0,
                        letterSpacing: "0.04em",
                        textTransform: "uppercase",
                      }}
                    >
                      Rate Chart
                    </h4>
                  </div>
                  <span style={{ fontSize: "12px", color: "#94a3b8" }}>
                    Currency: <strong style={{ color: "#f8fafc" }}>{fare.currency || "INR"}</strong>
                  </span>
                </div>

                <div
                  style={{
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "8px",
                    overflow: "hidden",
                    backgroundColor: "rgba(0, 0, 0, 0.2)",
                    maxHeight: "380px",
                    overflowY: "auto",
                  }}
                >
                  {fare.slabs.length === 0 ? (
                    <div
                      style={{
                        padding: "40px 20px",
                        textAlign: "center",
                        color: "#64748b",
                        fontSize: "13px",
                      }}
                    >
                      No distance slabs defined for this fare configuration.
                    </div>
                  ) : (
                    <table
                      style={{
                        width: "100%",
                        borderCollapse: "collapse",
                        fontSize: "13px",
                        textAlign: "left",
                      }}
                    >
                      <thead>
                        <tr
                          style={{
                            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                            backgroundColor: "#1b1f2b",
                            position: "sticky",
                            top: 0,
                            zIndex: 2,
                          }}
                        >
                          <th
                            style={{
                              padding: "10px 14px",
                              color: "#94a3b8",
                              fontWeight: 600,
                              fontSize: "11px",
                              textTransform: "uppercase",
                              letterSpacing: "0.04em",
                              width: "48px",
                              textAlign: "center",
                            }}
                          >
                            #
                          </th>
                          <th
                            style={{
                              padding: "10px 14px",
                              color: "#94a3b8",
                              fontWeight: 600,
                              fontSize: "11px",
                              textTransform: "uppercase",
                              letterSpacing: "0.04em",
                            }}
                          >
                            Distance Range
                          </th>
                          <th
                            style={{
                              padding: "10px 14px",
                              color: "#94a3b8",
                              fontWeight: 600,
                              fontSize: "11px",
                              textTransform: "uppercase",
                              letterSpacing: "0.04em",
                              textAlign: "right",
                            }}
                          >
                            Min
                          </th>
                          <th
                            style={{
                              padding: "10px 14px",
                              color: "#94a3b8",
                              fontWeight: 600,
                              fontSize: "11px",
                              textTransform: "uppercase",
                              letterSpacing: "0.04em",
                              textAlign: "right",
                            }}
                          >
                            Max
                          </th>
                          <th
                            style={{
                              padding: "10px 18px",
                              color: "#94a3b8",
                              fontWeight: 600,
                              fontSize: "11px",
                              textTransform: "uppercase",
                              letterSpacing: "0.04em",
                              textAlign: "right",
                            }}
                          >
                            Fare
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {fare.slabs.map((slab, index) => {
                          const isOpenEnded = slab.max_distance_km === null || slab.max_distance_km === undefined;
                          return (
                            <tr
                              key={slab.id || index}
                              style={{
                                borderBottom:
                                  index < fare.slabs.length - 1
                                    ? "1px solid rgba(255, 255, 255, 0.04)"
                                    : "none",
                                backgroundColor:
                                  index % 2 === 1 ? "rgba(255, 255, 255, 0.015)" : "transparent",
                                transition: "background-color 0.15s ease",
                              }}
                              onMouseEnter={(e) =>
                                (e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.04)")
                              }
                              onMouseLeave={(e) =>
                                (e.currentTarget.style.backgroundColor =
                                  index % 2 === 1 ? "rgba(255, 255, 255, 0.015)" : "transparent")
                              }
                            >
                              <td
                                style={{
                                  padding: "12px 14px",
                                  color: "#64748b",
                                  fontFamily: "monospace",
                                  fontSize: "12px",
                                  textAlign: "center",
                                }}
                              >
                                {index + 1}
                              </td>

                              {/* Visual Distance Range */}
                              <td style={{ padding: "12px 14px" }}>
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                    color: "#f8fafc",
                                    fontWeight: 600,
                                  }}
                                >
                                  <span>{formatKm(slab.min_distance_km)}</span>
                                  <ArrowRight size={13} style={{ color: "#64748b" }} />
                                  {isOpenEnded ? (
                                    <span
                                      style={{
                                        color: "#38bdf8",
                                        backgroundColor: "rgba(56, 189, 248, 0.12)",
                                        border: "1px solid rgba(56, 189, 248, 0.25)",
                                        padding: "1px 6px",
                                        borderRadius: "4px",
                                        fontSize: "12px",
                                      }}
                                    >
                                      Above / Open
                                    </span>
                                  ) : (
                                    <span>{formatKm(slab.max_distance_km)}</span>
                                  )}
                                </div>
                              </td>

                              {/* Min Distance */}
                              <td
                                style={{
                                  padding: "12px 14px",
                                  color: "#cbd5e1",
                                  textAlign: "right",
                                  fontFamily: "monospace",
                                }}
                              >
                                {formatKm(slab.min_distance_km)}
                              </td>

                              {/* Max Distance */}
                              <td
                                style={{
                                  padding: "12px 14px",
                                  color: isOpenEnded ? "#38bdf8" : "#cbd5e1",
                                  textAlign: "right",
                                  fontFamily: isOpenEnded ? "inherit" : "monospace",
                                }}
                              >
                                {isOpenEnded ? (
                                  <span style={{ fontStyle: "italic", fontSize: "12px" }}>
                                    Open-ended (∞)
                                  </span>
                                ) : (
                                  formatKm(slab.max_distance_km)
                                )}
                              </td>

                              {/* Fare Amount */}
                              <td
                                style={{
                                  padding: "12px 18px",
                                  textAlign: "right",
                                  fontWeight: 700,
                                  color: "#4ade80",
                                  fontSize: "14px",
                                  fontFamily: "monospace",
                                }}
                              >
                                {formatPrice(slab.fare_amount, fare.currency)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* EDIT MODE: High-efficiency Operational Slabs Editor */
            <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
              {formError && (
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "6px",
                    backgroundColor: "rgba(239, 68, 68, 0.12)",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    color: "#f87171",
                    fontSize: "13px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <AlertCircle size={16} style={{ flexShrink: 0 }} />
                  <span>{formError}</span>
                </div>
              )}

              {/* Fare Config Metadata Inputs */}
              <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: "14px" }}>
                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#94a3b8",
                      marginBottom: "6px",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    Fare Configuration Name
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Fare - SD5"
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      backgroundColor: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "13px",
                      outline: "none",
                    }}
                  />
                </div>

                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#94a3b8",
                      marginBottom: "6px",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    Effective From
                  </label>
                  <input
                    type="date"
                    required
                    value={effectiveFrom}
                    onChange={(e) => setEffectiveFrom(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      backgroundColor: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "13px",
                      outline: "none",
                    }}
                  />
                </div>
              </div>

              {/* Slabs Editor Section */}
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "8px",
                  }}
                >
                  <label
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#94a3b8",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    Rate Slabs ({slabs.length})
                  </label>
                  <span style={{ fontSize: "11px", color: "#64748b" }}>
                    Leave final Max Distance empty for open-ended slab (∞)
                  </span>
                </div>

                {/* Slabs Grid Table (eliminates repetitive labels per row) */}
                <div
                  style={{
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "8px",
                    overflow: "hidden",
                    backgroundColor: "rgba(0, 0, 0, 0.2)",
                    maxHeight: "340px",
                    overflowY: "auto",
                  }}
                >
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                    <thead>
                      <tr
                        style={{
                          backgroundColor: "#1b1f2b",
                          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                          position: "sticky",
                          top: 0,
                          zIndex: 2,
                        }}
                      >
                        <th
                          style={{
                            padding: "8px 10px",
                            color: "#94a3b8",
                            fontWeight: 600,
                            width: "36px",
                            textAlign: "center",
                          }}
                        >
                          #
                        </th>
                        <th
                          style={{
                            padding: "8px 10px",
                            color: "#94a3b8",
                            fontWeight: 600,
                            textAlign: "left",
                          }}
                        >
                          Min Distance (km)
                        </th>
                        <th
                          style={{
                            padding: "8px 10px",
                            color: "#94a3b8",
                            fontWeight: 600,
                            textAlign: "left",
                          }}
                        >
                          Max Distance (km)
                        </th>
                        <th
                          style={{
                            padding: "8px 10px",
                            color: "#94a3b8",
                            fontWeight: 600,
                            textAlign: "left",
                          }}
                        >
                          Fare ({fare.currency || "INR"})
                        </th>
                        <th
                          style={{
                            padding: "8px 10px",
                            color: "#94a3b8",
                            fontWeight: 600,
                            width: "44px",
                            textAlign: "center",
                          }}
                        >
                          Action
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {slabs.map((slab, index) => {
                        const isFinal = index === slabs.length - 1;
                        const hasError = Boolean(rowErrors[index]);
                        return (
                          <React.Fragment key={index}>
                            <tr
                              style={{
                                borderBottom:
                                  index < slabs.length - 1
                                    ? "1px solid rgba(255, 255, 255, 0.04)"
                                    : "none",
                                backgroundColor: hasError
                                  ? "rgba(239, 68, 68, 0.06)"
                                  : index % 2 === 1
                                  ? "rgba(255, 255, 255, 0.015)"
                                  : "transparent",
                              }}
                            >
                              {/* Index */}
                              <td
                                style={{
                                  padding: "8px 10px",
                                  textAlign: "center",
                                  color: "#818cf8",
                                  fontWeight: 700,
                                  fontFamily: "monospace",
                                }}
                              >
                                {index + 1}
                              </td>

                              {/* Min Distance */}
                              <td style={{ padding: "8px 10px" }}>
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  required
                                  value={slab.min_distance_km}
                                  onChange={(e) =>
                                    handleSlabChange(index, "min_distance_km", e.target.value)
                                  }
                                  style={{
                                    width: "100%",
                                    padding: "6px 8px",
                                    backgroundColor: "rgba(0, 0, 0, 0.35)",
                                    border: hasError
                                      ? "1px solid #ef4444"
                                      : "1px solid rgba(255, 255, 255, 0.12)",
                                    borderRadius: "5px",
                                    color: "#f8fafc",
                                    fontSize: "12px",
                                    fontFamily: "monospace",
                                    outline: "none",
                                  }}
                                />
                              </td>

                              {/* Max Distance */}
                              <td style={{ padding: "8px 10px" }}>
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  placeholder={isFinal ? "Open-ended (∞)" : "Required"}
                                  value={
                                    slab.max_distance_km !== null &&
                                    slab.max_distance_km !== undefined
                                      ? slab.max_distance_km
                                      : ""
                                  }
                                  onChange={(e) =>
                                    handleSlabChange(index, "max_distance_km", e.target.value)
                                  }
                                  style={{
                                    width: "100%",
                                    padding: "6px 8px",
                                    backgroundColor: "rgba(0, 0, 0, 0.35)",
                                    border: hasError
                                      ? "1px solid #ef4444"
                                      : "1px solid rgba(255, 255, 255, 0.12)",
                                    borderRadius: "5px",
                                    color: "#f8fafc",
                                    fontSize: "12px",
                                    fontFamily: "monospace",
                                    outline: "none",
                                  }}
                                />
                              </td>

                              {/* Fare Amount */}
                              <td style={{ padding: "8px 10px" }}>
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  required
                                  value={slab.fare_amount}
                                  onChange={(e) =>
                                    handleSlabChange(index, "fare_amount", e.target.value)
                                  }
                                  style={{
                                    width: "100%",
                                    padding: "6px 8px",
                                    backgroundColor: "rgba(0, 0, 0, 0.35)",
                                    border: hasError
                                      ? "1px solid #ef4444"
                                      : "1px solid rgba(255, 255, 255, 0.12)",
                                    borderRadius: "5px",
                                    color: "#4ade80",
                                    fontWeight: 600,
                                    fontSize: "12px",
                                    fontFamily: "monospace",
                                    outline: "none",
                                  }}
                                />
                              </td>

                              {/* Delete Action (subtle, secondary) */}
                              <td style={{ padding: "8px 10px", textAlign: "center" }}>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveSlab(index)}
                                  disabled={slabs.length <= 1}
                                  title={
                                    slabs.length <= 1
                                      ? "Cannot remove the only slab"
                                      : `Remove slab ${index + 1}`
                                  }
                                  style={{
                                    background: "transparent",
                                    border: "none",
                                    color: slabs.length <= 1 ? "#475569" : "#94a3b8",
                                    cursor: slabs.length <= 1 ? "not-allowed" : "pointer",
                                    padding: "4px",
                                    borderRadius: "4px",
                                    display: "inline-flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    transition: "color 0.15s ease",
                                  }}
                                  onMouseEnter={(e) => {
                                    if (slabs.length > 1) e.currentTarget.style.color = "#ef4444";
                                  }}
                                  onMouseLeave={(e) => {
                                    if (slabs.length > 1) e.currentTarget.style.color = "#94a3b8";
                                  }}
                                >
                                  <Trash2 size={15} />
                                </button>
                              </td>
                            </tr>
                            {/* Inline Row-Level Error Message */}
                            {hasError && (
                              <tr style={{ backgroundColor: "rgba(239, 68, 68, 0.08)" }}>
                                <td colSpan={5} style={{ padding: "4px 12px 8px", color: "#f87171", fontSize: "11px" }}>
                                  ⚠️ {rowErrors[index]}
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Split Open-Ended Slab Safety Card (Amendment 1) */}
                {showSplitPrompt && (
                  <div
                    style={{
                      marginTop: "12px",
                      padding: "14px 16px",
                      borderRadius: "8px",
                      backgroundColor: "rgba(99, 102, 241, 0.1)",
                      border: "1px solid rgba(99, 102, 241, 0.3)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <AlertCircle size={16} style={{ color: "#818cf8" }} />
                      <strong style={{ fontSize: "13px", color: "#f8fafc" }}>
                        Specify Split Boundary for Open-Ended Slab {slabs.length}
                      </strong>
                    </div>
                    <p style={{ fontSize: "12px", color: "#cbd5e1", margin: 0 }}>
                      The current final slab starts at{" "}
                      <strong>{safeNumber(slabs[slabs.length - 1]?.min_distance_km) ?? 0} km</strong> and is open-ended.
                      Please enter the boundary distance (km) to close this slab and add a new open-ended slab beyond it.
                    </p>

                    {splitError && (
                      <div style={{ color: "#f87171", fontSize: "12px" }}>
                        ⚠️ {splitError}
                      </div>
                    )}

                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <input
                        type="number"
                        step="0.01"
                        min={(safeNumber(slabs[slabs.length - 1]?.min_distance_km) ?? 0) + 0.01}
                        placeholder={`e.g. ${(safeNumber(slabs[slabs.length - 1]?.min_distance_km) ?? 0) + 5}`}
                        value={splitBoundaryInput}
                        onChange={(e) => setSplitBoundaryInput(e.target.value)}
                        autoFocus
                        style={{
                          width: "160px",
                          padding: "6px 10px",
                          backgroundColor: "rgba(0, 0, 0, 0.4)",
                          border: "1px solid rgba(255, 255, 255, 0.15)",
                          borderRadius: "5px",
                          color: "#f8fafc",
                          fontSize: "13px",
                          outline: "none",
                          fontFamily: "monospace",
                        }}
                      />
                      <button
                        type="button"
                        onClick={handleConfirmSplit}
                        style={{
                          padding: "6px 14px",
                          backgroundColor: "#4f46e5",
                          border: "none",
                          borderRadius: "5px",
                          color: "#ffffff",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        Confirm Split & Add Slab
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setShowSplitPrompt(false);
                          setSplitError(null);
                        }}
                        style={{
                          padding: "6px 12px",
                          backgroundColor: "transparent",
                          border: "1px solid rgba(255, 255, 255, 0.12)",
                          borderRadius: "5px",
                          color: "#94a3b8",
                          fontSize: "12px",
                          cursor: "pointer",
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {/* Add Slab Button */}
                {!showSplitPrompt && (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "10px" }}>
                    <button
                      type="button"
                      onClick={handleAddSlabClick}
                      style={{
                        padding: "7px 14px",
                        backgroundColor: "rgba(99, 102, 241, 0.1)",
                        border: "1px solid rgba(99, 102, 241, 0.25)",
                        borderRadius: "6px",
                        color: "#818cf8",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        transition: "all 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = "rgba(99, 102, 241, 0.18)";
                        e.currentTarget.style.color = "#a5b4fc";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = "rgba(99, 102, 241, 0.1)";
                        e.currentTarget.style.color = "#818cf8";
                      }}
                    >
                      <Plus size={14} /> Add Slab
                    </button>
                    <span style={{ fontSize: "11px", color: "#64748b" }}>
                      Slabs must be contiguous. The final slab is open-ended.
                    </span>
                  </div>
                )}
              </div>
            </form>
          )}
        </div>

        {/* Modal Footer Actions (Always visible, locked at bottom) */}
        <div
          style={{
            padding: "16px 24px",
            borderTop: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: "10px",
            backgroundColor: "rgba(0, 0, 0, 0.25)",
            flexShrink: 0,
          }}
        >
          {mode === "view" ? (
            <>
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: "8px 18px",
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.12)",
                  borderRadius: "6px",
                  color: "#cbd5e1",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.08)";
                  e.currentTarget.style.color = "#f8fafc";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
                  e.currentTarget.style.color = "#cbd5e1";
                }}
              >
                Close
              </button>

              {fare && (
                <button
                  type="button"
                  onClick={switchToEdit}
                  style={{
                    padding: "8px 18px",
                    backgroundColor: "#4f46e5",
                    border: "none",
                    borderRadius: "6px",
                    color: "#ffffff",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    boxShadow: "0 2px 4px rgba(79, 70, 229, 0.3)",
                    transition: "all 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = "#4338ca";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "#4f46e5";
                  }}
                >
                  <Edit2 size={14} /> Edit Fare
                </button>
              )}
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={cancelEdit}
                disabled={submitting}
                style={{
                  padding: "8px 18px",
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.12)",
                  borderRadius: "6px",
                  color: "#cbd5e1",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: submitting ? "not-allowed" : "pointer",
                  transition: "all 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  if (!submitting) {
                    e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.08)";
                    e.currentTarget.style.color = "#f8fafc";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!submitting) {
                    e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
                    e.currentTarget.style.color = "#cbd5e1";
                  }
                }}
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleSave}
                disabled={submitting}
                style={{
                  padding: "8px 20px",
                  backgroundColor: submitting ? "#3730a3" : "#4f46e5",
                  border: "none",
                  borderRadius: "6px",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: submitting ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "7px",
                  boxShadow: "0 2px 4px rgba(79, 70, 229, 0.3)",
                  transition: "all 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  if (!submitting) e.currentTarget.style.backgroundColor = "#4338ca";
                }}
                onMouseLeave={(e) => {
                  if (!submitting) e.currentTarget.style.backgroundColor = "#4f46e5";
                }}
              >
                {submitting ? (
                  <>
                    <Loader2 size={14} className="animate-spin" /> Saving Changes...
                  </>
                ) : (
                  <>
                    <Save size={14} /> Save Changes
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
