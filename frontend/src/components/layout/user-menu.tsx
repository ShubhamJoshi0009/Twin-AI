"use client";

import { useRouter } from "next/navigation";
import { CreditCard, LogOut, Settings, User } from "lucide-react";
import { toast } from "sonner";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useProfileStore } from "@/stores/profile-store";

const FALLBACK = { name: "Alex Morgan", role: "Chief Operations Officer", email: "alex.morgan@acmecorp.com" };

/** Header user menu with profile and settings links — reflects the AI-collected profile. */
export function UserMenu() {
  const { personal, business } = useProfileStore();
  const user = {
    name: personal.name || FALLBACK.name,
    role: personal.role ? personal.role.replace("_", " ") : FALLBACK.role,
    email: personal.email || FALLBACK.email,
    company: business.name || "—",
  };
  const initials = user.name.split(" ").map((p) => p[0]).slice(0, 2).join("");
  const router = useRouter();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-9 gap-2 px-2" aria-label="User menu">
          <Avatar className="h-7 w-7">
            <AvatarFallback className="bg-gradient-to-br from-blue-500 to-violet-600 text-[10px] font-semibold text-white">
              {initials}
            </AvatarFallback>
          </Avatar>
          <span className="hidden text-left md:block">
            <span className="block text-xs font-medium leading-tight">{user.name}</span>
            <span className="block text-[10px] leading-tight text-muted-foreground">{user.company === "—" ? user.role : user.company}</span>
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <p className="text-sm font-medium">{user.name}</p>
          <p className="text-xs font-normal text-muted-foreground">{user.email}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/settings")}>
          <User /> Profile
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => toast.info("Billing is managed by your plan administrator.")}>
          <CreditCard /> Billing
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => router.push("/settings")}>
          <Settings /> Preferences
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onSelect={() => toast.info("Signed out (demo) — no active session on this build")}
        >
          <LogOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
