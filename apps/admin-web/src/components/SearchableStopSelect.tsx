import React, { useState, useRef, useEffect, useMemo } from "react";
import { Search, ChevronDown, X, Check, AlertCircle } from "lucide-react";

export interface StopOption {
  id: string;
  stop_code: string;
  name: string;
  aliases?: string[];
  latitude?: number;
  longitude?: number;
  status?: string;
}

export interface SearchableStopSelectProps {
  stops: StopOption[];
  value: string;
  onChange: (stopId: string) => void;
  placeholder?: string;
  disabledStopIds?: string[];
  disabled?: boolean;
  required?: boolean;
  accentColor?: string;
  id?: string;
}

export const SearchableStopSelect: React.FC<SearchableStopSelectProps> = ({
  stops,
  value,
  onChange,
  placeholder = "-- Select Existing Stop --",
  disabledStopIds = [],
  disabled = false,
  accentColor,
  id,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [openDirection, setOpenDirection] = useState<"down" | "up">("down");

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Find currently selected stop object
  const selectedStop = useMemo(() => {
    return stops.find((s) => s.id === value) || null;
  }, [stops, value]);

  // Client-side search across stop_code, name, and aliases
  const filteredStops = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return stops;

    return stops.filter((s) => {
      const codeMatch = s.stop_code.toLowerCase().includes(q);
      const nameMatch = s.name.toLowerCase().includes(q);
      const aliasMatch = s.aliases && s.aliases.some((a) => a.toLowerCase().includes(q));
      return codeMatch || nameMatch || aliasMatch;
    });
  }, [stops, searchQuery]);

  // Handle open direction and auto-focus
  useEffect(() => {
    if (isOpen && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;

      // If available space below is small (< 280px) and above is larger, open upward
      if (spaceBelow < 280 && spaceAbove > spaceBelow) {
        setOpenDirection("up");
      } else {
        setOpenDirection("down");
      }

      setHighlightedIndex(-1);
      // Focus the search input with a slight delay for render stability
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

  // Outside click handler to close dropdown without altering value
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
        let next = prev + 1;
        if (next >= filteredStops.length) next = 0;
        return next;
      });
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => {
        let next = prev - 1;
        if (next < 0) next = filteredStops.length - 1;
        return next;
      });
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < filteredStops.length) {
        const item = filteredStops[highlightedIndex];
        const isDuplicate = disabledStopIds.includes(item.id) && item.id !== value;
        if (!isDuplicate) {
          handleSelectStop(item.id);
        }
      }
    }
  };

  // Scroll highlighted item into view
  useEffect(() => {
    if (isOpen && listRef.current && highlightedIndex >= 0) {
      const itemEl = listRef.current.children[highlightedIndex] as HTMLElement;
      if (itemEl) {
        itemEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
  }, [highlightedIndex, isOpen]);

  const handleSelectStop = (stopId: string) => {
    onChange(stopId);
    setIsOpen(false);
  };

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
      }}
      onKeyDown={handleKeyDown}
    >
      {/* TRIGGER BUTTON (CLOSED STATE) */}
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        style={{
          width: "100%",
          padding: "10px 14px",
          borderRadius: "8px",
          border: isOpen
            ? `1px solid ${accentColor || "var(--accent, #3b82f6)"}`
            : "1px solid var(--border, rgba(255, 255, 255, 0.15))",
          background: "var(--bg-dark, #0b0f17)",
          color: selectedStop ? "var(--text-main, #ffffff)" : "var(--text-muted, #94a3b8)",
          fontFamily: "inherit",
          fontSize: "0.9rem",
          fontWeight: 500,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
          boxShadow: isOpen ? `0 0 0 2px ${accentColor ? accentColor + "33" : "rgba(59, 130, 246, 0.25)"}` : "none",
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
          {selectedStop ? (
            <>
              <span
                style={{
                  fontWeight: 700,
                  color: accentColor || "var(--text-main, #ffffff)",
                  flexShrink: 0,
                }}
              >
                {selectedStop.stop_code}
              </span>
              <span style={{ color: "var(--text-muted, #64748b)" }}>—</span>
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  color: "var(--text-main, #ffffff)",
                }}
                title={selectedStop.name}
              >
                {selectedStop.name}
              </span>
            </>
          ) : (
            <span style={{ color: "var(--text-muted, #94a3b8)" }}>{placeholder}</span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0, marginLeft: "8px" }}>
          {selectedStop && !disabled && (
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
          {/* SEARCH FIELD AT TOP */}
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
              placeholder="Search by Stop Code, Name, or Alias..."
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

          {/* RESULTS LIST (INTERNAL SCROLL ONLY) */}
          <div
            ref={listRef}
            style={{
              overflowY: "auto",
              flex: 1,
              maxHeight: "240px",
              padding: "4px",
            }}
          >
            {filteredStops.length === 0 ? (
              <div
                style={{
                  padding: "24px 16px",
                  textAlign: "center",
                  color: "var(--text-muted, #94a3b8)",
                  fontSize: "0.85rem",
                }}
              >
                No matching Stops found.
              </div>
            ) : (
              filteredStops.map((stop, idx) => {
                const isSelected = stop.id === value;
                const isDuplicate = disabledStopIds.includes(stop.id) && !isSelected;
                const isHighlighted = idx === highlightedIndex;

                // Determine matched alias if any
                const queryLower = searchQuery.trim().toLowerCase();
                const matchedAlias = queryLower
                  ? stop.aliases?.find((a) => a.toLowerCase().includes(queryLower))
                  : stop.aliases && stop.aliases.length > 0
                  ? stop.aliases[0]
                  : null;

                return (
                  <div
                    key={stop.id}
                    onClick={() => {
                      if (!isDuplicate) {
                        handleSelectStop(stop.id);
                      }
                    }}
                    onMouseEnter={() => setHighlightedIndex(idx)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "6px",
                      cursor: isDuplicate ? "not-allowed" : "pointer",
                      background: isHighlighted
                        ? "rgba(255, 255, 255, 0.08)"
                        : isSelected
                        ? "rgba(59, 130, 246, 0.15)"
                        : "transparent",
                      border: isSelected ? "1px solid rgba(59, 130, 246, 0.3)" : "1px solid transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "8px",
                      opacity: isDuplicate ? 0.4 : 1,
                      transition: "background 0.1s ease",
                      marginBottom: "2px",
                    }}
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: 0, flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
                        <span
                          style={{
                            fontWeight: 700,
                            fontSize: "0.85rem",
                            color: isSelected ? "var(--accent, #3b82f6)" : "var(--text-main, #ffffff)",
                            flexShrink: 0,
                          }}
                        >
                          {stop.stop_code}
                        </span>
                        <span style={{ color: "var(--text-muted, #64748b)" }}>—</span>
                        <span
                          style={{
                            fontSize: "0.85rem",
                            fontWeight: 500,
                            color: isSelected ? "var(--accent, #3b82f6)" : "var(--text-main, #ffffff)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {stop.name}
                        </span>
                      </div>

                      {matchedAlias && (
                        <div
                          style={{
                            fontSize: "0.75rem",
                            color: "var(--text-muted, #94a3b8)",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <span
                            style={{
                              background: "rgba(255, 255, 255, 0.06)",
                              padding: "1px 6px",
                              borderRadius: "4px",
                              fontSize: "0.7rem",
                              color: "var(--text-muted, #94a3b8)",
                            }}
                          >
                            Alias: {matchedAlias}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* STATUS / BADGE */}
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                      {isDuplicate && (
                        <span
                          style={{
                            fontSize: "0.7rem",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            background: "rgba(239, 68, 68, 0.15)",
                            color: "var(--danger, #ef4444)",
                            border: "1px solid rgba(239, 68, 68, 0.3)",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                        >
                          <AlertCircle size={10} /> Already selected in this route
                        </span>
                      )}

                      {isSelected && (
                        <Check size={16} style={{ color: "var(--accent, #3b82f6)" }} />
                      )}
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
