"use client";

import { useEffect } from "react";

interface ErrorProps {
  error: Error;
  reset: () => void;
}

export default function GlobalError({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="grid min-h-screen place-items-center bg-slate-950 px-6 py-24 text-slate-100">
      <div className="mx-auto w-full max-w-xl rounded-3xl border border-white/10 bg-slate-900/90 p-10 shadow-2xl shadow-black/40 backdrop-blur-xl">
        <p className="text-sm uppercase tracking-[0.3em] text-rose-400">Application error</p>
        <h1 className="mt-6 text-4xl font-semibold tracking-tight text-white">Something went wrong.</h1>
        <p className="mt-4 text-slate-400">We’re having trouble loading the page. Try again or return to the dashboard.</p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <button onClick={() => reset()} className="inline-flex items-center justify-center rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400">
            Retry
          </button>
          <a href="/dashboard" className="inline-flex items-center justify-center rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-800">
            Back to dashboard
          </a>
        </div>
      </div>
    </div>
  );
}
