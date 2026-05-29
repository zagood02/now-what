"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  TodoItem,
  createId,
  getFatigueLabel,
  readCurrentUser,
  readVariableSchedules,
  saveVariableSchedules,
  readTodos,
  saveTodos,
} from "@/lib/thirdStageStorage";

type TodoForm = {
  title: string;
  goal_score: string;
  exam_date: string;
  target_hours: string;
  importance: string;
  fatigue: string;
  memo: string;
};

const initialForm: TodoForm = {
  title: "",
  goal_score: "",
  exam_date: "",
  target_hours: "",
  importance: "5",
  fatigue: "5",
  memo: "",
};

export default function TodoPage() {
  const [form, setForm] =
    useState<TodoForm>(initialForm);

  const [items, setItems] =
    useState<TodoItem[]>([]);

  const [editingId, setEditingId] =
    useState<string | null>(null);

  const [activeTab, setActiveTab] =
    useState<"active" | "done">(
      "active"
    );

  const [isLoaded, setIsLoaded] =
    useState(false);

  const currentUser =
    readCurrentUser();

  const userId =
    currentUser?.id ?? "guest";

  useEffect(() => {
    const refreshTodos = () => {
      const nextItems = readTodos();

      setItems((prev) =>
        JSON.stringify(prev) === JSON.stringify(nextItems)
          ? prev
          : nextItems
      );

      setIsLoaded(true);
    };

    refreshTodos();

    window.addEventListener(
      "todo-state-changed",
      refreshTodos
    );

    window.addEventListener(
      "auth-state-changed",
      refreshTodos
    );

    return () => {
      window.removeEventListener(
        "todo-state-changed",
        refreshTodos
      );

      window.removeEventListener(
        "auth-state-changed",
        refreshTodos
      );
    };
  }, []);

  useEffect(() => {
    if (isLoaded) {
      saveTodos(items);
    }
  }, [items, isLoaded]);

  const visibleItems = useMemo(
    () =>
      items
        .filter(
          (item) =>
            item.user_id === userId
        )
        .sort((a, b) =>
          a.exam_date.localeCompare(
            b.exam_date
          )
        ),
    [items, userId]
  );

  const activeItems =
    visibleItems.filter(
      (item) => !item.is_done
    );

  const doneItems =
    visibleItems.filter(
      (item) => item.is_done
    );

  const resetForm = () => {
    setForm(initialForm);
    setEditingId(null);
  };

  const handleSubmit = (
    e: React.FormEvent<HTMLFormElement>
  ) => {
    e.preventDefault();

    if (
      !form.title.trim() ||
      !form.exam_date
    ) {
      return;
    }

    const now =
      new Date().toISOString();

    const nextItem: TodoItem = {
      id:
        editingId ??
        createId("todo"),

      user_id: userId,

      title: form.title.trim(),

      goal_score:
        form.goal_score.trim(),

      exam_date:
        form.exam_date,

      target_hours:
        Number(form.target_hours) ||
        0,

      importance: Number(
        form.importance
      ),

      fatigue: Number(
        form.fatigue
      ),

      memo: form.memo.trim(),

      is_done: false,

      created_at: editingId
        ? items.find(
            (item) =>
              item.id === editingId
          )?.created_at ?? now
        : now,

      updated_at: now,
    };

    setItems((prev) =>
      editingId
        ? prev.map((item) =>
            item.id === editingId
              ? nextItem
              : item
          )
        : [...prev, nextItem]
    );

    resetForm();
  };

  const handleEdit = (
    item: TodoItem
  ) => {
    setEditingId(item.id);

    setForm({
      title: item.title,
      goal_score:
        item.goal_score,
      exam_date:
        item.exam_date,
      target_hours: String(
        item.target_hours
      ),
      importance: String(
        item.importance
      ),
      fatigue: String(
        item.fatigue
      ),
      memo: item.memo,
    });
  };

  const toggleDone = (
    id: string
  ) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              is_done:
                !item.is_done,
            }
          : item
      )
    );
  };

  const deleteItem = (
    id: string
  ) => {
    setItems((prev) =>
      prev.filter(
        (item) => item.id !== id
      )
    );
  };

  function syncVariableSchedule(
    todoId: string,
    title: string,
    isDone: boolean,
    shouldDelete = false
  ) {
    const schedules =
      readVariableSchedules();

    const nextSchedules =
      schedules.filter((schedule) => {
        const isLinked =
          schedule.title.includes(
            title.replace(
              /\s+(개념 정리|문제 풀이|오답 정리)$/,""
            )
          );

        if (!isLinked) {
          return true;
        }

        if (shouldDelete) {
          return false;
        }

        return true;
      }).map((schedule) => {
        const isLinked =
          schedule.title.includes(
            title.replace(
              /\s+(개념 정리|문제 풀이|오답 정리)$/,""
            )
          );

        if (!isLinked) {
          return schedule;
        }

        return {
          ...schedule,
          is_done: isDone,
          updated_at:
            new Date().toISOString(),
        };
      });

    saveVariableSchedules(
      nextSchedules
    );
  }

  return (
    <div>
      <h1
        className="text-3xl font-bold mb-2"
        style={{
          color: "var(--app-text)",
        }}
      >
        할일 관리
      </h1>

      <p
        className="mb-6"
        style={{
          color:
            "var(--app-text-muted)",
        }}
      >
        목표 점수, 시험 일정,
        예상 공부 시간을 기준으로
        관리하는 페이지입니다.
      </p>

      <div className="grid grid-cols-1 xl:grid-cols-[420px_1fr] gap-6">
        <section
          className="rounded-2xl border p-5 shadow-sm"
          style={{
            background:
              "var(--app-surface)",
            borderColor:
              "var(--app-border)",
          }}
        >
          <h2
            className="text-xl font-bold mb-4"
            style={{
              color:
                "var(--app-text)",
            }}
          >
            {editingId
              ? "할일 수정"
              : "할일 추가"}
          </h2>

          <form
            onSubmit={handleSubmit}
            className="space-y-4"
          >
            <InputLabel label="할일 이름">
              <input
                value={form.title}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    title:
                      e.target.value,
                  }))
                }
                className="form-input"
                placeholder="예: 정보처리기사 필기"
              />
            </InputLabel>

            <div className="grid grid-cols-2 gap-3">
              <InputLabel label="목표 점수">
                <input
                  value={
                    form.goal_score
                  }
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,
                      goal_score:
                        e.target
                          .value,
                    }))
                  }
                  className="form-input"
                  placeholder="예: 80점"
                />
              </InputLabel>

              <InputLabel label="시험 일정">
                <input
                  type="date"
                  value={
                    form.exam_date
                  }
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,
                      exam_date:
                        e.target
                          .value,
                    }))
                  }
                  className="form-input"
                />
              </InputLabel>
            </div>

            <InputLabel label="예상 공부 시간">
              <input
                type="number"
                min="0"
                value={
                  form.target_hours
                }
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    target_hours:
                      e.target
                        .value,
                  }))
                }
                className="form-input"
                placeholder="시간 단위"
              />
            </InputLabel>

            <div className="grid grid-cols-2 gap-3">
              <InputLabel label="중요도">
                <input
                  type="number"
                  min="0"
                  max="10"
                  value={
                    form.importance
                  }
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,
                      importance:
                        e.target
                          .value,
                    }))
                  }
                  className="form-input"
                />
              </InputLabel>

              <InputLabel label="피로도">
                <input
                  type="number"
                  min="0"
                  max="10"
                  value={
                    form.fatigue
                  }
                  onChange={(e) =>
                    setForm((p) => ({
                      ...p,
                      fatigue:
                        e.target
                          .value,
                    }))
                  }
                  className="form-input"
                />
              </InputLabel>
            </div>

            <InputLabel label="메모">
              <textarea
                value={form.memo}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    memo:
                      e.target.value,
                  }))
                }
                className="form-input min-h-24 resize-none"
              />
            </InputLabel>

            <button
              className="w-full rounded-xl py-3 font-bold"
              style={{
                background:
                  "var(--primary-button-bg)",
                color:
                  "var(--primary-button-text)",
              }}
            >
              {editingId
                ? "수정 저장"
                : "할일 추가"}
            </button>

            {editingId && (
              <button
                type="button"
                onClick={resetForm}
                className="w-full rounded-xl py-3 font-bold"
                style={{
                  background:
                    "var(--app-surface-muted)",
                  color:
                    "var(--app-text)",
                }}
              >
                취소
              </button>
            )}
          </form>
        </section>

        <section
          className="rounded-2xl border p-5 shadow-sm"
          style={{
            background:
              "var(--app-surface)",
            borderColor:
              "var(--app-border)",
          }}
        >
          <h2
            className="text-xl font-bold mb-4"
            style={{
              color:
                "var(--app-text)",
            }}
          >
            등록된 할일
          </h2>

          <div className="space-y-3">
            {visibleItems.length ===
            0 ? (
              <EmptyText>
                등록된 할일이
                없습니다.
              </EmptyText>
            ) : (
              visibleItems.map(
                (item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border p-4"
                    style={{
                      background:
                        "var(--app-bg)",
                      borderColor:
                        "var(--app-border)",
                    }}
                  >
                    <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <strong
                            style={{
                              color:
                                "var(--app-text)",
                            }}
                          >
                            {
                              item.title
                            }
                          </strong>

                          <span
                            className="px-2 py-1 rounded-full text-xs font-bold"
                            style={{
                              background:
                                item.is_done
                                  ? "var(--card-green-bg)"
                                  : "var(--card-yellow-bg)",

                              color:
                                item.is_done
                                  ? "var(--card-green-text)"
                                  : "var(--card-yellow-text)",
                            }}
                          >
                            {item.is_done
                              ? "완료"
                              : "진행 중"}
                          </span>
                        </div>

                        <div
                          className="text-sm mt-2"
                          style={{
                            color:
                              "var(--app-text-muted)",
                          }}
                        >
                          목표{" "}
                          {item.goal_score ||
                            "-"}{" "}
                          · 시험일{" "}
                          {
                            item.exam_date
                          }{" "}
                          ·{" "}
                          {
                            item.target_hours
                          }
                          시간
                        </div>

                        <div
                          className="text-sm mt-1"
                          style={{
                            color:
                              "var(--app-text-muted)",
                          }}
                        >
                          중요도{" "}
                          {
                            item.importance
                          }{" "}
                          · 피로도{" "}
                          {
                            item.fatigue
                          }{" "}
                          (
                          {getFatigueLabel(
                            item.fatigue
                          )}
                          )
                        </div>

                        {item.memo && (
                          <p
                            className="text-sm mt-2"
                            style={{
                              color:
                                "var(--app-text)",
                            }}
                          >
                            {
                              item.memo
                            }
                          </p>
                        )}
                      </div>

                      <div className="flex gap-2 flex-wrap">
                        <SmallButton
                          onClick={() =>
                            toggleDone(
                              item.id
                            )
                          }
                          type="green"
                        >
                          완료 전환
                        </SmallButton>

                        <SmallButton
                          onClick={() =>
                            handleEdit(
                              item
                            )
                          }
                          type="blue"
                        >
                          수정
                        </SmallButton>

                        <SmallButton
                          onClick={() =>
                            deleteItem(
                              item.id
                            )
                          }
                          type="red"
                        >
                          삭제
                        </SmallButton>
                      </div>
                    </div>
                  </div>
                )
              )
            )}
          </div>
        </section>
      </div>

      <style jsx global>{`
        .form-input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid
            var(--app-border);
          background: var(--app-bg);
          color: var(--app-text);
          padding: 0.75rem;
          outline: none;
        }
      `}</style>
    </div>
  );
}

function InputLabel({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  function syncVariableSchedule(
    todoId: string,
    title: string,
    isDone: boolean,
    shouldDelete = false
  ) {
    const schedules =
      readVariableSchedules();

    const nextSchedules =
      schedules.filter((schedule) => {
        const isLinked =
          schedule.title.includes(
            title.replace(
              /\s+(개념 정리|문제 풀이|오답 정리)$/,""
            )
          );

        if (!isLinked) {
          return true;
        }

        if (shouldDelete) {
          return false;
        }

        return true;
      }).map((schedule) => {
        const isLinked =
          schedule.title.includes(
            title.replace(
              /\s+(개념 정리|문제 풀이|오답 정리)$/,""
            )
          );

        if (!isLinked) {
          return schedule;
        }

        return {
          ...schedule,
          is_done: isDone,
          updated_at:
            new Date().toISOString(),
        };
      });

    saveVariableSchedules(
      nextSchedules
    );
  }

  return (
    <div>
      <div
        className="text-sm font-bold mb-2"
        style={{
          color: "var(--app-text)",
        }}
      >
        {label}
      </div>

      {children}
    </div>
  );
}

function SmallButton({
  children,
  onClick,
  type,
}: {
  children: React.ReactNode;
  onClick: () => void;
  type:
    | "blue"
    | "green"
    | "red";
}) {
  const style =
    type === "blue"
      ? {
          background:
            "var(--card-blue-bg)",
          color:
            "var(--card-blue-text)",
        }
      : type === "green"
      ? {
          background:
            "var(--card-green-bg)",
          color:
            "var(--card-green-text)",
        }
      : {
          background:
            "var(--card-red-bg)",
          color:
            "var(--card-red-text)",
        };

  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg px-3 py-2 text-sm font-bold"
      style={style}
    >
      {children}
    </button>
  );
}

function EmptyText({
  children,
}: {
  children: React.ReactNode;
}) {
  function syncVariableSchedule(
    todoId: string,
    title: string,
    isDone: boolean,
    shouldDelete = false
  ) {
    const schedules =
      readVariableSchedules();

    const nextSchedules =
      schedules.filter((schedule) => {
        const isLinked =
          schedule.title.includes(
            title.replace(
              /\s+(개념 정리|문제 풀이|오답 정리)$/,""
            )
          );

        if (!isLinked) {
          return true;
        }

        if (shouldDelete) {
          return false;
        }

        return true;
      }).map((schedule) => {
        const isLinked =
          schedule.title.includes(
            title.replace(
              /\s+(개념 정리|문제 풀이|오답 정리)$/,""
            )
          );

        if (!isLinked) {
          return schedule;
        }

        return {
          ...schedule,
          is_done: isDone,
          updated_at:
            new Date().toISOString(),
        };
      });

    saveVariableSchedules(
      nextSchedules
    );
  }

  return (
    <div
      className="rounded-xl border p-4 text-center"
      style={{
        background:
          "var(--app-bg)",
        borderColor:
          "var(--app-border)",
        color:
          "var(--app-text-muted)",
      }}
    >
      {children}
    </div>
  );
}