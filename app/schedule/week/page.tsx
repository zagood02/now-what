import { Suspense } from "react";
import WeekPageClient from "./WeekPageClient";

export default function WeekPage() {
  return (
    <Suspense fallback={<div>불러오는 중...</div>}>
      <WeekPageClient />
    </Suspense>
  );
}