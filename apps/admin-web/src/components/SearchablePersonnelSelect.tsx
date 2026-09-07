import React, { useState, useRef, useEffect, useLayoutEffect, useMemo, useCallback } from "react";
import { createPortal } from "react-dom";
import { Search, ChevronDown, X, Check, UserCheck, Phone, Shield } from "lucide-react";

export interface PersonnelOption {
  id: string;
  name: string;
  employee_code?: string;
  role: "DRIVER" | "CONDUCTOR" | string;
  phone?: string;
  email?: string;
  current_bus?: string;
  current_bus_id?: string;
  registration_number?: string;
}

export interface SearchablePersonnelSelectProps {
  personnel: PersonnelOption[];
  value: string;
  onChange: (userId: string) => void;
  role: "DRIVER" | "CONDUCTOR";
  placeholder?: string;
  disabled?: boolean;
  accentColor?: string;
  id?: string;
  error?: string;
  isLoading?: boolean;
  currentVehicleId?: string;
}

export const SearchablePersonnelSelect: React.FC<SearchablePersonnelSelectProps> = ({
  personnel,
  value,
  onChange,
  role,
  placeholder,
  disabled = false,
  accentColor,
  id,
  error,
  isLoading = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});

  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const defaultPlaceholder = role === "DRIVER" ? "-- Select Driver --" : "-- Select Conductor --";
  const effectivePlaceholder = placeholder || defaultPlaceholder;
  const roleLabel = role === "DRIVER" ? "Driver" : "Conductor";

  // Selected personnel object
  const selectedPerson = useMemo(() => {
    return personnel.find((p) => p.id === value) || null;
  }, [personnel, value]);

  // Client-side search across name, employee_code, phone, current_bus, registration_number
  const filteredPersonnel = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return personnel;

    return personnel.filter((p) => {
      const nameMatch = (p.name || "").toLowerCase().includes(q);
      const codeMatch = (p.employee_code || "").toLowerCase().includes(q);
      const phoneMatch = (p.phone || "").toLowerCase().includes(q);
      const busMatch = (p.current_bus || "").toLowerCase().includes(q);
      const regMatch = (p.registration_number || "").toLowerCase().includes(q);
      return nameMatch || codeMatch || phoneMatch || busMatch || regMatch;
    });
  }, [personnel, searchQuery]);

  // Viewport-aware position calculation
  const calculatePosition = useCallback((): React.CSSProperties | null => {
    if (!containerRef.current) return null;
    const rect = containerRef.current.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;

    // If trigger element is completely off-screen, don't position
    if (rect.bottom < 0 || rect.top > viewportHeight) {
      return null;
    }

    const spaceBelow = viewportHeight - rect.bottom;
    const spaceAbove = rect.top;

    const idealHeight = 280;
    const gap = 4;
    const margin = 12;

    // Open upward if space below is tight (< 240px) and there is more room above
    const openUp = spaceBelow < 240 && spaceAbove > spaceBelow;

    let maxHeight: number;
    let top: number | undefined;
    let bottom: number | undefined;

    if (openUp) {
      maxHeight = Math.min(idealHeight, Math.max(140, spaceAbove - gap - margin));
      bottom = viewportHeight - rect.top + gap;
      top = undefined;
    } else {
      maxHeight = Math.min(idealHeight, Math.max(140, spaceBelow - gap - margin));
      top = rect.bottom + gap;
      bottom = undefined;
    }

    let width = rect.width;
    let left = rect.left;

    // Constrain horizontally within viewport margins
    if (left + width > viewportWidth - margin) {
      left = Math.max(margin, viewportWidth - width - margin);
    }
    if (left < margin) {
      left = margin;
      width = Math.min(width, viewportWidth - margin * 2);
    }

    return {
      position: "fixed",
      left: `${left}px`,
      width: `${width}px`,
      ...(top !== undefined ? { top: `${top}px` } : {}),
      ...(bottom !== undefined ? { bottom: `${bottom}px` } : {}),
      maxHeight: `${maxHeight}px`,
      zIndex: 1200,
    };
  }, []);

  const updatePosition = useCallback(() => {
    const pos = calculatePosition();
    if (pos) {
      setDropdownStyle(pos);
    } else if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > window.innerHeight) {
        setIsOpen(false);
      }
    }
  }, [calculatePosition]);

  // Synchronous position update before paint when opening
  useLayoutEffect(() => {
    if (isOpen) {
      const pos = calculatePosition();
      if (pos) setDropdownStyle(pos);
    }
  }, [isOpen, calculatePosition]);

  // Focus search input on open, clear query on close
  useEffect(() => {
    if (isOpen) {
      setHighlightedIndex(-1);
      const timer = setTimeout(() => {
        if (searchInputRef.current) {
          searchInputRef.current.focus();
        }
      }, 40);
      return () => clearTimeout(timer);
    } else {
      setSearchQuery("");
      setHighlightedIndex(-1);
    }
  }, [isOpen]);

  // Reposition on modal/window scroll and resize
  useEffect(() => {
    if (!isOpen) return;

    const handleScroll = (e: Event) => {
      // Ignore scroll events originating from inside the dropdown list itself
      if (listRef.current && listRef.current.contains(e.target as Node)) {
        return;
      }
      updatePosition();
    };

    window.addEventListener("scroll", handleScroll, true);
    window.addEventListener("resize", updatePosition);

    return () => {
      window.removeEventListener("scroll", handleScroll, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [isOpen, updatePosition]);

  // Outside click listener handling both container and portalled dropdown
  useEffect(() => {
    if (!isOpen) return;

    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        containerRef.current &&
        !containerRef.current.contains(target) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(target)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleOutsideClick);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, [isOpen]);

  // Toggle open with immediate position calculation
  const handleToggle = () => {
    if (disabled) return;
    if (!isOpen) {
      const pos = calculatePosition();
      if (pos) setDropdownStyle(pos);
      setIsOpen(true);
    } else {
      setIsOpen(false);
    }
  };

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
        e.preventDefault();
        const pos = calculatePosition();
        if (pos) setDropdownStyle(pos);
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
        return next >= filteredPersonnel.length ? 0 : next;
      });
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => {
        const next = prev - 1;
        return next < 0 ? filteredPersonnel.length - 1 : next;
      });
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < filteredPersonnel.length) {
        const person = filteredPersonnel[highlightedIndex];
        onChange(person.id);
        setIsOpen(false);
      }
    }
  };

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIndex >= 0 && listRef.current) {
      const items = listRef.current.querySelectorAll<HTMLElement>(".person-select-item");
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
        zIndex: 1,
      }}
      onKeyDown={handleKeyDown}
    >
      {/* TRIGGER BUTTON */}
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        onClick={handleToggle}
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
          color: selectedPerson ? "var(--text-main, #ffffff)" : "var(--text-muted, #94a3b8)",
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
          <UserCheck size={16} style={{ color: accentColor || "var(--accent, #3b82f6)", flexShrink: 0 }} />
          {selectedPerson ? (
            <>
              {selectedPerson.employee_code && (
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
                  {selectedPerson.employee_code}
                </span>
              )}
              <span
                style={{
                  fontWeight: 600,
                  color: "var(--text-main, #ffffff)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={selectedPerson.name}
              >
                {selectedPerson.name}
              </span>

              {selectedPerson.current_bus ? (
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginLeft: "auto" }}>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted, #94a3b8)",
                      fontFamily: "monospace",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {selectedPerson.current_bus}
                    {selectedPerson.registration_number ? ` · ${selectedPerson.registration_number}` : ""}
                  </span>
                  <span
                    style={{
                      fontSize: "0.68rem",
                      padding: "2px 8px",
                      borderRadius: "12px",
                      background: "rgba(16, 185, 129, 0.15)",
                      color: "#10b981",
                      border: "1px solid rgba(16, 185, 129, 0.35)",
                      fontWeight: 700,
                      letterSpacing: "0.04em",
                      whiteSpace: "nowrap",
                    }}
                  >
                    ASSIGNED
                  </span>
                </div>
              ) : (
                <span
                  style={{
                    fontSize: "0.68rem",
                    padding: "2px 8px",
                    borderRadius: "12px",
                    background: "rgba(255, 255, 255, 0.08)",
                    color: "var(--text-muted, #94a3b8)",
                    border: "1px solid rgba(255, 255, 255, 0.15)",
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    marginLeft: "auto",
                    whiteSpace: "nowrap",
                  }}
                >
                  UNASSIGNED
                </span>
              )}

              {selectedPerson.phone && (
                <span
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-muted, #94a3b8)",
                    background: "rgba(255, 255, 255, 0.06)",
                    padding: "1px 6px",
                    borderRadius: "4px",
                    marginLeft: "auto",
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <Phone size={10} />
                  {selectedPerson.phone}
                </span>
              )}
            </>
          ) : (
            <span style={{ color: "var(--text-muted, #94a3b8)" }}>
              {isLoading ? `Loading ${roleLabel.toLowerCase()}s...` : effectivePlaceholder}
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0, marginLeft: "8px" }}>
          {selectedPerson && !disabled && (
            <button
              type="button"
              onClick={handleClear}
              title={`Unassign ${roleLabel}`}
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

      {/* DROPDOWN POPUP VIA PORTAL */}
      {isOpen &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            ref={dropdownRef}
            style={{
              ...dropdownStyle,
              background: "var(--bg-card, #161f30)",
              border: "1px solid var(--border, rgba(255, 255, 255, 0.15))",
              borderRadius: "10px",
              boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              animation: "fadeIn 0.15s ease",
            }}
            onKeyDown={handleKeyDown}
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
                placeholder={`Search ${roleLabel.toLowerCase()} by code, name, phone...`}
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
                minHeight: 0,
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
                Loading {roleLabel.toLowerCase()}s...
              </div>
            ) : personnel.length === 0 ? (
              <div
                style={{
                  padding: "20px 16px",
                  textAlign: "center",
                  color: "var(--text-muted, #94a3b8)",
                  fontSize: "0.85rem",
                  lineHeight: 1.5,
                }}
              >
                <Shield size={24} style={{ margin: "0 auto 8px auto", opacity: 0.4 }} />
                <div>
                  No {roleLabel.toLowerCase()}s available. Add a {roleLabel} in <strong>Users & Team</strong> before assigning crew.
                </div>
              </div>
            ) : filteredPersonnel.length === 0 ? (
              <div
                style={{
                  padding: "24px 16px",
                  textAlign: "center",
                  color: "var(--text-muted, #94a3b8)",
                  fontSize: "0.85rem",
                }}
              >
                No {roleLabel.toLowerCase()}s matching "{searchQuery}".
              </div>
            ) : (
              filteredPersonnel.map((person, index) => {
                const isSelected = person.id === value;
                const isHighlighted = index === highlightedIndex;

                return (
                  <div
                    key={person.id}
                    className="person-select-item"
                    onClick={() => {
                      onChange(person.id);
                      setIsOpen(false);
                    }}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      cursor: "pointer",
                      background: isSelected
                        ? "rgba(59, 130, 246, 0.15)"
                        : isHighlighted
                        ? "rgba(255, 255, 255, 0.05)"
                        : "transparent",
                      transition: "background-color 0.1s ease",
                      gap: "10px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        minWidth: 0,
                        flex: 1,
                      }}
                    >
                      {person.employee_code ? (
                        <span
                          style={{
                            fontWeight: 700,
                            fontFamily: "monospace",
                            color: isSelected ? "var(--accent, #3b82f6)" : "var(--text-main, #ffffff)",
                            background: isSelected
                              ? "rgba(59, 130, 246, 0.2)"
                              : "rgba(255, 255, 255, 0.08)",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            fontSize: "0.8rem",
                            flexShrink: 0,
                          }}
                        >
                          {person.employee_code}
                        </span>
                      ) : (
                        <span
                          style={{
                            fontFamily: "monospace",
                            color: "var(--text-muted, #64748b)",
                            fontSize: "0.75rem",
                            flexShrink: 0,
                          }}
                        >
                          [{role.substring(0, 3)}]
                        </span>
                      )}

                      <span
                        style={{
                          fontWeight: isSelected ? 600 : 400,
                          color: isSelected ? "var(--accent, #3b82f6)" : "var(--text-main, #ffffff)",
                          fontSize: "0.85rem",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {person.name}
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
                      {person.current_bus ? (
                        <>
                          <span
                            style={{
                              fontSize: "0.78rem",
                              color: "var(--text-muted, #94a3b8)",
                              fontFamily: "monospace",
                              fontWeight: 500,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {person.current_bus}
                            {person.registration_number ? ` · ${person.registration_number}` : ""}
                          </span>
                          <span
                            style={{
                              fontSize: "0.68rem",
                              padding: "2px 8px",
                              borderRadius: "12px",
                              background: "rgba(16, 185, 129, 0.15)",
                              color: "#10b981",
                              border: "1px solid rgba(16, 185, 129, 0.35)",
                              fontWeight: 700,
                              letterSpacing: "0.04em",
                              whiteSpace: "nowrap",
                            }}
                          >
                            ASSIGNED
                          </span>
                        </>
                      ) : (
                        <span
                          style={{
                            fontSize: "0.68rem",
                            padding: "2px 8px",
                            borderRadius: "12px",
                            background: "rgba(255, 255, 255, 0.08)",
                            color: "var(--text-muted, #94a3b8)",
                            border: "1px solid rgba(255, 255, 255, 0.15)",
                            fontWeight: 600,
                            letterSpacing: "0.04em",
                            whiteSpace: "nowrap",
                          }}
                        >
                          UNASSIGNED
                        </span>
                      )}

                      {person.phone && (
                        <span
                          style={{
                            fontSize: "0.75rem",
                            color: "var(--text-muted, #94a3b8)",
                            display: "flex",
                            alignItems: "center",
                            gap: "3px",
                          }}
                        >
                          <Phone size={10} />
                          {person.phone}
                        </span>
                      )}
                      {isSelected && <Check size={16} style={{ color: "var(--accent, #3b82f6)" }} />}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};
