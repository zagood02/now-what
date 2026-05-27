"use client";

export type AppUser = {
  id: string;
  email: string;
  password: string;
  name: string;
  nickname?: string;
  profile_image?: string;
  created_at: string;
};

export type TodoItem = {
  id: string;
  user_id: string;
  title: string;
  goal_score: string;
  exam_date: string;
  target_hours: number;
  importance: number;
  fatigue: number;
  memo: string;
  is_done: boolean;
  created_at: string;
  updated_at: string;
};

export type AiQuestion = {
  id: string;
  question: string;
  answer: string;
};

export type AiPlanDraft = {
  id: string;
  user_id: string;
  prompt: string;
  questions: AiQuestion[];
  todos: TodoItem[];
  variableSchedules: VariableSchedule[];
  created_at: string;
};

export type VariableSchedule = {
  id: string;
  user_id: string;
  title: string;
  estimated_time: number;
  fatigue: number;
  color_key: number;
  memo: string;
  is_done: boolean;
  created_at: string;
  updated_at: string;
};

export type FixedSchedule = {
  id: string;
  user_id: string;
  title: string;
  start_time: string;
  end_time: string;
  repeat_type: "WEEKLY" | "BIWEEKLY" | "MONTHLY";
  days: string[];
  month_days: number[];
  color_key: number;
  fatigue: number;
  created_at: string;
  updated_at: string;
};

const USERS_KEY = "third_stage_users";
const CURRENT_USER_KEY = "third_stage_current_user";
const GUEST_SESSION_KEY = "third_stage_guest_session";

const TODOS_KEY = "third_stage_todos";
const VARIABLE_KEY = "third_stage_variable_schedules";
const FIXED_KEY = "third_stage_fixed_schedules";
const AI_DRAFTS_KEY = "third_stage_ai_plan_drafts";

function safeRead<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;

  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function safeWrite<T>(key: string, value: T) {
  if (typeof window === "undefined") return;
  localStorage.setItem(key, JSON.stringify(value));
}

function normalizeUser(user: AppUser): AppUser {
  return {
    ...user,
    nickname: user.nickname ?? user.name,
    profile_image: user.profile_image ?? "",
  };
}

export function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function readUsers() {
  return safeRead<AppUser[]>(USERS_KEY, []).map(normalizeUser);
}

export function saveUsers(users: AppUser[]) {
  safeWrite(USERS_KEY, users.map(normalizeUser));
}

export function readCurrentUser() {
  const user = safeRead<AppUser | null>(CURRENT_USER_KEY, null);
  return user ? normalizeUser(user) : null;
}

export function saveCurrentUser(user: AppUser | null) {
  if (typeof window === "undefined") return;

  if (user) {
    localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(normalizeUser(user)));
  } else {
    localStorage.removeItem(CURRENT_USER_KEY);
  }

  window.dispatchEvent(new Event("auth-state-changed"));
}

export function updateCurrentUserProfile(
  patch: Partial<
    Pick<AppUser, "nickname" | "name" | "email" | "password" | "profile_image">
  >
) {
  const current = readCurrentUser();
  if (!current) return null;

  const updated = normalizeUser({
    ...current,
    ...patch,
  });

  const users = readUsers().map((user) =>
    user.id === current.id ? updated : user
  );

  saveUsers(users);
  saveCurrentUser(updated);

  return updated;
}

export function startGuestSession() {
  if (typeof window === "undefined") return;

  sessionStorage.setItem(
    GUEST_SESSION_KEY,
    JSON.stringify({
      isGuest: true,
      started_at: new Date().toISOString(),
    })
  );

  localStorage.removeItem(CURRENT_USER_KEY);
  window.dispatchEvent(new Event("auth-state-changed"));
}

export function clearGuestSession() {
  if (typeof window === "undefined") return;

  sessionStorage.removeItem(GUEST_SESSION_KEY);
  window.dispatchEvent(new Event("auth-state-changed"));
}

export function isGuestSessionActive() {
  if (typeof window === "undefined") return false;
  return Boolean(sessionStorage.getItem(GUEST_SESSION_KEY));
}

export function logoutCurrentSession() {
  if (typeof window === "undefined") return;

  localStorage.removeItem(CURRENT_USER_KEY);
  sessionStorage.removeItem(GUEST_SESSION_KEY);
  window.dispatchEvent(new Event("auth-state-changed"));
}

export function getActiveUserLabel() {
  const user = readCurrentUser();
  if (user) return user.nickname || user.name || user.email;
  if (isGuestSessionActive()) return "게스트";
  return "";
}

function getActiveStorageScope() {
  if (typeof window === "undefined") return "server";

  const currentUser = readCurrentUser();
  if (currentUser?.id) return `user_${currentUser.id}`;

  if (isGuestSessionActive()) return "guest";

  return "locked";
}

function scopedStorageKey(baseKey: string) {
  return `${baseKey}_${getActiveStorageScope()}`;
}

function dedupeById<T extends { id: string }>(items: T[]) {
  const map = new Map<string, T>();

  items.forEach((item) => {
    map.set(item.id, item);
  });

  return Array.from(map.values());
}

export function readTodos() {
  if (typeof window === "undefined") return [];

  const scope = getActiveStorageScope();
  if (scope === "locked") return [];

  try {
    if (scope === "guest") {
      const raw = sessionStorage.getItem(scopedStorageKey(TODOS_KEY));
      return raw ? dedupeById(JSON.parse(raw) as TodoItem[]) : [];
    }

    return dedupeById(safeRead<TodoItem[]>(scopedStorageKey(TODOS_KEY), []));
  } catch {
    return [];
  }
}

export function saveTodos(items: TodoItem[]) {
  if (typeof window === "undefined") return;

  const scope = getActiveStorageScope();
  if (scope === "locked") return;

  const key = scopedStorageKey(TODOS_KEY);
  const next = dedupeById(items);
  const nextRaw = JSON.stringify(next);

  if (scope === "guest") {
    const prevRaw = sessionStorage.getItem(key);

    if (prevRaw !== nextRaw) {
      sessionStorage.setItem(key, nextRaw);
      window.dispatchEvent(new Event("todo-state-changed"));
    }

    return;
  }

  const prevRaw = localStorage.getItem(key);

  if (prevRaw !== nextRaw) {
    localStorage.setItem(key, nextRaw);
    window.dispatchEvent(new Event("todo-state-changed"));
  }
}

export function readVariableSchedules() {
  return safeRead<VariableSchedule[]>(VARIABLE_KEY, []);
}

export function saveVariableSchedules(items: VariableSchedule[]) {
  safeWrite(VARIABLE_KEY, items);
}

export function readFixedSchedules() {
  return safeRead<FixedSchedule[]>(FIXED_KEY, []);
}

export function saveFixedSchedules(items: FixedSchedule[]) {
  safeWrite(FIXED_KEY, items);
}

export function readAiDrafts() {
  return safeRead<AiPlanDraft[]>(AI_DRAFTS_KEY, []);
}

export function saveAiDrafts(items: AiPlanDraft[]) {
  safeWrite(AI_DRAFTS_KEY, items);
}

export const colorOptions = [
  {
    key: 0,
    label: "파랑",
    bg: "var(--card-blue-bg)",
    text: "var(--card-blue-text)",
  },
  {
    key: 1,
    label: "초록",
    bg: "var(--card-green-bg)",
    text: "var(--card-green-text)",
  },
  {
    key: 2,
    label: "노랑",
    bg: "var(--card-yellow-bg)",
    text: "var(--card-yellow-text)",
  },
  {
    key: 3,
    label: "빨강",
    bg: "var(--card-red-bg)",
    text: "var(--card-red-text)",
  },
];

export function getColor(key: number) {
  return colorOptions.find((item) => item.key === key) ?? colorOptions[0];
}

export function getFatigueLabel(value: number) {
  if (value <= 2) return "낮음";
  if (value <= 5) return "보통";
  if (value <= 8) return "높음";
  return "매우 높음";
}
