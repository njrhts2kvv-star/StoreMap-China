import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import OverviewPage from '../pages/overview/OverviewPage';
import BrandListPage from '../pages/brands/BrandListPage';
import BrandDetailPage from '../pages/brands/BrandDetailPage';
import CityOverviewPage from '../pages/cities/CityOverviewPage';
import MallDetailPage from '../pages/malls/MallDetailPage';
import DistrictDetailPage from '../pages/districts/DistrictDetailPage';
import CompareBrandsPage from '../pages/compare/CompareBrandsPage';
import CompareMallsDistrictsPage from '../pages/compare/CompareMallsDistrictsPage';
import DataBrandsPage from '../pages/data-admin/DataBrandsPage';
import DataMallsPage from '../pages/data-admin/DataMallsPage';
import DataDistrictsPage from '../pages/data-admin/DataDistrictsPage';
import SettingsUsersPage from '../pages/settings/SettingsUsersPage';
import SettingsProfilePage from '../pages/settings/SettingsProfilePage';
import SettingsSystemPage from '../pages/settings/SettingsSystemPage';
import { PATHS } from './paths';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to={PATHS.overview} replace />} />
        <Route path="dashboard">
          <Route path="overview" element={<OverviewPage />} />
          <Route path="brands" element={<BrandListPage />} />
          <Route path="brands/:brandId" element={<BrandDetailPage />} />
          <Route path="cities/:cityId" element={<CityOverviewPage />} />
          <Route path="malls/:mallId" element={<MallDetailPage />} />
          <Route path="districts/:districtId" element={<DistrictDetailPage />} />
          <Route path="compare">
            <Route path="brands" element={<CompareBrandsPage />} />
            <Route path="malls-districts" element={<CompareMallsDistrictsPage />} />
          </Route>
        </Route>
        <Route path="data">
          <Route path="brands" element={<DataBrandsPage />} />
          <Route path="malls" element={<DataMallsPage />} />
          <Route path="districts" element={<DataDistrictsPage />} />
        </Route>
        <Route path="settings">
          <Route path="users" element={<SettingsUsersPage />} />
          <Route path="profile" element={<SettingsProfilePage />} />
          <Route path="system" element={<SettingsSystemPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to={PATHS.overview} replace />} />
    </Routes>
  );
}

