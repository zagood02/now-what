"use client";

import { useEffect, useMemo, useState } from "react";
import {
  fixedScheduleAPI,
  flexibleTaskAPI,
  handleApiError,
  type FixedSchedule,
  type FlexibleTask,
} from "@/lib/api";
import { useAuth } from "@/app/contexts/AuthContext";

type FixedFormState = {
  title: string;
  start_time: string;
  end_time: string;
  freq_type: "NONE" | "WEEKLY" | "BIWEEKLY" | "MONTHLY";
  recurrence_rule: string;
  day_of_week: number | null;
  repeat_start_date: string
};

type VariableFormState = {
  title: string;
  estimated_time: string;
  level: string;
  deadline: string;
};

const todayString = new Date().toISOString().split("T")[0];

const fixedInitialForm: FixedFormState = {
  title: "",
  start_time: "09:00",
  end_time: "10:00",
  freq_type: "WEEKLY",
  recurrence_rule: "weekly",
  day_of_week: null,
  repeat_start_date: todayString,
};

const variableInitialForm: VariableFormState = {
  title: "",
  estimated_time: "",
  level: "5",
  deadline: "",
};

export default function ManagePage() {
  const { user, isLoading: isAuthLoading } = useAuth();
  const [activeTab, setActiveTab] = useState<"fixed" | "variable">("fixed");
  const [fixedForm, setFixedForm] = useState<FixedFormState>(fixedInitialForm);
  const [variableForm, setVariableForm] = useState<VariableFormState>(variableInitialForm);

  const [isLoadingApi, setIsLoadingApi] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [fixedSchedules, setFixedSchedules] = useState<FixedSchedule[]>([]);
  const [flexibleTasks, setFlexibleTasks] = useState<FlexibleTask[]>([]);

  // Initialize test user and load data from API
  useEffect(() => {
    const initializeData = async () => {
      if (isAuthLoading) {
        return;
      }

      if (!user) {
        setFixedSchedules([]);
        setFlexibleTasks([]);
        setApiError(null);
        return;
      }

      try {
        setIsLoadingApi(true);

        // Load schedules from API
        const schedulesRes = await fixedScheduleAPI.list();
        setFixedSchedules(schedulesRes.data);

        // Load flexible tasks from API
        const tasksRes = await flexibleTaskAPI.list();
        setFlexibleTasks(tasksRes.data);

        setApiError(null);
      } catch (error) {
        console.error("Failed to load data from API:", error);
        setApiError(handleApiError(error));
        setFixedSchedules([]);
        setFlexibleTasks([]);
      } finally {
        setIsLoadingApi(false);
      }
    };

    initializeData();
  }, [isAuthLoading, user]);

  const sortedFixedSchedules = useMemo(() => {
    return [...fixedSchedules].sort((a, b) => a.title.localeCompare(b.title));
  }, [fixedSchedules]);

  const sortedFlexibleTasks = useMemo(() => {
    return [...flexibleTasks].sort((a, b) => {
      if (!a.due_at && !b.due_at) return 0;
      if (!a.due_at) return 1;
      if (!b.due_at) return -1;
      return new Date(a.due_at).getTime() - new Date(b.due_at).getTime();
    });
  }, [flexibleTasks]);

  const getAnchorDate = () => {
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

    if (fixedForm.repeat_start_date) {
      return fixedForm.repeat_start_date;
    }

    if ((fixedForm.freq_type === "WEEKLY" || fixedForm.freq_type === "BIWEEKLY") && fixedForm.day_of_week !== null) {
      const todayWeekday = now.getDay();
      const diff = (fixedForm.day_of_week - todayWeekday + 7) % 7;
      const nextDate = new Date(now);
      nextDate.setDate(now.getDate() + diff);
      return `${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, "0")}-${String(nextDate.getDate()).padStart(2, "0")}`;
    }

    return today;
  };

  const handleFixedSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!fixedForm.title.trim()) return;
    if (!fixedForm.start_time || !fixedForm.end_time) return;
    if (!user) {
      setApiError("로그인이 필요합니다.");
      return;
    }

    if ((fixedForm.freq_type === "WEEKLY" || fixedForm.freq_type === "BIWEEKLY") && fixedForm.day_of_week === null) {
      setApiError("매주/격주 반복은 요일 선택이 필요합니다.");
      return;
    }

    if (fixedForm.freq_type === "BIWEEKLY" && !fixedForm.repeat_start_date) {
      setApiError("격주 반복은 시작 날짜 선택이 필요합니다.");
      return;
    }

    if (fixedForm.freq_type === "MONTHLY" && !fixedForm.repeat_start_date) {
      setApiError("월 반복은 시작 날짜 선택이 필요합니다.");
      return;
    }

    try {
      setIsLoadingApi(true);
      setApiError(null);

      const anchorDate = getAnchorDate();
      const start_at = `${anchorDate}T${fixedForm.start_time}:00`;
      const end_at = `${anchorDate}T${fixedForm.end_time}:00`;
      const recurrence_rule =
        fixedForm.freq_type === "WEEKLY"
          ? "weekly"
          : fixedForm.freq_type === "BIWEEKLY"
          ? "biweekly"
          : fixedForm.freq_type === "MONTHLY"
          ? "monthly"
          : undefined;

      const response = await fixedScheduleAPI.create({
        title: fixedForm.title.trim(),
        start_at,
        end_at,
        is_all_day: false,
        recurrence_rule: recurrence_rule || undefined,
        day_of_week: fixedForm.day_of_week ?? undefined,
      });

      setFixedSchedules((prev) => [...prev, response.data]);
      setFixedForm(fixedInitialForm);

      alert("✅ 고정 스케줄이 등록되었습니다!");
    } catch (error) {
      console.error("Failed to create fixed schedule:", error);
      setApiError(handleApiError(error));
    } finally {
      setIsLoadingApi(false);
    }
  };

  const handleDeleteFixed = async (scheduleId: number) => {
    if (!user) {
      setApiError("로그인이 필요합니다.");
      return;
    }

    try {
      setIsLoadingApi(true);
      setApiError(null);
      await fixedScheduleAPI.delete(scheduleId);
      setFixedSchedules((prev) => prev.filter((schedule) => schedule.id !== scheduleId));
    } catch (error) {
      console.error("Failed to delete fixed schedule:", error);
      setApiError(handleApiError(error));
    } finally {
      setIsLoadingApi(false);
    }
  };

  const handleVariableSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!variableForm.title.trim()) return;
    if (!variableForm.estimated_time || Number(variableForm.estimated_time) <= 0) return;
    if (!user) {
      setApiError("로그인이 필요합니다.");
      return;
    }

    try {
      setIsLoadingApi(true);
      setApiError(null);

      const estimatedMinutes = Number(variableForm.estimated_time);

      const response = await flexibleTaskAPI.create({
        title: variableForm.title.trim(),
        estimated_minutes: estimatedMinutes,
        min_session_minutes: Math.max(15, Math.floor(estimatedMinutes / 4)),
        preferred_session_minutes: Math.max(30, Math.floor(estimatedMinutes / 2)),
        max_minutes_per_day: Math.min(180, estimatedMinutes),
        priority: Number(variableForm.level),
        due_at: variableForm.deadline ? `${variableForm.deadline}:00` : undefined,
        details_json: {},
      });

      setFlexibleTasks((prev) => [...prev, response.data]);
      setVariableForm(variableInitialForm);

      alert("✅ 유연한 작업이 등록되었습니다!");
    } catch (error) {
      console.error("Failed to save flexible task:", error);
      setApiError(handleApiError(error));
    } finally {
      setIsLoadingApi(false);
    }
  };

  const handleDeleteVariable = async (id: string) => {
    if (!user) {
      setApiError("로그인이 필요합니다.");
      return;
    }

    try {
      const taskId = parseInt(id);
      await flexibleTaskAPI.delete(taskId);
      setFlexibleTasks((prev) => prev.filter((item) => item.id !== taskId));
    } catch (error) {
      console.error("Failed to delete flexible task:", error);
      setApiError(handleApiError(error));
    }
  };

  return (
    <div className="space-y-6">
      {isLoadingApi && (
        <div
          className="rounded-xl border p-4"
          style={{
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
            color: "var(--app-text-muted)",
          }}
        >
          로딩 중...
        </div>
      )}

      {!isAuthLoading && !user && (
        <div
          className="rounded-xl border p-4"
          style={{
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
            color: "var(--app-text-muted)",
          }}
        >
          로그인 후 일정과 작업을 관리할 수 있습니다.
        </div>
      )}

      {apiError && (
        <div
          className="rounded-xl border p-4"
          style={{
            background: "rgba(239, 68, 68, 0.1)",
            borderColor: "var(--app-border)",
            color: "#dc2626",
          }}
        >
          ⚠️ API 오류: {apiError}
        </div>
      )}

      <div>
        <h1
          className="text-3xl font-bold mb-2"
          style={{ color: "var(--app-text)" }}
        >
          일정 관리
        </h1>
        <p style={{ color: "var(--app-text-muted)" }}>
          고정 스케줄과 변동 스케줄을 나눠 등록하고 관리할 수 있습니다.
        </p>
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => setActiveTab("fixed")}
          className="px-4 py-2 rounded-full border font-semibold transition"
          style={{
            background:
              activeTab === "fixed"
                ? "var(--primary-button-bg)"
                : "var(--app-surface)",
            color:
              activeTab === "fixed"
                ? "var(--primary-button-text)"
                : "var(--app-text)",
            borderColor: "var(--app-border)",
          }}
        >
          고정 스케줄
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("variable")}
          className="px-4 py-2 rounded-full border font-semibold transition"
          style={{
            background:
              activeTab === "variable"
                ? "var(--primary-button-bg)"
                : "var(--app-surface)",
            color:
              activeTab === "variable"
                ? "var(--primary-button-text)"
                : "var(--app-text)",
            borderColor: "var(--app-border)",
          }}
        >
          변동 스케줄
        </button>
      </div>

      {activeTab === "fixed" && (
        <div className="grid grid-cols-1 xl:grid-cols-[500px_1fr] gap-6">
          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{
              background: "var(--app-surface)",
              borderColor: "var(--app-border)",
            }}
          >
            <h2
              className="text-xl font-bold mb-4"
              style={{ color: "var(--app-text)" }}
            >
              고정 스케줄 등록
            </h2>

            <form onSubmit={handleFixedSubmit} className="space-y-4">
              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  제목
                </label>
                <input
                  type="text"
                  value={fixedForm.title}
                  onChange={(e) =>
                    setFixedForm((prev) => ({
                      ...prev,
                      title: e.target.value,
                    }))
                  }
                  placeholder="예: 알고리즘 수업"
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    className="block text-sm font-semibold mb-2"
                    style={{ color: "var(--app-text)" }}
                  >
                    시작 시간
                  </label>
                  <input
                    type="time"
                    value={fixedForm.start_time}
                    onChange={(e) =>
                      setFixedForm((prev) => ({
                        ...prev,
                        start_time: e.target.value,
                      }))
                    }
                    className="w-full rounded-xl border px-3 py-2 outline-none"
                    style={{
                      background: "var(--app-bg)",
                      borderColor: "var(--app-border)",
                      color: "var(--app-text)",
                    }}
                  />
                </div>

                <div>
                  <label
                    className="block text-sm font-semibold mb-2"
                    style={{ color: "var(--app-text)" }}
                  >
                    종료 시간
                  </label>
                  <input
                    type="time"
                    value={fixedForm.end_time}
                    onChange={(e) =>
                      setFixedForm((prev) => ({
                        ...prev,
                        end_time: e.target.value,
                      }))
                    }
                    className="w-full rounded-xl border px-3 py-2 outline-none"
                    style={{
                      background: "var(--app-bg)",
                      borderColor: "var(--app-border)",
                      color: "var(--app-text)",
                    }}
                  />
                </div>
              </div>

              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  반복 유형
                </label>
                <select
                  value={fixedForm.freq_type}
                  onChange={(e) =>
                    setFixedForm((prev) => ({
                      ...prev,
                      freq_type: e.target.value as "NONE" | "WEEKLY" | "BIWEEKLY" | "MONTHLY",
                      recurrence_rule:
                        e.target.value === "WEEKLY"
                          ? "weekly"
                          : e.target.value === "BIWEEKLY"
                          ? "biweekly"
                          : e.target.value === "MONTHLY"
                          ? "monthly"
                          : "",
                    }))
                  }
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                >
                  <option value="NONE">반복 없음</option>
                  <option value="WEEKLY">매주</option>
                  <option value="BIWEEKLY">격주</option>
                  <option value="MONTHLY">매월</option>
                </select>
              </div>

              {(fixedForm.freq_type === "WEEKLY" || fixedForm.freq_type === "BIWEEKLY") && (
                <div>
                  <label
                    className="block text-sm font-semibold mb-2"
                    style={{ color: "var(--app-text)" }}
                  >
                    요일
                  </label>
                  <select
                    value={fixedForm.day_of_week ?? ""}
                    onChange={(e) =>
                      setFixedForm((prev) => ({
                        ...prev,
                        day_of_week: e.target.value ? parseInt(e.target.value) : null,
                      }))
                    }
                    className="w-full rounded-xl border px-3 py-2 outline-none"
                    style={{
                      background: "var(--app-bg)",
                      borderColor: "var(--app-border)",
                      color: "var(--app-text)",
                    }}
                  >
                    <option value="">요일 선택</option>
                    <option value="0">일요일</option>
                    <option value="1">월요일</option>
                    <option value="2">화요일</option>
                    <option value="3">수요일</option>
                    <option value="4">목요일</option>
                    <option value="5">금요일</option>
                    <option value="6">토요일</option>
                  </select>
                </div>
              )}

              {(fixedForm.freq_type === "BIWEEKLY" || fixedForm.freq_type === "MONTHLY") && (
                <div>
                  <label
                    className="block text-sm font-semibold mb-2"
                    style={{ color: "var(--app-text)" }}
                  >
                    시작 날짜
                  </label>
                  <input
                    type="date"
                    value={fixedForm.repeat_start_date}
                    onChange={(e) =>
                      setFixedForm((prev) => ({
                        ...prev,
                        repeat_start_date: e.target.value,
                      }))
                    }
                    className="w-full rounded-xl border px-3 py-2 outline-none"
                    style={{
                      background: "var(--app-bg)",
                      borderColor: "var(--app-border)",
                      color: "var(--app-text)",
                    }}
                  />
                </div>
              )}

              <button
                type="submit"
                className="w-full rounded-xl py-3 font-semibold transition hover:opacity-90"
                style={{
                  background: "var(--primary-button-bg)",
                  color: "var(--primary-button-text)",
                }}
              >
                고정 스케줄 추가
              </button>
            </form>
          </section>


          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{
              background: "var(--app-surface)",
              borderColor: "var(--app-border)",
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2
                className="text-xl font-bold"
                style={{ color: "var(--app-text)" }}
              >
                등록된 고정 스케줄
              </h2>
              <span
                className="text-sm font-medium"
                style={{ color: "var(--app-text-muted)" }}
              >
                총 {sortedFixedSchedules.length}개
              </span>
            </div>

            <div className="space-y-3">
              {sortedFixedSchedules.length === 0 ? (
                <div
                  className="rounded-xl border px-4 py-6 text-center"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text-muted)",
                  }}
                >
                  등록된 고정 스케줄이 없습니다.
                </div>
              ) : (
                sortedFixedSchedules.map((schedule) => {
                  const startTime = new Date(schedule.start_at).toLocaleTimeString('ko-KR', {
                    hour: '2-digit',
                    minute: '2-digit'
                  });
                  const endTime = new Date(schedule.end_at).toLocaleTimeString('ko-KR', {
                    hour: '2-digit',
                    minute: '2-digit'
                  });

                  return (
                    <div
                      key={schedule.id}
                      className="rounded-xl border p-4"
                      style={{
                        background: "var(--app-bg)",
                        borderColor: "var(--app-border)",
                      }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ background: "var(--card-blue-bg)" }}
                            />
                            <div
                              className="font-bold text-base"
                              style={{ color: "var(--app-text)" }}
                            >
                              {schedule.title}
                            </div>
                          </div>
                          <div
                            className="text-sm mt-1"
                            style={{ color: "var(--app-text-muted)" }}
                          >
                            {startTime} - {endTime}
                            {schedule.day_of_week !== null && (
                              <span className="ml-2">
                                ({['일', '월', '화', '수', '목', '금', '토'][schedule.day_of_week]}요일)
                              </span>
                            )}
                            {schedule.recurrence_rule && (
                              <span className="ml-2">
                                ({schedule.recurrence_rule === 'weekly' ? '매주' :
                                  schedule.recurrence_rule === 'biweekly' ? '격주' :
                                  schedule.recurrence_rule})
                              </span>
                            )}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            if (confirm('정말 삭제하시겠습니까?')) {
                              handleDeleteFixed(schedule.id);
                            }
                          }}
                          className="px-3 py-1 rounded-lg text-sm font-semibold transition hover:opacity-90"
                          style={{
                            background: "var(--card-red-bg)",
                            color: "var(--card-red-text)",
                          }}
                        >
                          삭제
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </section>
        </div>
      )}

      {activeTab === "variable" && (
        <div className="grid grid-cols-1 xl:grid-cols-[500px_1fr] gap-6">
          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{
              background: "var(--app-surface)",
              borderColor: "var(--app-border)",
            }}
          >
            <h2
              className="text-xl font-bold mb-4"
              style={{ color: "var(--app-text)" }}
            >
              변동 스케줄 등록
            </h2>

            <form onSubmit={handleVariableSubmit} className="space-y-4">
              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  제목
                </label>
                <input
                  type="text"
                  value={variableForm.title}
                  onChange={(e) =>
                    setVariableForm((prev) => ({
                      ...prev,
                      title: e.target.value,
                    }))
                  }
                  placeholder="예: 운영체제 과제"
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  소요 시간
                </label>
                <input
                  type="number"
                  min={1}
                  value={variableForm.estimated_time}
                  onChange={(e) =>
                    setVariableForm((prev) => ({
                      ...prev,
                      estimated_time: e.target.value,
                    }))
                  }
                  placeholder="분 단위 입력"
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  우선순위 (1-10)
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={variableForm.level}
                  onChange={(e) =>
                    setVariableForm((prev) => ({
                      ...prev,
                      level: e.target.value,
                    }))
                  }
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <div>
                <label
                  className="block text-sm font-semibold mb-2"
                  style={{ color: "var(--app-text)" }}
                >
                  마감 기한
                </label>
                <input
                  type="datetime-local"
                  value={variableForm.deadline}
                  onChange={(e) =>
                    setVariableForm((prev) => ({
                      ...prev,
                      deadline: e.target.value,
                    }))
                  }
                  className="w-full rounded-xl border px-3 py-2 outline-none"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text)",
                  }}
                />
              </div>

              <button
                type="submit"
                className="w-full rounded-xl py-3 font-semibold transition hover:opacity-90"
                style={{
                  background: "var(--primary-button-bg)",
                  color: "var(--primary-button-text)",
                }}
              >
                변동 스케줄 추가
              </button>
            </form>
          </section>

          <section
            className="rounded-2xl border p-5 shadow-sm"
            style={{
              background: "var(--app-surface)",
              borderColor: "var(--app-border)",
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2
                className="text-xl font-bold"
                style={{ color: "var(--app-text)" }}
              >
                등록된 변동 스케줄
              </h2>
              <span
                className="text-sm font-medium"
                style={{ color: "var(--app-text-muted)" }}
              >
                총 {sortedFlexibleTasks.length}개
              </span>
            </div>

            <div className="space-y-3">
              {sortedFlexibleTasks.length === 0 ? (
                <div
                  className="rounded-xl border px-4 py-6 text-center"
                  style={{
                    background: "var(--app-bg)",
                    borderColor: "var(--app-border)",
                    color: "var(--app-text-muted)",
                  }}
                >
                  등록된 변동 스케줄이 없습니다.
                </div>
              ) : (
                sortedFlexibleTasks.map((task) => (
                  <div
                    key={task.id}
                    className="rounded-xl border p-4"
                    style={{
                      background: "var(--app-bg)",
                      borderColor: "var(--app-border)",
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div
                          className="font-bold text-base"
                          style={{ color: "var(--app-text)" }}
                        >
                          {task.title}
                        </div>

                        <div
                          className="text-sm"
                          style={{ color: "var(--app-text-muted)" }}
                        >
                          예상 소요 시간: {task.estimated_minutes}분
                        </div>

                        <div
                          className="text-sm"
                          style={{ color: "var(--app-text-muted)" }}
                        >
                          우선순위: {task.priority}
                        </div>

                        {task.due_at && (
                          <div
                            className="text-sm"
                            style={{ color: "var(--app-text-muted)" }}
                          >
                            마감: {new Date(task.due_at).toLocaleString('ko-KR')}
                          </div>
                        )}

                        <div className="flex items-center gap-2 pt-1">
                          <span
                            className="px-2 py-1 rounded-full text-xs font-semibold"
                            style={{
                              background: task.status === 'completed'
                                ? "var(--card-green-bg)"
                                : task.status === 'in_progress'
                                ? "var(--card-blue-bg)"
                                : "var(--card-yellow-bg)",
                              color: task.status === 'completed'
                                ? "var(--card-green-text)"
                                : task.status === 'in_progress'
                                ? "var(--card-blue-text)"
                                : "var(--card-yellow-text)",
                            }}
                          >
                            {task.status === 'completed' ? '완료' :
                             task.status === 'in_progress' ? '진행 중' :
                             task.status === 'pending' ? '대기' : task.status}
                          </span>
                        </div>
                      </div>

                      <div className="flex flex-col gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            alert('수정 기능은 아직 구현되지 않았습니다.');
                          }}
                          className="px-3 py-2 rounded-lg font-semibold text-sm"
                          style={{
                            background: "var(--card-blue-bg)",
                            color: "var(--card-blue-text)",
                          }}
                        >
                          수정
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDeleteVariable(String(task.id))}
                          className="px-3 py-2 rounded-lg font-semibold text-sm"
                          style={{
                            background: "var(--card-red-bg)",
                            color: "var(--card-red-text)",
                          }}
                        >
                          삭제
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
