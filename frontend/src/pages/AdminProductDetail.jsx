import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, imgUrl } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { ArrowLeft, Download, Save, Check, X, Edit2 } from "lucide-react";

export default function AdminProductDetail() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [product, setProduct] = useState(null);
  const [images, setImages] = useState({});
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState({});

  useEffect(() => {
    loadDetail();
  }, [productId]);

  const loadDetail = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/products/${productId}/detail`);
      setProduct(r.data.product);
      setImages(r.data.images);
      setFormData(r.data.product);
    } catch (e) {
      toast.error("Failed to load product details");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.patch(`/products/${productId}`, formData);
      toast.success("Product updated successfully");
      setEditing(false);
      loadDetail();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to update product");
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async () => {
    try {
      await api.post(`/products/${productId}/approve`);
      toast.success("Product approved for export");
      loadDetail();
    } catch (e) {
      toast.error("Failed to approve product");
    }
  };

  const handleReject = async () => {
    try {
      await api.post(`/products/${productId}/reject`);
      toast.success("Product rejected");
      loadDetail();
    } catch (e) {
      toast.error("Failed to reject product");
    }
  };

  const handleSetBaseImage = (imageId) => {
    setFormData({ ...formData, base_image_id: imageId, source_image_id: imageId });
  };

  const handleToggleAdditionalImage = (imageId) => {
    const current = formData.additional_image_ids || [];
    const newAdditional = current.includes(imageId)
      ? current.filter(id => id !== imageId)
      : [...current, imageId];
    setFormData({ ...formData, additional_image_ids: newAdditional });
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: "bg-gray-500/20 text-gray-300",
      approved: "bg-green-500/20 text-green-300",
      exported: "bg-blue-500/20 text-blue-300",
      rejected: "bg-red-500/20 text-red-300"
    };
    return colors[status] || "bg-gray-500/20 text-gray-300";
  };

  if (loading) return <AdminLayout><div className="text-[#A1B4A8]">Loading...</div></AdminLayout>;

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button onClick={() => navigate("/admin/csv-queue")} variant="ghost" className="text-[#A1B4A8]">
            <ArrowLeft className="w-4 h-4 mr-2"/>Back to Queue
          </Button>
          <div>
            <div className="label-overline text-[#D4AF37]">Product Review</div>
            <h1 className="font-display text-4xl mt-2">{product?.name}</h1>
          </div>
        </div>

        {/* Status and Actions */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex gap-3">
                <Badge className={getStatusColor(product?.export_status)}>{product?.export_status || "pending"}</Badge>
                <Badge className="bg-[#132018] text-[#A1B4A8] border border-[#21362A]">{product?.image_workflow_status || "assigned"}</Badge>
              </div>
              <div className="flex gap-2">
                {editing ? (
                  <>
                    <Button onClick={handleSave} disabled={saving} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]">
                      <Save className="w-4 h-4 mr-2"/>{saving ? "Saving..." : "Save"}
                    </Button>
                    <Button onClick={() => { setEditing(false); setFormData(product); }} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
                      Cancel
                    </Button>
                  </>
                ) : (
                  <>
                    <Button onClick={() => setEditing(true)} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
                      <Edit2 className="w-4 h-4 mr-2"/>Edit
                    </Button>
                    {product?.export_status !== "approved" && product?.export_status !== "exported" && (
                      <Button onClick={handleApprove} className="bg-[#097969] hover:bg-[#0a8a78]">
                        <Check className="w-4 h-4 mr-2"/>Approve
                      </Button>
                    )}
                    {product?.export_status !== "rejected" && (
                      <Button onClick={handleReject} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
                        <X className="w-4 h-4 mr-2"/>Reject
                      </Button>
                    )}
                  </>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Product Details */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Product Information</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="label-overline">Name</Label>
                <Input 
                  value={formData.name || ""} 
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  disabled={!editing}
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <Label className="label-overline">SKU</Label>
                <Input 
                  value={formData.sku || ""} 
                  onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                  disabled={!editing}
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <Label className="label-overline">Category</Label>
                <Input 
                  value={formData.category || ""} 
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  disabled={!editing}
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <Label className="label-overline">Brand</Label>
                <Input 
                  value={formData.brand || ""} 
                  onChange={(e) => setFormData({ ...formData, brand: e.target.value })}
                  disabled={!editing}
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <Label className="label-overline">Price</Label>
                <Input 
                  type="number"
                  value={formData.final_price || ""} 
                  onChange={(e) => setFormData({ ...formData, final_price: Number(e.target.value) })}
                  disabled={!editing}
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
              <div className="space-y-2">
                <Label className="label-overline">Tax Class</Label>
                <Input 
                  value={formData.tax_class || ""} 
                  onChange={(e) => setFormData({ ...formData, tax_class: e.target.value })}
                  disabled={!editing}
                  className="bg-[#132018] border-[#21362A]"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label className="label-overline">Short Description</Label>
              <textarea
                value={formData.short_description || ""}
                onChange={(e) => setFormData({ ...formData, short_description: e.target.value })}
                disabled={!editing}
                className="w-full bg-[#132018] border-[#21362A] rounded p-3 text-[#A1B4A8] min-h-[80px]"
              />
            </div>
            <div className="space-y-2">
              <Label className="label-overline">Full Description</Label>
              <textarea
                value={formData.full_description || ""}
                onChange={(e) => setFormData({ ...formData, full_description: e.target.value })}
                disabled={!editing}
                className="w-full bg-[#132018] border-[#21362A] rounded p-3 text-[#A1B4A8] min-h-[150px]"
              />
            </div>
            <div className="space-y-2">
              <Label className="label-overline">Tags (comma-separated)</Label>
              <Input 
                value={(formData.tags || []).join(", ")} 
                onChange={(e) => setFormData({ ...formData, tags: e.target.value.split(", ").filter(t => t) })}
                disabled={!editing}
                className="bg-[#132018] border-[#21362A]"
              />
            </div>
          </CardContent>
        </Card>

        {/* Image Mapping */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Image Mapping</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="label-overline">Base Image</Label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(images).map(([id, img]) => (
                  <div 
                    key={id}
                    onClick={() => editing && handleSetBaseImage(id)}
                    className={`relative cursor-pointer border-2 rounded-lg overflow-hidden ${
                      formData.base_image_id === id ? "border-[#D4AF37]" : "border-[#21362A]"
                    }`}
                  >
                    <img src={imgUrl(id)} alt={img.filename} className="w-full aspect-square object-cover"/>
                    {formData.base_image_id === id && (
                      <div className="absolute top-2 right-2 bg-[#D4AF37] text-[#050A07] text-xs px-2 py-1 rounded">Base</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label className="label-overline">Additional Images</Label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(images).map(([id, img]) => (
                  <div 
                    key={id}
                    onClick={() => editing && handleToggleAdditionalImage(id)}
                    className={`relative cursor-pointer border-2 rounded-lg overflow-hidden ${
                      (formData.additional_image_ids || []).includes(id) ? "border-[#D4AF37]" : "border-[#21362A] opacity-50"
                    }`}
                  >
                    <img src={imgUrl(id)} alt={img.filename} className="w-full aspect-square object-cover"/>
                    {(formData.additional_image_ids || []).includes(id) && (
                      <div className="absolute top-2 right-2 bg-[#097969] text-white text-xs px-2 py-1 rounded">Additional</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Worker Information */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader><CardTitle className="font-display text-xl">Worker Information</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <Label className="label-overline">Worker Name</Label>
                <div className="text-[#A1B4A8]">{product?.generated_by_name}</div>
              </div>
              <div>
                <Label className="label-overline">Generated At</Label>
                <div className="text-[#A1B4A8]">{new Date(product?.generated_at).toLocaleString()}</div>
              </div>
              <div>
                <Label className="label-overline">Session ID</Label>
                <div className="text-[#A1B4A8]">{product?.session_id || "-"}</div>
              </div>
              <div>
                <Label className="label-overline">Punch Status</Label>
                <div className="text-[#A1B4A8]">{product?.punch_status_at_generation || "-"}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}
