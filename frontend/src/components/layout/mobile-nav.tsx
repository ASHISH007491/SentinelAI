"use client";

import { useState } from "react";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { Brand } from "@/components/layout/brand";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { NAV_ITEMS, SECONDARY_NAV } from "@/constants/navigation";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 p-0">
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <div className="flex h-16 items-center px-4">
          <Brand />
        </div>
        <Separator />
        <div className="flex flex-col gap-4 px-3 py-4">
          <SidebarNav items={NAV_ITEMS} collapsed={false} onNavigate={close} />
          <Separator />
          <SidebarNav items={SECONDARY_NAV} collapsed={false} onNavigate={close} />
        </div>
      </SheetContent>
    </Sheet>
  );
}
