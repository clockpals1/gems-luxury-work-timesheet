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
  const [selectedImages, setSelectedImages] = useState(new Set());
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupCategory, setGroupCategory] = useState("");
  const [groupTags, setGroupTags] = useState("");
  const [creatingGroup, setCreatingGroup] = useState(false);
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

  const handleDelete = async (id) => {
    if (!confirm("Are you sure you want to delete this image?")) return;
    try {
      await api.delete(`/admin/images/${id}`);
      toast.success("Image deleted");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to delete image");
    }
  };

  const toggleImageSelection = (id) => {
    const newSelected = new Set(selectedImages);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedImages(newSelected);
  };

  const handleCreateGroup = async () => {
    if (selectedImages.size === 0) {
      toast.error("Select at least one image to create a group");
      return;
    }
    if (!groupName) {
      toast.error("Enter a group name");
      return;
    }
    setCreatingGroup(true);
    try {
      const r = await api.post("/admin/product-groups/create-from-images", {
        image_ids: Array.from(selectedImages),
        folder_name: groupName,
        category: groupCategory,
        tags: groupTags ? groupTags.split(",").map(t => t.trim()) : []
      });
      toast.success("Product group created successfully");
      setShowGroupModal(false);
      setSelectedImages(new Set());
      setGroupName("");
      setGroupCategory("");
      setGroupTags("");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to create product group");
    } finally {
      setCreatingGroup(false);
    }
  };

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
        <div className="flex gap-2">
          {selectedImages.size > 0 && (
            <Button onClick={() => setShowGroupModal(true)} variant="outline" className="border-[#097969] text-[#2A9D8F] hover:bg-[#097969]/10">
              Create Group ({selectedImages.size})
            </Button>
          )}
          <Button onClick={handleClearAll} variant="outline" className="border-[#E63946] text-[#E63946] hover:bg-[#E63946]/10">
            <Trash2 className="w-4 h-4 mr-2"/>Clear All Images
          </Button>
        </div>
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
            <div className="relative">
              <input
                type="checkbox"
                checked={selectedImages.has(img.id)}
                onChange={() => toggleImageSelection(img.id)}
                className="absolute top-2 left-2 z-10 w-5 h-5 cursor-pointer accent-[#D4AF37]"
              />
              <button type="button" onClick={() => setOpenId(img.id)} className="aspect-square bg-[#132018] flex items-center justify-center overflow-hidden block w-full" data-testid={`open-img-${img.id}`}>
                <img src={imgUrl(img.id)} alt={img.filename} className="w-full h-full object-cover"/>
              </button>
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
              <div className="flex gap-2">
                <Button size="sm" variant="outline" className="border-[#21362A] flex-1 text-xs" onClick={() => setOpenId(img.id)} data-testid={`open-btn-${img.id}`}><Layers className="w-3 h-3 mr-1"/>Variations</Button>
                <Button size="sm" variant="outline" className="border-[#E63946] text-[#E63946] hover:bg-[#E63946]/10 text-xs px-2" onClick={() => handleDelete(img.id)}><Trash2 className="w-3 h-3"/></Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <ImageVariationsDialog id={openId} open={!!openId} onOpenChange={(v) => !v && setOpenId(null)}/>

      {/* Create Group Modal */}
      {showGroupModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0C140F] border-[#21362A] rounded-sm max-w-md w-full">
            <div className="p-6 space-y-4">
              <h3 className="font-display text-xl">Create Product Group</h3>
              <div className="space-y-2">
                <Label className="label-overline">Group Name</Label>
                <Input 
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  placeholder="e.g. Summer Collection 2024"
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <Label className="label-overline">Category (optional)</Label>
                <Input 
                  value={groupCategory}
                  onChange={(e) => setGroupCategory(e.target.value)}
                  placeholder="e.g. Dresses"
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <Label className="label-overline">Tags (optional, comma-separated)</Label>
                <Input 
                  value={groupTags}
                  onChange={(e) => setGroupTags(e.target.value)}
                  placeholder="e.g. summer, casual, cotton"
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="text-sm text-[#A1B4A8]">
                {selectedImages.size} image(s) selected
              </div>
              <div className="flex gap-3 pt-4">
                <Button onClick={() => setShowGroupModal(false)} variant="outline" className="flex-1 border-[#21362A] text-[#A1B4A8]">
                  Cancel
                </Button>
                <Button onClick={handleCreateGroup} disabled={creatingGroup} className="flex-1 bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]">
                  {creatingGroup ? "Creating..." : "Create Group"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
