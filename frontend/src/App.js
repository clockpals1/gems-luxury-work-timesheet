import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import { Toaster } from "./components/ui/sonner";

import Login from "./pages/Login";
import WorkerDashboard from "./pages/WorkerDashboard";
import ProductDetail from "./pages/ProductDetail";
import AdminDashboard from "./pages/AdminDashboard";
import AdminCSVQueue from "./pages/AdminCSVQueue";
import AdminProductDetail from "./pages/AdminProductDetail";
import AdminUsers from "./pages/AdminUsers";
import AdminProducts from "./pages/AdminProducts";
import AdminNaming from "./pages/AdminNaming";
import AdminPricing from "./pages/AdminPricing";
import AdminImages from "./pages/AdminImages";
import AdminAttendance from "./pages/AdminAttendance";
import AdminActivityLogs from "./pages/AdminActivityLogs";
import AdminSettings from "./pages/AdminSettings";
import AdminPrompts from "./pages/AdminPrompts";

function Protected({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center bg-[#050A07] text-[#A1B4A8]">Loading studio…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={user.role === "worker" ? "/worker" : "/admin"} replace />;
  return children;
}

function Router() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/worker" element={<Protected roles={["worker","manager","admin"]}><WorkerDashboard /></Protected>} />
      <Route path="/products/:productId" element={<Protected roles={["worker","manager","admin"]}><ProductDetail /></Protected>} />
      <Route path="/admin" element={<Protected roles={["admin","manager"]}><AdminDashboard /></Protected>} />
      <Route path="/admin/csv-queue" element={<Protected roles={["admin","manager"]}><AdminCSVQueue /></Protected>} />
      <Route path="/admin/products/:productId" element={<Protected roles={["admin","manager"]}><AdminProductDetail /></Protected>} />
      <Route path="/admin/users" element={<Protected roles={["admin","manager"]}><AdminUsers /></Protected>} />
      <Route path="/admin/products" element={<Protected roles={["admin","manager"]}><AdminProducts /></Protected>} />
      <Route path="/admin/naming" element={<Protected roles={["admin","manager"]}><AdminNaming /></Protected>} />
      <Route path="/admin/pricing" element={<Protected roles={["admin","manager"]}><AdminPricing /></Protected>} />
      <Route path="/admin/images" element={<Protected roles={["admin","manager"]}><AdminImages /></Protected>} />
      <Route path="/admin/attendance" element={<Protected roles={["admin","manager"]}><AdminAttendance /></Protected>} />
      <Route path="/admin/activity" element={<Protected roles={["admin","manager"]}><AdminActivityLogs /></Protected>} />
      <Route path="/admin/prompts" element={<Protected roles={["admin","manager"]}><AdminPrompts /></Protected>} />
      <Route path="/admin/settings" element={<Protected roles={["admin"]}><AdminSettings /></Protected>} />
      <Route path="/" element={<Navigate to={user ? (user.role === "worker" ? "/worker" : "/admin") : "/login"} replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Router />
          <Toaster position="bottom-right" theme="dark" />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}
