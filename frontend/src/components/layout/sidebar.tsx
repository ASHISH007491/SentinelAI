"use client";

import { ChevronLeft } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Brand } from "@/components/layout/brand";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { NAV_ITEMS, SECONDARY_NAV } from "@/constants/navigation";
import { useSidebar } from "@/hooks/use-sidebar";

export function Sidebar() {
  const { collapsed, toggle } = useSidebar();

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 76 : 264 }}
      transition={{ type: "spring", stiffness: 300, damping: 32 }}
      className="sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border/60 bg-card/40 backdrop-blur-xl lg:flex"
    >
      <div className="flex h-16 items-center justify-between px-4">
        <Brand collapsed={collapsed} />
      </div>
      <Separator />

      <div className="flex-1 overflow-y-auto px-3 py-4">
        <SidebarNav items={NAV_ITEMS} collapsed={collapsed} />
      </div>

      <Separator />
      <div className="px-3 py-4">
        <SidebarNav items={SECONDARY_NAV} collapsed={collapsed} />
      </div>

      <div className="px-3 pb-4">
        <Button
          variant="outline"
          size="sm"
          onClick={toggle}
          className={cn("w-full justify-center", collapsed && "px-0")}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <ChevronLeft className={cn("h-4 w-4 transition-transform", collapsed && "rotate-180")} />
          {!collapsed && <span>Collapse</span>}
        </Button>
      </div>
    </motion.aside>
  );
}
