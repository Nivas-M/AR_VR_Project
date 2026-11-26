import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import StorefrontPage from "./pages/StorefrontPage";
import ProductDetailPage from "./pages/ProductDetailPage";
import StudioPage from "./pages/StudioPage";
import ArViewerPage from "./pages/ArViewerPage";

export function AppRoutes() {
  return (
    <div className="ts-app-shell">
      <Navbar />
      <main className="ts-main">
        <Routes>
          <Route path="/" element={<StorefrontPage />} />
          <Route path="/product/:id" element={<ProductDetailPage />} />
          <Route path="/studio" element={<StudioPage />} />
          <Route path="/ar/:id" element={<ArViewerPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
