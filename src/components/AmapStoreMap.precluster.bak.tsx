// @ts-nocheck
// 用高德 JS API 重写门店地图，复刻原有交互和视觉
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Crosshair, Minus, Plus, Star, X } from 'lucide-react';
import type { Mall, Store } from '../types/store';
import { loadAmap } from '../utils/loadAmap';
import djiLogoBlack from '../assets/dji_logo_black_small.svg';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoBlack from '../assets/insta360_logo_black_small.svg';
import instaLogoWhite from '../assets/insta360_logo_white_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';
import { isNewThisMonth } from '../utils/storeRules';
import { MALL_STATUS_COLORS } from '../config/competitionColors';
import { lighten, mixColors } from '../utils/color';

type Props = {
  viewMode?: 'stores' | 'malls' | 'competition';
  stores: Store[];
  malls?: Mall[];
  selectedId?: string;
  selectedMallId?: string;
  onSelect: (id: string) => void;
  onMallClick?: (mall: Mall) => void;
  userPos?: { lat: number; lng: number } | null;
  favorites?: string[];
  onToggleFavorite?: (id: string) => void;
  showPopup?: boolean;
  resetToken?: number;
  mapId?: string;
  autoFitOnClear?: boolean;
  showControls?: boolean;
  fitToStores?: boolean;
  initialCenter?: [number, number]; // 仍沿用旧组件的「纬度, 经度」顺序
  initialZoom?: number;
  colorBaseStores?: Store[]; // 色块基准：不受筛选影响的全量数据
  regionMode?: 'province' | 'none'; // none: 不展示省市色块，直接展示点位
};

const DEFAULT_CENTER: [number, number] = [35.5, 103.5];
const DEFAULT_ZOOM = 5.4; // 总览放大一级
const MIN_FOCUS_ZOOM = 11;
const CITY_MAX_ZOOM = 10; // 城市层最高放大，避免直接落到街道级
const DJI_COLOR = '#111827';
const INSTA_COLOR = '#facc15';
const NO_DATA_COLOR = '#e5e7eb';

type RegionShape = {
  name: string;
  adcode: string;
  center: [number, number];
  boundaries: [number, number][][];
};

type DrillLevel = 'province' | 'city';

type RegionStats = {
  dji: number;
  insta: number;
  total: number;
};
const EMPTY_STATS: RegionStats = { dji: 0, insta: 0, total: 0 };

const safeCenter = (center: string | number[] | undefined): [number, number] => {
  if (!center) return DEFAULT_CENTER;
  if (Array.isArray(center) && center.length >= 2) {
    const [lng, lat] = center;
    if (Number.isFinite(lat) && Number.isFinite(lng)) return [Number(lng), Number(lat)];
  }
  if (typeof center === 'string') {
    const [lng, lat] = center.split(',').map((v) => Number(v));
    if (Number.isFinite(lat) && Number.isFinite(lng)) return [lng, lat];
  }
  return DEFAULT_CENTER;
};

const normalizeBoundaries = (paths: any[] = []): [number, number][][] =>
  paths
    .map((path) =>
      (path || []).map((p: any) => {
        if (Array.isArray(p) && p.length >= 2) return [Number(p[0]), Number(p[1])] as [number, number];
        if (p && typeof p === 'object' && 'lng' in p && 'lat' in p) {
          return [Number((p as any).lng), Number((p as any).lat)] as [number, number];
        }
        return null;
      }),
    )
    .filter((p: any) => Array.isArray(p) && p.length)
    .map((p: any) => p.filter(Boolean)) as [number, number][][];

const aggregateByProvince = (stores: Store[]) =>
  stores.reduce<Record<string, RegionStats>>((acc, store) => {
    const key = store.province || '未知';
    if (!acc[key]) acc[key] = { dji: 0, insta: 0, total: 0 };
    if (store.brand === 'DJI') acc[key].dji += 1;
    else acc[key].insta += 1;
    acc[key].total += 1;
    return acc;
  }, {});

const aggregateByCity = (stores: Store[]) =>
  stores.reduce<Record<string, RegionStats>>((acc, store) => {
    const province = store.province || '未知';
    const city = store.city || province;
    const key = `${province}||${city}`;
    if (!acc[key]) acc[key] = { dji: 0, insta: 0, total: 0 };
    if (store.brand === 'DJI') acc[key].dji += 1;
    else acc[key].insta += 1;
    acc[key].total += 1;
    return acc;
  }, {});

const calcFillColor = (share: number | null) => {
  if (share === null || Number.isNaN(share)) return NO_DATA_COLOR;
  return mixColors(INSTA_COLOR, DJI_COLOR, share);
};

const calcStrokeColor = (fill: string) => lighten(fill, 0.15);

const flattenGeoBoundary = (geom: any): [number, number][][] => {
  if (!geom) return [];
  const coords = geom.coordinates || [];
  const paths: [number, number][][] = [];
  if (geom.type === 'MultiPolygon') {
    coords.forEach((poly: any) => {
      poly.forEach((ring: any) => {
        paths.push(
          (ring || [])
            .map((p: any) => (Array.isArray(p) && p.length >= 2 ? ([p[0], p[1]] as [number, number]) : null))
            .filter(Boolean) as [number, number][],
        );
      });
    });
  } else if (geom.type === 'Polygon') {
    coords.forEach((ring: any) => {
      paths.push(
        (ring || [])
          .map((p: any) => (Array.isArray(p) && p.length >= 2 ? ([p[0], p[1]] as [number, number]) : null))
          .filter(Boolean) as [number, number][],
      );
    });
  }
  return paths.filter((r) => r.length);
};

const centroid = (ring: [number, number][]) => {
  if (!ring.length) return DEFAULT_CENTER;
  const sum = ring.reduce(
    (acc, [lng, lat]) => {
      acc[0] += lng;
      acc[1] += lat;
      return acc;
    },
    [0, 0] as [number, number],
  );
  return [sum[0] / ring.length, sum[1] / ring.length] as [number, number];
};

const buildRegionShapeFromGeo = (feature: any): RegionShape | null => {
  const props = feature?.properties || {};
  const name = props.name || '';
  const adcode = String(props.adcode || '');
  const paths = flattenGeoBoundary(feature?.geometry);
  if (!name || !adcode || !paths.length) return null;
  const center = safeCenter(props.center) ?? centroid(paths[0]);
  return {
    name,
    adcode,
    center,
    boundaries: paths,
  };
};

const toLngLat = (coords: { latitude?: number; longitude?: number; lat?: number; lng?: number }): [number, number] | null => {
  const lat = coords.lat ?? coords.latitude;
  const lng = coords.lng ?? coords.longitude;
  if (typeof lat !== 'number' || typeof lng !== 'number') return null;
  return [lng, lat];
};

const toStoreLngLat = (store: Store) => toLngLat({ latitude: store.latitude, longitude: store.longitude, lat: (store as any).lat, lng: (store as any).lng });
const toMallLngLat = (mall: Mall) => toLngLat({ latitude: mall.latitude, longitude: mall.longitude });

const isInChinaRough = (point: { latitude?: number; longitude?: number; lat?: number; lng?: number }): boolean => {
  const lat = point.lat ?? point.latitude;
  const lng = point.lng ?? point.longitude;
  if (typeof lat !== 'number' || typeof lng !== 'number') return false;
  // 中国大致范围：纬度 18-54，经度 73-135
  return lat >= 18 && lat <= 54 && lng >= 73 && lng <= 135;
};

export function AmapStoreMap({
  viewMode = 'stores',
  stores,
  malls = [],
  selectedId,
  selectedMallId,
  onSelect,
  onMallClick,
  userPos = null,
  favorites = [],
  onToggleFavorite,
  showPopup = true,
  resetToken = 0,
  mapId,
  autoFitOnClear = true,
  showControls = true,
  fitToStores = false,
  initialCenter = DEFAULT_CENTER,
  initialZoom = DEFAULT_ZOOM,
  colorBaseStores,
  regionMode = 'province',
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<AMap.Map | null>(null);
  const markersRef = useRef<AMap.Marker[]>([]);
  const userMarkerRef = useRef<AMap.Marker | null>(null);
  const amapRef = useRef<typeof AMap | null>(null);
  const favoritesSet = useMemo(() => new Set(favorites), [favorites]);
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const normalizedCenter = useMemo<[number, number]>(() => {
    const [lat = DEFAULT_CENTER[0], lng = DEFAULT_CENTER[1]] = initialCenter ?? DEFAULT_CENTER;
    return [lng, lat];
  }, [initialCenter]);
  const [showNavSelector, setShowNavSelector] = useState(false);
  const colorStores = useMemo(() => (colorBaseStores && colorBaseStores.length ? colorBaseStores : stores), [colorBaseStores, stores]);
  const provinceStatsBase = useMemo(() => aggregateByProvince(colorStores), [colorStores]);
  const cityStatsBase = useMemo(() => aggregateByCity(colorStores), [colorStores]);
  const provinceStatsFiltered = useMemo(() => aggregateByProvince(stores), [stores]);
  const cityStatsFiltered = useMemo(() => aggregateByCity(stores), [stores]);
  const regionEnabled = regionMode !== 'none';
  const getProvinceBase = useCallback((name: string) => provinceStatsBase[name] ?? EMPTY_STATS, [provinceStatsBase]);
  const getProvinceFiltered = useCallback((name: string) => provinceStatsFiltered[name] ?? EMPTY_STATS, [provinceStatsFiltered]);
  const getCityBase = useCallback(
    (province: string, city: string) => cityStatsBase[`${province}||${city}`] ?? EMPTY_STATS,
    [cityStatsBase],
  );
  const getCityFiltered = useCallback(
    (province: string, city: string) => cityStatsFiltered[`${province}||${city}`] ?? EMPTY_STATS,
    [cityStatsFiltered],
  );
  const [drillLevel, setDrillLevel] = useState<DrillLevel>('province');
  const [activeProvince, setActiveProvince] = useState<string | null>(null);
  const [activeCity, setActiveCity] = useState<string | null>(null);
  const [provinceShapes, setProvinceShapes] = useState<RegionShape[]>([]);
  const [cityShapesByProvince, setCityShapesByProvince] = useState<Record<string, RegionShape[]>>({});
  const [activeProvinceAdcode, setActiveProvinceAdcode] = useState<string | null>(null);
  const regionPolygonsRef = useRef<AMap.Polygon[]>([]);
  const geoCacheRef = useRef<Record<string, RegionShape[]>>({});
  const isSameCityName = (a: string, b: string) => {
    if (!a || !b) return false;
    return a === b || a.startsWith(b) || b.startsWith(a);
  };
  const scopedStorePoints = useMemo(() => {
    if (!regionEnabled) return stores;
    if (drillLevel !== 'city' || !activeProvince || !activeCity) return [];
    return stores.filter(
      (s) => s.province === activeProvince && (s.city === activeCity || isSameCityName(s.city, activeCity)),
    );
  }, [stores, drillLevel, activeProvince, activeCity, isSameCityName, regionEnabled]);
  const provinceFilteredStats = useMemo(
    () => (activeProvince ? getProvinceFiltered(activeProvince) : EMPTY_STATS),
    [activeProvince, getProvinceFiltered],
  );
  const cityFilteredStats = useMemo(
    () => {
      if (!activeProvince || !activeCity) return EMPTY_STATS;
      const keyed = getCityFiltered(activeProvince, activeCity);
      if (keyed.total > 0) return keyed;
      // 兜底：用当前城市门店直接统计，避免命名不一致导致 0
      const derived = scopedStorePoints.reduce(
        (acc, s) => {
          if (s.brand === 'DJI') acc.dji += 1;
          else acc.insta += 1;
          acc.total += 1;
          return acc;
        },
        { ...EMPTY_STATS },
      );
      return derived;
    },
    [activeProvince, activeCity, getCityFiltered, scopedStorePoints],
  );
  const selectedStore = useMemo(
    () =>
      viewMode === 'stores' && selectedId && selectedId.trim()
        ? scopedStorePoints.find((s) => s.id === selectedId) ?? null
        : null,
    [viewMode, scopedStorePoints, selectedId],
  );
  useEffect(() => {
    setShowNavSelector(false);
  }, [selectedId, viewMode]);

  const destroyMap = useCallback(() => {
    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current = [];
    regionPolygonsRef.current.forEach((p) => p.setMap(null));
    regionPolygonsRef.current = [];
    if (userMarkerRef.current) {
      userMarkerRef.current.setMap(null);
      userMarkerRef.current = null;
    }
    if (mapRef.current) {
      mapRef.current.destroy();
      mapRef.current = null;
    }
  }, []);

  useEffect(() => {
    let disposed = false;
    loadAmap()
      .then((AMap) => {
        if (disposed) return;
        amapRef.current = AMap;
        if (!containerRef.current) return;
        destroyMap();
        mapRef.current = new AMap.Map(containerRef.current, {
          viewMode: '2D',
          resizeEnable: true,
          dragEnable: true,
          zoomEnable: true,
          zoom: initialZoom,
          center: normalizedCenter,
          mapStyle: 'amap://styles/whitesmoke',
        });
        setLoadError(null);
        setReady(true);
      })
      .catch((err) => {
        if (disposed) return;
        console.error('[AMap] load error', err);
        setLoadError(err.message || '高德地图 SDK 加载失败');
        setReady(false);
      });
    return () => {
      disposed = true;
      destroyMap();
    };
  }, [destroyMap, initialZoom, normalizedCenter, mapId]);

  useEffect(() => {
    if (!regionEnabled) return;
    if (!ready || !amapRef.current || !mapRef.current) return;
    if (provinceShapes.length) return;
    const url = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json';
    fetch(url)
      .then((res) => res.json())
      .then((json) => {
        const shapes = (json?.features || []).map(buildRegionShapeFromGeo).filter(Boolean) as RegionShape[];
        setProvinceShapes(shapes);
        geoCacheRef.current['100000'] = shapes;
      })
      .catch((err) => {
        console.warn('[Map] load province geojson failed', err);
      });
  }, [ready, provinceShapes.length, regionEnabled]);

  const recenter = useCallback(() => {
    if (!mapRef.current) return;
    mapRef.current.setZoomAndCenter(initialZoom, normalizedCenter, true);
  }, [initialZoom, normalizedCenter]);

  const clearRegionOverlays = useCallback(() => {
    regionPolygonsRef.current.forEach((p) => p.setMap(null));
    regionPolygonsRef.current = [];
  }, []);

  useEffect(() => {
    if (!regionEnabled) return;
    if (!ready || !amapRef.current || !activeProvince || !activeProvinceAdcode) return;
    if (cityShapesByProvince[activeProvince]) return;
    // 省 adcode 对应的城市边界
    const cached = geoCacheRef.current[activeProvinceAdcode];
    if (cached) {
      setCityShapesByProvince((prev) => ({ ...prev, [activeProvince]: cached }));
      return;
    }
    const url = `https://geo.datav.aliyun.com/areas_v3/bound/${activeProvinceAdcode}_full.json`;
    fetch(url)
      .then((res) => res.json())
      .then((json) => {
        const shapes = (json?.features || []).map(buildRegionShapeFromGeo).filter(Boolean) as RegionShape[];
        geoCacheRef.current[activeProvinceAdcode] = shapes;
        setCityShapesByProvince((prev) => ({ ...prev, [activeProvince]: shapes }));
      })
      .catch((err) => {
        console.warn('[Map] load city geojson failed', activeProvince, err);
      });
  }, [activeProvince, activeProvinceAdcode, cityShapesByProvince, ready, regionEnabled]);

  const drawRegionLayer = useCallback(
    (shapes: RegionShape[], level: 'province' | 'city', provinceContext?: string) => {
      if (!amapRef.current || !mapRef.current || !shapes.length) return;
      clearRegionOverlays();
      const AMapLib = amapRef.current;
      const nextPolygons: AMap.Polygon[] = [];
      const nextLabels: AMap.Text[] = [];

      shapes.forEach((shape) => {
        if (!shape.boundaries?.length) return;
        const baseStats =
          level === 'province'
            ? getProvinceBase(shape.name)
            : getCityBase(provinceContext || activeProvince || '未知', shape.name);
        const hasData = baseStats.total > 0;
        const share = hasData ? baseStats.dji / baseStats.total : null;
        const fillColor = hasData ? calcFillColor(share) : 'transparent';
        const strokeColor = hasData ? calcStrokeColor(fillColor) : '#cbd5e1';
        const polygon = new AMapLib.Polygon({
          path: shape.boundaries,
          fillColor,
          fillOpacity: hasData ? 0.24 : 0,
          strokeColor,
          strokeOpacity: hasData ? 0.85 : 0.9,
          strokeWeight: 1.2,
          bubble: true,
          cursor: 'pointer',
        });
        polygon.setExtData(shape);
        polygon.on('click', () => {
          onSelect('');
          if (level === 'province') {
            setActiveProvince(shape.name);
            setActiveProvinceAdcode(shape.adcode);
            setActiveCity(null);
            setDrillLevel('city');
          } else {
            setActiveCity(shape.name);
            setDrillLevel('city');
          }
        if (mapRef.current) {
          mapRef.current.setFitView([polygon], false, [40, 40, 40, 80]);
          const current = mapRef.current.getZoom();
          const target =
            level === 'province'
              ? Math.max(current, 5.2) // 省级略放大，露出省名
              : Math.min(Math.max(current, 6.5), CITY_MAX_ZOOM); // 城市层限制最大缩放，避免直落街道
          mapRef.current.setZoom(target, true);
        }
      });
        nextPolygons.push(polygon);
        // 省、市层不再额外叠加自定义标签，使用底图自带名称
      });

      regionPolygonsRef.current = nextPolygons;
      nextPolygons.forEach((p) => p.setMap(mapRef.current!));
      if (nextPolygons.length) {
        mapRef.current.setFitView(nextPolygons, false, [60, 40, 60, 120]);
      } else {
        // 兜底：如果依旧没有边界，居中到中国
        mapRef.current.setZoomAndCenter(4, [103.5, 35.5], true);
      }
    },
    [
      activeProvince,
      clearRegionOverlays,
      getCityBase,
      getCityFiltered,
      getProvinceBase,
      getProvinceFiltered,
      onSelect,
      recenter,
    ],
  );

  useEffect(() => {
    if (!regionEnabled) return;
    if (!ready || !mapRef.current || viewMode !== 'stores') return;
    if (drillLevel === 'province') {
      if (provinceShapes.length) {
        drawRegionLayer(provinceShapes, 'province');
      } else {
        recenter();
      }
    } else if (drillLevel === 'city' && activeProvince) {
      const cities = cityShapesByProvince[activeProvince];
      if (cities?.length) {
        drawRegionLayer(cities, 'city', activeProvince);
      }
    }
  }, [
    activeProvince,
    cityShapesByProvince,
    drillLevel,
    drawRegionLayer,
    provinceShapes,
    ready,
    regionEnabled,
    viewMode,
  ]);

  useEffect(() => {
    if (!ready || !mapRef.current || !amapRef.current) return;
    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current = [];

    const AMapLib = amapRef.current;
    const nextMarkers: AMap.Marker[] = [];

    const showStoreMarkers = viewMode === 'stores' && (!regionEnabled || drillLevel === 'city');
    if (showStoreMarkers) {
      scopedStorePoints.forEach((store) => {
        if (!isInChinaRough(store)) return;
        const point = toStoreLngLat(store);
        if (!point) return;
        const isFavorite = favoritesSet.has(store.id);
        const isSelected = selectedId === store.id;
        const isNew = isNewThisMonth(store);
        const markerEl = document.createElement('div');
        const brandClass = store.brand === 'DJI' ? 'store-marker--dji' : 'store-marker--insta';
        let markerClass = `store-marker ${brandClass}`;
        if (isNew) {
          markerClass += ' store-marker--new';
        }
        if (isFavorite) {
          markerClass += ' store-marker--favorite';
          markerClass += store.brand === 'DJI' ? ' store-marker--favorite-dji' : ' store-marker--favorite-insta';
        }
        markerEl.className = markerClass.trim();
        if (isSelected) markerEl.classList.add('store-marker--selected');
        markerEl.title = store.storeName;

        const logoImg = document.createElement('img');
        logoImg.className = 'store-marker__logo';
        const logoSrc =
          store.brand === 'DJI'
            ? isFavorite
              ? djiLogoBlack
              : djiLogoWhite
            : isFavorite
              ? instaLogoWhite
              : instaLogoBlack;
        logoImg.src = logoSrc;
        logoImg.alt = store.brand;
        markerEl.appendChild(logoImg);

        const baseSize = isFavorite ? 22 : 20;
        const ringExtra = isNew ? 4 : 0; // 双环描边向外延伸的尺寸
        const offsetVal = -(baseSize / 2 + ringExtra);

        const marker = new AMapLib.Marker({
          position: point,
          content: markerEl,
          offset: new AMapLib.Pixel(offsetVal, offsetVal),
          zIndex: isSelected ? 140 : isNew ? 130 : isFavorite ? 120 : 100,
        });
        marker.setExtData(store);

        marker.on('click', () => {
          onSelect(store.id);
          if (mapRef.current) {
            const currentZoom = mapRef.current.getZoom();
            if (currentZoom < MIN_FOCUS_ZOOM) {
              mapRef.current.setZoom(MIN_FOCUS_ZOOM, true);
            }
            mapRef.current.setCenter(point, true);
          }
        });

        nextMarkers.push(marker);
      });
    } else if (viewMode !== 'stores') {
      malls.forEach((mall) => {
        if (!isInChinaRough(mall)) return;
        const point = toMallLngLat(mall);
        if (!point) return;
        const isSelected = selectedMallId === mall.mallId;
        const markerEl = document.createElement('div');
        markerEl.className = 'mall-marker';
        const color = viewMode === 'competition' ? MALL_STATUS_COLORS[mall.status] : '#2563eb';
        markerEl.style.backgroundColor = color;
        if (isSelected) markerEl.classList.add('mall-marker--selected');
        markerEl.title = mall.mallName;

        const marker = new AMapLib.Marker({
          position: point,
          content: markerEl,
          offset: new AMapLib.Pixel(-8, -8),
          zIndex: isSelected ? 150 : 120,
        });
        marker.setExtData(mall);
        marker.on('click', () => {
          onMallClick?.(mall);
          if (mapRef.current) {
            const currentZoom = mapRef.current.getZoom();
            if (currentZoom < MIN_FOCUS_ZOOM) {
              mapRef.current.setZoom(MIN_FOCUS_ZOOM, true);
            }
            mapRef.current.setCenter(point, true);
          }
        });
        nextMarkers.push(marker);
      });
    }

    markersRef.current = nextMarkers;
    (window as any).__storeMarkers = nextMarkers;
    console.info('[Map] markers prepared:', nextMarkers.length);

    const hasSelection = viewMode === 'stores' ? selectedId : selectedMallId;
    const allowAutoFit = !(viewMode === 'stores' && drillLevel === 'city'); // 城市层不自动按照门店点位缩放
    const shouldFitAll = allowAutoFit && !hasSelection && (fitToStores || autoFitOnClear);
    if (mapRef.current && nextMarkers.length && shouldFitAll) {
      mapRef.current.setFitView(nextMarkers, false, [80, 40, 80, 80]);
    } else if (!nextMarkers.length && viewMode !== 'stores') {
      recenter();
    }

    if (nextMarkers.length && mapRef.current) {
      nextMarkers.forEach((marker) => marker.setMap(mapRef.current!));
      if (!shouldFitAll && !hasSelection && !fitToStores && !autoFitOnClear && viewMode !== 'stores') {
        recenter();
      }
    } else if (viewMode !== 'stores') {
      recenter();
    }
  }, [
    ready,
      viewMode,
      scopedStorePoints,
    malls,
    favoritesSet,
    selectedId,
    selectedMallId,
    autoFitOnClear,
    fitToStores,
    onSelect,
    onMallClick,
    recenter,
      drillLevel,
      regionEnabled,
  ]);

  useEffect(() => {
    if (!ready || !userPos || !amapRef.current || !mapRef.current) {
      if (userMarkerRef.current) {
        userMarkerRef.current.setMap(null);
        userMarkerRef.current = null;
      }
      return;
    }

    const markerEl = document.createElement('div');
    markerEl.className = 'store-marker store-marker--user';
    const position: [number, number] = [userPos.lng, userPos.lat];

    if (userMarkerRef.current) {
      userMarkerRef.current.setPosition(position);
      userMarkerRef.current.setContent(markerEl);
      userMarkerRef.current.setMap(mapRef.current);
    } else {
      userMarkerRef.current = new amapRef.current.Marker({
        position,
        content: markerEl,
        offset: new amapRef.current.Pixel(-9, -9),
      });
      userMarkerRef.current.setMap(mapRef.current);
    }
  }, [ready, userPos]);

  useEffect(() => {
    if (!ready || viewMode !== 'stores' || !selectedId || !mapRef.current) return;
    if (regionEnabled && drillLevel !== 'city') return;
    const target = scopedStorePoints.find((s) => s.id === selectedId);
    const point = target ? toStoreLngLat(target) : null;
    if (!point) return;
    const currentZoom = mapRef.current.getZoom();
    if (currentZoom < MIN_FOCUS_ZOOM) {
      mapRef.current.setZoom(MIN_FOCUS_ZOOM, true);
    }
    mapRef.current.setCenter(point, true);
  }, [ready, viewMode, selectedId, scopedStorePoints, drillLevel]);

  useEffect(() => {
    if (resetToken > 0) {
      setDrillLevel('province');
      setActiveProvince(null);
      setActiveProvinceAdcode(null);
      setActiveCity(null);
      clearRegionOverlays();
      recenter();
    }
  }, [resetToken, recenter, clearRegionOverlays]);

  const telLink = selectedStore?.phone ? `tel:${selectedStore.phone}` : '';
  const hasCoord = typeof selectedStore?.latitude === 'number' && typeof selectedStore?.longitude === 'number';
  const isFavorite = (id: string) => favoritesSet.has(id);

  const openMapService = (service: 'gaode' | 'tencent' | 'baidu') => {
    if (!selectedStore || !hasCoord) return;
    const lat = selectedStore.latitude;
    const lng = selectedStore.longitude;
    const name = encodeURIComponent(selectedStore.storeName);
    const addr = encodeURIComponent(selectedStore.address || '');
    let url = '';
    if (service === 'gaode') {
      url = `https://uri.amap.com/marker?position=${lng},${lat}&name=${name}&coordinate=wgs84&callnative=1`;
    } else if (service === 'tencent') {
      url = `https://map.qq.com/?type=marker&isopeninfowin=1&marker=coord:${lat},${lng};title:${name};addr:${addr}`;
    } else {
      url = `https://api.map.baidu.com/marker?location=${lat},${lng}&title=${name}&content=${addr}&output=html&coord_type=wgs84`;
    }
    window.open(url, '_blank');
  };

  const favoriteBtnClass = selectedStore
    ? selectedStore.brand === 'DJI'
      ? isFavorite(selectedStore.id)
        ? 'bg-slate-900 text-white border-slate-900'
        : 'bg-slate-100 text-slate-900 border-slate-200'
      : isFavorite(selectedStore.id)
        ? 'bg-yellow-400 text-slate-900 border-yellow-400'
        : 'bg-yellow-50 text-amber-700 border-amber-200'
    : 'bg-slate-100 text-slate-900 border-slate-200';

  const handleZoom = (delta: number) => {
    if (!mapRef.current) return;
    const current = mapRef.current.getZoom();
    const [minZoom = 3, maxZoom = 20] = mapRef.current.getZooms?.() ?? [3, 20];
    const next = Math.min(maxZoom, Math.max(minZoom, current + delta));
    mapRef.current.setZoom(next);
  };

  return (
    <div className="relative w-full h-full rounded-[28px] overflow-visible shadow-[0_16px_44px_rgba(15,23,42,0.08)] bg-gradient-to-b from-[#f9fafc] to-[#eef1f7] border border-white">
      <div className="absolute inset-0 rounded-[28px] overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(15,23,42,0.06),transparent_25%),radial-gradient(circle_at_80%_40%,rgba(254,230,0,0.18),transparent_30%)] pointer-events-none z-0" />
        <div
          id={mapId}
          ref={containerRef}
          className="absolute inset-0 z-[1]"
          style={{ minHeight: '100%', minWidth: '100%' }}
        />
      </div>
      {showControls && (
        <div className="absolute top-4 right-4 z-[100] flex flex-col gap-2">
          <button className="w-10 h-10 rounded-full bg-white shadow border border-slate-200 flex items-center justify-center" onClick={recenter}>
            <Crosshair className="w-4 h-4 text-slate-700" />
          </button>
          <button
            className="w-10 h-10 rounded-full bg-white shadow border border-slate-200 flex items-center justify-center"
            onClick={() => handleZoom(1)}
          >
            <Plus className="w-4 h-4 text-slate-700" />
          </button>
          <button
            className="w-10 h-10 rounded-full bg-white shadow border border-slate-200 flex items-center justify-center"
            onClick={() => handleZoom(-1)}
          >
            <Minus className="w-4 h-4 text-slate-700" />
          </button>
        </div>
      )}
      {viewMode === 'stores' && regionMode === 'none' && (
        <div className="absolute top-4 left-4 z-[95] pointer-events-none">
          <div className="bg-white/90 backdrop-blur-md border border-white/70 shadow-lg rounded-2xl px-3 py-2 flex flex-col gap-2 text-[11px] font-semibold text-slate-700 pointer-events-auto min-w-[160px]">
            <div className="flex items-center gap-2">
              <span className="store-marker store-marker--dji">
                <img src={djiLogoWhite} alt="DJI" className="store-marker__logo" />
              </span>
              <span>DJI 门店</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="store-marker store-marker--insta">
                <img src={instaLogoBlack} alt="Insta360" className="store-marker__logo" />
              </span>
              <span>Insta 门店</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="store-marker store-marker--dji store-marker--new">
                <img src={djiLogoWhite} alt="本月新增" className="store-marker__logo" />
              </span>
              <span>本月新增（双环高亮）</span>
            </div>
          </div>
        </div>
      )}
      {showNavSelector && selectedStore && (
        <div className="absolute inset-0 z-[250] bg-black/30 backdrop-blur-sm flex items-center justify-center px-4">
          <div className="bg-white rounded-3xl shadow-2xl border border-slate-100 w-full max-w-sm p-5 space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-base font-bold text-slate-900">选择导航应用</div>
                <div className="text-xs text-slate-500 mt-1 line-clamp-2">{selectedStore.storeName}</div>
              </div>
              <button
                className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-500"
                onClick={() => setShowNavSelector(false)}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { key: 'gaode', label: '高德地图' },
                { key: 'tencent', label: '腾讯地图' },
                { key: 'baidu', label: '百度地图' },
              ].map((item) => (
                <button
                  key={item.key}
                  className="h-11 rounded-2xl bg-slate-900 text-white text-xs font-bold border border-slate-900 hover:bg-slate-800 active:bg-slate-700 transition-colors"
                  onClick={() => {
                    openMapService(item.key as 'gaode' | 'tencent' | 'baidu');
                    setShowNavSelector(false);
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
      {loadError && (
        <div className="absolute inset-0 z-[200] bg-white/85 backdrop-blur-sm flex flex-col items-center justify-center text-center px-6 text-sm text-slate-600 gap-2">
          <p className="font-semibold text-slate-900">地图暂时无法加载</p>
          <p>{loadError}</p>
          <p className="text-xs text-slate-400">请检查高德 Key 设置或网络连接后重试。</p>
        </div>
      )}
      {viewMode === 'stores' && drillLevel === 'city' && activeProvince && !activeCity && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[180] w-[min(360px,88vw)] pointer-events-none">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-100 p-3 pointer-events-auto">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-bold text-slate-900">{activeProvince} - 省内对比</div>
              <div className="text-xs text-slate-500">仅当前筛选</div>
            </div>
            <div className="space-y-2">
              <div className="w-full h-3 rounded-full bg-slate-100 overflow-hidden">
                {(() => {
                  const total = provinceFilteredStats.total || 1;
                  const djiPct = Math.round((provinceFilteredStats.dji / total) * 100);
                  return (
                    <div className="flex h-full">
                      <div className="h-full" style={{ width: `${djiPct}%`, background: DJI_COLOR }} />
                      <div className="h-full flex-1" style={{ background: INSTA_COLOR }} />
                    </div>
                  );
                })()}
              </div>
              <div className="flex items-center justify-between text-xs text-slate-700">
                <span>DJI: {provinceFilteredStats.dji}</span>
                <span>Insta: {provinceFilteredStats.insta}</span>
                <span>总计: {provinceFilteredStats.total}</span>
              </div>
            </div>
          </div>
        </div>
      )}
      {viewMode === 'stores' && drillLevel === 'city' && activeProvince && activeCity && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[180] w-[min(360px,88vw)] pointer-events-none">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-100 p-3 pointer-events-auto">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-bold text-slate-900">{activeCity} - 城市对比</div>
              <div className="text-xs text-slate-500">仅当前筛选</div>
            </div>
            <div className="space-y-2">
              <div className="w-full h-3 rounded-full bg-slate-100 overflow-hidden">
                {(() => {
                  const total = cityFilteredStats.total || 1;
                  const djiPct = Math.round((cityFilteredStats.dji / total) * 100);
                  return (
                    <div className="flex h-full">
                      <div className="h-full" style={{ width: `${djiPct}%`, background: DJI_COLOR }} />
                      <div className="h-full flex-1" style={{ background: INSTA_COLOR }} />
                    </div>
                  );
                })()}
              </div>
              <div className="flex items-center justify-between text-xs text-slate-700">
                <span>DJI: {cityFilteredStats.dji}</span>
                <span>Insta: {cityFilteredStats.insta}</span>
                <span>总计: {cityFilteredStats.total}</span>
              </div>
            </div>
          </div>
        </div>
      )}
      {showPopup && viewMode === 'stores' && selectedStore && (!regionEnabled || drillLevel === 'city') && (
        <div className="absolute bottom-4 left-4 right-4 z-[200] animate-slide-up pointer-events-auto max-h-[50vh] overflow-y-auto" style={{ willChange: 'transform' }}>
          <div className="bg-white rounded-2xl shadow-xl border border-slate-100 relative overflow-hidden pointer-events-auto">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onSelect('');
              }}
              className="absolute top-3 right-3 p-2 hover:bg-slate-100 rounded-full transition-colors z-10 bg-white shadow-sm"
            >
              <X className="w-5 h-5 text-slate-600" />
            </button>
            <div className="p-4 pr-12">
              <div className="flex gap-3 items-start mb-2">
              <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 overflow-hidden shadow-sm ${
                    selectedStore.brand === 'DJI' ? 'bg-white border border-slate-900' : 'bg-white border border-amber-300'
                  }`}
                >
                  <img src={selectedStore.brand === 'DJI' ? djiLogoWhite : instaLogoYellow} alt={selectedStore.brand} className="w-9 h-9" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-sm font-bold text-slate-900 leading-tight mb-0.5 truncate">
                      {selectedStore.storeName}
                    </div>
                    {isNewThisMonth(selectedStore) && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500 text-white shadow-sm">
                        NEW
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 line-clamp-1">{selectedStore.address}</div>
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                <button
                  className={`flex-1 h-9 rounded-lg text-xs font-bold border transition-colors flex items-center justify-center gap-2 ${favoriteBtnClass}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleFavorite?.(selectedStore.id);
                  }}
                >
                  <Star
                    className={`w-4 h-4 ${
                      isFavorite(selectedStore.id) ? 'fill-current' : ''
                    } ${selectedStore.brand === 'DJI' ? 'text-white stroke-white' : 'text-amber-700 stroke-amber-700'}`}
                  />
                  收藏
                </button>
                <button
                  className="flex-1 h-9 rounded-lg bg-slate-100 text-slate-900 text-xs font-bold border border-slate-200 hover:bg-slate-200 active:bg-slate-300 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (telLink) window.location.href = telLink;
                  }}
                  disabled={!telLink}
                >
                  拨打电话
                </button>
                <button
                  className="flex-1 h-9 rounded-lg bg-slate-900 text-white text-xs font-bold border border-slate-900 hover:bg-slate-800 active:bg-slate-700 transition-colors disabled:opacity-40"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!hasCoord) return;
                    setShowNavSelector(true);
                  }}
                  disabled={!hasCoord}
                >
                  地图导航
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
// @ts-nocheck
