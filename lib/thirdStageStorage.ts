export type AppUser = {
  id: string;
  email: string;
  password: string;
  name: string;
  created_at: string;
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

const USERS_KEY = "third_stage_users";
const CURRENT_USER_KEY = "third_stage_current_user";
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

export function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function readUsers() {
  return safeRead<AppUser[]>(USERS_KEY, []);
}

export function saveUsers(users: AppUser[]) {
  safeWrite(USERS_KEY, users);
}

export function readCurrentUser() {
  return safeRead<AppUser | null>(CURRENT_USER_KEY, null);
}

export function saveCurrentUser(user: AppUser | null) {
  safeWrite(CURRENT_USER_KEY, user);
}

export function readTodos() {
  return safeRead<TodoItem[]>(TODOS_KEY, []);
}

export function saveTodos(items: TodoItem[]) {
  safeWrite(TODOS_KEY, items);
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
  return (
    colorOptions.find((item) => item.key === key) ?? colorOptions[0]
  );
}

export function getFatigueLabel(value: number) {
  if (value <= 2) return "낮음";
  if (value <= 5) return "보통";
  if (value <= 8) return "높음";
  return "매우 높음";
}