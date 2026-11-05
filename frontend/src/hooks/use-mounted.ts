"use client";

import { useEffect, useState } from "react";

/** True after first client render — guards hydration-sensitive UI (e.g. theme). */
export function useMounted() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}
