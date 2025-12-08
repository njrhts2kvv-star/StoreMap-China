/**
 * Data service entrypoint. Uses mock data by default; switch to real API by
 * replacing implementations here (e.g., using fetch/axios).
 */
import * as mock from './mockApi';
import type { Brand, Mall, BusinessDistrict, Store, CityOverview } from '../types/dashboard';

type OverviewData = Awaited<ReturnType<typeof mock.getOverview>>;

const baseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
const useApi = typeof baseUrl === 'string' && baseUrl.length > 0;

async function request<T>(path: string): Promise<T> {
  if (!useApi) return Promise.reject(new Error('no api'));
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/333c67a7-ca79-42a1-b5ef-454291d55846', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionId: 'debug-session',
      runId: 'pre-fix',
      hypothesisId: 'H1',
      location: 'dataService.ts:request:before',
      message: 'about to fetch',
      data: { baseUrl, path },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion agent log
  const res = await fetch(`${baseUrl}${path}`);
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/333c67a7-ca79-42a1-b5ef-454291d55846', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionId: 'debug-session',
      runId: 'pre-fix',
      hypothesisId: 'H2',
      location: 'dataService.ts:request:after',
      message: 'response received',
      data: { status: res.status, ok: res.ok, url: res.url },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion agent log
  if (!res.ok) throw new Error(`api error ${res.status}`);
  return res.json() as Promise<T>;
}

export const dataService = {
  async getOverview(): Promise<OverviewData> {
    if (useApi) {
      try {
        return await request('/overview');
      } catch (e) {
        console.warn('fallback to mock overview', e);
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/333c67a7-ca79-42a1-b5ef-454291d55846', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sessionId: 'debug-session',
            runId: 'pre-fix',
            hypothesisId: 'H3',
            location: 'dataService.ts:getOverview:fallback',
            message: 'api failed, using mock',
            data: { error: String(e) },
            timestamp: Date.now(),
          }),
        }).catch(() => {});
        // #endregion agent log
      }
    }
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/333c67a7-ca79-42a1-b5ef-454291d55846', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'pre-fix',
        hypothesisId: 'H4',
        location: 'dataService.ts:getOverview:mock',
        message: 'returning mock overview',
        data: {},
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion agent log
    return mock.getOverview();
  },
  async listBrands(): Promise<Brand[]> {
    if (useApi) {
      try {
        return await request('/brands');
      } catch (e) {
        console.warn('fallback to mock brands', e);
      }
    }
    return mock.listBrands();
  },
  async getBrand(id: string): Promise<Brand | undefined> {
    if (useApi) {
      try {
        return await request(`/brands/${id}`);
      } catch (e) {
        console.warn('fallback to mock brand', e);
      }
    }
    return mock.getBrand(id);
  },
  async listBrandStores(id: string): Promise<Store[]> {
    if (useApi) {
      try {
        return await request(`/brands/${id}/stores`);
      } catch (e) {
        console.warn('fallback to mock brand stores', e);
      }
    }
    return mock.listBrandStores(id);
  },
  async listMalls(): Promise<Mall[]> {
    if (useApi) {
      try {
        return await request('/malls');
      } catch (e) {
        console.warn('fallback to mock malls', e);
      }
    }
    return mock.listMalls();
  },
  async getMall(id: string): Promise<Mall | undefined> {
    if (useApi) {
      try {
        return await request(`/malls/${id}`);
      } catch (e) {
        console.warn('fallback to mock mall', e);
      }
    }
    return mock.getMall(id);
  },
  async listDistricts(): Promise<BusinessDistrict[]> {
    if (useApi) {
      try {
        return await request('/districts');
      } catch (e) {
        console.warn('fallback to mock districts', e);
      }
    }
    return mock.listDistricts();
  },
  async getDistrict(id: string): Promise<BusinessDistrict | undefined> {
    if (useApi) {
      try {
        return await request(`/districts/${id}`);
      } catch (e) {
        console.warn('fallback to mock district', e);
      }
    }
    return mock.getDistrict(id);
  },
  async listCities(): Promise<CityOverview[]> {
    if (useApi) {
      try {
        return await request('/cities');
      } catch (e) {
        console.warn('fallback to mock cities', e);
      }
    }
    return mock.listCities();
  },
  async getCity(id: string): Promise<CityOverview | undefined> {
    if (useApi) {
      try {
        return await request(`/cities/${id}`);
      } catch (e) {
        console.warn('fallback to mock city', e);
      }
    }
    return mock.getCity(id);
  },
  async listStores(): Promise<Store[]> {
    if (useApi) {
      try {
        return await request('/stores');
      } catch (e) {
        console.warn('fallback to mock stores', e);
      }
    }
    return mock.listStores();
  },
};

