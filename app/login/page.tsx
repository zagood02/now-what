"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type AppUser,
  clearGuestSession,
  createId,
  isGuestSessionActive,
  logoutCurrentSession,
  readCurrentUser,
  readTodos,
  readUsers,
  saveCurrentUser,
  saveUsers,
  startGuestSession,
  updateCurrentUserProfile,
} from "@/lib/thirdStageStorage";
import {
  dayLabelMap,
  getEffectiveVariableStatus,
  getFailReasonLabel,
  getFixedScheduleSeries,
  getScheduleColorsByKey,
  getVariableSchedules,
  timeToMinutes,
  type DayCode,
  type FailReason,
} from "@/lib/mockSchedules";

type ModalType = "signup" | "findId" | "findPassword" | "profileEdit" | null;

type WeeklyMiniItem = {
  title: string;
  day: DayCode;
  startMinute: number;
  endMinute: number;
  colorKey: number;
};

const weekOrder: DayCode[] = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

function createEmptyWeeklyByDay(): Record<DayCode, WeeklyMiniItem[]> {
  return {
    SUN: [],
    MON: [],
    TUE: [],
    WED: [],
    THU: [],
    FRI: [],
    SAT: [],
  };
}

export default function LoginPage() {
  const [currentUser, setCurrentUser] = useState<AppUser | null>(null);
  const [guestActive, setGuestActive] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [signupName, setSignupName] = useState("");
  const [signupNickname, setSignupNickname] = useState("");
  const [signupEmail, setSignupEmail] = useState("");
  const [signupPassword, setSignupPassword] = useState("");

  const [editNickname, setEditNickname] = useState("");
  const [editPassword, setEditPassword] = useState("");
  const [editProfileImage, setEditProfileImage] = useState("");

  const [message, setMessage] = useState("");
  const [modal, setModal] = useState<ModalType>(null);

  const refreshAuth = () => {
    const user = readCurrentUser();
    setCurrentUser(user);
    setGuestActive(isGuestSessionActive());

    if (user) {
      setEditNickname(user.nickname ?? user.name);
      setEditPassword(user.password);
      setEditProfileImage(user.profile_image ?? "");
    }
  };

  useEffect(() => {
    refreshAuth();
    window.addEventListener("auth-state-changed", refreshAuth);

    return () => {
      window.removeEventListener("auth-state-changed", refreshAuth);
    };
  }, []);

  const stats = useMemo(() => {
    if (guestActive && !currentUser) {
      return {
        doneVariables: 0,
        doneTodos: 0,
        failedVariablesCount: 0,
        topFailReasonLabel: "-",
        weeklyByDay: createEmptyWeeklyByDay(),
        weekStartHour: 9,
        weekEndHour: 18,
        monthly: [],
      };
    }

    const variables = getVariableSchedules();
    const fixedSeries = getFixedScheduleSeries();
    const todos = readTodos().filter((item) => !currentUser || item.user_id === currentUser.id);

    const doneVariables = variables.filter((item) => getEffectiveVariableStatus(item) === "done").length;
    const doneTodos = todos.filter((item) => item.is_done).length;
    const failedVariables = variables.filter((item) => getEffectiveVariableStatus(item) === "failed");

    const failCounter: Record<FailReason, number> = {
      TIME_SHORTAGE: 0,
      ENERGY_SHORTAGE: 0,
      TRAVEL_TIME_SHORTAGE: 0,
      TOOK_LONGER_THAN_EXPECTED: 0,
      SUDDEN_SCHEDULE: 0,
      LOW_FOCUS: 0,
      ETC: 0,
    };

    failedVariables.forEach((item) => {
      if (item.fail_reason) {
        failCounter[item.fail_reason] += 1;
      }
    });

    const topFailReason = Object.entries(failCounter).sort((a, b) => b[1] - a[1])[0];

    const weeklyByDay = createEmptyWeeklyByDay();
    const allWeeklyItems: WeeklyMiniItem[] = [];

    fixedSeries.forEach((series) => {
      series.rules
        .filter((rule) => rule.freq_type === "WEEKLY")
        .forEach((rule) => {
          const startMinute = timeToMinutes(rule.start_time);
          const endMinute = timeToMinutes(rule.end_time);

          rule.days.forEach((day) => {
            const item: WeeklyMiniItem = {
              title: series.title,
              day,
              startMinute,
              endMinute,
              colorKey: series.color_key,
            };

            weeklyByDay[day].push(item);
            allWeeklyItems.push(item);
          });
        });
    });

    weekOrder.forEach((day) => {
      weeklyByDay[day].sort((a, b) => a.startMinute - b.startMinute);
    });

    const weekStartHour =
      allWeeklyItems.length > 0
        ? Math.max(0, Math.floor(Math.min(...allWeeklyItems.map((item) => item.startMinute)) / 60))
        : 9;

    const weekEndHour =
      allWeeklyItems.length > 0
        ? Math.min(24, Math.ceil(Math.max(...allWeeklyItems.map((item) => item.endMinute)) / 60))
        : 18;

    const monthly = fixedSeries.flatMap((series) =>
      series.rules
        .filter((rule) => rule.freq_type === "MONTHLY")
        .map((rule) => ({
          title: series.title,
          date:
            rule.month_rule === "START"
              ? "매월 초"
              : rule.month_rule === "MID"
                ? "매월 15일"
                : rule.month_rule === "END"
                  ? "매월 말일"
                  : `매월 ${rule.month_days.join(", ")}일`,
        }))
    );

    return {
      doneVariables,
      doneTodos,
      failedVariablesCount: failedVariables.length,
      topFailReasonLabel: topFailReason && topFailReason[1] > 0 ? getFailReasonLabel(topFailReason[0] as FailReason) : "-",
      weeklyByDay,
      weekStartHour,
      weekEndHour,
      monthly,
    };
  }, [currentUser, guestActive]);

  const handleLogin = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const inputEmail = email.trim().toLowerCase();

    const user = readUsers().find(
      (item) => item.email.trim().toLowerCase() === inputEmail && item.password === password
    );

    if (!user) {
      setMessage("아이디 또는 비밀번호가 맞지 않습니다.");
      return;
    }

    clearGuestSession();
    saveCurrentUser(user);
    setCurrentUser(user);
    setGuestActive(false);
    setMessage("");
    window.dispatchEvent(new Event("auth-state-changed"));
  };

  const handleSignup = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const nextEmail = signupEmail.trim().toLowerCase();

    if (!signupName.trim() || !signupNickname.trim() || !nextEmail || !signupPassword) {
      setMessage("이름, 닉네임, 이메일, 비밀번호를 모두 입력하세요.");
      return;
    }

    const users = readUsers();

    if (users.some((user) => user.email.trim().toLowerCase() === nextEmail)) {
      setMessage("이미 가입된 이메일입니다.");
      return;
    }

    const now = new Date().toISOString();

    const user: AppUser = {
      id: createId("user"),
      name: signupName.trim(),
      nickname: signupNickname.trim(),
      email: nextEmail,
      password: signupPassword,
      profile_image: "",
      created_at: now,
    };

    saveUsers([...users, user]);
    clearGuestSession();
    saveCurrentUser(user);
    setCurrentUser(user);
    setGuestActive(false);
    setModal(null);
    setMessage("");
    setSignupName("");
    setSignupNickname("");
    setSignupEmail("");
    setSignupPassword("");
    window.dispatchEvent(new Event("auth-state-changed"));
  };

  const handleProfileEdit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const updated = updateCurrentUserProfile({
      nickname: editNickname.trim() || currentUser?.nickname || currentUser?.name,
      password: editPassword || currentUser?.password,
      profile_image: editProfileImage,
    });

    if (updated) {
      setCurrentUser(updated);
      setModal(null);
      setMessage("프로필이 수정되었습니다.");
    }
  };

  const handleProfileImageFile = (file: File | null) => {
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      setEditProfileImage(String(reader.result ?? ""));
    };
    reader.readAsDataURL(file);
  };

  const handleGuest = () => {
    startGuestSession();
    setCurrentUser(null);
    setGuestActive(true);
    setMessage("");
    window.dispatchEvent(new Event("auth-state-changed"));
  };

  const handleLogout = () => {
    logoutCurrentSession();
    setCurrentUser(null);
    setGuestActive(false);
    setMessage("");
  };

  if (currentUser || guestActive) {
    return (
      <div>
        <h1 className="text-3xl font-bold mb-6" style={{ color: "var(--app-text)" }}>
          마이페이지
        </h1>

        <section
          className="rounded-2xl border p-6 shadow-sm mb-6"
          style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
        >
          <div className="flex items-center gap-5">
            <ProfileAvatar src={currentUser?.profile_image ?? ""} />

            <div className="min-w-0">
              <div className="text-3xl font-bold truncate" style={{ color: "var(--app-text)" }}>
                {currentUser?.nickname ?? "게스트"}
              </div>

              <div className="text-sm mt-2" style={{ color: "var(--app-text-muted)" }}>
                {currentUser ? currentUser.name : "게스트 사용자"}
              </div>

              <div className="text-sm" style={{ color: "var(--app-text-muted)" }}>
                {currentUser ? currentUser.email : "일회성 체험 세션"}
              </div>
            </div>
          </div>

          <div className="mt-6 flex gap-2 flex-wrap">
            {currentUser && (
              <button
                type="button"
                onClick={() => setModal("profileEdit")}
                className="rounded-xl px-4 py-3 font-bold"
                style={{ background: "var(--primary-button-bg)", color: "var(--primary-button-text)" }}
              >
                프로필 편집
              </button>
            )}

            <button
              type="button"
              onClick={handleLogout}
              className="rounded-xl px-4 py-3 font-bold"
              style={{ background: "var(--card-red-bg)", color: "var(--card-red-text)" }}
            >
              로그아웃
            </button>
          </div>

          {message && (
            <p className="mt-3 font-semibold" style={{ color: "var(--app-text)" }}>
              {message}
            </p>
          )}
        </section>

        <section
          className="rounded-2xl border p-6 shadow-sm mb-6"
          style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
        >
          <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
            활동 통계
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <StatCard label="완료한 변동 일정" value={`${stats.doneVariables}개`} />
            <StatCard label="성공한 할 일" value={`${stats.doneTodos}개`} />
            <StatCard label="최다 실패 사유" value={stats.topFailReasonLabel ?? "-"} />
          </div>
        </section>

        <section
          className="rounded-2xl border p-6 shadow-sm mb-6"
          style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
        >
          <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
            이번주 일정
          </h2>

          <MiniWeeklyTable
            weeklyByDay={stats.weeklyByDay}
            startHour={stats.weekStartHour}
            endHour={stats.weekEndHour}
          />
        </section>

        <section
          className="rounded-2xl border p-6 shadow-sm"
          style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
        >
          <h2 className="text-xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
            매월 고정 일정
          </h2>

          <div className="space-y-2">
            {stats.monthly.length === 0 ? (
              <EmptyText>매월 고정 일정이 없습니다.</EmptyText>
            ) : (
              stats.monthly.map((item, index) => (
                <div key={`${item.title}-${index}`} className="rounded-xl border p-3" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)" }}>
                  <strong style={{ color: "var(--app-text)" }}>{item.date}</strong>
                  <span className="ml-3 text-sm" style={{ color: "var(--app-text-muted)" }}>
                    {item.title}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>

        {modal === "profileEdit" && (
          <ProfileEditModal
            nickname={editNickname}
            password={editPassword}
            profileImage={editProfileImage}
            onNicknameChange={setEditNickname}
            onPasswordChange={setEditPassword}
            onFileChange={handleProfileImageFile}
            onSubmit={handleProfileEdit}
            onClose={() => setModal(null)}
          />
        )}
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--app-text)" }}>
        로그인
      </h1>

      <p className="mb-6" style={{ color: "var(--app-text-muted)" }}>
        로그인하거나 게스트로 기능을 확인할 수 있습니다.
      </p>

      <form
        onSubmit={handleLogin}
        className="max-w-xl rounded-2xl border p-5 shadow-sm space-y-4"
        style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
      >
        <InputLabel label="아이디">
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="form-input"
            placeholder="이메일"
          />
        </InputLabel>

        <InputLabel label="비밀번호">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="form-input"
            placeholder="비밀번호"
          />
        </InputLabel>

        <button
          className="w-full rounded-xl py-3 font-bold"
          style={{ background: "var(--primary-button-bg)", color: "var(--primary-button-text)" }}
        >
          로그인
        </button>

        <div className="flex justify-center gap-2 text-sm flex-wrap">
          <TextButton onClick={() => setModal("findId")}>아이디 찾기</TextButton>
          <span style={{ color: "var(--app-text-muted)" }}>|</span>
          <TextButton onClick={() => setModal("findPassword")}>비밀번호 찾기</TextButton>
          <span style={{ color: "var(--app-text-muted)" }}>|</span>
          <TextButton onClick={() => setModal("signup")}>회원가입</TextButton>
          <span style={{ color: "var(--app-text-muted)" }}>|</span>
          <TextButton onClick={handleGuest}>게스트 로그인</TextButton>
        </div>

        {message && (
          <p className="font-semibold" style={{ color: "var(--app-text)" }}>
            {message}
          </p>
        )}
      </form>

      {(modal === "signup" || modal === "findId" || modal === "findPassword") && (
        <div
          className="fixed inset-0 flex items-center justify-center p-4"
          style={{ zIndex: 120, background: "rgba(0,0,0,0.45)" }}
        >
          <div
            className="w-full md:w-1/4 min-w-[320px] h-auto md:h-2/3 rounded-2xl border p-6 shadow-xl overflow-y-auto"
            style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
          >
            {modal === "signup" ? (
              <>
                <h2 className="text-2xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
                  회원가입
                </h2>

                <form onSubmit={handleSignup} className="space-y-4">
                  <InputLabel label="닉네임">
                    <input value={signupNickname} onChange={(e) => setSignupNickname(e.target.value)} className="form-input" />
                  </InputLabel>

                  <InputLabel label="이름">
                    <input value={signupName} onChange={(e) => setSignupName(e.target.value)} className="form-input" />
                  </InputLabel>

                  <InputLabel label="이메일">
                    <input value={signupEmail} onChange={(e) => setSignupEmail(e.target.value)} className="form-input" />
                  </InputLabel>

                  <InputLabel label="비밀번호">
                    <input type="password" value={signupPassword} onChange={(e) => setSignupPassword(e.target.value)} className="form-input" />
                  </InputLabel>

                  <button className="w-full rounded-xl py-3 font-bold" style={{ background: "var(--primary-button-bg)", color: "var(--primary-button-text)" }}>
                    가입하기
                  </button>
                </form>
              </>
            ) : (
              <>
                <h2 className="text-2xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
                  {modal === "findId" ? "아이디 찾기" : "비밀번호 찾기"}
                </h2>
                <p style={{ color: "var(--app-text-muted)" }}>아직 개발중입니다.</p>
              </>
            )}

            <button
              type="button"
              onClick={() => setModal(null)}
              className="mt-4 w-full rounded-xl py-3 font-bold"
              style={{ background: "var(--app-surface-muted)", color: "var(--app-text)" }}
            >
              닫기
            </button>
          </div>
        </div>
      )}

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

function MiniWeeklyTable({
  weeklyByDay,
  startHour,
  endHour,
}: {
  weeklyByDay: Record<DayCode, WeeklyMiniItem[]>;
  startHour: number;
  endHour: number;
}) {
  const safeStartHour = Math.max(0, Math.min(startHour, 23));
  const safeEndHour = Math.max(safeStartHour + 1, Math.min(endHour, 24));
  const totalMinutes = (safeEndHour - safeStartHour) * 60;
  const tableHeight = Math.max(160, totalMinutes * 0.65);

  const hours = Array.from(
    {
      length: Math.max(1, safeEndHour - safeStartHour),
    },
    (_, index) => safeStartHour + index
  );

  const hasItems = weekOrder.some((day) => weeklyByDay[day].length > 0);

  if (!hasItems) {
    return <EmptyText>이번주 고정 일정이 없습니다.</EmptyText>;
  }

  return (
    <div className="overflow-x-auto">
      <div
        className="w-full rounded-xl border overflow-hidden"
        style={{
          borderColor: "var(--app-border)",
          minWidth: "760px",
        }}
      >
        <div
          className="grid grid-cols-[64px_repeat(7,1fr)] border-b"
          style={{ borderColor: "var(--app-border)" }}
        >
          <div
            className="p-2 text-xs text-center"
            style={{ color: "var(--app-text-muted)" }}
          >
            시간
          </div>

          {weekOrder.map((day) => (
            <div
              key={day}
              className="p-2 text-sm font-bold text-center"
              style={{ color: "var(--app-text)" }}
            >
              {dayLabelMap[day]}
            </div>
          ))}
        </div>

        <div
          className="grid grid-cols-[64px_repeat(7,1fr)] relative"
          style={{
            height: `${tableHeight}px`,
            background: "var(--app-bg)",
          }}
        >
          <div
            className="relative border-r"
            style={{ borderColor: "var(--app-border)" }}
          >
            {hours.map((hour) => {
              const top =
                ((hour - safeStartHour) * 60 / totalMinutes) * 100;

              return (
                <div
                  key={hour}
                  className="absolute left-0 right-0 text-xs text-center"
                  style={{
                    top: `${top}%`,
                    color: "var(--app-text-muted)",
                    transform: "translateY(-50%)",
                  }}
                >
                  {String(hour).padStart(2, "0")}:00
                </div>
              );
            })}
          </div>

          {weekOrder.map((day) => (
            <div
              key={day}
              className="relative border-r last:border-r-0"
              style={{ borderColor: "var(--app-border)" }}
            >
              {hours.map((hour) => {
                const top =
                  ((hour - safeStartHour) * 60 / totalMinutes) * 100;

                return (
                  <div
                    key={`${day}-${hour}`}
                    className="absolute left-0 right-0 border-t"
                    style={{
                      top: `${top}%`,
                      borderColor: "var(--app-border)",
                    }}
                  />
                );
              })}

              {weeklyByDay[day].map((item, index) => {
                const colors = getScheduleColorsByKey(item.colorKey);

                const top =
                  ((item.startMinute - safeStartHour * 60) / totalMinutes) *
                  100;

                const height =
                  Math.max(
                    10,
                    ((item.endMinute - item.startMinute) / totalMinutes) * 100
                  );

                return (
                  <div
                    key={`${item.title}-${item.startMinute}-${index}`}
                    className="absolute left-1 right-1 rounded-lg px-2 py-1 text-xs font-bold text-center truncate shadow-sm"
                    style={{
                      top: `${Math.max(0, top)}%`,
                      height: `${Math.min(100 - Math.max(0, top), height)}%`,
                      background: colors.bg,
                      color: colors.text,
                      border: `1px solid ${colors.border}`,
                    }}
                    title={`${item.title} ${Math.floor(item.startMinute / 60)}:${String(
                      item.startMinute % 60
                    ).padStart(2, "0")}~${Math.floor(item.endMinute / 60)}:${String(
                      item.endMinute % 60
                    ).padStart(2, "0")}`}
                  >
                    {item.title}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ProfileAvatar({ src }: { src: string }) {
  if (src) {
    return (
      <img
        src={src}
        alt="프로필"
        className="w-24 h-24 rounded-full object-cover shrink-0"
        style={{ border: "1px solid var(--app-border)" }}
      />
    );
  }

  return (
    <div
      className="w-24 h-24 rounded-full flex items-center justify-center shrink-0"
      style={{ background: "var(--app-surface-muted)", border: "1px solid var(--app-border)" }}
    >
      <div className="relative w-14 h-14">
        <div className="absolute left-1/2 top-1 -translate-x-1/2 w-6 h-6 rounded-full" style={{ background: "var(--app-text-muted)" }} />
        <div className="absolute left-1/2 bottom-1 -translate-x-1/2 w-12 h-7 rounded-t-full" style={{ background: "var(--app-text-muted)" }} />
      </div>
    </div>
  );
}

function ProfileEditModal({
  nickname,
  password,
  profileImage,
  onNicknameChange,
  onPasswordChange,
  onFileChange,
  onSubmit,
  onClose,
}: {
  nickname: string;
  password: string;
  profileImage: string;
  onNicknameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onFileChange: (file: File | null) => void;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ zIndex: 120, background: "rgba(0,0,0,0.45)" }}
    >
      <div
        className="w-full md:w-1/4 min-w-[320px] h-auto md:h-2/3 rounded-2xl border p-6 shadow-xl overflow-y-auto"
        style={{ background: "var(--app-surface)", borderColor: "var(--app-border)" }}
      >
        <h2 className="text-2xl font-bold mb-4" style={{ color: "var(--app-text)" }}>
          프로필 편집
        </h2>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="flex justify-center">
            <ProfileAvatar src={profileImage} />
          </div>

          <InputLabel label="프로필 사진">
            <input
              type="file"
              accept="image/*"
              onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
              className="form-input"
            />
          </InputLabel>

          <InputLabel label="닉네임">
            <input value={nickname} onChange={(e) => onNicknameChange(e.target.value)} className="form-input" />
          </InputLabel>

          <InputLabel label="비밀번호">
            <input type="password" value={password} onChange={(e) => onPasswordChange(e.target.value)} className="form-input" />
          </InputLabel>

          <button className="w-full rounded-xl py-3 font-bold" style={{ background: "var(--primary-button-bg)", color: "var(--primary-button-text)" }}>
            저장
          </button>
        </form>

        <button
          type="button"
          onClick={onClose}
          className="mt-4 w-full rounded-xl py-3 font-bold"
          style={{ background: "var(--app-surface-muted)", color: "var(--app-text)" }}
        >
          닫기
        </button>
      </div>
    </div>
  );
}

function InputLabel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-sm font-bold mb-2" style={{ color: "var(--app-text)" }}>
        {label}
      </div>
      {children}
    </label>
  );
}

function TextButton({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="underline"
      style={{ color: "var(--app-text-muted)" }}
    >
      {children}
    </button>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border p-4" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)" }}>
      <div className="text-sm" style={{ color: "var(--app-text-muted)" }}>{label}</div>
      <div className="text-2xl font-bold mt-2" style={{ color: "var(--app-text)" }}>{value}</div>
    </div>
  );
}

function EmptyText({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border p-4 text-center" style={{ background: "var(--app-bg)", borderColor: "var(--app-border)", color: "var(--app-text-muted)" }}>
      {children}
    </div>
  );
}
