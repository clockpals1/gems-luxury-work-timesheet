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
  const [s, setS] = useState({ idle_timeout_minutes: 60, warning_seconds: 300, max_break_minutes: 30, currency: "USD", features: {}, ai: {} });
  const [aiSettings, setAiSettings] = useState({ text_provider: "huggingface", image_provider: "huggingface", huggingface_text_model: "meta-llama/Meta-Llama-3.1-8B-Instruct:fastest", anthropic_api_key: "", gemini_api_key: "", huggingface_api_key: "" });
  useEffect(() => { api.get("/admin/settings").then(r => setS(prev => ({ ...prev, ...r.data }))); }, []);
  useEffect(() => { api.get("/admin/settings/ai").then(r => setAiSettings(r.data)).catch(() => {}); }, []);
  const save = async () => {
    try { await api.patch("/admin/settings", s); toast.success("Settings saved"); }
    catch { toast.error("Failed"); }
  };
  const saveAiSettings = async () => {
    try { await api.patch("/admin/settings/ai", aiSettings); toast.success("AI settings saved"); }
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
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm md:col-span-2">
          <CardHeader><CardTitle className="font-display text-xl">AI Model Settings</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="label-overline">Text Provider</Label>
                <select 
                  value={aiSettings.text_provider || "huggingface"} 
                  onChange={(e) => setAiSettings({ ...aiSettings, text_provider: e.target.value })}
                  className="w-full bg-[#132018] border-[#21362A] rounded p-2 text-[#A1B4A8]"
                >
                  <option value="huggingface">HuggingFace (Free)</option>
                  <option value="anthropic">Anthropic Claude (Requires API Key)</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label className="label-overline">Image Provider</Label>
                <select 
                  value={aiSettings.image_provider || "huggingface"} 
                  onChange={(e) => setAiSettings({ ...aiSettings, image_provider: e.target.value })}
                  className="w-full bg-[#132018] border-[#21362A] rounded p-2 text-[#A1B4A8]"
                >
                  <option value="huggingface">HuggingFace (Free)</option>
                  <option value="gemini">Google Gemini (Requires API Key)</option>
                </select>
              </div>
            </div>
            <div className="space-y-3">
              <div className="space-y-2">
                <Label className="label-overline">HuggingFace Text Model</Label>
                <Input 
                  value={aiSettings.huggingface_text_model || ""} 
                  onChange={(e) => setAiSettings({ ...aiSettings, huggingface_text_model: e.target.value })}
                  placeholder="meta-llama/Meta-Llama-3.1-8B-Instruct:fastest"
                  className="bg-[#132018] border-[#21362A]"
                />
                <div className="text-xs text-[#A1B4A8]">Model ID with policy suffix (e.g., :fastest, :cheapest)</div>
              </div>
              <div className="space-y-2">
                <Label className="label-overline">Anthropic API Key</Label>
                <Input 
                  type="password" 
                  value={aiSettings.anthropic_api_key || ""} 
                  onChange={(e) => setAiSettings({ ...aiSettings, anthropic_api_key: e.target.value })}
                  placeholder="sk-ant-..."
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <Label className="label-overline">Gemini API Key</Label>
                <Input 
                  type="password" 
                  value={aiSettings.gemini_api_key || ""} 
                  onChange={(e) => setAiSettings({ ...aiSettings, gemini_api_key: e.target.value })}
                  placeholder="AIza..."
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <Label className="label-overline">HuggingFace API Key (Optional - improves rate limits)</Label>
                <Input 
                  type="password" 
                  value={aiSettings.huggingface_api_key || ""} 
                  onChange={(e) => setAiSettings({ ...aiSettings, huggingface_api_key: e.target.value })}
                  placeholder="hf_..."
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
      <div className="mt-6 flex gap-3">
        <Button className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" onClick={save} data-testid="settings-save">Save settings</Button>
        <Button className="bg-[#21362A] hover:bg-[#2D4A3C] text-[#A1B4A8]" onClick={saveAiSettings} data-testid="ai-settings-save">Save AI Settings</Button>
      </div>
    </AdminLayout>
  );
}
