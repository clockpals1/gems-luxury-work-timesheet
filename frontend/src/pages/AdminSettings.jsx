import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";

export default function AdminSettings() {
  const [s, setS] = useState({ idle_timeout_minutes: 60, warning_seconds: 300, max_break_minutes: 30, currency: "USD", features: {} });
  useEffect(() => { api.get("/admin/settings").then(r => setS(prev => ({ ...prev, ...r.data }))); }, []);
  const save = async () => {
    try { await api.patch("/admin/settings", s); toast.success("Settings saved"); }
    catch { toast.error("Failed"); }
  };
  const feat = (k, v) => setS({ ...s, features: { ...(s.features || {}), [k]: v } });
  return (
    <AdminLayout>
      <div className="mb-6"><div className="label-overline text-[#D4AF37]">Configuration</div><h1 className="font-display text-4xl mt-2">Settings</h1></div>
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Idle & breaks</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2"><Label className="label-overline">Idle timeout (minutes)</Label><Input type="number" value={s.idle_timeout_minutes || 60} onChange={(e) => setS({ ...s, idle_timeout_minutes: Number(e.target.value) })} className="bg-[#132018] border-[#21362A]" data-testid="setting-idle"/></div>
            <div className="space-y-2"><Label className="label-overline">Warning seconds</Label><Input type="number" value={s.warning_seconds || 300} onChange={(e) => setS({ ...s, warning_seconds: Number(e.target.value) })} className="bg-[#132018] border-[#21362A]" data-testid="setting-warning"/></div>
            <div className="space-y-2"><Label className="label-overline">Max break minutes</Label><Input type="number" value={s.max_break_minutes || 30} onChange={(e) => setS({ ...s, max_break_minutes: Number(e.target.value) })} className="bg-[#132018] border-[#21362A]" data-testid="setting-break"/></div>
            <div className="space-y-2"><Label className="label-overline">Currency</Label><Input value={s.currency || "USD"} onChange={(e) => setS({ ...s, currency: e.target.value })} className="bg-[#132018] border-[#21362A]" data-testid="setting-currency"/></div>
          </CardContent>
        </Card>
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Feature toggles</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {[
              ["ai_images","AI image enhancement"],
              ["alternates","Alternate views generation"],
              ["admin_pricing_reveal","Admin can see pricing reasoning"],
            ].map(([k,label]) => (
              <div key={k} className="flex items-center justify-between">
                <Label>{label}</Label>
                <Switch checked={!!(s.features || {})[k]} onCheckedChange={(v) => feat(k, v)} data-testid={`feat-${k}`}/>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
      <div className="mt-6"><Button className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" onClick={save} data-testid="settings-save">Save settings</Button></div>
    </AdminLayout>
  );
}
