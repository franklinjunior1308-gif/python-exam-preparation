import { Suspense } from "react";
import { RequestsView } from "@/components/RequestsView";

export default function RequestsPage() {
  return (
    <Suspense>
      <RequestsView />
    </Suspense>
  );
}
