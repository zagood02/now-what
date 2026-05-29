"use client";

import {
  useMemo,
  useState,
} from "react";

import {
  AiQuestion,
  TodoItem,
  createId,
  readAiDrafts,
  readCurrentUser,
  readTodos,
  saveAiDrafts,
  saveTodos,
} from "@/lib/thirdStageStorage";

import {
  type VariableSchedule,
  getNextColorKey,
  getVariableSchedules,
  saveVariableSchedules,
} from "@/lib/mockSchedules";

const defaultQuestions = [
  "목표 이름은 무엇인가요?",
  "시험일이나 목표 완료일은 언제인가요?",
  "목표 점수나 원하는 성과는 무엇인가요?",
  "하루에 확보 가능한 시간은 어느 정도인가요?",
  "현재 진도는 어느 정도인가요?",
  "평일과 주말 공부 가능 시간이 다른가요?",
  "피로도가 높은 활동인가요?",
];

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function toDateInputValue(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function addDays(base: Date, days: number) {
  const next = new Date(base);
  next.setDate(next.getDate() + days);
  return next;
}

function createDateTime(dateValue: string, timeValue: string) {
  return `${dateValue}T${timeValue}:00+09:00`;
}

function parsePlanDeadline(text: string) {
  const currentYear =
    new Date().getFullYear();

  const koreanDate =
    text.match(
      /(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일/
    );

  if (koreanDate) {
    const [, year, month, day] =
      koreanDate;

    return `${year}-${pad(Number(month))}-${pad(Number(day))}`;
  }

  const koreanMonthDay =
    text.match(
      /(\d{1,2})\s*월\s*(\d{1,2})\s*일/
    );

  if (koreanMonthDay) {
    const [, month, day] =
      koreanMonthDay;

    return `${currentYear}-${pad(Number(month))}-${pad(Number(day))}`;
  }

  const koreanEarlyMonth =
    text.match(
      /(\d{1,2})\s*월\s*초/
    );

  if (koreanEarlyMonth) {
    const [, month] =
      koreanEarlyMonth;

    return `${currentYear}-${pad(Number(month))}-05`;
  }

  const koreanMidMonth =
    text.match(
      /(\d{1,2})\s*월\s*중순/
    );

  if (koreanMidMonth) {
    const [, month] =
      koreanMidMonth;

    return `${currentYear}-${pad(Number(month))}-15`;
  }

  const koreanLateMonth =
    text.match(
      /(\d{1,2})\s*월\s*(말|말쯤|말까지)/
    );

  if (koreanLateMonth) {
    const [, month] =
      koreanLateMonth;

    const lastDay =
      new Date(
        currentYear,
        Number(month),
        0
      ).getDate();

    return `${currentYear}-${pad(Number(month))}-${pad(lastDay)}`;
  }

  const dashDate =
    text.match(
      /(20\d{2})[-./](\d{1,2})[-./](\d{1,2})/
    );

  if (dashDate) {
    const [, year, month, day] =
      dashDate;

    return `${year}-${pad(Number(month))}-${pad(Number(day))}`;
  }

  return "";
}

function parseAvoidDays(text: string) {
  const avoidWords = [
    "피해",
    "빼",
    "제외",
    "하지 말",
  ];

  const avoidIndex =
    avoidWords
      .map((word) => text.indexOf(word))
      .filter((index) => index >= 0)
      .sort((a, b) => a - b)[0] ?? -1;

  if (avoidIndex < 0) return [];

  const start =
    Math.max(0, avoidIndex - 30);

  const avoidSection =
    text.slice(start, avoidIndex + 10);

  const days: number[] = [];

  if (avoidSection.includes("일")) days.push(0);
  if (avoidSection.includes("월")) days.push(1);
  if (avoidSection.includes("화")) days.push(2);
  if (avoidSection.includes("수")) days.push(3);
  if (avoidSection.includes("목")) days.push(4);
  if (avoidSection.includes("금")) days.push(5);
  if (avoidSection.includes("토")) days.push(6);

  return Array.from(new Set(days));
}

function findDistributedPlanSlots(deadlineText: string, combinedText: string) {
  const today = new Date();
  const deadline =
    deadlineText
      ? new Date(`${deadlineText}T00:00:00+09:00`)
      : addDays(today, 21);

  const safeDeadline =
    Number.isNaN(deadline.getTime()) ||
    deadline.getTime() <= today.getTime()
      ? addDays(today, 21)
      : deadline;

  const totalDays =
    Math.max(
      3,
      Math.ceil(
        (safeDeadline.getTime() - today.getTime()) /
          (1000 * 60 * 60 * 24)
      )
    );

  const avoidDays =
    parseAvoidDays(combinedText);

  const ratios =
    totalDays >= 60
      ? [0.25, 0.55, 0.85]
      : totalDays >= 21
        ? [0.2, 0.5, 0.8]
        : [0.25, 0.5, 0.75];

  const usedDates =
    new Set<string>();

  const result: {
    date: string;
    start: string;
    end: string;
  }[] = [];

  ratios.forEach((ratio, index) => {
    let offset =
      Math.max(
        1,
        Math.floor(totalDays * ratio)
      );

    let candidate =
      addDays(today, offset);

    let guard = 0;

    while (guard < 60) {
      if (candidate.getTime() > safeDeadline.getTime()) {
        candidate =
          addDays(safeDeadline, -guard);
      }

      const dateValue =
        toDateInputValue(candidate);

      const isAvoidedDay =
        avoidDays.includes(
          candidate.getDay()
        );

      if (
        !isAvoidedDay &&
        !usedDates.has(dateValue)
      ) {
        usedDates.add(dateValue);

        result.push({
          date: dateValue,
          start: "19:00",
          end:
            index === 1
              ? "20:30"
              : index === 2
                ? "19:45"
                : "20:00",
        });

        return;
      }

      candidate =
        addDays(candidate, 1);

      guard += 1;
    }
  });

  let fallbackCursor =
    addDays(today, 1);

  while (result.length < 3) {
    const dateValue =
      toDateInputValue(fallbackCursor);

    if (
      !avoidDays.includes(fallbackCursor.getDay()) &&
      !usedDates.has(dateValue)
    ) {
      usedDates.add(dateValue);

      result.push({
        date: dateValue,
        start: "19:00",
        end: "20:00",
      });
    }

    fallbackCursor =
      addDays(fallbackCursor, 1);
  }

  return result;
}

export default function AiPlanPage() {
  const currentUser =
    readCurrentUser();

  const userId =
    currentUser?.id ?? "guest";

  const [prompt, setPrompt] =
    useState("");

  const [questions, setQuestions] =
    useState<AiQuestion[]>([]);

  const [
    generatedTodos,
    setGeneratedTodos,
  ] = useState<TodoItem[]>([]);

  const [
    generatedVariables,
    setGeneratedVariables,
  ] = useState<
    VariableSchedule[]
  >([]);

  const [message, setMessage] =
    useState("");

  const answeredCount =
    useMemo(
      () =>
        questions.filter((item) =>
          item.answer.trim()
        ).length,
      [questions]
    );

  const handleCreateQuestions =
    () => {
      const lower =
        prompt.toLowerCase();

      const extra =
        lower.includes("시험") ||
        lower.includes("기사") ||
        lower.includes(
          "자격증"
        )
          ? [
              "과목은 몇 개인가요?",
              "약한 과목은 무엇인가요?",
              "기출 문제 풀이가 필요한가요?",
            ]
          : [
              "목표를 달성하기 위해 필요한 활동은 무엇인가요?",
              "반드시 피해야 하는 시간대가 있나요?",
            ];

      setQuestions(
        [
          ...defaultQuestions,
          ...extra,
        ].map((question) => ({
          id: createId(
            "question"
          ),
          question,
          answer: "",
        }))
      );

      setGeneratedTodos([]);
      setGeneratedVariables(
        []
      );

      setMessage(
        "질문 리스트를 만들었습니다."
      );
    };

  const handleAnswerChange = (
    id: string,
    answer: string
  ) => {
    setQuestions((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              answer,
            }
          : item
      )
    );
  };

  const findAnswer = (
    keyword: string
  ) => {
    return (
      questions.find((item) =>
        item.question.includes(
          keyword
        )
      )?.answer.trim() ?? ""
    );
  };

  const handleGeneratePlan =
    () => {
      const now =
        new Date().toISOString();

      const title =
        findAnswer(
          "목표 이름"
        ) ||
        prompt ||
        "새 목표";

      const examDate =
        findAnswer(
          "시험일"
        ) || "";

      const goalScore =
        findAnswer(
          "목표 점수"
        ) ||
        findAnswer("성과") ||
        "";

      const dailyTimeText =
        findAnswer(
          "하루에 확보"
        );

      const currentProgress =
        findAnswer(
          "현재 진도"
        );

      const highFatigue =
        findAnswer(
          "피로도"
        ).includes("높") ||
        prompt.includes(
          "빡"
        ) ||
        prompt.includes(
          "힘"
        );

      const baseFatigue =
        highFatigue ? 8 : 5;

      const targetHours =
        Number(
          dailyTimeText.replace(
            /[^0-9]/g,
            ""
          )
        ) || 30;

      const todo: TodoItem = {
        id: createId("todo"),

        user_id: userId,

        title,

        goal_score:
          goalScore,

        exam_date:
          examDate,

        target_hours:
          targetHours,

        importance: 8,

        fatigue:
          baseFatigue,

        memo: `AI 질문 기반 생성. 현재 진도: ${
          currentProgress ||
          "미입력"
        }`,

        is_done: false,

        created_at: now,

        updated_at: now,
      };

      const combinedText = [
        prompt,
        ...questions.map(
          (item) =>
            `${item.question} ${item.answer}`
        ),
      ].join(" ");

      const parsedDeadline =
        parsePlanDeadline(
          combinedText
        );

      const parsedExamDate =
        parsePlanDeadline(
          examDate
        );

      const finalExamDate =
        parsedExamDate ||
        parsedDeadline;

      const slots =
        findDistributedPlanSlots(
          finalExamDate,
          combinedText
        );

      const existingVariables =
        getVariableSchedules();

      const nextColor =
        getNextColorKey(
          existingVariables
        );

      todo.exam_date =
        finalExamDate;

      const variables: VariableSchedule[] =
        [
          {
            id: createId(
              "variable"
            ),

            user_id: userId,

            title: `${title} 개념 정리`,

            estimated_time: 60,

            is_done: false,

            status: "pending",

            level:
              baseFatigue,

            color_key:
              nextColor,

            deadline:
              "2099-12-31T23:59:00+09:00",

            scheduled_start:
              createDateTime(
                slots[0].date,
                slots[0].start
              ),

            scheduled_end:
              createDateTime(
                slots[0].date,
                slots[0].end
              ),

            fail_reason: null,

            fail_reason_text: null,

            priority: null,

            created_at:
              now,

            updated_at:
              now,
          },

          {
            id: createId(
              "variable"
            ),

            user_id: userId,

            title: `${title} 문제 풀이`,

            estimated_time: 90,

            is_done: false,

            status: "pending",

            level:
              Math.min(
                baseFatigue +
                  1,
                10
              ),

            color_key:
              nextColor + 1,

            deadline:
              "2099-12-31T23:59:00+09:00",

            scheduled_start:
              createDateTime(
                slots[1].date,
                slots[1].start
              ),

            scheduled_end:
              createDateTime(
                slots[1].date,
                slots[1].end
              ),

            fail_reason: null,

            fail_reason_text: null,

            priority: null,

            created_at:
              now,

            updated_at:
              now,
          },

          {
            id: createId(
              "variable"
            ),

            user_id: userId,

            title: `${title} 오답 정리`,

            estimated_time: 45,

            is_done: false,

            status: "pending",

            level:
              Math.max(
                baseFatigue -
                  1,
                0
              ),

            color_key:
              nextColor + 2,

            deadline:
              "2099-12-31T23:59:00+09:00",

            scheduled_start:
              createDateTime(
                slots[2].date,
                slots[2].start
              ),

            scheduled_end:
              createDateTime(
                slots[2].date,
                slots[2].end
              ),

            fail_reason: null,

            fail_reason_text: null,

            priority: null,

            created_at:
              now,

            updated_at:
              now,
          },
        ];

      setGeneratedTodos([
        todo,
      ]);

      setGeneratedVariables(
        variables
      );

      setMessage(
        "계획 초안을 만들었습니다."
      );
    };

  const handleSavePlan =
    () => {
      if (
        generatedTodos.length ===
          0 &&
        generatedVariables.length ===
          0
      ) {
        return;
      }

      const existingTodos =
        readTodos();

      const nextTodos =
        [...existingTodos];

      generatedTodos.forEach(
        (item) => {
          if (
            !nextTodos.some(
              (saved) =>
                saved.id === item.id
            )
          ) {
            nextTodos.push(item);
          }
        }
      );

      saveTodos(nextTodos);

      const existingVariables =
        getVariableSchedules();

      const nextVariables =
        [...existingVariables];

      generatedVariables.forEach(
        (item) => {
          if (
            !nextVariables.some(
              (saved) =>
                saved.id === item.id
            )
          ) {
            nextVariables.push(item);
          }
        }
      );

      saveVariableSchedules(
        nextVariables
      );

      saveAiDrafts([
        ...readAiDrafts(),
        {
          id: createId(
            "draft"
          ),

          user_id: userId,

          prompt,

          questions,

          todos:
            generatedTodos,

          variableSchedules:
            generatedVariables.map(
              (item) => ({
                id: item.id,
                user_id: item.user_id,
                title: item.title,
                estimated_time:
                  item.estimated_time,
                fatigue:
                  item.level,
                color_key:
                  item.color_key,
                memo:
                  "AI 생성 변동 일정",
                is_done:
                  item.is_done,
                created_at:
                  item.created_at ??
                  new Date().toISOString(),
                updated_at:
                  item.updated_at ??
                  new Date().toISOString(),
              })
            ),

          created_at:
            new Date().toISOString(),
        },
      ]);

      setMessage(
        "할일과 변동 스케줄에 저장했습니다."
      );
    };

  return (
    <div>
      <h1
        className="text-3xl font-bold mb-2"
        style={{
          color:
            "var(--app-text)",
        }}
      >
        AI 계획 생성
      </h1>

      <p
        className="mb-6"
        style={{
          color:
            "var(--app-text-muted)",
        }}
      >
        프롬프트를 입력하면
        질문 리스트를 만들고,
        답변을 바탕으로
        할일과 변동 스케줄을
        생성합니다.
      </p>

      <section
        className="rounded-2xl border p-5 shadow-sm mb-6"
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
          1. 프롬프트 입력
        </h2>

        <textarea
          value={prompt}
          onChange={(e) =>
            setPrompt(
              e.target.value
            )
          }
          className="form-input min-h-32 resize-none"
          placeholder="예: 정보처리기사 시험 준비 계획 짜줘"
        />

        <button
          type="button"
          onClick={
            handleCreateQuestions
          }
          className="mt-4 rounded-xl px-4 py-3 font-bold"
          style={{
            background:
              "var(--primary-button-bg)",
            color:
              "var(--primary-button-text)",
          }}
        >
          질문 리스트 만들기
        </button>
      </section>

      {questions.length >
        0 && (
        <section
          className="rounded-2xl border p-5 shadow-sm mb-6"
          style={{
            background:
              "var(--app-surface)",
            borderColor:
              "var(--app-border)",
          }}
        >
          <h2
            className="text-xl font-bold mb-2"
            style={{
              color:
                "var(--app-text)",
            }}
          >
            2. 질문 답변
          </h2>

          <p
            className="mb-4"
            style={{
              color:
                "var(--app-text-muted)",
            }}
          >
            답변{" "}
            {
              answeredCount
            }
            /
            {
              questions.length
            }
          </p>

          <div className="space-y-3">
            {questions.map(
              (
                item,
                index
              ) => (
                <label
                  key={
                    item.id
                  }
                  className="block"
                >
                  <div
                    className="font-bold mb-2"
                    style={{
                      color:
                        "var(--app-text)",
                    }}
                  >
                    {index +
                      1}
                    .{" "}
                    {
                      item.question
                    }
                  </div>

                  <input
                    value={
                      item.answer
                    }
                    onChange={(
                      e
                    ) =>
                      handleAnswerChange(
                        item.id,
                        e.target
                          .value
                      )
                    }
                    className="form-input"
                  />
                </label>
              )
            )}
          </div>

          <button
            type="button"
            onClick={
              handleGeneratePlan
            }
            className="mt-4 rounded-xl px-4 py-3 font-bold"
            style={{
              background:
                "var(--primary-button-bg)",
              color:
                "var(--primary-button-text)",
            }}
          >
            계획 초안 생성
          </button>
        </section>
      )}

      {(generatedTodos.length >
        0 ||
        generatedVariables.length >
          0) && (
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
            3. 생성된 계획
          </h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <h3
                className="font-bold mb-3"
                style={{
                  color:
                    "var(--app-text)",
                }}
              >
                할일
              </h3>

              {generatedTodos.map(
                (todo) => (
                  <div
                    key={
                      todo.id
                    }
                    className="rounded-xl border p-4 mb-3"
                    style={{
                      background:
                        "var(--app-bg)",
                      borderColor:
                        "var(--app-border)",
                    }}
                  >
                    <strong
                      style={{
                        color:
                          "var(--app-text)",
                      }}
                    >
                      {
                        todo.title
                      }
                    </strong>

                    <div
                      className="text-sm mt-2"
                      style={{
                        color:
                          "var(--app-text-muted)",
                      }}
                    >
                      목표{" "}
                      {todo.goal_score ||
                        "-"}{" "}
                      · 시험일{" "}
                      {todo.exam_date ||
                        "-"}{" "}
                      ·{" "}
                      {
                        todo.target_hours
                      }
                      시간
                    </div>
                  </div>
                )
              )}
            </div>

            <div>
              <h3
                className="font-bold mb-3"
                style={{
                  color:
                    "var(--app-text)",
                }}
              >
                변동 스케줄
              </h3>

              {generatedVariables.map(
                (
                  item
                ) => (
                  <div
                    key={
                      item.id
                    }
                    className="rounded-xl border p-4 mb-3"
                    style={{
                      background:
                        "var(--app-bg)",
                      borderColor:
                        "var(--app-border)",
                    }}
                  >
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

                    <div
                      className="text-sm mt-2"
                      style={{
                        color:
                          "var(--app-text-muted)",
                      }}
                    >
                      {item.scheduled_start
                        ?.slice(0, 10) ||
                        "-"}{" "}
                      · {
                        item.estimated_time
                      }
                      분 · 피로도{" "}
                      {
                        item.level
                      }
                    </div>
                  </div>
                )
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={
              handleSavePlan
            }
            className="mt-4 rounded-xl px-4 py-3 font-bold"
            style={{
              background:
                "var(--primary-button-bg)",
              color:
                "var(--primary-button-text)",
            }}
          >
            할일/스케줄 저장
          </button>
        </section>
      )}

      {message && (
        <p
          className="mt-4 font-bold"
          style={{
            color:
              "var(--app-text)",
          }}
        >
          {message}
        </p>
      )}

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