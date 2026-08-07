import { Suspense } from "react";
import PlanDashboard from "./plan-dashboard";

export default function PlanPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <PlanDashboard />
    </Suspense>
  );
}
