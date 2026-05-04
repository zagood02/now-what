export default function Home() {
  return (
    <div>
      <h1
        className="text-3xl font-bold mb-2"
        style={{ color: "var(--app-text)" }}
      >
        그래서 이제 뭐함?
      </h1>
      <p className="mb-8" style={{ color: "var(--app-text-muted)" }}>
        AI 기반 일정 관리 시스템
      </p>

      <div className="grid grid-cols-3 gap-6">
        <div
          className="rounded-xl border shadow-sm p-5"
          style={{
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
          }}
        >
          <h2
            className="text-lg font-semibold mb-2"
            style={{ color: "var(--app-text)" }}
          >
            오늘의 핵심 일정
          </h2>
          <p className="text-sm" style={{ color: "var(--app-text-muted)" }}>
            오전 수업, 오후 과제, 저녁 운동 일정이 배정되어 있습니다.
          </p>
        </div>

        <div
          className="rounded-xl border shadow-sm p-5"
          style={{
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
          }}
        >
          <h2
            className="text-lg font-semibold mb-2"
            style={{ color: "var(--app-text)" }}
          >
            마감 임박 과제
          </h2>
          <p className="text-sm" style={{ color: "var(--app-text-muted)" }}>
            네트워크 과제 제출까지 2일 남았습니다.
          </p>
        </div>

        <div
          className="rounded-xl border shadow-sm p-5"
          style={{
            background: "var(--app-surface)",
            borderColor: "var(--app-border)",
          }}
        >
          <h2
            className="text-lg font-semibold mb-2"
            style={{ color: "var(--app-text)" }}
          >
            AI 추천
          </h2>
          <p className="text-sm" style={{ color: "var(--app-text-muted)" }}>
            오늘은 수업 후 1시간 휴식 뒤 운동을 진행하는 것을 추천합니다.
          </p>
        </div>
      </div>
    </div>
  );
}