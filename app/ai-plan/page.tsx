"use client";

import {
  useMemo,
  useState,
} from "react";

import {
  AiQuestion,
  TodoItem,
  VariableSchedule,
  createId,
  readAiDrafts,
  readCurrentUser,
  readTodos,
  readVariableSchedules,
  saveAiDrafts,
  saveTodos,
  saveVariableSchedules,
} from "@/lib/thirdStageStorage";

const defaultQuestions = [
  "목표 이름은 무엇인가요?",
  "시험일이나 목표 완료일은 언제인가요?",
  "목표 점수나 원하는 성과는 무엇인가요?",
  "하루에 확보 가능한 시간은 어느 정도인가요?",
  "현재 진도는 어느 정도인가요?",
  "평일과 주말 공부 가능 시간이 다른가요?",
  "피로도가 높은 활동인가요?",
];

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

      const variables: VariableSchedule[] =
        [
          {
            id: createId(
              "variable"
            ),

            user_id: userId,

            title: `${title} 개념 정리`,

            estimated_time: 60,

            fatigue:
              baseFatigue,

            color_key: 0,

            memo:
              "AI 생성 변동 일정",

            is_done: false,

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

            fatigue:
              Math.min(
                baseFatigue +
                  1,
                10
              ),

            color_key: 1,

            memo:
              "AI 생성 변동 일정",

            is_done: false,

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

            fatigue:
              Math.max(
                baseFatigue -
                  1,
                0
              ),

            color_key: 2,

            memo:
              "AI 생성 변동 일정",

            is_done: false,

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

      saveTodos([
        ...readTodos(),
        ...generatedTodos,
      ]);

      saveVariableSchedules([
        ...readVariableSchedules(),
        ...generatedVariables,
      ]);

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
            generatedVariables,

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
                      {
                        item.estimated_time
                      }
                      분 · 피로도{" "}
                      {
                        item.fatigue
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