export const PATHS = {
  overview: '/dashboard/overview',
  brands: '/dashboard/brands',
  brandDetail: (id: string | number) => `/dashboard/brands/${id}`,
  cities: (cityCode: string | number) => `/dashboard/cities/${cityCode}`,
  malls: (mallId: string | number) => `/dashboard/malls/${mallId}`,
  districts: (districtId: string | number) => `/dashboard/districts/${districtId}`,
  compareBrands: '/dashboard/compare/brands',
  compareMallsDistricts: '/dashboard/compare/malls-districts',
  dataBrands: '/data/brands',
  dataMalls: '/data/malls',
  dataDistricts: '/data/districts',
  settingsUsers: '/settings/users',
  settingsProfile: '/settings/profile',
  settingsSystem: '/settings/system',
};

