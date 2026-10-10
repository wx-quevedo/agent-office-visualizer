"use client";

/** /oficina — first version of the office in plain boxes (see components/oficina). */

import { Suspense } from "react";
import Oficina from "@/components/oficina/Oficina";

export default function OficinaPage() {
  return (
    <Suspense fallback={null}>
      <Oficina />
    </Suspense>
  );
}
