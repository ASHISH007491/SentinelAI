"use client";

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { NAV_ITEMS, SECONDARY_NAV } from "@/constants/navigation";
import { useAuth } from "@/hooks/use-auth";
import { useRuns } from "@/hooks/use-runs";

/** Global Ctrl/⌘-K command palette: jump to any page or recent run. */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const { data: runs } = useRuns(isAuthenticated && open);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div
        className="mx-auto mt-24 w-full max-w-lg px-4"
        onClick={(e) => e.stopPropagation()}
      >
        <Command
          label="Command menu"
          className="overflow-hidden rounded-xl border border-border bg-popover text-popover-foreground shadow-2xl"
        >
          <Command.Input
            autoFocus
            placeholder="Search pages and recent runs…"
            className="w-full border-b border-border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
          />
          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="px-3 py-6 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>

            <Command.Group
              heading="Navigate"
              className="px-2 py-1 text-xs font-medium text-muted-foreground"
            >
              {[...NAV_ITEMS, ...SECONDARY_NAV].map((item) => (
                <Command.Item
                  key={item.href}
                  value={item.title}
                  onSelect={() => go(item.href)}
                  className="flex cursor-pointer items-center rounded-md px-3 py-2 text-sm text-foreground aria-selected:bg-accent aria-selected:text-accent-foreground"
                >
                  {item.title}
                </Command.Item>
              ))}
            </Command.Group>

            {runs && runs.length > 0 && (
              <Command.Group
                heading="Recent runs"
                className="px-2 py-1 text-xs font-medium text-muted-foreground"
              >
                {runs.slice(0, 6).map((r) => (
                  <Command.Item
                    key={r.id}
                    value={`run ${r.id} ${r.workflow}`}
                    onSelect={() => go(`/runs/${r.id}`)}
                    className="flex cursor-pointer items-center rounded-md px-3 py-2 text-sm text-foreground aria-selected:bg-accent aria-selected:text-accent-foreground"
                  >
                    Run #{r.id} · {r.workflow}
                  </Command.Item>
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
