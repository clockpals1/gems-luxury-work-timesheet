import React from "react";

export const Brand = ({ className = "" }) => (
  <div className={`flex items-center gap-3 ${className}`} data-testid="brand">
    <div className="w-9 h-9 rounded-sm bg-[#D4AF37] flex items-center justify-center text-[#050A07] font-display text-lg font-bold">G</div>
    <div className="leading-tight">
      <div className="font-display text-lg text-white">Gems &amp; Luxury</div>
      <div className="label-overline text-[10px]">Internal Studio</div>
    </div>
  </div>
);

export default Brand;
