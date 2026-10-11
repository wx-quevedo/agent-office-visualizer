"use client";

/** /donde-quedamos?proyecto=<id> — where each project was left (see components/donde). */

import { Suspense } from "react";
import DondeQuedamos from "@/components/donde/DondeQuedamos";

export default function DondePage() {
  return (
    <Suspense fallback={null}>
      <DondeQuedamos />
    </Suspense>
  );
}
