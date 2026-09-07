import React, { useState, useEffect, useMemo } from "react";
import {
  Users,
  Plus,
  Search,
  Filter,
  Key,
  Activity,
  Ban,
  CheckCircle,
  Edit2,
  Mail,
  Phone,
  X,
  AlertTriangle,
  Loader2,
  UserCheck,
  RotateCcw,
} from "lucide-react";
import {
  getAdminUsers,
  createAdminUser,
  updateAdminUser,
  updateAdminUserPassword,
  updateAdminUserStatus,
} from "../api/api";
import { useAuth } from "../contexts/AuthContext";

interface OperatorProfile {
  id?: string;
  employee_code: string;
  operator_type: string;
  verification_status?: string;
}

interface AdminUser {
  id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  role: "FLEET_ADMIN" | "DEPOT_ADMIN" | "DRIVER" | "CONDUCTOR" | string;
  status: "ACTIVE" | "INACTIVE" | "SUSPENDED" | string;
  created_at?: string;
  updated_at?: string;
  operator_profile?: OperatorProfile | null;
}

export const UsersPage: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [statusConfirmUser, setStatusConfirmUser] = useState<{
    user: AdminUser;
    targetStatus: "ACTIVE" | "INACTIVE";
  } | null>(null);

  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);

  // Form states
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    password: "",
    role: "DRIVER",
    employee_code: "",
    operator_type: "CITY_BUS",
  });

  const [passwordData, setPasswordData] = useState({ password: "", confirmPassword: "" });
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const isFleetAdmin = currentUser?.role === "FLEET_ADMIN";

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getAdminUsers(roleFilter, statusFilter);
      setUsers(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err.message || "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [roleFilter, statusFilter]);

  // Derived KPI metrics
  const kpiMetrics = useMemo(() => {
    const total = users.length;
    const active = users.filter((u) => u.status === "ACTIVE").length;
    const drivers = users.filter((u) => u.role === "DRIVER").length;
    const conductors = users.filter((u) => u.role === "CONDUCTOR").length;
    const admins = users.filter(
      (u) => u.role === "FLEET_ADMIN" || u.role === "DEPOT_ADMIN"
    ).length;

    return { total, active, drivers, conductors, admins };
  }, [users]);

  // Client-side filtered list for search
  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users;
    const query = searchQuery.toLowerCase().trim();

    return users.filter((u) => {
      const nameMatch = u.name?.toLowerCase().includes(query);
      const emailMatch = u.email?.toLowerCase().includes(query);
      const phoneMatch = u.phone?.toLowerCase().includes(query);
      const empMatch = u.operator_profile?.employee_code?.toLowerCase().includes(query);
      const idMatch = u.id?.toLowerCase().includes(query);
      return nameMatch || emailMatch || phoneMatch || empMatch || idMatch;
    });
  }, [users, searchQuery]);

  const hasActiveFilters = Boolean(roleFilter || statusFilter || searchQuery);

  const handleResetFilters = () => {
    setRoleFilter("");
    setStatusFilter("");
    setSearchQuery("");
  };

  // ── CREATE USER SUBMIT ──
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const trimmedName = formData.name.trim();
    if (!trimmedName) {
      setFormError("Full name is required.");
      return;
    }

    if (!formData.password || formData.password.length < 4) {
      setFormError("Initial password must be at least 4 characters long.");
      return;
    }

    if (
      (formData.role === "DRIVER" || formData.role === "CONDUCTOR") &&
      !formData.employee_code.trim()
    ) {
      setFormError("Employee code is required for operating personnel (Driver/Conductor).");
      return;
    }

    try {
      setFormSubmitting(true);
      const payload: any = {
        name: trimmedName,
        password: formData.password,
        role: formData.role,
        email: formData.email.trim() ? formData.email.trim() : undefined,
        phone: formData.phone.trim() ? formData.phone.trim() : undefined,
      };

      if (formData.role === "DRIVER" || formData.role === "CONDUCTOR") {
        payload.operator_profile = {
          employee_code: formData.employee_code.trim().toUpperCase(),
          operator_type: formData.operator_type || "CITY_BUS",
          verification_status: "PENDING",
        };
      }

      await createAdminUser(payload);
      setIsCreateModalOpen(false);
      setActionSuccess(`Team member "${trimmedName}" created successfully.`);
      fetchUsers();
    } catch (err: any) {
      setFormError(err.message || "Failed to create user");
    } finally {
      setFormSubmitting(false);
    }
  };

  // ── EDIT USER SUBMIT ──
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    setFormError(null);

    const trimmedName = formData.name.trim();
    if (!trimmedName) {
      setFormError("Full name is required.");
      return;
    }

    try {
      setFormSubmitting(true);
      const payload: any = {
        name: trimmedName,
        role: formData.role,
        email: formData.email.trim() ? formData.email.trim() : undefined,
        phone: formData.phone.trim() ? formData.phone.trim() : undefined,
      };

      if (formData.role === "DRIVER" || formData.role === "CONDUCTOR") {
        payload.employee_code = formData.employee_code.trim().toUpperCase() || undefined;
        payload.operator_type = formData.operator_type || undefined;
      }

      await updateAdminUser(selectedUser.id, payload);
      setIsEditModalOpen(false);
      setActionSuccess(`Updated personnel profile for "${trimmedName}".`);
      fetchUsers();
    } catch (err: any) {
      setFormError(err.message || "Failed to update user");
    } finally {
      setFormSubmitting(false);
    }
  };

  // ── PASSWORD RESET SUBMIT ──
  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    setFormError(null);

    if (!passwordData.password || passwordData.password.length < 4) {
      setFormError("Password must be at least 4 characters long.");
      return;
    }

    if (passwordData.password !== passwordData.confirmPassword) {
      setFormError("Passwords do not match.");
      return;
    }

    try {
      setFormSubmitting(true);
      await updateAdminUserPassword(selectedUser.id, { password: passwordData.password });
      setIsPasswordModalOpen(false);
      setActionSuccess(`Password reset successfully for "${selectedUser.name}".`);
    } catch (err: any) {
      setFormError(err.message || "Failed to update password");
    } finally {
      setFormSubmitting(false);
    }
  };

  // ── STATUS CONFIRM SUBMIT ──
  const handleConfirmStatusChange = async () => {
    if (!statusConfirmUser) return;
    const { user, targetStatus } = statusConfirmUser;

    try {
      setFormSubmitting(true);
      await updateAdminUserStatus(user.id, { status: targetStatus });
      setStatusConfirmUser(null);
      setActionSuccess(
        `User "${user.name}" status changed to ${targetStatus}.`
      );
      fetchUsers();
    } catch (err: any) {
      alert(err.message || `Failed to set status to ${targetStatus}`);
    } finally {
      setFormSubmitting(false);
    }
  };

  // Open modal handlers
  const openCreateModal = () => {
    setFormData({
      name: "",
      email: "",
      phone: "",
      password: "",
      role: "DRIVER",
      employee_code: "",
      operator_type: "CITY_BUS",
    });
    setFormError(null);
    setIsCreateModalOpen(true);
  };

  const openEditModal = (user: AdminUser) => {
    setSelectedUser(user);
    setFormData({
      name: user.name || "",
      email: user.email || "",
      phone: user.phone || "",
      password: "",
      role: user.role || "DRIVER",
      employee_code: user.operator_profile?.employee_code || "",
      operator_type: user.operator_profile?.operator_type || "CITY_BUS",
    });
    setFormError(null);
    setIsEditModalOpen(true);
  };

  const openPasswordModal = (user: AdminUser) => {
    setSelectedUser(user);
    setPasswordData({ password: "", confirmPassword: "" });
    setFormError(null);
    setIsPasswordModalOpen(true);
  };

  // Helper for role pill styling
  const getRoleBadgeStyle = (role: string) => {
    switch (role) {
      case "FLEET_ADMIN":
        return {
          bg: "rgba(168, 85, 247, 0.12)",
          border: "1px solid rgba(168, 85, 247, 0.3)",
          color: "#c084fc",
          label: "FLEET ADMIN",
          avatarBg: "rgba(168, 85, 247, 0.2)",
          avatarColor: "#c084fc",
        };
      case "DEPOT_ADMIN":
        return {
          bg: "rgba(56, 189, 248, 0.12)",
          border: "1px solid rgba(56, 189, 248, 0.3)",
          color: "#38bdf8",
          label: "DEPOT ADMIN",
          avatarBg: "rgba(56, 189, 248, 0.2)",
          avatarColor: "#38bdf8",
        };
      case "DRIVER":
        return {
          bg: "rgba(52, 211, 153, 0.12)",
          border: "1px solid rgba(52, 211, 153, 0.3)",
          color: "#34d399",
          label: "DRIVER",
          avatarBg: "rgba(52, 211, 153, 0.2)",
          avatarColor: "#34d399",
        };
      case "CONDUCTOR":
        return {
          bg: "rgba(251, 191, 36, 0.12)",
          border: "1px solid rgba(251, 191, 36, 0.3)",
          color: "#fbbf24",
          label: "CONDUCTOR",
          avatarBg: "rgba(251, 191, 36, 0.2)",
          avatarColor: "#fbbf24",
        };
      default:
        return {
          bg: "rgba(148, 163, 184, 0.12)",
          border: "1px solid rgba(148, 163, 184, 0.2)",
          color: "#94a3b8",
          label: role.replace("_", " "),
          avatarBg: "rgba(148, 163, 184, 0.2)",
          avatarColor: "#94a3b8",
        };
    }
  };

  // Helper for status pill styling
  const getStatusBadgeStyle = (status: string) => {
    switch (status) {
      case "ACTIVE":
        return {
          bg: "rgba(34, 197, 94, 0.15)",
          border: "1px solid rgba(34, 197, 94, 0.3)",
          color: "#4ade80",
        };
      case "INACTIVE":
        return {
          bg: "rgba(148, 163, 184, 0.12)",
          border: "1px solid rgba(148, 163, 184, 0.2)",
          color: "#94a3b8",
        };
      case "SUSPENDED":
        return {
          bg: "rgba(239, 68, 68, 0.15)",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          color: "#f87171",
        };
      default:
        return {
          bg: "rgba(148, 163, 184, 0.12)",
          border: "1px solid rgba(148, 163, 184, 0.2)",
          color: "#94a3b8",
        };
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "24px",
        color: "#f8fafc",
        paddingBottom: "40px",
      }}
    >
      {/* ── ACTION SUCCESS BANNER ── */}
      {actionSuccess && (
        <div
          style={{
            padding: "12px 18px",
            borderRadius: "10px",
            backgroundColor: "rgba(34, 197, 94, 0.12)",
            border: "1px solid rgba(34, 197, 94, 0.3)",
            color: "#4ade80",
            fontSize: "14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <UserCheck size={18} />
            <span>{actionSuccess}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionSuccess(null)}
            style={{
              background: "none",
              border: "none",
              color: "#4ade80",
              cursor: "pointer",
              padding: "4px",
            }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* ── PAGE HEADER (Section 4) ── */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "12px",
              fontWeight: 700,
              color: "#38bdf8",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: "4px",
            }}
          >
            PERSONNEL & ACCESS
          </div>
          <h1
            style={{
              fontSize: "24px",
              fontWeight: 700,
              margin: 0,
              color: "#f8fafc",
              letterSpacing: "-0.02em",
            }}
          >
            Users & Team
          </h1>
          <p
            style={{
              fontSize: "14px",
              color: "#94a3b8",
              margin: "4px 0 0 0",
            }}
          >
            Manage administrators and operating personnel across the organization.
          </p>
        </div>

        <button
          type="button"
          onClick={openCreateModal}
          style={{
            padding: "10px 18px",
            backgroundColor: "#0284c7",
            border: "1px solid rgba(56, 189, 248, 0.3)",
            borderRadius: "8px",
            color: "#ffffff",
            fontSize: "14px",
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            boxShadow: "0 2px 8px rgba(2, 132, 199, 0.25)",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "#0369a1";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "#0284c7";
          }}
        >
          <Plus size={18} />
          <span>Add User</span>
        </button>
      </div>

      {/* ── KPI SUMMARY CARDS ROW (Section 5) ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "14px",
        }}
      >
        <div
          style={{
            padding: "16px 18px",
            backgroundColor: "#161922",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "12px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "6px" }}>
            Total Personnel
          </div>
          <div style={{ fontSize: "22px", fontWeight: 700, color: "#f8fafc", fontFamily: "monospace" }}>
            {kpiMetrics.total}
          </div>
        </div>

        <div
          style={{
            padding: "16px 18px",
            backgroundColor: "#161922",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "12px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "6px" }}>
            Active Personnel
          </div>
          <div style={{ fontSize: "22px", fontWeight: 700, color: "#4ade80", fontFamily: "monospace" }}>
            {kpiMetrics.active}
          </div>
        </div>

        <div
          style={{
            padding: "16px 18px",
            backgroundColor: "#161922",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "12px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "6px" }}>
            Drivers
          </div>
          <div style={{ fontSize: "22px", fontWeight: 700, color: "#34d399", fontFamily: "monospace" }}>
            {kpiMetrics.drivers}
          </div>
        </div>

        <div
          style={{
            padding: "16px 18px",
            backgroundColor: "#161922",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "12px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "6px" }}>
            Conductors
          </div>
          <div style={{ fontSize: "22px", fontWeight: 700, color: "#fbbf24", fontFamily: "monospace" }}>
            {kpiMetrics.conductors}
          </div>
        </div>

        <div
          style={{
            padding: "16px 18px",
            backgroundColor: "#161922",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "12px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "6px" }}>
            Administrators
          </div>
          <div style={{ fontSize: "22px", fontWeight: 700, color: "#c084fc", fontFamily: "monospace" }}>
            {kpiMetrics.admins}
          </div>
        </div>
      </div>

      {/* ── SEARCH & FILTER TOOLBAR (Section 6) ── */}
      <div
        style={{
          backgroundColor: "#161922",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: "12px",
          padding: "14px 18px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "14px",
        }}
      >
        <div
          style={{
            position: "relative",
            flex: "1 1 280px",
            maxWidth: "420px",
          }}
        >
          <Search
            size={16}
            style={{
              position: "absolute",
              left: "12px",
              top: "50%",
              transform: "translateY(-50%)",
              color: "#64748b",
            }}
          />
          <input
            type="text"
            placeholder="Search users by name, email, phone, or ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              padding: "9px 14px 9px 36px",
              backgroundColor: "#0d1017",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "8px",
              color: "#f8fafc",
              fontSize: "14px",
              outline: "none",
            }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          {/* Role Filter */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              backgroundColor: "#0d1017",
              padding: "6px 12px",
              borderRadius: "8px",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <Filter size={14} style={{ color: "#94a3b8" }} />
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              aria-label="Filter by Role"
              style={{
                backgroundColor: "transparent",
                border: "none",
                color: "#f8fafc",
                fontSize: "13px",
                fontWeight: 500,
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="" style={{ backgroundColor: "#161922" }}>All Roles</option>
              <option value="FLEET_ADMIN" style={{ backgroundColor: "#161922" }}>Fleet Admin</option>
              <option value="DEPOT_ADMIN" style={{ backgroundColor: "#161922" }}>Depot Admin</option>
              <option value="DRIVER" style={{ backgroundColor: "#161922" }}>Driver</option>
              <option value="CONDUCTOR" style={{ backgroundColor: "#161922" }}>Conductor</option>
            </select>
          </div>

          {/* Status Filter */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              backgroundColor: "#0d1017",
              padding: "6px 12px",
              borderRadius: "8px",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <Activity size={14} style={{ color: "#94a3b8" }} />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by Status"
              style={{
                backgroundColor: "transparent",
                border: "none",
                color: "#f8fafc",
                fontSize: "13px",
                fontWeight: 500,
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="" style={{ backgroundColor: "#161922" }}>All Statuses</option>
              <option value="ACTIVE" style={{ backgroundColor: "#161922" }}>Active</option>
              <option value="INACTIVE" style={{ backgroundColor: "#161922" }}>Inactive</option>
              <option value="SUSPENDED" style={{ backgroundColor: "#161922" }}>Suspended</option>
            </select>
          </div>

          {/* Reset Filters button */}
          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleResetFilters}
              style={{
                padding: "7px 12px",
                backgroundColor: "rgba(255, 255, 255, 0.04)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "8px",
                color: "#94a3b8",
                fontSize: "13px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = "#f8fafc";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = "#94a3b8";
              }}
            >
              <RotateCcw size={13} />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* ── PERSONNEL TABLE CARD (Section 7, 8, 9, 10, 11, 12) ── */}
      <div
        style={{
          backgroundColor: "#161922",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: "14px",
          overflow: "hidden",
        }}
      >
        {loading ? (
          <div
            style={{
              padding: "60px 20px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: "12px",
              color: "#94a3b8",
            }}
          >
            <Loader2 size={28} className="animate-spin" style={{ color: "#38bdf8" }} />
            <span style={{ fontSize: "14px" }}>Loading team members...</span>
          </div>
        ) : error ? (
          <div
            style={{
              padding: "40px 20px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: "12px",
              color: "#f87171",
            }}
          >
            <AlertTriangle size={28} />
            <span style={{ fontSize: "14px" }}>{error}</span>
            <button
              type="button"
              onClick={fetchUsers}
              style={{
                marginTop: "8px",
                padding: "6px 14px",
                backgroundColor: "rgba(255, 255, 255, 0.06)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                borderRadius: "6px",
                color: "#f8fafc",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Retry
            </button>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div
            style={{
              padding: "60px 20px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: "12px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "50%",
                backgroundColor: "rgba(255, 255, 255, 0.04)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#64748b",
              }}
            >
              <Users size={24} />
            </div>
            <div style={{ fontSize: "15px", fontWeight: 600, color: "#f8fafc" }}>
              {hasActiveFilters
                ? "No team members match your search or filter criteria."
                : "No users found in your organization."}
            </div>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={handleResetFilters}
                style={{
                  padding: "6px 14px",
                  backgroundColor: "rgba(56, 189, 248, 0.12)",
                  border: "1px solid rgba(56, 189, 248, 0.3)",
                  borderRadius: "6px",
                  color: "#38bdf8",
                  fontSize: "13px",
                  cursor: "pointer",
                  marginTop: "4px",
                }}
              >
                Clear Filters
              </button>
            )}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                textAlign: "left",
                fontSize: "14px",
              }}
            >
              <thead>
                <tr
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                    borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
                    color: "#94a3b8",
                    fontSize: "11px",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}
                >
                  <th style={{ padding: "14px 20px" }}>Person</th>
                  <th style={{ padding: "14px 20px" }}>Role</th>
                  <th style={{ padding: "14px 20px" }}>Contact</th>
                  <th style={{ padding: "14px 20px" }}>Status</th>
                  <th style={{ padding: "14px 20px", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((user) => {
                  const roleStyle = getRoleBadgeStyle(user.role);
                  const statusStyle = getStatusBadgeStyle(user.status);
                  const isSelf = user.id === currentUser?.id;
                  const employeeCode = user.operator_profile?.employee_code;

                  return (
                    <tr
                      key={user.id}
                      style={{
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                        transition: "background-color 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.02)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = "transparent";
                      }}
                    >
                      {/* ── PERSON COLUMN (Section 8) ── */}
                      <td style={{ padding: "14px 20px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                          <div
                            style={{
                              width: "38px",
                              height: "38px",
                              borderRadius: "10px",
                              backgroundColor: roleStyle.avatarBg,
                              color: roleStyle.avatarColor,
                              fontWeight: 700,
                              fontSize: "15px",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                              border: `1px solid ${roleStyle.border.split(" ")[2]}`,
                            }}
                          >
                            {user.name.charAt(0).toUpperCase()}
                          </div>

                          <div style={{ minWidth: 0 }}>
                            <div
                              style={{
                                fontWeight: 600,
                                color: "#f8fafc",
                                fontSize: "14px",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {user.name}
                              {isSelf && (
                                <span
                                  style={{
                                    marginLeft: "8px",
                                    fontSize: "10px",
                                    fontWeight: 700,
                                    padding: "1px 6px",
                                    borderRadius: "4px",
                                    backgroundColor: "rgba(56, 189, 248, 0.15)",
                                    color: "#38bdf8",
                                    border: "1px solid rgba(56, 189, 248, 0.3)",
                                  }}
                                >
                                  YOU
                                </span>
                              )}
                            </div>

                            <div style={{ marginTop: "2px" }}>
                              {employeeCode ? (
                                <span
                                  style={{
                                    fontFamily: "monospace",
                                    fontSize: "11px",
                                    fontWeight: 700,
                                    padding: "1px 6px",
                                    borderRadius: "4px",
                                    backgroundColor: "rgba(255, 255, 255, 0.05)",
                                    color: "#94a3b8",
                                    border: "1px solid rgba(255, 255, 255, 0.08)",
                                  }}
                                >
                                  ID: {employeeCode}
                                </span>
                              ) : (
                                <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>
                                  ID: {user.id.slice(0, 8)}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* ── ROLE COLUMN (Section 9) ── */}
                      <td style={{ padding: "14px 20px" }}>
                        <span
                          style={{
                            display: "inline-block",
                            padding: "3px 10px",
                            borderRadius: "6px",
                            fontSize: "11px",
                            fontWeight: 700,
                            letterSpacing: "0.04em",
                            backgroundColor: roleStyle.bg,
                            border: roleStyle.border,
                            color: roleStyle.color,
                          }}
                        >
                          {roleStyle.label}
                        </span>
                      </td>

                      {/* ── CONTACT COLUMN (Section 10) ── */}
                      <td style={{ padding: "14px 20px" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                              fontSize: "13px",
                              color: user.email ? "#cbd5e1" : "#64748b",
                              whiteSpace: "nowrap",
                            }}
                          >
                            <Mail size={12} style={{ color: "#64748b", flexShrink: 0 }} />
                            <span>{user.email || "—"}</span>
                          </div>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                              fontSize: "12px",
                              color: user.phone ? "#94a3b8" : "#64748b",
                              whiteSpace: "nowrap",
                            }}
                          >
                            <Phone size={12} style={{ color: "#64748b", flexShrink: 0 }} />
                            <span>{user.phone || "—"}</span>
                          </div>
                        </div>
                      </td>

                      {/* ── STATUS COLUMN (Section 11) ── */}
                      <td style={{ padding: "14px 20px" }}>
                        <span
                          style={{
                            display: "inline-block",
                            padding: "2px 8px",
                            borderRadius: "4px",
                            fontSize: "11px",
                            fontWeight: 600,
                            backgroundColor: statusStyle.bg,
                            border: statusStyle.border,
                            color: statusStyle.color,
                          }}
                        >
                          {user.status}
                        </span>
                      </td>

                      {/* ── ACTIONS COLUMN (Section 12, 16, 17) ── */}
                      <td style={{ padding: "14px 20px", textAlign: "right" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "8px" }}>
                          {/* Edit Action */}
                          <button
                            type="button"
                            onClick={() => openEditModal(user)}
                            style={{
                              padding: "5px 10px",
                              backgroundColor: "rgba(255, 255, 255, 0.04)",
                              border: "1px solid rgba(255, 255, 255, 0.08)",
                              borderRadius: "6px",
                              color: "#f8fafc",
                              fontSize: "12px",
                              fontWeight: 500,
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              gap: "5px",
                              transition: "all 0.15s ease",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = "rgba(56, 189, 248, 0.12)";
                              e.currentTarget.style.borderColor = "rgba(56, 189, 248, 0.3)";
                              e.currentTarget.style.color = "#38bdf8";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.04)";
                              e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.08)";
                              e.currentTarget.style.color = "#f8fafc";
                            }}
                          >
                            <Edit2 size={13} />
                            <span>Edit</span>
                          </button>

                          {/* Reset Password Action */}
                          <button
                            type="button"
                            onClick={() => openPasswordModal(user)}
                            title="Reset Password"
                            aria-label={`Reset password for ${user.name}`}
                            style={{
                              padding: "5px 8px",
                              backgroundColor: "rgba(255, 255, 255, 0.04)",
                              border: "1px solid rgba(255, 255, 255, 0.08)",
                              borderRadius: "6px",
                              color: "#94a3b8",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              transition: "all 0.15s ease",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = "rgba(251, 191, 36, 0.12)";
                              e.currentTarget.style.borderColor = "rgba(251, 191, 36, 0.3)";
                              e.currentTarget.style.color = "#fbbf24";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.04)";
                              e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.08)";
                              e.currentTarget.style.color = "#94a3b8";
                            }}
                          >
                            <Key size={14} />
                          </button>

                          {/* Deactivate / Activate Toggle */}
                          {user.status === "ACTIVE" ? (
                            <button
                              type="button"
                              onClick={() => setStatusConfirmUser({ user, targetStatus: "INACTIVE" })}
                              disabled={isSelf}
                              title={isSelf ? "Cannot deactivate your own account" : "Deactivate user"}
                              aria-label={`Deactivate ${user.name}`}
                              style={{
                                padding: "5px 8px",
                                backgroundColor: isSelf ? "rgba(255, 255, 255, 0.02)" : "rgba(255, 255, 255, 0.04)",
                                border: "1px solid rgba(255, 255, 255, 0.08)",
                                borderRadius: "6px",
                                color: isSelf ? "#475569" : "#94a3b8",
                                cursor: isSelf ? "not-allowed" : "pointer",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                transition: "all 0.15s ease",
                              }}
                              onMouseEnter={(e) => {
                                if (!isSelf) {
                                  e.currentTarget.style.backgroundColor = "rgba(239, 68, 68, 0.12)";
                                  e.currentTarget.style.borderColor = "rgba(239, 68, 68, 0.3)";
                                  e.currentTarget.style.color = "#f87171";
                                }
                              }}
                              onMouseLeave={(e) => {
                                if (!isSelf) {
                                  e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.04)";
                                  e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.08)";
                                  e.currentTarget.style.color = "#94a3b8";
                                }
                              }}
                            >
                              <Ban size={14} />
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setStatusConfirmUser({ user, targetStatus: "ACTIVE" })}
                              title="Activate user"
                              aria-label={`Activate ${user.name}`}
                              style={{
                                padding: "5px 8px",
                                backgroundColor: "rgba(255, 255, 255, 0.04)",
                                border: "1px solid rgba(255, 255, 255, 0.08)",
                                borderRadius: "6px",
                                color: "#94a3b8",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                transition: "all 0.15s ease",
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = "rgba(34, 197, 94, 0.12)";
                                e.currentTarget.style.borderColor = "rgba(34, 197, 94, 0.3)";
                                e.currentTarget.style.color = "#4ade80";
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.04)";
                                e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.08)";
                                e.currentTarget.style.color = "#94a3b8";
                              }}
                            >
                              <CheckCircle size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── CREATE USER MODAL (Section 15, 22) ── */}
      {isCreateModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-user-title"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "16px",
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !formSubmitting) setIsCreateModalOpen(false);
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "540px",
              maxHeight: "90vh",
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
            }}
          >
            <div
              style={{
                flexShrink: 0,
                padding: "18px 24px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <h2
                id="create-user-title"
                style={{
                  fontSize: "18px",
                  fontWeight: 700,
                  margin: 0,
                  color: "#f8fafc",
                }}
              >
                Add Team Member
              </h2>
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(false)}
                disabled={formSubmitting}
                style={{
                  background: "none",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  padding: "4px",
                }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} style={{ flex: 1, overflowY: "auto", padding: "24px" }}>
              {formError && (
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(239, 68, 68, 0.12)",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    color: "#f87171",
                    fontSize: "13px",
                    marginBottom: "18px",
                  }}
                >
                  {formError}
                </div>
              )}

              {/* Personnel Details */}
              <div style={{ marginBottom: "18px" }}>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "#38bdf8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "12px" }}>
                  Personnel Details
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                      Full Name *
                    </label>
                    <input
                      required
                      type="text"
                      placeholder="e.g. Akash Mondal"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      style={{
                        width: "100%",
                        padding: "9px 12px",
                        backgroundColor: "#0d1017",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        borderRadius: "8px",
                        color: "#f8fafc",
                        fontSize: "14px",
                        outline: "none",
                      }}
                    />
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                        Email (Optional)
                      </label>
                      <input
                        type="email"
                        placeholder="akash@example.com"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        style={{
                          width: "100%",
                          padding: "9px 12px",
                          backgroundColor: "#0d1017",
                          border: "1px solid rgba(255, 255, 255, 0.1)",
                          borderRadius: "8px",
                          color: "#f8fafc",
                          fontSize: "14px",
                          outline: "none",
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                        Phone (Optional)
                      </label>
                      <input
                        type="text"
                        placeholder="+91..."
                        value={formData.phone}
                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                        style={{
                          width: "100%",
                          padding: "9px 12px",
                          backgroundColor: "#0d1017",
                          border: "1px solid rgba(255, 255, 255, 0.1)",
                          borderRadius: "8px",
                          color: "#f8fafc",
                          fontSize: "14px",
                          outline: "none",
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Role & Operator Profile */}
              <div style={{ marginBottom: "18px", borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: "16px" }}>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "#38bdf8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "12px" }}>
                  Role & Operator Profile
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                    Role *
                  </label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      backgroundColor: "#0d1017",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                      borderRadius: "8px",
                      color: "#f8fafc",
                      fontSize: "14px",
                      outline: "none",
                    }}
                  >
                    <option value="DRIVER">Driver</option>
                    <option value="CONDUCTOR">Conductor</option>
                    <option value="DEPOT_ADMIN">Depot Admin</option>
                    {isFleetAdmin && <option value="FLEET_ADMIN">Fleet Admin</option>}
                  </select>
                </div>

                {(formData.role === "DRIVER" || formData.role === "CONDUCTOR") && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "12px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                        Employee Code *
                      </label>
                      <input
                        required
                        type="text"
                        placeholder="e.g. DR01, CD01"
                        value={formData.employee_code}
                        onChange={(e) => setFormData({ ...formData, employee_code: e.target.value })}
                        style={{
                          width: "100%",
                          padding: "9px 12px",
                          backgroundColor: "#0d1017",
                          border: "1px solid rgba(255, 255, 255, 0.1)",
                          borderRadius: "8px",
                          color: "#f8fafc",
                          fontSize: "14px",
                          fontFamily: "monospace",
                          outline: "none",
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                        Operator Type *
                      </label>
                      <select
                        value={formData.operator_type}
                        onChange={(e) => setFormData({ ...formData, operator_type: e.target.value })}
                        style={{
                          width: "100%",
                          padding: "9px 12px",
                          backgroundColor: "#0d1017",
                          border: "1px solid rgba(255, 255, 255, 0.1)",
                          borderRadius: "8px",
                          color: "#f8fafc",
                          fontSize: "14px",
                          outline: "none",
                        }}
                      >
                        <option value="CITY_BUS">City Bus</option>
                        <option value="EXPRESS">Express</option>
                      </select>
                    </div>
                  </div>
                )}
              </div>

              {/* Security Credentials */}
              <div style={{ marginBottom: "18px", borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: "16px" }}>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "#38bdf8", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "12px" }}>
                  Security Credentials
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                    Initial Password *
                  </label>
                  <input
                    required
                    minLength={4}
                    type="password"
                    placeholder="At least 4 characters"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      backgroundColor: "#0d1017",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                      borderRadius: "8px",
                      color: "#f8fafc",
                      fontSize: "14px",
                      outline: "none",
                    }}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "24px" }}>
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  disabled={formSubmitting}
                  style={{
                    padding: "9px 16px",
                    backgroundColor: "rgba(255, 255, 255, 0.06)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    color: "#cbd5e1",
                    fontSize: "14px",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  style={{
                    padding: "9px 18px",
                    backgroundColor: "#0284c7",
                    border: "1px solid rgba(56, 189, 248, 0.3)",
                    borderRadius: "8px",
                    color: "#ffffff",
                    fontSize: "14px",
                    fontWeight: 600,
                    cursor: formSubmitting ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  {formSubmitting && <Loader2 size={16} className="animate-spin" />}
                  <span>{formSubmitting ? "Creating..." : "Create User"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── EDIT USER MODAL (Section 13, 22) ── */}
      {isEditModalOpen && selectedUser && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-user-title"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "16px",
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !formSubmitting) setIsEditModalOpen(false);
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "540px",
              maxHeight: "90vh",
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
            }}
          >
            <div
              style={{
                flexShrink: 0,
                padding: "18px 24px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <h2
                id="edit-user-title"
                style={{
                  fontSize: "18px",
                  fontWeight: 700,
                  margin: 0,
                  color: "#f8fafc",
                }}
              >
                Edit Personnel
              </h2>
              <button
                type="button"
                onClick={() => setIsEditModalOpen(false)}
                disabled={formSubmitting}
                style={{
                  background: "none",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  padding: "4px",
                }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} style={{ flex: 1, overflowY: "auto", padding: "24px" }}>
              {formError && (
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(239, 68, 68, 0.12)",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    color: "#f87171",
                    fontSize: "13px",
                    marginBottom: "18px",
                  }}
                >
                  {formError}
                </div>
              )}

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                  Full Name *
                </label>
                <input
                  required
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    backgroundColor: "#0d1017",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    fontSize: "14px",
                    outline: "none",
                  }}
                />
              </div>

              <div style={{ marginTop: "14px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                  Role *
                </label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  disabled={selectedUser.id === currentUser?.id}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    backgroundColor: selectedUser.id === currentUser?.id ? "#090b10" : "#0d1017",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    color: selectedUser.id === currentUser?.id ? "#64748b" : "#f8fafc",
                    fontSize: "14px",
                    outline: "none",
                    cursor: selectedUser.id === currentUser?.id ? "not-allowed" : "pointer",
                  }}
                >
                  <option value="DRIVER">Driver</option>
                  <option value="CONDUCTOR">Conductor</option>
                  <option value="DEPOT_ADMIN">Depot Admin</option>
                  {(isFleetAdmin || selectedUser.role === "FLEET_ADMIN") && (
                    <option value="FLEET_ADMIN">Fleet Admin</option>
                  )}
                </select>
                {selectedUser.id === currentUser?.id && (
                  <span style={{ fontSize: "11px", color: "#64748b", marginTop: "4px", display: "block" }}>
                    You cannot change your own role.
                  </span>
                )}
              </div>

              {(formData.role === "DRIVER" || formData.role === "CONDUCTOR") && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "14px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                      Employee Code *
                    </label>
                    <input
                      required
                      type="text"
                      value={formData.employee_code}
                      onChange={(e) => setFormData({ ...formData, employee_code: e.target.value })}
                      style={{
                        width: "100%",
                        padding: "9px 12px",
                        backgroundColor: "#0d1017",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        borderRadius: "8px",
                        color: "#f8fafc",
                        fontSize: "14px",
                        fontFamily: "monospace",
                        outline: "none",
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                      Operator Type *
                    </label>
                    <select
                      value={formData.operator_type}
                      onChange={(e) => setFormData({ ...formData, operator_type: e.target.value })}
                      style={{
                        width: "100%",
                        padding: "9px 12px",
                        backgroundColor: "#0d1017",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        borderRadius: "8px",
                        color: "#f8fafc",
                        fontSize: "14px",
                        outline: "none",
                      }}
                    >
                      <option value="CITY_BUS">City Bus</option>
                      <option value="EXPRESS">Express</option>
                    </select>
                  </div>
                </div>
              )}

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "14px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                    Email
                  </label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      backgroundColor: "#0d1017",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                      borderRadius: "8px",
                      color: "#f8fafc",
                      fontSize: "14px",
                      outline: "none",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                    Phone
                  </label>
                  <input
                    type="text"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    style={{
                      width: "100%",
                      padding: "9px 12px",
                      backgroundColor: "#0d1017",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                      borderRadius: "8px",
                      color: "#f8fafc",
                      fontSize: "14px",
                      outline: "none",
                    }}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "24px" }}>
                <button
                  type="button"
                  onClick={() => setIsEditModalOpen(false)}
                  disabled={formSubmitting}
                  style={{
                    padding: "9px 16px",
                    backgroundColor: "rgba(255, 255, 255, 0.06)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    color: "#cbd5e1",
                    fontSize: "14px",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  style={{
                    padding: "9px 18px",
                    backgroundColor: "#0284c7",
                    border: "1px solid rgba(56, 189, 248, 0.3)",
                    borderRadius: "8px",
                    color: "#ffffff",
                    fontSize: "14px",
                    fontWeight: 600,
                    cursor: formSubmitting ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  {formSubmitting && <Loader2 size={16} className="animate-spin" />}
                  <span>{formSubmitting ? "Saving..." : "Save Changes"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── RESET PASSWORD MODAL (Section 16, 22) ── */}
      {isPasswordModalOpen && selectedUser && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="password-user-title"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "16px",
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !formSubmitting) setIsPasswordModalOpen(false);
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "460px",
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
            }}
          >
            <div
              style={{
                flexShrink: 0,
                padding: "18px 24px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Key size={18} style={{ color: "#fbbf24" }} />
                <h2
                  id="password-user-title"
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    margin: 0,
                    color: "#f8fafc",
                  }}
                >
                  Reset Password
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setIsPasswordModalOpen(false)}
                disabled={formSubmitting}
                style={{
                  background: "none",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  padding: "4px",
                }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handlePasswordSubmit} style={{ padding: "24px" }}>
              {formError && (
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(239, 68, 68, 0.12)",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    color: "#f87171",
                    fontSize: "13px",
                    marginBottom: "18px",
                  }}
                >
                  {formError}
                </div>
              )}

              <p style={{ fontSize: "14px", color: "#94a3b8", margin: "0 0 16px 0" }}>
                Set a new password for <strong style={{ color: "#f8fafc" }}>{selectedUser.name}</strong>.
              </p>

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                  New Password *
                </label>
                <input
                  required
                  minLength={4}
                  type="password"
                  placeholder="At least 4 characters"
                  value={passwordData.password}
                  onChange={(e) => setPasswordData({ ...passwordData, password: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    backgroundColor: "#0d1017",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    fontSize: "14px",
                    outline: "none",
                  }}
                />
              </div>

              <div style={{ marginTop: "14px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                  Confirm Password *
                </label>
                <input
                  required
                  minLength={4}
                  type="password"
                  placeholder="Re-enter new password"
                  value={passwordData.confirmPassword}
                  onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    backgroundColor: "#0d1017",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    fontSize: "14px",
                    outline: "none",
                  }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "24px" }}>
                <button
                  type="button"
                  onClick={() => setIsPasswordModalOpen(false)}
                  disabled={formSubmitting}
                  style={{
                    padding: "9px 16px",
                    backgroundColor: "rgba(255, 255, 255, 0.06)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    color: "#cbd5e1",
                    fontSize: "14px",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  style={{
                    padding: "9px 18px",
                    backgroundColor: "#d97706",
                    border: "1px solid rgba(245, 158, 11, 0.3)",
                    borderRadius: "8px",
                    color: "#ffffff",
                    fontSize: "14px",
                    fontWeight: 600,
                    cursor: formSubmitting ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  {formSubmitting && <Loader2 size={16} className="animate-spin" />}
                  <span>{formSubmitting ? "Updating..." : "Update Password"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── STATUS CONFIRMATION MODAL (Section 17, 22) ── */}
      {statusConfirmUser && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="status-confirm-title"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "16px",
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !formSubmitting) setStatusConfirmUser(null);
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "460px",
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
            }}
          >
            <div style={{ padding: "24px" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: "14px" }}>
                <div
                  style={{
                    width: "44px",
                    height: "44px",
                    borderRadius: "10px",
                    backgroundColor:
                      statusConfirmUser.targetStatus === "INACTIVE"
                        ? "rgba(239, 68, 68, 0.15)"
                        : "rgba(34, 197, 94, 0.15)",
                    border:
                      statusConfirmUser.targetStatus === "INACTIVE"
                        ? "1px solid rgba(239, 68, 68, 0.3)"
                        : "1px solid rgba(34, 197, 94, 0.3)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {statusConfirmUser.targetStatus === "INACTIVE" ? (
                    <Ban size={22} style={{ color: "#f87171" }} />
                  ) : (
                    <CheckCircle size={22} style={{ color: "#4ade80" }} />
                  )}
                </div>

                <div>
                  <h3
                    id="status-confirm-title"
                    style={{
                      margin: "0 0 6px 0",
                      fontSize: "18px",
                      fontWeight: 700,
                      color: "#f8fafc",
                    }}
                  >
                    {statusConfirmUser.targetStatus === "INACTIVE"
                      ? "Deactivate Personnel?"
                      : "Activate Personnel?"}
                  </h3>
                  <p style={{ margin: "0 0 10px 0", fontSize: "14px", color: "#cbd5e1" }}>
                    Are you sure you want to change status for{" "}
                    <strong style={{ color: "#f8fafc" }}>
                      {statusConfirmUser.user.name}
                    </strong>{" "}
                    ({statusConfirmUser.user.operator_profile?.employee_code || statusConfirmUser.user.role})?
                  </p>
                  <p style={{ margin: 0, fontSize: "13px", color: "#94a3b8" }}>
                    {statusConfirmUser.targetStatus === "INACTIVE"
                      ? "This user will no longer be active for operational duty assignments."
                      : "This user will be restored to active operational status."}
                  </p>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "24px" }}>
                <button
                  type="button"
                  onClick={() => setStatusConfirmUser(null)}
                  disabled={formSubmitting}
                  style={{
                    padding: "9px 16px",
                    backgroundColor: "rgba(255, 255, 255, 0.06)",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    borderRadius: "8px",
                    color: "#cbd5e1",
                    fontSize: "14px",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmStatusChange}
                  disabled={formSubmitting}
                  style={{
                    padding: "9px 18px",
                    backgroundColor:
                      statusConfirmUser.targetStatus === "INACTIVE" ? "#dc2626" : "#16a34a",
                    border: "none",
                    borderRadius: "8px",
                    color: "#ffffff",
                    fontSize: "14px",
                    fontWeight: 600,
                    cursor: formSubmitting ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  {formSubmitting && <Loader2 size={16} className="animate-spin" />}
                  <span>
                    {statusConfirmUser.targetStatus === "INACTIVE"
                      ? "Deactivate User"
                      : "Activate User"}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
