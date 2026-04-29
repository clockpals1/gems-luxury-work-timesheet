import React, { useEffect, useRef, useState } from "react";
import { api, imgUrl } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Upload, Sparkles } from "lucide-react";

export default function AdminImages() {
  const [items, setItems] = useState([]);
  const [category, setCategory] = useState("");
  const [tags, setTags] = useState("");
  const fileRef = useRef(null);

  const load = async () => { const r = await api.get("/admin/images"); setItems(r.data); };
  useEffect(() => { load(); }, []);

  const onUpload = async (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    const fd = new FormData();
    fd.append("file", file); fd.append("category", category); fd.append("tags", tags);
    try {
      await api.post("/admin/images/upload", fd, { headers: { "Content-Type": "multipart/form-data" }});
      toast.success("Image uploaded"); load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Upload failed"); }
    if (fileRef.current) fileRef.current.value = "";
  };

  const setStatus = async (id, status) => { await api.patch(`/admin/images/${id}`, { status }); load(); };
  const enhance = async (id) => { try { toast.message("Enhancing image (this may take a moment)…"); await api.post(`/admin/images/${id}/enhance`); toast.success("Enhanced variation added"); } catch { toast.error("Enhance failed"); } };
  const alts = async (id) => { try { toast.message("Generating alternate views…"); await api.post(`/admin/images/${id}/alternates`); toast.success("Alternates ready"); } catch { toast.error("Failed"); } };

  return (
    <AdminLayout>
      <div className="flex items-end justify-between mb-6">
        <div><div className="label-overline text-[#D4AF37]">Library</div><h1 className="font-display text-4xl mt-2">Images</h1></div>
      </div>
      <Card className="bg-[#0C140F] border-[#21362A] rounded-sm mb-6">
        <CardHeader><CardTitle className="font-display text-xl">Upload</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-3 flex-wrap items-center">
            <Input placeholder="Category (optional)" value={category} onChange={(e) => setCategory(e.target.value)} className="bg-[#132018] border-[#21362A] w-60" data-testid="upload-category"/>
            <Input placeholder="Tags (comma separated)" value={tags} onChange={(e) => setTags(e.target.value)} className="bg-[#132018] border-[#21362A] flex-1 min-w-[200px]" data-testid="upload-tags"/>
            <input ref={fileRef} type="file" accept="image/*" onChange={onUpload} hidden data-testid="upload-file-input"/>
            <Button onClick={() => fileRef.current?.click()} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" data-testid="upload-btn"><Upload className="w-4 h-4 mr-2"/>Upload image</Button>
          </div>
        </CardContent>
      </Card>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4" data-testid="images-grid">
        {items.map((img) => (
          <Card key={img.id} className="bg-[#0C140F] border-[#21362A] rounded-sm overflow-hidden">
            <div className="aspect-square bg-[#132018] flex items-center justify-center overflow-hidden">
              <img src={imgUrl(img.id)} alt={img.filename} className="w-full h-full object-cover"/>
            </div>
            <CardContent className="p-3 space-y-2">
              <div className="text-xs truncate">{img.filename}</div>
              <div className="flex flex-wrap gap-1">{(img.tags || []).slice(0,3).map(t => <Badge key={t} className="bg-[#132018] border border-[#21362A] text-[#A1B4A8] text-[10px]">{t}</Badge>)}</div>
              <Select value={img.status} onValueChange={(v) => setStatus(img.id, v)}>
                <SelectTrigger className="bg-[#132018] border-[#21362A] h-8 text-xs" data-testid={`status-${img.id}`}><SelectValue/></SelectTrigger>
                <SelectContent className="bg-[#0C140F] border-[#21362A] text-white">
                  {["available","assigned","skipped","needs_review","archived"].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
              <div className="flex gap-1">
                <Button size="sm" variant="outline" className="border-[#21362A] flex-1 text-xs" onClick={() => enhance(img.id)} data-testid={`enhance-${img.id}`}><Sparkles className="w-3 h-3 mr-1"/>Enhance</Button>
                <Button size="sm" variant="outline" className="border-[#21362A] flex-1 text-xs" onClick={() => alts(img.id)} data-testid={`alts-${img.id}`}>Alts</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </AdminLayout>
  );
}
