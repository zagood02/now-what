"use client";

import React, { useEffect, useMemo, useState } from "react";

import {
  TodoItem,
  createId,
  getFatigueLabel,
  readVariableSchedules,
  saveVariableSchedules,
  readTodos,
  saveTodos,
} from "@/lib/thirdStageStorage";
import { useAuth } from "@/app/contexts/AuthContext";
import { flexibleTaskAPI, type FlexibleTask, plannerAPI } from "@/lib/api";

type TodoForm = {
  title: string;
  due_at: string; // 마감일자
  target_hours: string; // 시간 단위
  importance: string;
  fatigue: string;
  memo: string;
};

const initialForm: TodoForm = {
  title: "",
  due_at: "",
  target_hours: "",
  importance: "5",
  fatigue: "5",
  memo: "",
};

export default function TodoPage() {
  const { user } = useAuth();

  const [form, setForm] = useState<TodoForm>(initialForm);
  const [items, setItems] = useState<TodoItem[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"active" | "done">("active");
  const [isLoaded, setIsLoaded] = useState(false);

  const userId = user?.id ? String(user.id) : "guest";

  function mapFlexibleTaskToTodoItem(task: FlexibleTask): TodoItem {
    const details = (task.details_json as any) ?? {};
    return {
      id: `flex-${task.id}`,
      user_id: String(task.user_id),
      title: task.title,
      goal_score: "",
      exam_date: task.due_at ? new Date(task.due_at).toISOString().slice(0, 10) : "",
      target_hours: Math.round((task.estimated_minutes || 0) / 60),
      importance: Number(details.importance ?? 5),
      fatigue: Number(details.fatigue ?? 5),
      memo: task.description ?? (details.memo ?? ""),
      is_done: (task.status as string) === "completed",
      created_at: (task.created_at as unknown) as string,
      updated_at: (task.updated_at as unknown) as string,
    } as TodoItem;
  }

  useEffect(() => {
    const refreshLocal = () => {
      const next = readTodos();
      setItems((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next));
      setIsLoaded(true);
    };

    const refreshRemote = async () => {
      try {
        const resp = await flexibleTaskAPI.list();
        const tasks = resp.data as FlexibleTask[];
        setItems(tasks.map(mapFlexibleTaskToTodoItem));
      } catch {
        refreshLocal();
      } finally {
        setIsLoaded(true);
      }
    };

    if (user) refreshRemote();
    else refreshLocal();

    const onTodoState = () => refreshLocal();
    const onAuthState = () => {
      if (user) refreshRemote();
      else refreshLocal();
    };

    window.addEventListener("todo-state-changed", onTodoState);
    window.addEventListener("auth-state-changed", onAuthState);

    return () => {
      window.removeEventListener("todo-state-changed", onTodoState);
      window.removeEventListener("auth-state-changed", onAuthState);
    };
  }, [user]);

  useEffect(() => {
    if (isLoaded && !user) saveTodos(items);
  }, [items, isLoaded, user]);

  const visibleItems = useMemo(
    () =>
      items
        .filter((it) => it.user_id === userId)
        .sort((a, b) => (a.exam_date || "").localeCompare(b.exam_date || "")),
    [items, userId]
  );

  const activeItems = visibleItems.filter((it) => !it.is_done);
  const doneItems = visibleItems.filter((it) => it.is_done);

  const resetForm = () => {
    setForm(initialForm);
    setEditingId(null);
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form.title.trim() || !form.due_at) return;
    const now = new Date().toISOString();

    if (user) {
      const payload = {
        title: form.title.trim(),
        description: form.memo.trim() || undefined,
        estimated_minutes: Math.round((Number(form.target_hours) || 0) * 60),
        min_session_minutes: 120, // 최소 2시간
        preferred_session_minutes: 180, // 선호 3시간
        max_minutes_per_day: 180,
        priority: Number(form.importance) || 2,
        due_at: form.due_at || undefined,
        details_json: { importance: Number(form.importance) || 5, fatigue: Number(form.fatigue) || 5 },
      } as any;

      try {
        if (editingId && editingId.startsWith("flex-")) {
          const id = Number(editingId.replace("flex-", ""));
          const resp = await flexibleTaskAPI.update(id, payload);
          const mapped = mapFlexibleTaskToTodoItem(resp.data as FlexibleTask);
          setItems((prev) => prev.map((it) => (it.id === editingId ? mapped : it)));
        } else {
          const resp = await flexibleTaskAPI.create(payload);
          const mapped = mapFlexibleTaskToTodoItem(resp.data as FlexibleTask);
          setItems((prev) => [...prev, mapped]);
        }
      } catch (err) {
        // ignore for now
      } finally {
        resetForm();
      }

      return;
    }

    // guest/local fallback
    const next: TodoItem = {
      id: editingId ?? createId("todo"),
      user_id: userId,
      title: form.title.trim(),
      goal_score: "",
      exam_date: form.due_at,
      target_hours: Number(form.target_hours) || 0,
      importance: Number(form.importance),
      fatigue: Number(form.fatigue),
      memo: form.memo.trim(),
      is_done: false,
      created_at: editingId ? items.find((it) => it.id === editingId)?.created_at ?? now : now,
      updated_at: now,
    };

    setItems((prev) => (editingId ? prev.map((it) => (it.id === editingId ? next : it)) : [...prev, next]));
    resetForm();
  };

  const handleEdit = (item: TodoItem) => {
    setEditingId(item.id);
    setForm({ title: item.title, due_at: item.exam_date, target_hours: String(item.target_hours), importance: String(item.importance), fatigue: String(item.fatigue), memo: item.memo });
  };

  const handleAllocate = async (item: TodoItem) => {
    if (!item.exam_date) return;
    try {
      const today = new Date();
      // 배치 전 기존 할당된 일정이 있다면 정리하는 로직이 필요한 경우
      // 현재 완료/삭제 로직은 백엔드에서 처리되므로, 배치 요청 시 clear_existing을 false로 유지
      await plannerAPI.allocate({
        range_start: today.toISOString(),
        range_end: new Date(item.exam_date).toISOString(),
        clear_existing: false,
      });
      alert("배치가 완료되었습니다.");
    } catch (err) {
      alert("배치 중 오류가 발생했습니다.");
    }
  };

  const toggleDone = (id: string) => {
    if (id.startsWith("flex-") && user) {
      const idNum = Number(id.replace("flex-", ""));
      const target = items.find((it) => it.id === id);
      if (!target) return;
      const nextStatus = target.is_done ? "pending" : "completed";

      // 낙관적 업데이트
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, is_done: !it.is_done } : it)));

      (async () => {
        try {
          await flexibleTaskAPI.update(idNum, { status: nextStatus } as any);

          // 스케줄 재계산하여 완료된 일정 제거
          const today = new Date();
          const endDate = new Date();
          endDate.setMonth(endDate.getMonth() + 1); 
          await plannerAPI.allocate({
            range_start: today.toISOString(),
            range_end: endDate.toISOString(),
            clear_existing: true,
          });

          const resp = await flexibleTaskAPI.list();
          const tasks = resp.data as FlexibleTask[];
          setItems(tasks.map(mapFlexibleTaskToTodoItem));
        } catch {
          // 실패 시 복구
          setItems((prev) => prev.map((it) => (it.id === id ? { ...it, is_done: target.is_done } : it)));
        }
      })();
      return;
    }
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, is_done: !it.is_done } : it)));
  };

  const deleteItem = (id: string) => {
    if (id.startsWith("flex-") && user) {
      const idNum = Number(id.replace("flex-", ""));
      (async () => {
        try {
          await flexibleTaskAPI.delete(idNum);
          const resp = await flexibleTaskAPI.list();
          const tasks = resp.data as FlexibleTask[];
          setItems(tasks.map(mapFlexibleTaskToTodoItem));
        } catch {
          // ignore
        }
      })();
      return;
    }
    setItems((prev) => prev.filter((it) => it.id !== id));
  };

  function syncVariableSchedule(todoId: string, title: string, isDone: boolean, shouldDelete = false) {
    const schedules = readVariableSchedules();
    const next = schedules
      .filter((schedule) => {
        const isLinked = schedule.title.includes(title.replace(/\s+(개념 정리|문제 풀이|오답 정리)$/, ""));
        if (!isLinked) return true;
        if (shouldDelete) return false;
        return true;
      })
      .map((schedule) => {
        const isLinked = schedule.title.includes(title.replace(/\s+(개념 정리|문제 풀이|오답 정리)$/, ""));
        if (!isLinked) return schedule;
        return { ...schedule, is_done: isDone, updated_at: new Date().toISOString() };
      });

    saveVariableSchedules(next);
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
        할일 관리
      </h1>

      <p className="mb-6" style={{ color: "var(--app-text-muted)" }}>
        마감일자와 예상 소요 시간으로 관리하는 페이지입니다.
      </p>

      <div className="grid grid-cols-1 xl:grid-cols-[420px_1fr] gap-6">
        <section className="rounded-2xl border p-5 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
          <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>{editingId ? "할일 수정" : "할일 추가"}</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <InputLabel label="할일 이름">
              <input value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} className="form-input" placeholder="예: 정보처리기사 필기" />
            </InputLabel>

            <div className="grid grid-cols-2 gap-3">
              <InputLabel label="마감일자">
                <input type="date" value={form.due_at} onChange={(e) => setForm((p) => ({ ...p, due_at: e.target.value }))} className="form-input" />
              </InputLabel>
            </div>

            <InputLabel label="예상 소요 시간">
              <input type="number" min="0" value={form.target_hours} onChange={(e) => setForm((p) => ({ ...p, target_hours: e.target.value }))} className="form-input" placeholder="시간 단위" />
            </InputLabel>

            <div className="grid grid-cols-2 gap-3">
              <InputLabel label="중요도">
                <input type="number" min="0" max="10" value={form.importance} onChange={(e) => setForm((p) => ({ ...p, importance: e.target.value }))} className="form-input" />
              </InputLabel>

              <InputLabel label="피로도">
                <input type="number" min="0" max="10" value={form.fatigue} onChange={(e) => setForm((p) => ({ ...p, fatigue: e.target.value }))} className="form-input" />
              </InputLabel>
            </div>

            <InputLabel label="메모">
              <textarea value={form.memo} onChange={(e) => setForm((p) => ({ ...p, memo: e.target.value }))} className="form-input min-h-24 resize-none" />
            </InputLabel>

            <button className="w-full rounded-xl py-3 font-bold" style={{ background: "var(--primary-button-bg)", color: "var(--primary-button-text)" }}>{editingId ? "수정 저장" : "할일 추가"}</button>

            {editingId && (
              <button type="button" onClick={resetForm} className="w-full rounded-xl py-3 font-bold" style={{ background: "var(--app-surface-muted)", color: "var(--app-text)" }}>취소</button>
            )}
          </form>
        </section>

        <section className="rounded-2xl border p-5 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
          <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>등록된 할일</h2>

          <div className="space-y-3">
            {visibleItems.length === 0 ? (
              <EmptyText>등록된 할일이 없습니다.</EmptyText>
            ) : (
              visibleItems.map((item) => (
                <div key={item.id} className="rounded-xl border p-4" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)" }}>
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <strong style={{ color: "var(--app-text)" }}>{item.title}</strong>
                        <span className="px-2 py-1 rounded-full text-xs font-bold" style={{ background: item.is_done ? "var(--card-green-bg)" : "var(--card-yellow-bg)", color: item.is_done ? "var(--card-green-text)" : "var(--card-yellow-text)" }}>{item.is_done ? "완료" : "진행 중"}</span>
                      </div>

                      <div className="text-sm mt-2" style={{ color: "var(--app-text-muted)" }}>마감일자 {item.exam_date || "-"} · 예상 소요 시간 {item.target_hours} 시간</div>

                      <div className="text-sm mt-1" style={{ color: "var(--app-text-muted)" }}>중요도 {item.importance} · 피로도 {item.fatigue} ({getFatigueLabel(item.fatigue)})</div>

                      {item.memo && <p className="text-sm mt-2" style={{ color: "var(--app-text)" }}>{item.memo}</p>}
                    </div>

                    <div className="flex gap-2 flex-wrap">
                      <SmallButton onClick={() => toggleDone(item.id)} type="green">완료 전환</SmallButton>
                      <SmallButton onClick={() => handleAllocate(item)} type="blue">배치</SmallButton>
                      <SmallButton onClick={() => handleEdit(item)} type="blue">수정</SmallButton>
                      <SmallButton onClick={() => deleteItem(item.id)} type="red">삭제</SmallButton>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      <style jsx global>{`
        .form-input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid var(--app-border);
          background: var(--app-bg);
          color: var(--app-text);
          padding: 0.75rem;
          outline: none;
        }
      `}</style>
    </div>
  );
}

function InputLabel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-sm font-bold mb-2" style={{ color: "var(--app-text)" }}>{label}</div>
      {children}
    </div>
  );
}

function SmallButton({ children, onClick, type }: { children: React.ReactNode; onClick: () => void; type: "blue" | "green" | "red"; }) {
  const style =
    type === "blue"
      ? { background: "var(--card-blue-bg)", color: "var(--card-blue-text)" }
      : type === "green"
      ? { background: "var(--card-green-bg)", color: "var(--card-green-text)" }
      : { background: "var(--card-red-bg)", color: "var(--card-red-text)" };

  return (
    <button onClick={onClick} className="px-3 py-2 rounded-md font-bold" style={style}>
      {children}
    </button>
  );
}

function EmptyText({ children }: { children: React.ReactNode }) {
  return <div style={{ color: "var(--app-text-muted)" }}>{children}</div>;
}
