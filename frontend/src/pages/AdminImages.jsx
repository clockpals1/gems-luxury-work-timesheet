import React, { useEffect, useRef, useState } from "react";
import { api, imgUrl } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Upload, Layers, Trash2 } from "lucide-react";
import ImageVariationsDialog from "../components/ImageVariationsDialog";

export default function AdminImages() {
  const [items, setItems] = useState([]);
  const [category, setCategory] = useState("");
  const [tags, setTags] = useState("");
  const [openId, setOpenId] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = async () => { const r = await api.get("/admin/images"); setItems(r.data); };
  useEffect(() => { load(); }, []);

  const onUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("category", category); fd.append("tags", tags);
    try {
      const r = await api.post("/admin/images/upload-bulk", fd, { headers: { "Content-Type": "multipart/form-data" }});
      toast.success(`Uploaded ${r.data.count}${r.data.errors?.length ? ` (${r.data.errors.length} failed)` : ""}`);
      load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Upload failed"); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const setStatus = async (id, status) => { await api.patch(`/admin/images/${id}`, { status }); load(); };

  const handleClearAll = async () => {
    if (!confirm("Are you sure you want to delete ALL images from the database? This action cannot be undone.")) return;
    if (!confirm("This will delete ALL image assets and variations. Type 'DELETE' to confirm.")) return;
    try {
      console.log("Calling clear-all endpoint...");
      const r = await api.delete("/admin/images/clear-all");
      console.log("Clear response:", r.data);
      toast.success(`Cleared ${r.data.assets_deleted} image assets and ${r.data.variations_deleted} variations`);
      load();
    } catch (err) {
      console.error("Clear error:", err);
      toast.error(err?.response?.data?.detail || err?.message || "Failed to clear images");
    }
  };

  return (
    <AdminLayout>
      <div className="flex items-end justify-between mb-6">
        <div><div className="label-overline text-[#D4AF37]">Library</div><h1 className="font-display text-4xl mt-2">Images</h1></div>
        <Button onClick={handleClearAll} variant="outline" className="border-[#E63946] text-[#E63946] hover:bg-[#E63946]/10">
          <Trash2 className="w-4 h-4 mr-2"/>Clear All Images
        </Button>
      </div>
      <Card className="bg-[#0C140F] border-[#21362A] rounded-sm mb-6">
        <CardHeader><CardTitle className="font-display text-xl">Upload (multiple supported)</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-3 flex-wrap items-center">
            <Input placeholder="Category (optional)" value={category} onChange={(e) => setCategory(e.target.value)} className="bg-[#132018] border-[#21362A] w-60" data-testid="upload-category"/>
            <Input placeholder="Tags applied to all (comma separated)" value={tags} onChange={(e) => setTags(e.target.value)} className="bg-[#132018] border-[#21362A] flex-1 min-w-[200px]" data-testid="upload-tags"/>
            <input ref={fileRef} type="file" accept="image/*" multiple onChange={onUpload} hidden data-testid="upload-file-input"/>
            <Button onClick={() => fileRef.current?.click()} disabled={uploading} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]" data-testid="upload-btn">
              <Upload className="w-4 h-4 mr-2"/>{uploading ? "Uploading…" : "Upload images"}
            </Button>
          </div>
          <p className="text-xs text-[#A1B4A8] mt-2">Tip: select multiple files in the picker — they will all be uploaded with the same tags &amp; category.</p>
        </CardContent>
      </Card>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4" data-testid="images-grid">
        {items.map((img) => (
          <Card key={img.id} className="bg-[#0C140F] border-[#21362A] rounded-sm overflow-hidden">
            <button type="button" onClick={() => setOpenId(img.id)} className="aspect-square bg-[#132018] flex items-center justify-center overflow-hidden block w-full" data-testid={`open-img-${img.id}`}>
              <img src={imgUrl(img.id)} alt={img.filename} className="w-full h-full object-cover"/>
            </button>
            <CardContent className="p-3 space-y-2">
              <div className="text-xs truncate">{img.filename}</div>
              <div className="flex flex-wrap gap-1">{(img.tags || []).slice(0,3).map(t => <Badge key={t} className="bg-[#132018] border border-[#21362A] text-[#A1B4A8] text-[10px]">{t}</Badge>)}</div>
              <Select value={img.status} onValueChange={(v) => setStatus(img.id, v)}>
                <SelectTrigger className="bg-[#132018] border-[#21362A] h-8 text-xs" data-testid={`status-${img.id}`}><SelectValue/></SelectTrigger>
                <SelectContent className="bg-[#0C140F] border-[#21362A] text-white">
                  {["available","assigned","skipped","needs_review","archived"].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button size="sm" variant="outline" className="border-[#21362A] w-full text-xs" onClick={() => setOpenId(img.id)} data-testid={`open-btn-${img.id}`}><Layers className="w-3 h-3 mr-1"/>Variations</Button>
            </CardContent>
          </Card>
        ))}
      </div>
      <ImageVariationsDialog id={openId} open={!!openId} onOpenChange={(v) => !v && setOpenId(null)}/>
    </AdminLayout>
  );
}
