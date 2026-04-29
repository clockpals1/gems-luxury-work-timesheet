import React from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Brand } from "./Brand";
import { Button } from "./ui/button";
import { LogOut, LayoutDashboard, Users, Package, Tag, DollarSign, Image, Clock, Activity, Settings } from "lucide-react";

const adminNav = [
  { to: "/admin", icon: LayoutDashboard, label: "Overview", end: true },
  { to: "/admin/users", icon: Users, label: "Users" },
  { to: "/admin/products", icon: Package, label: "Products" },
  { to: "/admin/naming", icon: Tag, label: "Naming" },
  { to: "/admin/pricing", icon: DollarSign, label: "Pricing" },
  { to: "/admin/images", icon: Image, label: "Images" },
  { to: "/admin/attendance", icon: Clock, label: "Attendance" },
  { to: "/admin/activity", icon: Activity, label: "Activity" },
  { to: "/admin/settings", icon: Settings, label: "Settings" },
];

export function AdminLayout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="min-h-screen flex bg-[#050A07] text-[#F5F5F5]">
      <aside className="w-64 border-r border-[#21362A] p-6 flex flex-col gap-6 sticky top-0 h-screen">
        <Link to="/admin"><Brand /></Link>
        <nav className="flex flex-col gap-1" data-testid="admin-nav">
          {adminNav.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-sm text-sm transition-colors ${
                  isActive
                    ? "bg-[#132018] text-[#D4AF37] border border-[#21362A]"
                    : "text-[#A1B4A8] hover:text-white hover:bg-[#0C140F]"
                }`
              }
              data-testid={`nav-${label.toLowerCase()}`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto pt-4 border-t border-[#21362A]">
          <div className="label-overline mb-1">Signed in</div>
          <div className="text-sm text-white">{user?.name}</div>
          <div className="text-xs text-[#A1B4A8]">{user?.email}</div>
          <Button
            variant="ghost"
            size="sm"
            className="mt-3 w-full justify-start text-[#A1B4A8] hover:text-white"
            onClick={async () => { await logout(); nav("/login"); }}
            data-testid="logout-btn"
          >
            <LogOut className="w-4 h-4 mr-2" /> Sign out
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}

export function WorkerLayout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="min-h-screen flex flex-col bg-[#050A07] text-[#F5F5F5]">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-black/60 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Brand />
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-sm text-white">{user?.name}</div>
              <div className="label-overline text-[10px]">Worker Studio</div>
            </div>
            <Button variant="ghost" size="sm" onClick={async () => { await logout(); nav("/login"); }} data-testid="logout-btn">
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto w-full p-6">{children}</main>
    </div>
  );
}
