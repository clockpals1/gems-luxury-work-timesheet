import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, imgUrl } from "../lib/api";
import { WorkerLayout } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { toast } from "sonner";
import { Download, Sparkles, X, ArrowLeft } from "lucide-react";

export default function ProductDetail() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState({});

  useEffect(() => {
    loadProduct();
  }, [productId]);

  const loadProduct = async () => {
    try {
      const r = await api.get(`/products/${productId}`);
      setProduct(r.data);
    } catch (e) {
      toast.error("Failed to load product");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (imageId) => {
    try {
      const r = await api.get(`/images/${imageId}/download`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `product_${productId}_image.png`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      toast.error("Download failed");
    }
  };

  const handleRefine = async () => {
    setProcessing((p) => ({ ...p, refine: true }));
    try {
      await api.post(`/products/${productId}/refine-image`);
      toast.success("Image refined successfully");
      loadProduct();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Refine failed");
    } finally {
      setProcessing((p) => ({ ...p, refine: false }));
    }
  };

  const handleGenerateViews = async () => {
    setProcessing((p) => ({ ...p, views: true }));
    try {
      await api.post(`/products/${productId}/generate-views`);
      toast.success("AI views generated successfully");
      loadProduct();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "View generation failed");
    } finally {
      setProcessing((p) => ({ ...p, views: false }));
    }
  };

  const handleSkip = async () => {
    if (!confirm("Skip this image? It will be returned to the available pool.")) return;
    setProcessing((p) => ({ ...p, skip: true }));
    try {
      await api.post(`/products/${productId}/skip-image`);
      toast.success("Image skipped");
      loadProduct();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Skip failed");
    } finally {
      setProcessing((p) => ({ ...p, skip: false }));
    }
  };

  const handleComplete = async () => {
    setProcessing((p) => ({ ...p, complete: true }));
    try {
      await api.post(`/products/${productId}/complete`);
      toast.success("Product completed");
      loadProduct();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Complete failed");
    } finally {
      setProcessing((p) => ({ ...p, complete: false }));
    }
  };

  if (loading) return <WorkerLayout><div className="p-8">Loading...</div></WorkerLayout>;
  if (!product) return <WorkerLayout><div className="p-8">Product not found</div></WorkerLayout>;

  const workflowStatus = product.image_workflow_status || "assigned";
  const statusColors = {
    assigned: "bg-blue-500/20 text-blue-300",
    refined: "bg-yellow-500/20 text-yellow-300",
    "variation-created": "bg-purple-500/20 text-purple-300",
    skipped: "bg-gray-500/20 text-gray-300",
    completed: "bg-green-500/20 text-green-300",
  };

  return (
    <WorkerLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button onClick={() => navigate(-1)} variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <div className="label-overline text-[#D4AF37]">Product Details</div>
            <h1 className="font-display text-4xl mt-2">{product.name}</h1>
          </div>
        </div>

        <div className="flex gap-3">
          <Badge className={statusColors[workflowStatus]}>{workflowStatus}</Badge>
          <Badge className="bg-[#21362A] text-[#A1B4A8]">{product.category}</Badge>
          <Badge className="bg-[#D4AF37]/20 text-[#D4AF37]">${product.final_price}</Badge>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Image Workflow */}
          <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
            <CardHeader>
              <CardTitle className="font-display text-2xl">Image Workflow</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Original Image */}
              {product.image_asset_id && (
                <div className="space-y-2">
                  <div className="label-overline">Original Image</div>
                  <div className="relative aspect-square bg-[#132018] border border-[#21362A] rounded-sm overflow-hidden">
                    <img src={imgUrl(product.image_asset_id)} alt="original" className="w-full h-full object-cover" />
                    <Button
                      onClick={() => handleDownload(product.image_asset_id)}
                      className="absolute top-2 right-2 bg-[#050A07]/80 hover:bg-[#050A07]"
                      size="icon"
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}

              {/* Refined Image */}
              {product.refined_image_id && (
                <div className="space-y-2">
                  <div className="label-overline">Refined Image</div>
                  <div className="relative aspect-square bg-[#132018] border border-[#21362A] rounded-sm overflow-hidden">
                    <img src={imgUrl(product.refined_image_id)} alt="refined" className="w-full h-full object-cover" />
                    <Button
                      onClick={() => handleDownload(product.refined_image_id)}
                      className="absolute top-2 right-2 bg-[#050A07]/80 hover:bg-[#050A07]"
                      size="icon"
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}

              {/* AI Views */}
              {product.variation_image_ids?.length > 0 && (
                <div className="space-y-2">
                  <div className="label-overline">AI Generated Views</div>
                  <div className="grid grid-cols-2 gap-3">
                    {product.variation_image_ids.map((vid, i) => (
                      <div key={vid} className="relative aspect-square bg-[#132018] border border-[#21362A] rounded-sm overflow-hidden">
                        <img src={imgUrl(vid)} alt={`view ${i + 1}`} className="w-full h-full object-cover" />
                        <Button
                          onClick={() => handleDownload(vid)}
                          className="absolute top-2 right-2 bg-[#050A07]/80 hover:bg-[#050A07]"
                          size="icon"
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Workflow Actions */}
              <div className="space-y-3 pt-4 border-t border-[#21362A]">
                {product.image_asset_id && workflowStatus === "assigned" && (
                  <>
                    <Button
                      onClick={handleRefine}
                      disabled={processing.refine}
                      className="w-full bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]"
                    >
                      <Sparkles className="w-4 h-4 mr-2" />
                      {processing.refine ? "Refining..." : "Refine Image"}
                    </Button>
                    <Button
                      onClick={handleSkip}
                      disabled={processing.skip}
                      variant="outline"
                      className="w-full border-[#21362A] text-[#A1B4A8]"
                    >
                      <X className="w-4 h-4 mr-2" />
                      {processing.skip ? "Skipping..." : "Skip Image"}
                    </Button>
                  </>
                )}

                {(workflowStatus === "refined" || workflowStatus === "assigned") && (
                  <Button
                    onClick={handleGenerateViews}
                    disabled={processing.views || product.variation_image_ids?.length > 0}
                    className="w-full bg-[#D4AF37] hover:bg-[#F0C84A] text-[#050A07]"
                  >
                    <Sparkles className="w-4 h-4 mr-2" />
                    {processing.views ? "Generating..." : "Create 2 AI Views"}
                  </Button>
                )}

                {(workflowStatus === "refined" || workflowStatus === "variation-created") && (
                  <Button
                    onClick={handleComplete}
                    disabled={processing.complete}
                    className="w-full bg-[#097969] hover:bg-[#0a8a78]"
                  >
                    {processing.complete ? "Completing..." : "Save Product Record"}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Product Details */}
          <Card className="bg-[#0C140F] border-[#21362A] rounded-sm">
            <CardHeader>
              <CardTitle className="font-display text-2xl">Product Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="label-overline">Short Title</div>
                <div className="text-[#A1B4A8]">{product.short_title}</div>
              </div>

              <div className="space-y-2">
                <div className="label-overline">Short Description</div>
                <div className="text-[#A1B4A8]">{product.short_description}</div>
              </div>

              <div className="space-y-2">
                <div className="label-overline">Full Description</div>
                <div className="text-[#A1B4A8] whitespace-pre-line">{product.full_description}</div>
              </div>

              <div className="space-y-2">
                <div className="label-overline">Tags</div>
                <div className="flex gap-2 flex-wrap">
                  {product.tags?.map((t) => <Badge key={t} className="bg-[#132018] text-[#A1B4A8] border border-[#21362A]">{t}</Badge>)}
                </div>
              </div>

              <div className="space-y-2">
                <div className="label-overline">Sizes</div>
                <div className="text-[#A1B4A8]">{product.sizes?.join(", ")}</div>
              </div>

              <div className="space-y-2 pt-4 border-t border-[#21362A]">
                <div className="label-overline">Worker Information</div>
                <div className="text-sm text-[#A1B4A8]">
                  <div>Name: {product.generated_by_name}</div>
                  <div>Created: {new Date(product.generated_at).toLocaleString()}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </WorkerLayout>
  );
}
