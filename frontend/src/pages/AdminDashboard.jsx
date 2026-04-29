import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Users, Coffee, Timer, Package, Image as ImageIcon } from "lucide-react";

const stateStyle = {
  active: "bg-[#097969]/20 text-[#2A9D8F] border-[#097969]/40",
  on_break: "bg-[#D4AF37]/15 text-[#D4AF37] border-[#D4AF37]/30",
  idle: "bg-[#E63946]/15 text-[#E63946] border-[#E63946]/30",
};

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [liveUsers, setLiveUsers] = useState([]);
  const [recent, setRecent] = useState([]);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    const load = async () => {
      const [s, l, p, a] = await Promise.all([
        api.get("/admin/dashboard/stats"),
        api.get("/admin/dashboard/live-users"),
        api.get("/products?limit=8"),
        api.get("/admin/activity-logs?limit=10"),
      ]);
      setStats(s.data); setLiveUsers(l.data); setRecent(p.data); setLogs(a.data);
    };
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  return (
    <AdminLayout>
      <div className="space-y-8">
        <header className="flex items-end justify-between">
          <div>
            <div className="label-overline text-[#D4AF37]">Control room</div>
            <h1 className="font-display text-4xl mt-2">Overview</h1>
          </div>
        </header>

        <section className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Kpi icon={Users} label="Punched in" value={stats?.punched_in ?? "—"} data-testid="kpi-punched-in"/>
          <Kpi icon={Coffee} label="On break" value={stats?.on_break ?? "—"} data-testid="kpi-on-break"/>
          <Kpi icon={Timer} label="Idle" value={stats?.idle ?? "—"} tone="danger" data-testid="kpi-idle"/>
          <Kpi icon={Package} label="Products today" value={stats?.products_today ?? "—"} data-testid="kpi-products-today"/>
        </section>

        <section className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Kpi label="Products (7d)" value={stats?.products_week ?? "—"} icon={Package} data-testid="kpi-products-week"/>
          <Kpi label="Total products" value={stats?.total_products ?? "—"} icon={Package} data-testid="kpi-total-products"/>
          <Kpi label="Images available" value={stats?.available_images ?? "—"} icon={ImageIcon} data-testid="kpi-images"/>
          <Kpi label="Active users" value={stats?.users_active ?? "—"} icon={Users} data-testid="kpi-active-users"/>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="bg-[#0C140F] border-[#21362A] rounded-sm lg:col-span-2">
            <CardHeader><CardTitle className="font-display text-2xl">Live workers</CardTitle></CardHeader>
            <CardContent className="space-y-2" data-testid="live-users">
              {liveUsers.length === 0 && <div className="text-sm text-[#A1B4A8]">No one punched in.</div>}
              {liveUsers.map((u) => (
                <div key={u.attendance_id} className="flex items-center justify-between p-3 border-b border-[#21362A] last:border-0">
                  <div>
                    <div className="text-sm">{u.user_name}</div>
                    <div className="text-xs text-[#A1B4A8]">Since {new Date(u.punch_in).toLocaleTimeString()}</div>
                  </div>
                  <Badge className={`border ${stateStyle[u.state]}`}>{u.state.replace("_", " ")}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
            <CardHeader><CardTitle className="font-display text-2xl">Activity</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm" data-testid="activity-feed">
              {logs.map((l) => (
                <div key={l.id} className="flex justify-between gap-2 py-1 border-b border-[#21362A] last:border-0">
                  <div className="truncate">
                    <span className="text-[#D4AF37]">{l.event_type}</span>{" "}
                    <span className="text-[#A1B4A8]">{l.detail?.name || l.item_id?.slice(0, 8) || ""}</span>
                  </div>
                  <div className="text-xs text-[#A1B4A8] shrink-0">{new Date(l.timestamp).toLocaleTimeString()}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>

        <section>
          <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
            <CardHeader><CardTitle className="font-display text-2xl">Recent products</CardTitle></CardHeader>
            <CardContent>
              <table className="w-full text-sm" data-testid="recent-products-table">
                <thead className="text-[#A1B4A8] text-xs uppercase tracking-widest">
                  <tr><th className="text-left py-2">Name</th><th className="text-left">Category</th><th className="text-left">Worker</th><th className="text-right">Price</th><th className="text-right">Status</th></tr>
                </thead>
                <tbody>
                  {recent.map((p) => (
                    <tr key={p.id} className="border-t border-[#21362A]">
                      <td className="py-2">{p.name}</td>
                      <td className="text-[#A1B4A8]">{p.category}</td>
                      <td className="text-[#A1B4A8]">{p.generated_by_name}</td>
                      <td className="text-right font-display text-[#D4AF37]">${p.final_price}</td>
                      <td className="text-right"><Badge className="bg-[#132018] border border-[#21362A] text-[#A1B4A8]">{p.status}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </section>
      </div>
    </AdminLayout>
  );
}

function Kpi({ icon: Icon, label, value, tone, ...rest }) {
  return (
    <Card className="bg-[#0C140F] border-[#21362A] rounded-sm" {...rest}>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div className="label-overline">{label}</div>
          {Icon && <Icon className={`w-4 h-4 ${tone === "danger" ? "text-[#E63946]" : "text-[#D4AF37]"}`} />}
        </div>
        <div className="font-display text-4xl mt-3">{value}</div>
      </CardContent>
    </Card>
  );
}
