import { Suspense } from "react";
import { SchedulePage } from "@/components/SchedulePage";

export default function Page() {
  return (
    <Suspense>
      <SchedulePage />
    </Suspense>
  );
}
