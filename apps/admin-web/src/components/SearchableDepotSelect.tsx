import React, { useState, useRef, useEffect, useMemo } from "react";
import { Search, ChevronDown, X, Check, Building2, MapPin } from "lucide-react";
import type { MajorDepot } from "../api/api";

export interface SearchableDepotSelectProps {
  depots: MajorDepot[];
  value: string;
  onChange: (depotId: string) => void;
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  isLoading?: boolean;
}

export const SearchableDepotSelect: React.FC<SearchableDepotSelectProps> = ({
  depots,
  value,
  onChange,
  placeholder = "-- Select Major Depot --",
  disabled = false,
  id = "major-depot-select",
  isLoading = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [openDirection, setOpenDirection] = useState<"down" | "up">("down");

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Selected depot object
  const selectedDepot = useMemo(() => {
    return depots.find((d) => d.id === value) || null;
  }, [depots, value]);

  // Filtered depots based on search query
  const filteredDepots = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return depots;

    return depots.filter((d) => {
      const nameMatch = d.stop_name.toLowerCase().includes(q);
      const codeMatch = d.stop_code.toLowerCase().includes(q);
      return nameMatch || codeMatch;
    });
  }, [depots, searchQuery]);

  // Viewport direction detection
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
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((prev) =>
        prev < filteredDepots.length - 1 ? prev + 1 : 0
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) =>
        prev > 0 ? prev - 1 : filteredDepots.length - 1
      );
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < filteredDepots.length) {
        handleSelect(filteredDepots[highlightedIndex]);
      }
    }
  };

  const handleSelect = (depot: MajorDepot) => {
    onChange(depot.id);
    setIsOpen(false);
    setSearchQuery("");
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange("");
    setSearchQuery("");
  };

  return (
    <div
      ref={containerRef}
      id={id}
      style={{
        position: "relative",
        width: "100%",
        userSelect: "none",
      }}
      onKeyDown={handleKeyDown}
    >
      {/* Trigger Button */}
      <div
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        tabIndex={disabled ? -1 : 0}
        onClick={() => {
          if (!disabled && !isLoading) {
            setIsOpen((prev) => !prev);
          }
        }}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          minHeight: "46px",
          padding: "8px 14px",
          backgroundColor: "#161922",
          border: isOpen
            ? "1px solid #6366f1"
            : "1px solid rgba(255, 255, 255, 0.12)",
          borderRadius: "8px",
          cursor: disabled || isLoading ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
          boxShadow: isOpen ? "0 0 0 3px rgba(99, 102, 241, 0.25)" : "none",
          transition: "all 0.15s ease",
          outline: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1, minWidth: 0 }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "6px",
              background: selectedDepot
                ? "linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.2))"
                : "rgba(255, 255, 255, 0.05)",
              border: selectedDepot
                ? "1px solid rgba(99, 102, 241, 0.4)"
                : "1px solid rgba(255, 255, 255, 0.08)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Building2
              size={15}
              style={{ color: selectedDepot ? "#818cf8" : "#94a3b8" }}
            />
          </div>

          {selectedDepot ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                flexWrap: "wrap",
                minWidth: 0,
                overflow: "hidden",
              }}
            >
              <span
                style={{
                  fontWeight: 600,
                  fontSize: "14px",
                  color: "#f8fafc",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {selectedDepot.stop_name}
              </span>
              <span
                style={{
                  fontSize: "12px",
                  fontFamily: "monospace",
                  color: "#94a3b8",
                  backgroundColor: "rgba(255, 255, 255, 0.06)",
                  padding: "1px 6px",
                  borderRadius: "4px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                }}
              >
                {selectedDepot.stop_code}
              </span>
              <span
                style={{
                  fontSize: "11px",
                  color: "#a5b4fc",
                  backgroundColor: "rgba(99, 102, 241, 0.12)",
                  padding: "1px 6px",
                  borderRadius: "4px",
                  border: "1px solid rgba(99, 102, 241, 0.25)",
                }}
              >
                {selectedDepot.routes_count} {selectedDepot.routes_count === 1 ? "route" : "routes"}
              </span>
            </div>
          ) : (
            <span style={{ color: "#64748b", fontSize: "14px" }}>
              {isLoading ? "Loading Major Depots..." : placeholder}
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
          {selectedDepot && !disabled && (
            <button
              type="button"
              onClick={handleClear}
              title="Clear selection"
              style={{
                background: "transparent",
                border: "none",
                color: "#94a3b8",
                cursor: "pointer",
                padding: "2px",
                borderRadius: "4px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#f8fafc")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
            >
              <X size={15} />
            </button>
          )}
          <ChevronDown
            size={16}
            style={{
              color: "#94a3b8",
              transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.2s ease",
            }}
          />
        </div>
      </div>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            ...(openDirection === "up"
              ? { bottom: "calc(100% + 4px)" }
              : { top: "calc(100% + 4px)" }),
            backgroundColor: "#161922",
            border: "1px solid rgba(255, 255, 255, 0.15)",
            borderRadius: "8px",
            boxShadow:
              "0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4)",
            zIndex: 9999,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            maxHeight: "340px",
          }}
        >
          {/* Search Box */}
          <div
            style={{
              padding: "8px",
              borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              backgroundColor: "rgba(0, 0, 0, 0.2)",
            }}
          >
            <Search size={15} style={{ color: "#64748b", flexShrink: 0 }} />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setHighlightedIndex(0);
              }}
              placeholder="Search depot by name or code..."
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#f8fafc",
                fontSize: "13px",
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#64748b",
                  cursor: "pointer",
                  padding: "2px",
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* Depot Options List */}
          <div
            ref={listRef}
            role="listbox"
            style={{
              overflowY: "auto",
              padding: "4px",
              display: "flex",
              flexDirection: "column",
              gap: "2px",
            }}
          >
            {filteredDepots.length === 0 ? (
              <div
                style={{
                  padding: "18px 12px",
                  textAlign: "center",
                  color: "#64748b",
                  fontSize: "13px",
                }}
              >
                No matching major depots found
              </div>
            ) : (
              filteredDepots.map((depot, idx) => {
                const isSelected = depot.id === value;
                const isHighlighted = idx === highlightedIndex;

                return (
                  <div
                    key={depot.id}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleSelect(depot)}
                    onMouseEnter={() => setHighlightedIndex(idx)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      cursor: "pointer",
                      backgroundColor: isSelected
                        ? "rgba(99, 102, 241, 0.15)"
                        : isHighlighted
                        ? "rgba(255, 255, 255, 0.05)"
                        : "transparent",
                      transition: "background-color 0.1s ease",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
                      <div
                        style={{
                          width: "24px",
                          height: "24px",
                          borderRadius: "4px",
                          backgroundColor: isSelected
                            ? "rgba(99, 102, 241, 0.25)"
                            : "rgba(255, 255, 255, 0.04)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        <MapPin
                          size={13}
                          style={{
                            color: isSelected ? "#818cf8" : "#94a3b8",
                          }}
                        />
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", gap: "2px", minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span
                            style={{
                              fontSize: "13px",
                              fontWeight: isSelected ? 600 : 500,
                              color: isSelected ? "#c7d2fe" : "#f1f5f9",
                            }}
                          >
                            {depot.stop_name}
                          </span>
                          <span
                            style={{
                              fontSize: "11px",
                              fontFamily: "monospace",
                              color: "#64748b",
                              backgroundColor: "rgba(255, 255, 255, 0.04)",
                              padding: "0 4px",
                              borderRadius: "3px",
                            }}
                          >
                            {depot.stop_code}
                          </span>
                        </div>
                        <span style={{ fontSize: "11px", color: "#64748b" }}>
                          Endpoint for {depot.routes_count} {depot.routes_count === 1 ? "route" : "routes"}
                        </span>
                      </div>
                    </div>

                    {isSelected && (
                      <Check size={16} style={{ color: "#818cf8", flexShrink: 0 }} />
                    )}
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
