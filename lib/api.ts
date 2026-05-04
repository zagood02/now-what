import axios, { type AxiosInstance } from "axios";

const normalizeUrl = (url: string) => url.replace(/\/+$/, "");

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim() || "";
const defaultApiUrl = typeof window !== "undefined"
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : "http://localhost:8000";
const API_BASE_URL = normalizeUrl(rawApiUrl || defaultApiUrl);
const API_V1_PREFIX = "/api/v1";

// Axios 인스턴스 생성
export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}${API_V1_PREFIX}`,
  headers: {
    "Content-Type": "application/json",
  },
});

// Types
export interface User {
  id: number;
  email: string;
  name: string;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface CreateUserRequest {
  email: string;
  name: string;
  timezone: string;
}

export interface FixedSchedule {
  id: number;
  user_id: number;
  title: string;
  description: string | null;
  location: string | null;
  start_at: string;
  end_at: string;
  is_all_day: boolean;
  recurrence_rule: string | null;
  day_of_week: number | null;
  created_at: string;
  updated_at: string;
}

export interface CreateFixedScheduleRequest {
  user_id: number;
  title: string;
  description?: string;
  location?: string;
  start_at: string;
  end_at: string;
  is_all_day?: boolean;
  recurrence_rule?: string;
  day_of_week?: number;
}

export interface UpdateFixedScheduleRequest {
  title?: string;
  description?: string;
  location?: string;
  start_at?: string;
  end_at?: string;
  is_all_day?: boolean;
  recurrence_rule?: string;
  day_of_week?: number;
}

export interface FlexibleTask {
  id: number;
  user_id: number;
  title: string;
  description: string | null;
  estimated_minutes: number;
  min_session_minutes: number;
  preferred_session_minutes: number;
  max_minutes_per_day: number;
  priority: number;
  due_at: string | null;
  status: "pending" | "scheduled" | "in_progress" | "completed" | "cancelled";
  details_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateFlexibleTaskRequest {
  user_id: number;
  title: string;
  description?: string;
  estimated_minutes: number;
  min_session_minutes: number;
  preferred_session_minutes: number;
  max_minutes_per_day: number;
  priority: number;
  due_at?: string;
  details_json?: Record<string, unknown>;
}

export interface Goal {
  id: number;
  user_id: number;
  title: string;
  description: string | null;
  category: "study" | "health" | "work" | "habit" | "general";
  status: "draft" | "active" | "paused" | "completed" | "archived";
  target_date: string | null;
  details_json: Record<string, unknown>;
  answers_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateGoalRequest {
  user_id: number;
  title: string;
  description?: string;
  category: "study" | "health" | "work" | "habit" | "general";
  target_date?: string;
  details_json?: Record<string, unknown>;
}

export interface AllocatedTask {
  id: number;
  user_id: number;
  flexible_task_id: number;
  title_snapshot: string;
  scheduled_start: string;
  scheduled_end: string;
  duration_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface CalendarEvent {
  id: string;
  source_type: string;
  source_id: number;
  title: string;
  description: string | null;
  start_at: string;
  end_at: string;
  status: string;
  metadata_json: Record<string, unknown>;
}

export interface CalendarResponse {
  user_id: number;
  start: string;
  end: string;
  events: CalendarEvent[];
  totals: Record<string, number>;
}

// User APIs
export const userAPI = {
  create: (data: CreateUserRequest) => apiClient.post<User>("/users", data),
  list: () => apiClient.get<User[]>("/users"),
  get: (userId: number) => apiClient.get<User>(`/users/${userId}`),
};

// Fixed Schedule APIs
export const fixedScheduleAPI = {
  create: (data: CreateFixedScheduleRequest) =>
    apiClient.post<FixedSchedule>("/schedules/fixed", data),
  list: (params?: { user_id?: number }) =>
    apiClient.get<FixedSchedule[]>("/schedules/fixed", { params }),
  get: (scheduleId: number, userId: number) =>
    apiClient.get<FixedSchedule>(
      `/schedules/fixed/${scheduleId}?user_id=${userId}`
    ),
  update: (scheduleId: number, userId: number, data: UpdateFixedScheduleRequest) =>
    apiClient.patch<FixedSchedule>(
      `/schedules/fixed/${scheduleId}?user_id=${userId}`,
      data
    ),
  delete: (scheduleId: number, userId: number) =>
    apiClient.delete(`/schedules/fixed/${scheduleId}?user_id=${userId}`),
};

// Flexible Task APIs
export const flexibleTaskAPI = {
  create: (data: CreateFlexibleTaskRequest) =>
    apiClient.post<FlexibleTask>("/tasks/flexible", data),
  list: (params?: { user_id?: number }) =>
    apiClient.get<FlexibleTask[]>("/tasks/flexible", { params }),
  get: (taskId: number, userId: number) =>
    apiClient.get<FlexibleTask>(`/tasks/flexible/${taskId}?user_id=${userId}`),
  update: (taskId: number, userId: number, data: Partial<CreateFlexibleTaskRequest>) =>
    apiClient.patch<FlexibleTask>(
      `/tasks/flexible/${taskId}?user_id=${userId}`,
      data
    ),
  delete: (taskId: number, userId: number) =>
    apiClient.delete(`/tasks/flexible/${taskId}?user_id=${userId}`),
};

// Goal APIs
export const goalAPI = {
  create: (data: CreateGoalRequest) =>
    apiClient.post<Goal>("/goals", data),
  list: (params?: { user_id?: number }) =>
    apiClient.get<Goal[]>("/goals", { params }),
  get: (goalId: number, userId: number) =>
    apiClient.get<Goal>(`/goals/${goalId}?user_id=${userId}`),
  update: (goalId: number, userId: number, data: Partial<CreateGoalRequest>) =>
    apiClient.patch<Goal>(`/goals/${goalId}?user_id=${userId}`, data),
  intake: (data: { user_id: number; goal_title: string }) =>
    apiClient.post("/goals/intake", data),
};

// Calendar APIs
export const calendarAPI = {
  get: (params: { user_id: number; start: string; end: string }) =>
    apiClient.get<CalendarResponse>("/calendar", { params }),
};

// Planner APIs
export const plannerAPI = {
  allocate: (data: { user_id: number }) =>
    apiClient.post("/planner/allocate", data),
};

// Health check
export const healthAPI = {
  check: () => apiClient.get("/health"),
  checkDB: () => apiClient.get("/health/db"),
};

// Error handling utility
export const handleApiError = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    if (error.response) {
      return error.response.data?.detail || "서버 오류가 발생했습니다.";
    } else if (error.request) {
      return "서버에 연결할 수 없습니다.";
    }
  }
  return "알 수 없는 오류가 발생했습니다.";
};
