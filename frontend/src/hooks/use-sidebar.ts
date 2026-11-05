"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "sentinelai:sidebar-collapsed";

/** Persisted collapsed/expanded state for the desktop sidebar. */
export function useSidebar() {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) setCollapsed(saved === "1");
  }, []);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }, []);

  return { collapsed, toggle };
}
