import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Upload, Folder, Eye, Check, AlertTriangle } from "lucide-react";

export default function AdminProductGroups() {
  const navigate = useNavigate();
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [filters, setFilters] = useState({
    review_status: "all"
  });
  const [showUpload, setShowUpload] = useState(false);
  const [uploadForm, setUploadForm] = useState({
    folder_name: "",
    category: "",
    tags: "",
    files: []
  });

  useEffect(() => {
    loadGroups();
  }, [filters]);

  const loadGroups = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.review_status !== "all") params.append("review_status", filters.review_status);
      
      const r = await api.get(`/admin/product-groups?${params.toString()}`);
      setGroups(r.data);
    } catch (e) {
      toast.error("Failed to load product groups");
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    setUploadForm({ ...uploadForm, files: selectedFiles });
  };

  const handleUpload = async () => {
    if (!uploadForm.folder_name) {
      toast.error("Folder name is required");
      return;
    }
    if (uploadForm.files.length < 2) {
      toast.error("At least 2 images required");
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("folder_name", uploadForm.folder_name);
      if (uploadForm.category) formData.append("category", uploadForm.category);
      if (uploadForm.tags) formData.append("tags", uploadForm.tags);
      uploadForm.files.forEach(file => formData.append("files", file));

      const r = await api.post("/admin/product-groups/upload-folder", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      
      toast.success(`Uploaded ${uploadForm.files.length} images as product group`);
      setUploadForm({ folder_name: "", category: "", tags: "", files: [] });
      setShowUpload(false);
      loadGroups();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: "bg-yellow-500/20 text-yellow-300",
      reviewed: "bg-blue-500/20 text-blue-300",
      approved: "bg-green-500/20 text-green-300",
      needs_review: "bg-red-500/20 text-red-300"
    };
    return colors[status] || "bg-gray-500/20 text-gray-300";
  };

  if (loading) return <AdminLayout><div className="text-[#A1B4A8]">Loading...</div></AdminLayout>;

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="label-overline text-[#D4AF37]">Product Groups</div>
            <h1 className="font-display text-4xl mt-2">Folder Ingestion</h1>
          </div>
          <Button onClick={() => setShowUpload(true)} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]">
            <Upload className="w-4 h-4 mr-2"/>Upload Folder
          </Button>
        </div>

        {/* Upload Modal */}
        {showUpload && (
          <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
            <CardHeader><CardTitle className="font-display text-xl">Upload Product Group</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="label-overline text-xs">Folder Name</label>
                <Input 
                  value={uploadForm.folder_name}
                  onChange={(e) => setUploadForm({ ...uploadForm, folder_name: e.target.value })}
                  placeholder="e.g., Summer-Dress-Collection-001"
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <label className="label-overline text-xs">Category (optional)</label>
                <Input 
                  value={uploadForm.category}
                  onChange={(e) => setUploadForm({ ...uploadForm, category: e.target.value })}
                  placeholder="e.g., Women / Dresses"
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <label className="label-overline text-xs">Tags (optional, comma-separated)</label>
                <Input 
                  value={uploadForm.tags}
                  onChange={(e) => setUploadForm({ ...uploadForm, tags: e.target.value })}
                  placeholder="e.g., summer, casual, cotton"
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <label className="label-overline text-xs">Images (2-10 required)</label>
                <input
                  type="file"
                  multiple
                  accept="image/jpeg,image/jpg,image/png,image/webp"
                  onChange={handleFileSelect}
                  className="w-full bg-[#132018] border-[#21362A] rounded p-2 text-[#A1B4A8]"
                />
                <div className="text-xs text-[#A1B4A8]">{uploadForm.files.length} files selected</div>
              </div>
              <div className="flex gap-2">
                <Button onClick={handleUpload} disabled={uploading} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]">
                  {uploading ? "Uploading..." : "Upload"}
                </Button>
                <Button onClick={() => setShowUpload(false)} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Filters */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardContent className="pt-6">
            <div className="flex gap-4">
              <div className="space-y-2">
                <label className="label-overline text-xs">Review Status</label>
                <Select value={filters.review_status} onValueChange={(v) => setFilters({ ...filters, review_status: v })}>
                  <SelectTrigger className="bg-[#132018] border-[#21362A] w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="reviewed">Reviewed</SelectItem>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="needs_review">Needs Review</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Product Groups List */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Product Groups ({groups.length})</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              {groups.map((group) => (
                <div key={group.id} className="flex items-center justify-between p-4 border border-[#21362A] rounded-sm hover:bg-[#132018]/50">
                  <div className="flex items-center gap-4">
                    <Folder className="w-8 h-8 text-[#D4AF37]" />
                    <div>
                      <div className="text-sm font-semibold">{group.folder_name}</div>
                      <div className="text-xs text-[#A1B4A8]">
                        {group.image_count} images • {group.category || "No category"} • Uploaded by {group.uploaded_by_name}
                      </div>
                      <div className="text-xs text-[#A1B4A8]">{new Date(group.uploaded_at).toLocaleString()}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {group.flags && group.flags.length > 0 && (
                      <Badge className="bg-[#E63946]/20 text-[#E63946] flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        {group.flags.length} flags
                      </Badge>
                    )}
                    <Badge className={getStatusColor(group.review_status)}>{group.review_status}</Badge>
                    <Button 
                      onClick={() => navigate(`/admin/product-groups/${group.id}`)}
                      variant="outline" 
                      size="sm"
                      className="border-[#21362A] text-[#A1B4A8]"
                    >
                      <Eye className="w-4 h-4 mr-2"/>Review
                    </Button>
                  </div>
                </div>
              ))}
              {groups.length === 0 && (
                <div className="text-center py-8 text-[#A1B4A8]">No product groups found. Upload a folder to get started.</div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}
