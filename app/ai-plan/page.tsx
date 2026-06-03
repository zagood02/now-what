"use client";

import React, { useState } from "react";
import { createId } from "@/lib/thirdStageStorage";
import { goalAPI, flexibleTaskAPI, plannerAPI, handleApiError } from "@/lib/api";
import { useAuth } from "@/app/contexts/AuthContext";
import HelpButton from "@/components/HelpButton";

export default function AiPlanPage() {
  const { user } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [questions, setQuestions] = useState<any[]>([]);
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [generatedPlans, setGeneratedPlans] = useState<any[]>([]);
  const [message, setMessage] = useState("");

  const handleCreateQuestions = async () => {
    if (!prompt.trim()) return setErrorMessage("프롬프트를 입력해주세요.");
    setIsLoadingQuestions(true);
    setErrorMessage(null);
    try {
      const response = await goalAPI.intake({ text: prompt });
      setQuestions(response.data.questions.map((q: any) => ({ ...q, id: createId("q"), answer: "" })));
      setGeneratedPlans([]);
      setMessage("");
    } catch (err) {
      setErrorMessage(handleApiError(err));
    } finally {
      setIsLoadingQuestions(false);
    }
  };

  const handleGeneratePlan = async () => {
    const answers_json = Object.fromEntries(questions.map((q) => [q.key, q.answer]));
    try {
      const response = await goalAPI.complete({ text: prompt, answers_json, replace_existing: true });
      // 백엔드에서 이미 한글 요약된 제목을 items로 반환하도록 planning.py를 수정했습니다.
      setGeneratedPlans(response.data.plan.items);
      setMessage("계획이 생성되었습니다!");
    } catch (err) {
      setErrorMessage(handleApiError(err));
    }
  };

  const handleSavePlan = async () => {
    try {
      setMessage("할 일과 스케줄이 성공적으로 저장되었습니다!");
      setTimeout(() => setMessage(""), 5000);
    } catch (err) {
      setErrorMessage(handleApiError(err));
    }
  };

  const handleDeletePlan = async (goalId: number) => {
    try {
      await goalAPI.delete(goalId);
      setGeneratedPlans([]);
      setMessage("계획이 삭제되었습니다.");
      setTimeout(() => setMessage(""), 3000);
    } catch (err) {
      setErrorMessage(handleApiError(err));
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-3xl font-bold" style={{ color: "var(--app-text)" }}>AI 계획 생성</h1>
        <HelpButton title="AI 계획 생성 도움말">
          <p className="mb-2">AI를 활용하여 목표에 맞는 계획을 생성하고 관리할 수 있습니다.</p>
          <ul className="list-disc list-inside space-y-1 text-xs">
            <li><strong>프롬프트 입력</strong>: 원하는 목표를 구체적으로 입력하세요.</li>
            <li><strong>질문 생성</strong>: AI가 계획 수립을 위해 필요한 질문을 생성합니다.</li>
            <li><strong>계획 초안 생성</strong>: 답변을 바탕으로 계획을 생성합니다.</li>
            <li><strong>저장</strong>: 생성된 계획을 시스템에 저장합니다.</li>
          </ul>
        </HelpButton>
      </div>
      
      <section className="rounded-2xl border p-6 shadow-sm mb-6" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
        <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>1. 프롬프트 입력</h2>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} className="w-full p-4 rounded-xl border min-h-32" style={{ background: "var(--app-bg)", color: "var(--app-text)", borderColor: "var(--app-border)" }} placeholder="예: 정보처리기사 시험 준비 계획 짜줘" />
        <button onClick={handleCreateQuestions} disabled={isLoadingQuestions} className="mt-4 px-6 py-3 rounded-xl font-bold bg-blue-600 text-white">
          {isLoadingQuestions ? "질문 생성 중..." : "AI 질문 생성"}
        </button>
      </section>

      {questions.length > 0 && (
        <section className="rounded-2xl border p-6 shadow-sm mb-6" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
          <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>2. 세부 질문 및 답변</h2>
          {questions.map((q, i) => (
            <div key={q.id} className="mb-4">
              <p className="font-semibold mb-2" style={{ color: "var(--app-text)" }}>{i + 1}. {q.prompt}</p>
              {q.answer_type === "date" ? (
                <input type="date" value={q.answer} onChange={(e) => setQuestions(prev => prev.map(p => p.id === q.id ? {...p, answer: e.target.value} : p))} className="w-full p-3 border rounded-xl" style={{ background: "var(--app-bg)", color: "var(--app-text)", borderColor: "var(--app-border)" }} />
              ) : q.answer_type === "number" ? (
                <input type="number" value={q.answer} onChange={(e) => setQuestions(prev => prev.map(p => p.id === q.id ? {...p, answer: e.target.value} : p))} className="w-full p-3 border rounded-xl" style={{ background: "var(--app-bg)", color: "var(--app-text)", borderColor: "var(--app-border)" }} />
              ) : q.answer_type === "select" ? (
                <select value={q.answer} onChange={(e) => setQuestions(prev => prev.map(p => p.id === q.id ? {...p, answer: e.target.value} : p))} className="w-full p-3 border rounded-xl" style={{ background: "var(--app-bg)", color: "var(--app-text)", borderColor: "var(--app-border)" }}>
                  <option value="">선택해주세요</option>
                  {q.options?.map((opt: string) => <option key={opt} value={opt}>{opt}</option>)}
                </select>
              ) : (
                <input value={q.answer} onChange={(e) => setQuestions(prev => prev.map(p => p.id === q.id ? {...p, answer: e.target.value} : p))} className="w-full p-3 border rounded-xl" style={{ background: "var(--app-bg)", color: "var(--app-text)", borderColor: "var(--app-border)" }} />
              )}
            </div>
          ))}
          <button onClick={handleGeneratePlan} className="bg-green-600 text-white px-6 py-3 rounded-xl font-bold">계획 초안 생성</button>
        </section>
      )}

      {generatedPlans.length > 0 && (
        <section className="rounded-2xl border p-6 shadow-sm" style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}>
          <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>3. 생성된 계획 확인</h2>
          <div className="space-y-3 mb-6">
            {generatedPlans.map((item, i) => (
              <div key={i} className="p-4 border rounded-xl" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)" }}>
                <strong style={{ color: "var(--app-text)" }}>{item.title}</strong>
                <p className="text-sm mt-1" style={{ color: "var(--app-text-muted)" }}>{item.description}</p>
              </div>
            ))}
          </div>
          <div className="flex gap-4 mt-4">
            <button onClick={handleSavePlan} className="bg-purple-600 text-white px-6 py-3 rounded-xl font-bold">할 일/스케줄 저장</button>
            <button onClick={() => handleDeletePlan(generatedPlans[0].id)} className="bg-red-600 text-white px-6 py-3 rounded-xl font-bold">계획 전체 삭제</button>
          </div>
        </section>
      )}
      {message && <p className="mt-4 font-bold" style={{ color: "var(--app-text)" }}>{message}</p>}
      {errorMessage && <p className="mt-4 font-bold text-red-500">{errorMessage}</p>}
    </div>
  );
}
