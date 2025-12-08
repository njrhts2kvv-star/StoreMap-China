import { Navigate, Route, Routes } from "react-router-dom";
import BrandDetailPage from "../pages/BrandDetailPage";
import BrandListPage from "../pages/BrandListPage";
import CityDetailPage from "../pages/CityDetailPage";
import CityListPage from "../pages/CityListPage";
import MallDetailPage from "../pages/MallDetailPage";

export const AppRouter = () => (
  <Routes>
    <Route path="/" element={<Navigate to="/cities" replace />} />
    <Route path="/cities" element={<CityListPage />} />
    <Route path="/cities/:cityCode" element={<CityDetailPage />} />
    <Route path="/malls/:mallId" element={<MallDetailPage />} />
    <Route path="/brands" element={<BrandListPage />} />
    <Route path="/brands/:brandId" element={<BrandDetailPage />} />
  </Routes>
);

export default AppRouter;
