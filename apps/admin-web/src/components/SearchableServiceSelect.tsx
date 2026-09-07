import React, { useState, useRef, useEffect, useMemo } from "react";
import { Search, ChevronDown, X, Check, Network } from "lucide-react";

export interface ServiceOption {
  id: string;
  service_code: string;
  service_name: string;
  route_id?: string;
  route_code?: string;
  route_name?: string;
  status?: string;
}

export interface SearchableServiceSelectProps {
  services: ServiceOption[];
  value: string;
  onChange: (serviceId: string) => void;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  accentColor?: string;
  id?: string;
  error?: string;
  isLoading?: boolean;
}

export const SearchableServiceSelect: React.FC<SearchableServiceSelectProps> = ({
  services,
  value,
  onChange,
  placeholder = "-- Select Existing Service --",
  disabled = false,
  accentColor,
  id,
  error,
  isLoading = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [openDirection, setOpenDirection] = useState<"down" | "up">("down");

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Selected service object
  const selectedService = useMemo(() => {
    return services.find((s) => s.id === value) || null;
  }, [services, value]);

  // Client-side search across service_code and service_name
  const filteredServices = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return services;

    return services.filter((s) => {
      const codeMatch = s.service_code.toLowerCase().includes(q);
      const nameMatch = (s.service_name || "").toLowerCase().includes(q);
      const routeCodeMatch = (s.route_code || "").toLowerCase().includes(q);
      const routeNameMatch = (s.route_name || "").toLowerCase().includes(q);
      return codeMatch || nameMatch || routeCodeMatch || routeNameMatch;
    });
  }, [services, searchQuery]);

  // Viewport-safe direction check and focus
  useEffect(() => {
    if (isOpen && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;

      if (spaceBelow < 280 && spaceAbove > spaceBelow) {
        setOpenDirection("up");
      } else {
        setOpenDirection("down");
      }

      setHighlightedIndex(-1);
      const timer = setTimeout(() => {
        if (searchInputRef.current) {
          searchInputRef.current.focus();
        }
      }, 50);

      return () => clearTimeout(timer);
    } else {
      setSearchQuery("");
      setHighlightedIndex(-1);
    }
  }, [isOpen]);

  // Outside click listener
  useEffect(() => {
    if (!isOpen) return;

    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, [isOpen]);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    if (e.key === "Escape") {
      e.preventDefault();
      setIsOpen(false);
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((prev) => {
        const next = prev + 1;
        return next >= filteredServices.length ? 0 : next;
      });
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => {
        const next = prev - 1;
        return next < 0 ? filteredServices.length - 1 : next;
      });
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < filteredServices.length) {
        const svc = filteredServices[highlightedIndex];
        onChange(svc.id);
        setIsOpen(false);
      }
    }
  };

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const items = listRef.current.querySelectorAll<HTMLElement>(".service-select-item");
      if (items[highlightedIndex]) {
        items[highlightedIndex].scrollIntoView({ block: "nearest" });
      }
    }
  }, [highlightedIndex]);

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange("");
    setIsOpen(false);
  };

  return (
    <div
      ref={containerRef}
      id={id}
      style={{
        position: "relative",
        width: "100%",
        minWidth: 0,
        zIndex: isOpen ? 50 : 1,
      }}
      onKeyDown={handleKeyDown}
    >
      {/* TRIGGER BUTTON */}
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        style={{
          width: "100%",
          padding: "10px 14px",
          borderRadius: "8px",
          border: error
            ? "1px solid var(--danger, #ef4444)"
            : isOpen
            ? `1px solid ${accentColor || "var(--accent, #3b82f6)"}`
            : "1px solid var(--border, rgba(255, 255, 255, 0.15))",
          background: "var(--bg-dark, #0b0f17)",
          color: selectedService ? "var(--text-main, #ffffff)" : "var(--text-muted, #94a3b8)",
          fontFamily: "inherit",
          fontSize: "0.9rem",
          fontWeight: 500,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
          boxShadow: isOpen
            ? `0 0 0 2px ${accentColor ? accentColor + "33" : "rgba(59, 130, 246, 0.25)"}`
            : "none",
          transition: "border-color 0.15s, box-shadow 0.15s",
          minWidth: 0,
          userSelect: "none",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            minWidth: 0,
            overflow: "hidden",
            whiteSpace: "nowrap",
            textOverflow: "ellipsis",
            flex: 1,
          }}
        >
          <Network size={16} style={{ color: "var(--accent, #3b82f6)", flexShrink: 0 }} />
          {selectedService ? (
            <>
              <span
                style={{
                  fontWeight: 700,
                  fontFamily: "monospace",
                  color: accentColor || "var(--accent, #3b82f6)",
                  flexShrink: 0,
                  background: "rgba(59, 130, 246, 0.12)",
                  padding: "2px 6px",
                  borderRadius: "4px",
                  fontSize: "0.85rem",
                }}
              >
                {selectedService.service_code}
              </span>
              <span style={{ color: "var(--text-muted, #64748b)" }}>—</span>
              <span
                style={{
                  fontWeight: 600,
                  color: "var(--text-main, #ffffff)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
                title={selectedService.service_name}
              >
                {selectedService.service_name}
              </span>
              {(selectedService.route_code || selectedService.route_name) && (
                <span
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-muted, #94a3b8)",
                    background: "rgba(255, 255, 255, 0.06)",
                    padding: "1px 6px",
                    borderRadius: "4px",
                    marginLeft: "auto",
                    flexShrink: 0,
                  }}
                >
                  {selectedService.route_code || selectedService.route_name}
                </span>
              )}
            </>
          ) : (
            <span style={{ color: "var(--text-muted, #94a3b8)" }}>
              {isLoading ? "Loading services..." : placeholder}
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0, marginLeft: "8px" }}>
          {selectedService && !disabled && (
            <button
              type="button"
              onClick={handleClear}
              title="Clear selection"
              style={{
                background: "transparent",
                border: "none",
                padding: "2px",
                cursor: "pointer",
                color: "var(--text-muted, #94a3b8)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "4px",
              }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = "var(--danger, #ef4444)")}
              onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = "var(--text-muted, #94a3b8)")}
            >
              <X size={15} />
            </button>
          )}
          <ChevronDown
            size={16}
            style={{
              color: "var(--text-muted, #94a3b8)",
              transform: isOpen ? "rotate(180deg)" : "none",
              transition: "transform 0.15s ease",
            }}
          />
        </div>
      </div>

      {/* DROPDOWN POPUP */}
      {isOpen && (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            [openDirection === "up" ? "bottom" : "top"]: "calc(100% + 4px)",
            zIndex: 100,
            background: "var(--bg-card, #161f30)",
            border: "1px solid var(--border, rgba(255, 255, 255, 0.15))",
            borderRadius: "10px",
            boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            maxHeight: "320px",
            animation: "fadeIn 0.15s ease",
          }}
        >
          {/* SEARCH FIELD */}
          <div
            style={{
              padding: "10px 12px",
              borderBottom: "1px solid var(--border, rgba(255, 255, 255, 0.1))",
              background: "var(--bg-dark, #0b0f17)",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              flexShrink: 0,
            }}
          >
            <Search size={16} style={{ color: "var(--text-muted, #94a3b8)", flexShrink: 0 }} />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by Service Code or Name..."
              style={{
                width: "100%",
                background: "transparent",
                border: "none",
                outline: "none",
                color: "var(--text-main, #ffffff)",
                fontSize: "0.85rem",
                fontFamily: "inherit",
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--text-muted, #94a3b8)",
                  padding: "2px",
                  display: "flex",
                }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* RESULTS LIST */}
          <div
            ref={listRef}
            style={{
              overflowY: "auto",
              flex: 1,
              maxHeight: "240px",
              padding: "4px",
            }}
          >
            {isLoading ? (
              <div
                style={{
                  padding: "24px 16px",
                  textAlign: "center",
                  color: "var(--text-muted, #94a3b8)",
                  fontSize: "0.85rem",
                }}
              >
                Loading services...
              </div>
            ) : error ? (
              <div
                style={{
                  padding: "24px 16px",
                  textAlign: "center",
                  color: "var(--danger, #ef4444)",
                  fontSize: "0.85rem",
                }}
              >
                {error}
              </div>
            ) : services.length === 0 ? (
              <div
                style={{
                  padding: "24px 16px",
                  textAlign: "center",
                  color: "var(--warning, #f59e0b)",
                  fontSize: "0.85rem",
                  lineHeight: 1.4,
                }}
              >
                No services available. Create a Service before managing fleet.
              </div>
            ) : filteredServices.length === 0 ? (
              <div
                style={{
                  padding: "24px 16px",
                  textAlign: "center",
                  color: "var(--text-muted, #94a3b8)",
                  fontSize: "0.85rem",
                }}
              >
                No matching services found.
              </div>
            ) : (
              filteredServices.map((svc, idx) => {
                const isSelected = svc.id === value;
                const isHighlighted = idx === highlightedIndex;

                return (
                  <div
                    key={svc.id}
                    className="service-select-item"
                    onClick={() => {
                      onChange(svc.id);
                      setIsOpen(false);
                    }}
                    onMouseEnter={() => setHighlightedIndex(idx)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "6px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      cursor: "pointer",
                      background: isSelected
                        ? "rgba(59, 130, 246, 0.18)"
                        : isHighlighted
                        ? "rgba(255, 255, 255, 0.05)"
                        : "transparent",
                      transition: "background 0.1s ease",
                      gap: "8px",
                      minWidth: 0,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        minWidth: 0,
                        overflow: "hidden",
                        flex: 1,
                      }}
                    >
                      <span
                        style={{
                          fontWeight: 700,
                          fontFamily: "monospace",
                          color: isSelected ? "var(--accent, #3b82f6)" : "var(--text-main, #ffffff)",
                          fontSize: "0.85rem",
                          background: "rgba(255, 255, 255, 0.06)",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          flexShrink: 0,
                        }}
                      >
                        {svc.service_code}
                      </span>
                      <span
                        style={{
                          color: isSelected ? "var(--text-main, #ffffff)" : "var(--text-muted, #cbd5e1)",
                          fontSize: "0.85rem",
                          fontWeight: 600,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={svc.service_name}
                      >
                        {svc.service_name}
                      </span>
                      {(svc.route_code || svc.route_name) && (
                        <span
                          style={{
                            fontSize: "0.75rem",
                            color: "var(--text-muted, #94a3b8)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            marginLeft: "4px",
                          }}
                        >
                          ({svc.route_code || svc.route_name})
                        </span>
                      )}
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
                      {isSelected && <Check size={16} color="var(--accent, #3b82f6)" />}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
