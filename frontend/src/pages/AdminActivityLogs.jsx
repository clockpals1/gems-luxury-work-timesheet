import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent } from "../components/ui/card";

export default function AdminActivityLogs() {
  const [logs, setLogs] = useState([]);
  useEffect(() => { api.get("/admin/activity-logs?limit=400").then(r => setLogs(r.data)); }, []);
  return (
    <AdminLayout>
      <div className="mb-6"><div className="label-overline text-[#D4AF37]">Audit</div><h1 className="font-display text-4xl mt-2">Activity logs</h1></div>
      <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="activity-table">
            <thead className="text-[#A1B4A8] text-xs uppercase tracking-widest">
              <tr><th className="text-left p-4">When</th><th className="text-left">User</th><th className="text-left">Event</th><th className="text-left">Target</th><th className="text-left p-4">Detail</th></tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-t border-[#21362A]">
                  <td className="p-4 text-[#A1B4A8] text-xs">{new Date(l.timestamp).toLocaleString()}</td>
                  <td className="text-[#A1B4A8] text-xs">{l.user_id?.slice(0,8)}</td>
                  <td className="text-[#D4AF37]">{l.event_type}</td>
                  <td className="text-[#A1B4A8] text-xs">{l.item_type || ""} {l.item_id?.slice(0,8) || ""}</td>
                  <td className="p-4 text-[#A1B4A8] text-xs font-mono">{JSON.stringify(l.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </AdminLayout>
  );
}
