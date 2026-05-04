import axios, { type AxiosInstance } from "axios";

const normalizeUrl = (url: string) => url.replace(/\/+$/, "");

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim() || "";
const defaultApiUrl =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000";
const API_BASE_URL = normalizeUrl(rawApiUrl || defaultApiUrl);
const API_V1_PREFIX = "/api/v1";
const ACCESS_TOKEN_STORAGE_KEY = "now_what_access_token";

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}${API_V1_PREFIX}`,
  headers: {
    "Content-Type": "application/json",
  },
});

export const getStoredAccessToken = () => {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
};

export const setApiAccessToken = (token: string | null) => {
  if (token) {
    apiClient.defaults.headers.common.Authorization = `Bearer ${token}`;
    if (typeof window !== "undefined") {
      window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
    }
    return;
  }

  delete apiClient.defaults.headers.common.Authorization;
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  }
};

apiClient.interceptors.request.use((config) => {
  const token = getStoredAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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
  password: string;
  timezone: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
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

export const authAPI = {
  me: () => apiClient.get<User>("/auth/me"),
  loginWithGoogle: (credential: string) =>
    apiClient.post<LoginResponse>("/auth/google", { credential }),
  loginWithKakao: (accessToken: string) =>
    apiClient.post<LoginResponse>("/auth/kakao", { access_token: accessToken }),
};

export const userAPI = {
  create: (data: CreateUserRequest) => apiClient.post<User>("/users", data),
  list: () => apiClient.get<User[]>("/users"),
  get: (userId: number) => apiClient.get<User>(`/users/${userId}`),
};

export const fixedScheduleAPI = {
  create: (data: CreateFixedScheduleRequest) =>
    apiClient.post<FixedSchedule>("/schedules/fixed", data),
  list: (params?: { start?: string; end?: string }) =>
    apiClient.get<FixedSchedule[]>("/schedules/fixed", { params }),
  get: (scheduleId: number) => apiClient.get<FixedSchedule>(`/schedules/fixed/${scheduleId}`),
  update: (scheduleId: number, data: UpdateFixedScheduleRequest) =>
    apiClient.patch<FixedSchedule>(`/schedules/fixed/${scheduleId}`, data),
  delete: (scheduleId: number) => apiClient.delete(`/schedules/fixed/${scheduleId}`),
};

export const flexibleTaskAPI = {
  create: (data: CreateFlexibleTaskRequest) =>
    apiClient.post<FlexibleTask>("/tasks/flexible", data),
  list: () => apiClient.get<FlexibleTask[]>("/tasks/flexible"),
  get: (taskId: number) => apiClient.get<FlexibleTask>(`/tasks/flexible/${taskId}`),
  update: (taskId: number, data: Partial<CreateFlexibleTaskRequest>) =>
    apiClient.patch<FlexibleTask>(`/tasks/flexible/${taskId}`, data),
  delete: (taskId: number) => apiClient.delete(`/tasks/flexible/${taskId}`),
};

export const goalAPI = {
  create: (data: CreateGoalRequest) => apiClient.post<Goal>("/goals", data),
  list: () => apiClient.get<Goal[]>("/goals"),
  get: (goalId: number) => apiClient.get<Goal>(`/goals/${goalId}`),
  update: (goalId: number, data: Partial<CreateGoalRequest>) =>
    apiClient.patch<Goal>(`/goals/${goalId}`, data),
  intake: (data: { text: string; category?: Goal["category"] }) =>
    apiClient.post("/goals/intake", data),
  complete: (data: {
    text: string;
    category?: Goal["category"];
    answers_json?: Record<string, unknown>;
    replace_existing?: boolean;
  }) => apiClient.post("/goals/complete", data),
};

export const calendarAPI = {
  get: (params: { start: string; end: string }) =>
    apiClient.get<CalendarResponse>("/calendar", { params }),
};

export const plannerAPI = {
  allocate: (data: {
    range_start: string;
    range_end: string;
    day_start?: string;
    day_end?: string;
    clear_existing?: boolean;
  }) => apiClient.post("/planner/allocate", data),
};

export const healthAPI = {
  check: () => apiClient.get("/health"),
  checkDB: () => apiClient.get("/health/db"),
};

export const handleApiError = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    if (error.response) {
      return error.response.data?.detail || "서버 오류가 발생했습니다.";
    }
    if (error.request) {
      return "서버에 연결할 수 없습니다.";
    }
  }
  return "알 수 없는 오류가 발생했습니다.";
};
