import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";

export default function AdminNaming() {
  const [families, setFamilies] = useState([]);
  const [newName, setNewName] = useState("");
  const [newWords, setNewWords] = useState("");
  const load = async () => { const r = await api.get("/admin/naming-families"); setFamilies(r.data); };
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/naming-families", { name: newName, words: newWords.split(",").map(w => w.trim()).filter(Boolean), enabled: true });
      setNewName(""); setNewWords(""); toast.success("Family added"); load();
    } catch { toast.error("Failed"); }
  };

  const save = async (f) => {
    try { await api.patch(`/admin/naming-families/${f.id}`, { name: f.name, words: f.words, enabled: f.enabled }); toast.success("Saved"); }
    catch { toast.error("Failed"); }
  };

  return (
    <AdminLayout>
      <div className="mb-6">
        <div className="label-overline text-[#D4AF37]">Brand language</div>
        <h1 className="font-display text-4xl mt-2">Naming families</h1>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm md:col-span-2">
          <CardHeader><CardTitle className="font-display text-2xl">New family</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={create} className="flex gap-3 flex-wrap" data-testid="family-form">
              <Input placeholder="Family name (e.g. Heritage)" value={newName} onChange={(e) => setNewName(e.target.value)} required className="bg-[#132018] border-[#21362A] flex-1 min-w-[200px]" data-testid="family-name"/>
              <Input placeholder="Words (comma separated)" value={newWords} onChange={(e) => setNewWords(e.target.value)} className="bg-[#132018] border-[#21362A] flex-1 min-w-[260px]" data-testid="family-words"/>
              <Button type="submit" className="bg-[#D4AF37] text-[#050A07] hover:bg-[#F0C84A]" data-testid="family-submit">Add</Button>
            </form>
          </CardContent>
        </Card>
        {families.map((f, i) => (
          <Card key={f.id} className="bg-[#0C140F] border-[#21362A] rounded-sm">
            <CardContent className="p-5 space-y-3">
              <div className="flex items-center justify-between">
                <Input value={f.name} onChange={(e) => { const c = [...families]; c[i] = { ...c[i], name: e.target.value }; setFamilies(c); }}
                  className="bg-[#132018] border-[#21362A] font-display text-lg" data-testid={`family-name-${f.id}`}/>
                <Switch checked={!!f.enabled} onCheckedChange={(v) => { const c = [...families]; c[i] = { ...c[i], enabled: v }; setFamilies(c); save({ ...c[i] }); }} data-testid={`family-toggle-${f.id}`}/>
              </div>
              <Input value={(f.words || []).join(", ")}
                onChange={(e) => { const c = [...families]; c[i] = { ...c[i], words: e.target.value.split(",").map(w => w.trim()).filter(Boolean) }; setFamilies(c); }}
                className="bg-[#132018] border-[#21362A] text-sm" data-testid={`family-words-${f.id}`}/>
              <div className="flex flex-wrap gap-1">
                {(f.words || []).slice(0, 10).map((w) => <Badge key={w} className="bg-[#132018] border border-[#21362A] text-[#A1B4A8]">{w}</Badge>)}
              </div>
              <Button size="sm" variant="outline" className="border-[#21362A]" onClick={() => save(f)} data-testid={`family-save-${f.id}`}>Save</Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </AdminLayout>
  );
}
