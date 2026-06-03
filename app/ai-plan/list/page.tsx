"use client";

import React, { useEffect, useState } from "react";
import { goalAPI, handleApiError, plannerAPI, AIPlanItem, GoalDetail } from "@/lib/api";
import HelpButton from "@/components/HelpButton";

const formatKstDate = (date: Date) => date.toLocaleString("sv", { timeZone: "Asia/Seoul" }).split(" ")[0];
const toKstEndOfDay = (dateString: string) => `${dateString.slice(0, 10)}T23:59:59`;

export default function AiPlanListPage() {
  const [plans, setPlans] = useState<GoalDetail[]>([]);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [itemUpdating, setItemUpdating] = useState<Record<number, boolean>>({});

  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      const response = await goalAPI.list();
      setPlans(response.data);
    } catch (err) {
      setErrorMessage(handleApiError(err));
    }
  };

  const fetchPlanDetail = async (goal: GoalDetail) => {
    if (goal.plans && goal.plans.length > 0) return;
    try {
      const resp = await goalAPI.get(goal.id);
      setPlans(prev => prev.map(p => p.id === goal.id ? resp.data : p));
    } catch (err) {
      setErrorMessage(handleApiError(err));
    }
  };

  const handleDeletePlan = async (goalId: number) => {
    if (!confirm("이 목표와 관련된 모든 계획을 삭제하시겠습니까?")) return;
    try {
      await goalAPI.delete(goalId);
      setMessage("계획 묶음이 삭제되었습니다.");
      fetchPlans();
      setTimeout(() => setMessage(""), 3000);
    } catch (err) {
      setErrorMessage(handleApiError(err));
    }
  };

  const updateGoalItem = (goalId: number, updatedItem: AIPlanItem) => {
    setPlans(prev => prev.map(goal => {
      if (goal.id !== goalId) return goal;
      return {
        ...goal,
        plans: goal.plans?.map(plan => ({
          ...plan,
          items: plan.items.map(item => item.id === updatedItem.id ? updatedItem : item),
        })) ?? [],
      };
    }));
  };

  const removeGoalItem = (goalId: number, itemId: number) => {
    setPlans(prev => prev.map(goal => {
      if (goal.id !== goalId) return goal;
      return {
        ...goal,
        plans: goal.plans?.map(plan => ({
          ...plan,
          items: plan.items.filter(item => item.id !== itemId),
        })) ?? [],
      };
    }));
  };

  const handleItemAction = async (
    goalId: number,
    itemId: number,
    action: "unschedule" | "skip" | "complete" | "delete"
  ) => {
    setItemUpdating(prev => ({ ...prev, [itemId]: true }));
    setErrorMessage(null);

    try {
      if (action === "delete") {
        await plannerAPI.deletePlanItem(itemId);
        removeGoalItem(goalId, itemId);
        setMessage("상세 계획이 삭제되었습니다.");
      } else if (action === "unschedule") {
        const resp = await plannerAPI.unschedulePlanItem(itemId);
        updateGoalItem(goalId, resp.data);
        setMessage("일정이 해제되었습니다.");
      } else if (action === "skip") {
        const resp = await plannerAPI.skipPlanItem(itemId);
        updateGoalItem(goalId, resp.data);
        setMessage("상세 계획이 건너뛰기로 표시되었습니다.");
      } else if (action === "complete") {
        const resp = await plannerAPI.completePlanItem(itemId);
        updateGoalItem(goalId, resp.data);
        setMessage("상세 계획이 완료 처리되었습니다.");
      }
      setTimeout(() => setMessage(""), 3000);
    } catch (err) {
      setErrorMessage(handleApiError(err));
    } finally {
      setItemUpdating(prev => ({ ...prev, [itemId]: false }));
    }
  };

  const getAllocateRangeEnd = (goal: GoalDetail) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    if (goal.target_date) {
      try {
        const target = new Date(goal.target_date);
        target.setHours(0, 0, 0, 0);
        
        // 마감일이 오늘보다 뒤인 경우, 그 날의 끝(23:59:59)을 범위 끝으로 설정
        if (target > today) {
          const endOfDay = new Date(target);
          endOfDay.setHours(23, 59, 59, 999);
          return endOfDay.toISOString();
        }
      } catch (e) {
        console.warn("target_date 파싱 실패:", goal.target_date, e);
      }
    }
    
    // 기본값: 오늘부터 7일 후의 끝
    const fallback = new Date(today);
    fallback.setDate(fallback.getDate() + 7);
    fallback.setHours(23, 59, 59, 999);
    return fallback.toISOString();
  };

  const handleReallocate = async (goal: GoalDetail) => {
    setErrorMessage(null);
    try {
      const rangeStart = `${formatKstDate(new Date())}T00:00:00`;

      let rangeEnd = `${formatKstDate(new Date(new Date().setDate(new Date().getDate() + 7)))}T23:59:59`;
      if (goal.target_date) {
        try {
          const targetDate = new Date(goal.target_date);
          const targetString = goal.target_date.toString().slice(0, 10);
          if (targetDate.getTime() > new Date().setHours(0, 0, 0, 0)) {
            rangeEnd = toKstEndOfDay(targetString);
          }
        } catch (e) {
          console.warn("마감일 파싱 실패:", goal.target_date);
        }
      }

      const payload = {
        range_start: rangeStart,
        range_end: rangeEnd,
        clear_existing: true,
      };
      
      console.log("배치 요청:", {
        시작: rangeStart.toString(),
        끝: rangeEnd.toString(),
        페이로드: payload,
      });
      
      await plannerAPI.allocate(payload);
      await fetchPlanDetail(goal);
      setMessage("전체 재배치가 완료되었습니다.");
      setTimeout(() => setMessage(""), 3000);
    } catch (err) {
      console.error("배치 에러:", err);
      setErrorMessage(handleApiError(err));
    }
  };

  const formatDateTime = (value: string) => new Date(value).toLocaleString();

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: "var(--app-text)" }}>AI 계획 관리</h1>
          <p className="text-sm mt-2" style={{ color: "var(--app-text-muted)" }}>
            생성된 목표별 계획을 확장하면 상세 스케줄 항목을 관리할 수 있습니다.
          </p>
        </div>
        <HelpButton title="AI 계획 관리 도움말">
          <p className="mb-2">생성된 목표별 계획을 확장하여 상세 스케줄 항목을 관리할 수 있습니다.</p>
          <ul className="list-disc list-inside space-y-1 text-xs">
            <li><strong>전체 삭제</strong>: 목표와 관련된 모든 계획 삭제</li>
            <li><strong>전체 재배치</strong>: 전체 계획 재할당 및 순서 재조정</li>
            <li><strong>일정 해제</strong>: 해당 항목의 일정만 제거</li>
            <li><strong>건너뛰기</strong>: 이번 계획에서 제외</li>
            <li><strong>완료</strong>: 완료 상태로 표시</li>
            <li><strong>삭제</strong>: 항목 완전히 제거</li>
          </ul>
        </HelpButton>
      </div>

      {errorMessage && <p className="mb-4 text-red-500 font-bold">{errorMessage}</p>}
      {message && <p className="mb-4 text-green-600 font-bold">{message}</p>}

      <div className="space-y-4">
        {plans.map((goal) => {
          const planItems = (goal.plans?.flatMap(plan => plan.items) ?? [])
            .slice()
            .sort((a, b) => {
              if (!a.scheduled_start && !b.scheduled_start) return 0;
              if (!a.scheduled_start) return 1;
              if (!b.scheduled_start) return -1;
              return new Date(a.scheduled_start).getTime() - new Date(b.scheduled_start).getTime();
            });
          return (
            <div key={goal.id} className="rounded-2xl border p-6 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
              <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-start">
                <div className="cursor-pointer" onClick={() => { setExpandedId(expandedId === goal.id ? null : goal.id); fetchPlanDetail(goal); }}>
                  <h2 className="text-xl font-bold" style={{ color: "var(--app-text)" }}>{goal.title}</h2>
                  <p className="text-sm mt-1" style={{ color: "var(--app-text-muted)" }}>카테고리: {goal.category} | 목표일: {goal.target_date || "미설정"}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); handleDeletePlan(goal.id); }}
                    className="bg-red-600 text-white px-4 py-2 rounded-xl text-sm font-bold"
                  >
                    전체 삭제
                  </button>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); handleReallocate(goal); }}
                    className="bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-bold hover:bg-blue-500"
                  >
                    전체 재배치
                  </button>
                </div>
              </div>

              {expandedId === goal.id && (
                <div className="mt-4 pt-4 border-t space-y-3" style={{ borderColor: "var(--app-border)" }}>
                  <h4 className="font-bold mb-2" style={{ color: "var(--app-text)" }}>상세 스케줄:</h4>

                  {planItems.length > 0 ? planItems.map((item) => (
                    <div key={item.id} className="rounded-2xl border p-4" style={{ borderColor: "var(--app-border)", background: "var(--app-surface-muted)" }}>
                      <div className="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-start">
                        <div>
                          <div className="font-semibold" style={{ color: "var(--app-text)" }}>{item.title}</div>
                          <div className="text-sm" style={{ color: "var(--app-text-muted)" }}>
                            {item.status} · {Math.round(item.estimated_minutes)}분
                          </div>
                          {item.scheduled_start && item.scheduled_end && (
                            <div className="text-xs mt-1" style={{ color: "var(--app-text-muted)" }}>
                              {formatDateTime(item.scheduled_start)} ~ {formatDateTime(item.scheduled_end)}
                            </div>
                          )}
                        </div>

                        <div className="flex flex-wrap gap-2 mt-3 sm:mt-0">
                          <button
                            type="button"
                            disabled={!item.scheduled_start || item.status === "skipped" || item.status === "completed" || itemUpdating[item.id]}
                            onClick={(e) => { e.stopPropagation(); handleItemAction(goal.id, item.id, "unschedule"); }}
                            className="px-3 py-2 rounded-xl text-sm font-bold border border-transparent bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:opacity-60"
                          >
                            {item.scheduled_start && item.status !== "skipped" && item.status !== "completed" ? "일정 해제" : item.status === "skipped" ? "일정 없음" : item.status === "completed" ? "완료됨" : "일정 없음"}
                          </button>

                          <button
                            type="button"
                            disabled={item.status === "skipped" || item.status === "completed" || itemUpdating[item.id]}
                            onClick={(e) => { e.stopPropagation(); handleItemAction(goal.id, item.id, "skip"); }}
                            className="px-3 py-2 rounded-xl text-sm font-bold bg-yellow-400 text-slate-900 hover:bg-yellow-300 disabled:opacity-60"
                          >
                            {item.status === "skipped" ? "건너뛰기됨" : "건너뛰기"}
                          </button>

                          {item.status !== "completed" ? (
                            <button
                              type="button"
                              disabled={itemUpdating[item.id]}
                              onClick={(e) => { e.stopPropagation(); handleItemAction(goal.id, item.id, "complete"); }}
                              className="px-3 py-2 rounded-xl text-sm font-bold bg-green-600 text-white hover:bg-green-500 disabled:opacity-60"
                            >
                              완료
                            </button>
                          ) : (
                            <button
                              type="button"
                              disabled
                              className="px-3 py-2 rounded-xl text-sm font-bold bg-green-600 text-white opacity-60"
                            >
                              완료됨
                            </button>
                          )}

                          <button
                            type="button"
                            disabled={itemUpdating[item.id]}
                            onClick={(e) => { e.stopPropagation(); handleItemAction(goal.id, item.id, "delete"); }}
                            className="px-3 py-2 rounded-xl text-sm font-bold bg-red-600 text-white hover:bg-red-500 disabled:opacity-60"
                          >
                            삭제
                          </button>
                        </div>
                      </div>
                    </div>
                  )) : (
                    <p className="text-sm" style={{ color: "var(--app-text-muted)" }}>생성된 세부 계획이 없습니다.</p>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {plans.length === 0 && <p style={{ color: "var(--app-text-muted)" }}>생성된 계획이 없습니다.</p>}
      </div>
    </div>
  );
}
