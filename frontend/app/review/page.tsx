import { Suspense } from "react";
import ReviewDashboard from "./review-dashboard";

export default function ReviewPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <ReviewDashboard />
    </Suspense>
  );
}
