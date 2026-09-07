import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { CalendarClock, Plus, ArrowLeft, Edit2, Trash2, AlertCircle, Save, X } from "lucide-react";
import {
  getServiceSchedules,
  createServiceSchedule,
  updateServiceSchedule,
  deleteServiceSchedule
} from "../api/api";

type ServiceSchedule = {
  id: string;
  service_id: string;
  direction: "A_TO_B" | "B_TO_A";
  start_time: string;
  end_time: string;
  typical_interval_minutes: number;
  days_of_week: number[];
  effective_from: string;
  effective_until?: string | null;
  status: string;
};

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatDays(days: number[]) {
  if (!days || days.length === 0) return "No days selected";
  if (days.length === 7) return "Every day";
  if (days.length === 5 && [1,2,3,4,5].every(d => days.includes(d))) return "Monday–Friday";
  if (days.length === 2 && [6,7].every(d => days.includes(d))) return "Weekends";
  
  return days
    .sort()
    .map(d => DAY_NAMES[d - 1])
    .join(", ");
}

export default function ServiceSchedulesPage() {
  const { id } = useParams<{ id: string }>();
  const [schedules, setSchedules] = useState<ServiceSchedule[]>([]);
  const [serviceInfo, setServiceInfo] = useState<{ service_code: string; service_name: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  
  const [showModal, setShowModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<ServiceSchedule | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    direction: "A_TO_B",
    start_time: "08:00:00",
    end_time: "10:00:00",
    typical_interval_minutes: 15,
    days_of_week: [1, 2, 3, 4, 5],
    effective_from: new Date().toISOString().split('T')[0],
  });

  const fetchSchedules = async () => {
    if (!id) return;
    try {
      setLoading(true);
      const [res, svcRes] = await Promise.all([
        getServiceSchedules(id),
        import("../api/api").then(api => api.apiFetch(`/admin/services/${id}`))
      ]);
      setSchedules(res);
      setServiceInfo(svcRes);
    } catch (err: any) {
      setError(err.message || "Failed to load schedules.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchedules();
  }, [id]);

  const openCreateModal = () => {
    setEditingSchedule(null);
    setFormData({
      direction: "A_TO_B",
      start_time: "08:00:00",
      end_time: "10:00:00",
      typical_interval_minutes: 15,
      days_of_week: [1, 2, 3, 4, 5],
      effective_from: new Date().toISOString().split('T')[0],
    });
    setShowModal(true);
  };

  const openEditModal = (schedule: ServiceSchedule) => {
    setEditingSchedule(schedule);
    setFormData({
      direction: schedule.direction,
      start_time: schedule.start_time,
      end_time: schedule.end_time,
      typical_interval_minutes: schedule.typical_interval_minutes,
      days_of_week: [...schedule.days_of_week],
      effective_from: schedule.effective_from.split('T')[0],
    });
    setShowModal(true);
  };

  const handleDelete = async (scheduleId: string) => {
    if (!id) return;
    if (!window.confirm("Are you sure you want to delete this schedule?")) return;
    try {
      await deleteServiceSchedule(id, scheduleId);
      await fetchSchedules();
    } catch (err: any) {
      alert(err.message || "Failed to delete schedule.");
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;

    if (formData.days_of_week.length === 0) {
      alert("Please select at least one day of the week.");
      return;
    }
    
    // Convert effective_from back to ISO format (start of day UTC or just ISO string)
    // FastAPI datetime expects a proper timestamp, we'll send a midnight UTC timestamp for the selected date
    const formattedData = {
      ...formData,
      effective_from: new Date(formData.effective_from).toISOString(),
    };

    try {
      if (editingSchedule) {
        await updateServiceSchedule(id, editingSchedule.id, formattedData);
      } else {
        await createServiceSchedule(id, formattedData);
      }
      setShowModal(false);
      await fetchSchedules();
    } catch (err: any) {
      alert(err.message || "Failed to save schedule.");
    }
  };

  const toggleDay = (dayIndex: number) => {
    setFormData(prev => {
      const days = [...prev.days_of_week];
      if (days.includes(dayIndex)) {
        return { ...prev, days_of_week: days.filter(d => d !== dayIndex) };
      } else {
        return { ...prev, days_of_week: [...days, dayIndex] };
      }
    });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6 animate-fade-in">
      <Link to="/services" className="inline-flex items-center gap-2 text-[var(--text-muted)] hover:text-white mb-4">
        <ArrowLeft size={16} />
        Back to Services
      </Link>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <CalendarClock size={28} className="text-[var(--primary)]" />
            Service Schedules {serviceInfo && <span className="text-gray-400 text-xl font-normal ml-2">/ {serviceInfo.service_code} - {serviceInfo.service_name}</span>}
          </h1>
          <p className="text-[var(--text-muted)] mt-2">
            Manage frequency and availability for passenger-facing schedules.
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white font-medium rounded-lg transition-colors"
        >
          <Plus size={18} />
          New Schedule
        </button>
      </div>

      {loading ? (
        <div className="animate-pulse bg-[var(--surface)] h-48 rounded-xl border border-gray-800"></div>
      ) : error ? (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl flex items-center gap-3">
          <AlertCircle size={20} />
          <p>{error}</p>
        </div>
      ) : schedules.length === 0 ? (
        <div className="bg-[var(--surface)] border border-gray-800 text-center p-16 rounded-xl text-gray-400">
          <CalendarClock size={48} className="mx-auto opacity-20 mb-4" />
          <p className="text-xl font-medium text-white mb-2">No schedules configured</p>
          <p className="text-sm">Create a schedule to define when this service operates.</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {schedules.map(schedule => (
            <div key={schedule.id} className="bg-[var(--surface)] border border-gray-800 rounded-xl p-6 hover:border-gray-700 transition-colors">
              <div className="flex justify-between items-start mb-4">
                <span className={`px-2.5 py-1 text-xs font-semibold rounded-md ${
                  schedule.direction === "A_TO_B" ? "bg-blue-500/20 text-blue-400" : "bg-purple-500/20 text-purple-400"
                }`}>
                  {schedule.direction === "A_TO_B" ? "Outbound (A → B)" : "Inbound (B → A)"}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => openEditModal(schedule)}
                    className="p-1.5 text-gray-400 hover:text-white rounded-md hover:bg-gray-800 transition-colors"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    onClick={() => handleDelete(schedule.id)}
                    className="p-1.5 text-gray-400 hover:text-red-400 rounded-md hover:bg-gray-800 transition-colors"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Operating Days</p>
                  <p className="text-white font-medium">{formatDays(schedule.days_of_week)}</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Time Window</p>
                    <p className="text-white font-medium">{schedule.start_time.slice(0, 5)} – {schedule.end_time.slice(0, 5)}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Interval</p>
                    <p className="text-white font-medium">Every {schedule.typical_interval_minutes} mins</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Reusable Form Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-[var(--surface)] w-full max-w-lg rounded-2xl border border-gray-800 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex justify-between items-center p-6 border-b border-gray-800">
              <h2 className="text-xl font-bold text-white">
                {editingSchedule ? "Edit Schedule" : "Create Schedule"}
              </h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-white">
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleSave} className="p-6 overflow-y-auto flex-1 space-y-6">
              
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">Direction</label>
                <select
                  value={formData.direction}
                  onChange={e => setFormData({ ...formData, direction: e.target.value })}
                  className="w-full bg-[#0f1115] border border-gray-700 text-white rounded-lg p-2.5 focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] outline-none"
                  required
                >
                  <option value="A_TO_B">Outbound (A → B)</option>
                  <option value="B_TO_A">Inbound (B → A)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-300">Start Time</label>
                  <input
                    type="time"
                    step="1"
                    value={formData.start_time}
                    onChange={e => setFormData({ ...formData, start_time: e.target.value })}
                    className="w-full bg-[#0f1115] border border-gray-700 text-white rounded-lg p-2.5 focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] outline-none"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-300">End Time</label>
                  <input
                    type="time"
                    step="1"
                    value={formData.end_time}
                    onChange={e => setFormData({ ...formData, end_time: e.target.value })}
                    className="w-full bg-[#0f1115] border border-gray-700 text-white rounded-lg p-2.5 focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] outline-none"
                    required
                  />
                  <p className="text-xs text-gray-500">End time can be earlier than start for overnight routes.</p>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">Typical Interval (minutes)</label>
                <input
                  type="number"
                  min="1"
                  value={formData.typical_interval_minutes}
                  onChange={e => setFormData({ ...formData, typical_interval_minutes: parseInt(e.target.value) || 1 })}
                  className="w-full bg-[#0f1115] border border-gray-700 text-white rounded-lg p-2.5 focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] outline-none"
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">Days of Week</label>
                <div className="flex flex-wrap gap-2">
                  {DAY_NAMES.map((day, i) => {
                    const dayIndex = i + 1;
                    const isSelected = formData.days_of_week.includes(dayIndex);
                    return (
                      <button
                        key={day}
                        type="button"
                        onClick={() => toggleDay(dayIndex)}
                        className={`w-12 h-10 rounded-lg text-sm font-medium transition-colors ${
                          isSelected ? "bg-[var(--primary)] text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                        }`}
                      >
                        {day}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-300">Effective From Date</label>
                <input
                  type="date"
                  value={formData.effective_from}
                  onChange={e => setFormData({ ...formData, effective_from: e.target.value })}
                  className="w-full bg-[#0f1115] border border-gray-700 text-white rounded-lg p-2.5 focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] outline-none"
                  required
                />
              </div>
              
              <div className="pt-4 border-t border-gray-800 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 bg-transparent text-gray-300 hover:text-white font-medium rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-6 py-2 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white font-medium rounded-lg flex items-center gap-2"
                >
                  <Save size={18} />
                  {editingSchedule ? "Update" : "Save"} Schedule
                </button>
              </div>

            </form>
          </div>
        </div>
      )}
    </div>
  );
}
