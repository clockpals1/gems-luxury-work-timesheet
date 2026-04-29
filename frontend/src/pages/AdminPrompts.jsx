import React, { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Sparkles, Save } from "lucide-react";

const PROVIDERS = {
  anthropic: ["claude-sonnet-4-5-20250929", "claude-opus-4-5-20251101", "claude-haiku-4-5-20251001"],
  openai: ["gpt-5.2", "gpt-5", "gpt-4o"],
  gemini: ["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview", "gemini-3-flash-preview"],
};

export default function AdminPrompts() {
  const [items, setItems] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const r = await api.get("/admin/prompts");
    setItems(r.data);
    if (!activeId && r.data.length) {
      setActiveId(r.data[0].id);
      setDraft(r.data[0]);
    }
  }, [activeId]);
  useEffect(() => { load(); }, [load]);

  const select = (it) => { setActiveId(it.id); setDraft({ ...it }); };

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      await api.patch(`/admin/prompts/${draft.id}`, {
        name: draft.name,
        description: draft.description,
        model_provider: draft.model_provider,
        model_name: draft.model_name,
        system_prompt: draft.system_prompt,
        user_prompt_template: draft.user_prompt_template,
        enabled: draft.enabled,
      });
      toast.success("Prompt saved");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  return (
    <AdminLayout>
      <div className="mb-6">
        <div className="label-overline text-[#D4AF37]">AI brain</div>
        <h1 className="font-display text-4xl mt-2">Prompt templates</h1>
        <p className="text-sm text-[#A1B4A8] mt-2">
          Manage the AI system + user prompts that drive product generation and image edits.
          Use <span className="text-white font-mono">{"{{placeholder}}"}</span> for variables (category, families_text, min_price, max_price, currency, category_multiplier, image_hint, avoid_names, view, size_template).
        </p>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="space-y-2 lg:col-span-1" data-testid="prompt-list">
          {items.map((p) => (
            <button key={p.id} type="button" onClick={() => select(p)} data-testid={`prompt-${p.key}`}
              className={`w-full text-left p-3 rounded-sm border transition-colors ${
                p.id === activeId ? "border-[#D4AF37] bg-[#132018]" : "border-[#21362A] hover:bg-[#0C140F]"
              }`}>
              <div className="flex items-center gap-2">
                <Sparkles className="w-3 h-3 text-[#D4AF37]"/>
                <div className="font-medium text-sm">{p.name}</div>
              </div>
              <div className="label-overline text-[10px] mt-1">{p.key}</div>
              <div className="flex gap-2 mt-2">
                <Badge className="bg-[#132018] border border-[#21362A] text-[#A1B4A8] text-[10px]">{p.model_provider}</Badge>
                {p.enabled ? <Badge className="bg-[#097969]/20 text-[#2A9D8F] border border-[#097969]/40 text-[10px]">on</Badge> : <Badge className="bg-[#E63946]/15 text-[#E63946] border border-[#E63946]/30 text-[10px]">off</Badge>}
              </div>
            </button>
          ))}
        </div>
        <div className="lg:col-span-3">
          {draft && (
            <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="font-display text-2xl">{draft.name}</CardTitle>
                  <div className="flex items-center gap-2"><Label className="text-xs">Enabled</Label><Switch checked={!!draft.enabled} onCheckedChange={(v) => setDraft({ ...draft, enabled: v })} data-testid="prompt-enabled"/></div>
                </div>
                <div className="label-overline">{draft.key}</div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2"><Label className="label-overline">Name</Label><Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className="bg-[#132018] border-[#21362A]" data-testid="prompt-name"/></div>
                <div className="space-y-2"><Label className="label-overline">Description</Label><Input value={draft.description || ""} onChange={(e) => setDraft({ ...draft, description: e.target.value })} className="bg-[#132018] border-[#21362A]" data-testid="prompt-desc"/></div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2"><Label className="label-overline">Provider</Label>
                    <Select value={draft.model_provider} onValueChange={(v) => setDraft({ ...draft, model_provider: v, model_name: PROVIDERS[v]?.[0] || draft.model_name })}>
                      <SelectTrigger className="bg-[#132018] border-[#21362A]" data-testid="prompt-provider"><SelectValue/></SelectTrigger>
                      <SelectContent className="bg-[#0C140F] border-[#21362A] text-white">
                        {Object.keys(PROVIDERS).map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2"><Label className="label-overline">Model</Label>
                    <Select value={draft.model_name} onValueChange={(v) => setDraft({ ...draft, model_name: v })}>
                      <SelectTrigger className="bg-[#132018] border-[#21362A]" data-testid="prompt-model"><SelectValue/></SelectTrigger>
                      <SelectContent className="bg-[#0C140F] border-[#21362A] text-white">
                        {(PROVIDERS[draft.model_provider] || []).map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2"><Label className="label-overline">System prompt</Label>
                  <Textarea rows={4} value={draft.system_prompt} onChange={(e) => setDraft({ ...draft, system_prompt: e.target.value })} className="bg-[#132018] border-[#21362A] font-mono text-xs" data-testid="prompt-system"/></div>
                <div className="space-y-2"><Label className="label-overline">User prompt template</Label>
                  <Textarea rows={14} value={draft.user_prompt_template} onChange={(e) => setDraft({ ...draft, user_prompt_template: e.target.value })} className="bg-[#132018] border-[#21362A] font-mono text-xs" data-testid="prompt-user"/></div>
                <Button onClick={save} disabled={saving} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" data-testid="prompt-save"><Save className="w-4 h-4 mr-2"/>{saving ? "Saving…" : "Save prompt"}</Button>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </AdminLayout>
  );
}
