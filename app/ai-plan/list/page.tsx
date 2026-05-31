"use client";

import React, { useEffect, useState } from "react";
import { goalAPI, handleApiError } from "@/lib/api";

export default function AiPlanListPage() {
  const [plans, setPlans] = useState<any[]>([]);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  const fetchPlanDetail = async (goal: any) => {
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

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6" style={{ color: "var(--app-text)" }}>AI 계획 관리</h1>
      
      {errorMessage && <p className="mb-4 text-red-500 font-bold">{errorMessage}</p>}
      {message && <p className="mb-4 text-green-600 font-bold">{message}</p>}

      <div className="space-y-4">
        {plans.map((goal) => (
          <div key={goal.id} className="rounded-2xl border p-6 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
            <div className="flex justify-between items-start cursor-pointer" onClick={() => { setExpandedId(expandedId === goal.id ? null : goal.id); fetchPlanDetail(goal); }}>
              <div>
                <h2 className="text-xl font-bold" style={{ color: "var(--app-text)" }}>{goal.title}</h2>
                <p className="text-sm mt-1" style={{ color: "var(--app-text-muted)" }}>카테고리: {goal.category} | 목표일: {goal.target_date || "미설정"}</p>
              </div>
              <button 
                onClick={(e) => { e.stopPropagation(); handleDeletePlan(goal.id); }}
                className="bg-red-600 text-white px-4 py-2 rounded-xl text-sm font-bold"
              >
                전체 삭제
              </button>
            </div>
            {expandedId === goal.id && (
              <div className="mt-4 pt-4 border-t" style={{ borderColor: "var(--app-border)" }}>
                <h4 className="font-bold mb-2" style={{ color: "var(--app-text)" }}>상세 스케줄:</h4>
                {goal.plans?.length > 0 ? goal.plans[0].items.map((item: any, idx: number) => (
                  <div key={idx} className="text-sm py-1" style={{ color: "var(--app-text)" }}>
                    • {item.title} ({Math.round(item.estimated_minutes)}분)
                  </div>
                )) : <p className="text-sm" style={{ color: "var(--app-text-muted)" }}>생성된 세부 계획이 없습니다.</p>}
              </div>
            )}
          </div>
        ))}
        {plans.length === 0 && <p style={{ color: "var(--app-text-muted)" }}>생성된 계획이 없습니다.</p>}
      </div>
    </div>
  );
}
