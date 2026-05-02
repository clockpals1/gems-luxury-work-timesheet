import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, imgUrl } from "../lib/api";
import { AdminLayout } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { toast } from "sonner";
import { ArrowLeft, Star, Check, AlertTriangle, Split } from "lucide-react";

export default function AdminProductGroupDetail() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [group, setGroup] = useState(null);
  const [images, setImages] = useState([]);
  const [baseImageId, setBaseImageId] = useState(null);
  const [additionalImageIds, setAdditionalImageIds] = useState([]);
  const [selectedForSplit, setSelectedForSplit] = useState(new Set());
  const [showSplit, setShowSplit] = useState(false);

  useEffect(() => {
    loadGroup();
  }, [groupId]);

  const loadGroup = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/admin/product-groups/${groupId}`);
      setGroup(r.data.product_group);
      setImages(r.data.images);
      setBaseImageId(r.data.product_group.base_image_id);
      setAdditionalImageIds(r.data.product_group.additional_image_ids || []);
    } catch (e) {
      toast.error("Failed to load product group");
    } finally {
      setLoading(false);
    }
  };

  const handleSetBaseImage = (imageId) => {
    setBaseImageId(imageId);
    // Remove from additional if it was there
    setAdditionalImageIds(prev => prev.filter(id => id !== imageId));
  };

  const handleToggleAdditional = (imageId) => {
    if (imageId === baseImageId) return; // Can't be both base and additional
    
    setAdditionalImageIds(prev => {
      if (prev.includes(imageId)) {
        return prev.filter(id => id !== imageId);
      } else {
        return [...prev, imageId];
      }
    });
  };

  const handleSaveReview = async () => {
    if (!baseImageId) {
      toast.error("Please select a base image");
      return;
    }

    setSaving(true);
    try {
      await api.patch(`/admin/product-groups/${groupId}/review`, {
        base_image_id: baseImageId,
        additional_image_ids: additionalImageIds
      });
      toast.success("Product group reviewed successfully");
      loadGroup();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to save review");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleSplit = (imageId) => {
    const newSelected = new Set(selectedForSplit);
    if (newSelected.has(imageId)) {
      newSelected.delete(imageId);
    } else {
      newSelected.add(imageId);
    }
    setSelectedForSplit(newSelected);
  };

  const handleSplit = async () => {
    if (selectedForSplit.size === 0) {
      toast.error("Select images to split");
      return;
    }
    
    setSaving(true);
    try {
      const r = await api.post(`/admin/product-groups/${groupId}/split`, {
        image_ids: Array.from(selectedForSplit),
        new_group_name: `${group.folder_name}-split`
      });
      toast.success("Product group split successfully");
      setSelectedForSplit(new Set());
      setShowSplit(false);
      loadGroup();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to split");
    } finally {
      setSaving(false);
    }
  };

  const handleConvertToProduct = async () => {
    setSaving(true);
    try {
      const r = await api.post(`/admin/product-groups/${groupId}/convert-to-product`);
      toast.success("Product group converted to product record");
      navigate(`/admin/products/${r.data.product.id}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to convert");
    } finally {
      setSaving(false);
    }
  };

  const suggestBaseImage = () => {
    // Suggest the first image as base if none selected
    if (!baseImageId && images.length > 0) {
      setBaseImageId(images[0].id);
      setAdditionalImageIds(images.slice(1).map(img => img.id));
    }
  };

  if (loading) return <AdminLayout><div className="text-[#A1B4A8]">Loading...</div></AdminLayout>;

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button onClick={() => navigate("/admin/product-groups")} variant="ghost" className="text-[#A1B4A8]">
            <ArrowLeft className="w-4 h-4 mr-2"/>Back to Groups
          </Button>
          <div>
            <div className="label-overline text-[#D4AF37]">Product Group Review</div>
            <h1 className="font-display text-4xl mt-2">{group?.folder_name}</h1>
          </div>
        </div>

        {/* Group Info */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex gap-4">
                <Badge className="bg-[#132018] text-[#A1B4A8] border border-[#21362A]">{group?.category || "No category"}</Badge>
                <Badge className="bg-[#132018] text-[#A1B4A8] border border-[#21362A]">{group?.image_count} images</Badge>
                {group?.flags && group.flags.length > 0 && (
                  <Badge className="bg-[#E63946]/20 text-[#E63946] flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    {group.flags.join(", ")}
                  </Badge>
                )}
              </div>
              <div className="text-sm text-[#A1B4A8]">
                Uploaded by {group?.uploaded_by_name} • {new Date(group?.uploaded_at).toLocaleString()}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex gap-3">
          <Button onClick={suggestBaseImage} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
            <Star className="w-4 h-4 mr-2"/>Auto-suggest Base Image
          </Button>
          <Button onClick={() => setShowSplit(!showSplit)} variant="outline" className="border-[#21362A] text-[#A1B4A8]">
            <Split className="w-4 h-4 mr-2"/>Split Group
          </Button>
          {showSplit && selectedForSplit.size > 0 && (
            <Button onClick={handleSplit} disabled={saving} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]">
              Split {selectedForSplit.size} Images
            </Button>
          )}
          <Button onClick={handleSaveReview} disabled={saving} className="bg-[#097969] hover:bg-[#0a8a78]">
            <Check className="w-4 h-4 mr-2"/>{saving ? "Saving..." : "Save Review"}
          </Button>
          {group?.review_status === "reviewed" && (
            <Button onClick={handleConvertToProduct} disabled={saving} className="bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]">
              Convert to Product
            </Button>
          )}
        </div>

        {/* Image Gallery */}
        <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
          <CardHeader>
            <CardTitle className="font-display text-xl">
              Images ({images.length})
              {baseImageId && <span className="text-sm text-[#A1B4A8] ml-2">• Base: 1, Additional: {additionalImageIds.length}</span>}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {images.map((img, idx) => (
                <div 
                  key={img.id}
                  className={`relative border-2 rounded-lg overflow-hidden cursor-pointer ${
                    baseImageId === img.id ? "border-[#D4AF37]" : 
                    additionalImageIds.includes(img.id) ? "border-[#097969]" : 
                    showSplit && selectedForSplit.has(img.id) ? "border-[#E63946]" : 
                    "border-[#21362A]"
                  }`}
                  onClick={() => showSplit ? handleToggleSplit(img.id) : handleSetBaseImage(img.id)}
                >
                  <img src={imgUrl(img.id)} alt={img.filename} className="w-full aspect-square object-cover"/>
                  <div className="absolute top-2 left-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                    #{img.sequence_number}
                  </div>
                  <div className="absolute top-2 right-2 flex gap-1">
                    {baseImageId === img.id && (
                      <div className="bg-[#D4AF37] text-[#050A07] text-xs px-2 py-1 rounded">Base</div>
                    )}
                    {additionalImageIds.includes(img.id) && (
                      <div className="bg-[#097969] text-white text-xs px-2 py-1 rounded">Additional</div>
                    )}
                    {showSplit && selectedForSplit.has(img.id) && (
                      <div className="bg-[#E63946] text-white text-xs px-2 py-1 rounded">Split</div>
                    )}
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 bg-black/70 text-white text-xs p-2">
                    <div className="truncate">{img.filename}</div>
                    <div className="text-[#A1B4A8] truncate">Original: {img.original_filename}</div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminLayout>
  );
}
