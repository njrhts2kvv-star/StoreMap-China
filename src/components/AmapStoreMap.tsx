// 用高德 JS API 重写门店地图，复刻原有交互和视觉
// @ts-nocheck
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Crosshair, Minus, Plus, Star, X } from 'lucide-react';
import type { Mall, Store } from '../types/store';
import { loadAmap } from '../utils/loadAmap';
import djiLogoBlack from '../assets/dji_logo_black_small.svg';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoBlack from '../assets/insta360_logo_black_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';
import { isNewThisMonth } from '../utils/storeRules';
import { MALL_STATUS_COLORS } from '../config/competitionColors';
import { lighten, mixColors } from '../utils/color';

// 根据商场属性计算点位颜色（与商场标签配色保持一致）
const getCompetitionMallColor = (mall: Mall): string => {
  const hasDJI = mall.djiOpened;
  const hasInsta = mall.instaOpened;
  const isPtMall = mall.djiExclusive === true; // PT 商场
  const isTarget = mall.djiTarget === true && !mall.djiOpened; // 目标未进驻：DJI Target 且尚未开业
  const isGap = mall.status === 'gap'; // 缺口机会（DJI 有布局但 Insta 未进）
  const isBothOpened = hasDJI && hasInsta;
  const isBothNone = !hasDJI && !hasInsta;
  const isInstaOnly = hasInsta && !hasDJI;
  const isDjiOnly = hasDJI && !hasInsta;

  // 按优先级返回颜色
  if (isPtMall) return '#EF4444';      // 红色 - PT商场
  if (isGap) return '#FFFFFF';         // 白色 - 缺口机会
  if (isTarget) return '#3B82F6';      // 蓝色 - 目标未进驻
  if (isBothOpened) return '#22C55E';  // 绿色 - 均进驻
  if (isBothNone) return '#94A3B8';    // 灰色 - 均未进驻
  if (isInstaOnly) return '#F5C400';   // 黄色 - 仅 Insta 进驻
  if (isDjiOnly) return '#111827';     // 深黑色 - 仅 DJI 进驻

  return '#9CA3AF'; // 默认灰色
};

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
  showLegend?: boolean; // 是否显示新增门店图例
  isFullscreen?: boolean; // 是否全屏模式（无圆角）
};

const DEFAULT_CENTER: [number, number] = [35.5, 103.5];
const DEFAULT_ZOOM = 3.2; // 默认进一步缩小
const CHINA_BOUNDS = { sw: [73, 15] as [number, number], ne: [135, 54] as [number, number] };
const MIN_FOCUS_ZOOM = 11;
const CITY_MAX_ZOOM = 10; // 城市层最高放大，避免直接落到街道级
const DJI_COLOR = '#111827';
const INSTA_COLOR = '#facc15';
const NO_DATA_COLOR = '#e5e7eb';
const CLUSTER_ZOOM_THRESHOLD = 9;
const CLUSTER_GRID_SIZE = 80;

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
  showLegend = false,
  isFullscreen = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<AMap.Map | null>(null);
  const markersRef = useRef<AMap.Marker[]>([]);
  const userMarkerRef = useRef<AMap.Marker | null>(null);
  const amapRef = useRef<typeof AMap | null>(null);
  const clusterRef = useRef<AMap.MarkerClusterer | null>(null);
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
  const [drillLevel, setDrillLevel] = useState<DrillLevel>('province'); // 默认全国视图
  const [activeProvince, setActiveProvince] = useState<string | null>(null);
  const [activeCity, setActiveCity] = useState<string | null>(null);
  const [provinceShapes, setProvinceShapes] = useState<RegionShape[]>([]);
  const [cityShapesByProvince, setCityShapesByProvince] = useState<Record<string, RegionShape[]>>({});
  const [activeProvinceAdcode, setActiveProvinceAdcode] = useState<string | null>(null);
  const regionPolygonsRef = useRef<any[]>([]);
  const geoCacheRef = useRef<Record<string, RegionShape[]>>({});
  const hasInitialCenteredRef = useRef(false);
  const markersReadyRef = useRef(false);
  const lastFocusedIdRef = useRef<string | null>(null);
  const popupRef = useRef<HTMLDivElement | null>(null);
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

  // 重置视野到中国边界
  function recenter() {
    if (!mapRef.current) return;
    mapRef.current.setZoomAndCenter(DEFAULT_ZOOM, normalizedCenter, true);
  }

  const focusOnStore = useCallback(
    (store: Store | null) => {
      if (!mapRef.current || !store) return false;
      const point = toStoreLngLat(store);
      if (!point) return false;
      setActiveProvince(store.province || null);
      setActiveCity(store.city || null);
      setDrillLevel('city');
      const currentZoom = mapRef.current.getZoom();
      const targetZoom = Math.max(currentZoom, MIN_FOCUS_ZOOM);
      mapRef.current.setZoomAndCenter(targetZoom, point, true);
      if (showPopup && containerRef.current && mapRef.current?.lngLatToContainer) {
        window.setTimeout(() => {
          const map = mapRef.current;
          const container = containerRef.current;
          if (!map || !container) return;
          const px = (map as any).lngLatToContainer(point as any);
          if (!px) return;
          const mapRect = container.getBoundingClientRect();
          const popupRect = popupRef.current?.getBoundingClientRect();
          const visibleBottom = popupRect ? popupRect.top - mapRect.top : mapRect.height;
          const targetY = visibleBottom / 2;
          const dy = targetY - px.y;
          if (Math.abs(dy) > 4 && (map as any).panBy) {
            (map as any).panBy(0, dy);
          }
        }, 120);
      }
      lastFocusedIdRef.current = store.id;
      return true;
    },
    [showPopup],
  );

  // 初始进入时将视野对齐中国边界（如果没有选中门店）
  useEffect(() => {
    if (ready && !hasInitialCenteredRef.current) {
      // 如果已有选中的门店，不执行 recenter，让 selectedId 的 useEffect 处理
      if (!selectedId) {
        recenter();
      }
      hasInitialCenteredRef.current = true;
    }
  }, [ready, normalizedCenter, initialZoom, selectedId]);

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
  // 从所有门店中查找选中的门店（而不是仅从 scopedStorePoints），确保全屏地图也能正确显示
  const selectedStore = useMemo(
    () =>
      viewMode === 'stores' && selectedId && selectedId.trim()
        ? stores.find((s) => s.id === selectedId) ?? null
        : null,
    [viewMode, stores, selectedId],
  );
  useEffect(() => {
    setShowNavSelector(false);
  }, [selectedId, viewMode]);

  const destroyMap = useCallback(() => {
    if (clusterRef.current) {
      clusterRef.current.setMap(null);
      clusterRef.current = null;
    }
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
      const nextPolygons: any[] = [];

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
        const polygon = new (AMapLib as any).Polygon({
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
                ? Math.max(current, 5.2)
                : Math.min(Math.max(current, 6.5), CITY_MAX_ZOOM);
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
    if (clusterRef.current) {
      clusterRef.current.setMap(null);
      clusterRef.current = null;
    }
    markersReadyRef.current = false;
    if (viewMode === 'stores') {
      lastFocusedIdRef.current = null;
    }
    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current = [];

    const AMapLib = amapRef.current;
    const nextMarkers: AMap.Marker[] = [];

    const showStoreMarkers = viewMode === 'stores';
    if (showStoreMarkers) {
      stores.forEach((store) => {
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
          markerClass += store.brand === 'DJI' ? ' store-marker--dji-new' : ' store-marker--insta-new';
        }
        if (isFavorite) {
          markerClass += ' store-marker--favorite';
        }
        markerEl.className = markerClass.trim();
        if (isSelected) markerEl.classList.add('store-marker--selected');
        markerEl.title = store.storeName;

        const logoImg = document.createElement('img');
        logoImg.className = 'store-marker__logo';
        const logoSrc = isNew
          ? store.brand === 'DJI'
            ? djiLogoWhite
            : instaLogoYellow
          : store.brand === 'DJI'
            ? djiLogoBlack
            : instaLogoBlack;
        logoImg.src = logoSrc;
        logoImg.alt = store.brand;
        if (isNew && store.brand === 'Insta360') {
          logoImg.classList.add('store-marker__logo--full');
        }
        markerEl.appendChild(logoImg);

        const baseSize = 16;
        const ringExtra = 0;
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
          focusOnStore(store);
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
        const color = viewMode === 'competition' ? getCompetitionMallColor(mall) : '#2563eb';
        markerEl.style.backgroundColor = color;
        if (color === '#FFFFFF') {
          // 缺口机会：白色圆圈 + 极细黑色描边
          markerEl.style.border = '0.5px solid #111827';
        } else {
          markerEl.style.border = '0px solid transparent';
        }
        if (isSelected) markerEl.classList.add('mall-marker--selected');
        markerEl.title = mall.mallName;

        const marker = new AMapLib.Marker({
          position: point,
          content: markerEl,
          offset: new AMapLib.Pixel(-6, -6),
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

    const hasSelection = viewMode === 'stores' ? selectedId : selectedMallId;
    const allowAutoFit = !(viewMode === 'stores' && drillLevel === 'city'); // 城市层不自动按照门店点位缩放
    const shouldFitAll = allowAutoFit && !hasSelection && fitToStores;

    if (showStoreMarkers && nextMarkers.length && mapRef.current) {
      if (!isFullscreen) {
        const ClusterCtor = (AMapLib as any).MarkerClusterer || (AMapLib as any).MarkerCluster;
        if (ClusterCtor) {
          const renderClusterMarker = (context: { count: number; marker: AMap.Marker }) => {
            const size = Math.max(28, Math.min(48, 18 + Math.log(context.count + 1) * 10));
            const div = document.createElement('div');
            div.className = 'store-cluster';
            div.style.width = `${size}px`;
            div.style.height = `${size}px`;
            div.textContent = String(context.count);
            context.marker.setContent(div);
            context.marker.setOffset(new AMapLib.Pixel(-size / 2, -size / 2));
          };

          clusterRef.current = new ClusterCtor(mapRef.current, nextMarkers, {
            gridSize: CLUSTER_GRID_SIZE,
            minClusterSize: 2,
            renderClusterMarker,
            maxZoom: CLUSTER_ZOOM_THRESHOLD,
          } as any);
        } else {
          nextMarkers.forEach((marker) => marker.setMap(mapRef.current!));
        }
      } else {
        // 全屏模式下不使用聚合，直接展示所有门店点位，视野完全由下钻逻辑控制
        nextMarkers.forEach((marker) => marker.setMap(mapRef.current!));
      }
    } else if (nextMarkers.length && mapRef.current) {
      nextMarkers.forEach((marker) => marker.setMap(mapRef.current!));
    }

    if (mapRef.current && nextMarkers.length && (shouldFitAll || (!hasSelection && !hasInitialCenteredRef.current))) {
      const fitTargets: any[] = [];
      if (showStoreMarkers && clusterRef.current) {
        fitTargets.push(clusterRef.current);
      } else {
        fitTargets.push(...nextMarkers);
      }
      mapRef.current.setFitView(fitTargets, false, [80, 40, 80, 80]);
      hasInitialCenteredRef.current = true;
    }
    if (showStoreMarkers && nextMarkers.length) {
      markersReadyRef.current = true;
    }
  }, [
    ready,
    viewMode,
    stores,
    malls,
    favoritesSet,
    autoFitOnClear,
    fitToStores,
    onSelect,
    onMallClick,
    drillLevel,
    regionEnabled,
    isFullscreen,
  ]);

  // 当 selectedMallId 从外部变更（例如点击商场列表卡片或地图上的商场气泡）时，平滑聚焦到对应商场
  useEffect(() => {
    if (!ready || !selectedMallId || !mapRef.current) return;
    const mall = malls.find((m) => m.mallId === selectedMallId);
    if (!mall) return;
    const point = toMallLngLat(mall);
    if (!point) return;
    const currentZoom = mapRef.current.getZoom();
    const targetZoom = Math.max(currentZoom, MIN_FOCUS_ZOOM);
    mapRef.current.setZoomAndCenter(targetZoom, point, true);
  }, [ready, selectedMallId, malls]);

  // 单独处理选中状态的样式更新，避免重新创建所有 markers
  useEffect(() => {
    if (!ready || viewMode !== 'stores' || !markersRef.current) return;
    markersRef.current.forEach((marker) => {
      const store = marker.getExtData() as Store;
      if (!store) return;
      const markerEl = marker.getContent() as HTMLElement;
      if (!markerEl) return;

      const isSelected = selectedId === store.id;
      const setZ = (marker as any).setzIndex?.bind(marker) ?? (marker as any).setZIndex?.bind(marker);

      if (isSelected) {
        markerEl.classList.add('store-marker--selected');
        if (setZ) setZ(140);
      } else {
        markerEl.classList.remove('store-marker--selected');
        const isNew = markerEl.classList.contains('store-marker--new');
        const isFavorite = markerEl.classList.contains('store-marker--favorite');
        if (setZ) setZ(isNew ? 130 : isFavorite ? 120 : 100);
      }
    });
  }, [ready, selectedId, viewMode]);

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

  // 当选中门店时，下钻到门店位置（统一处理总览和全屏进入时已选中的场景）
  useEffect(() => {
    if (!ready || !mapRef.current || !selectedId || viewMode !== 'stores') return;
    if (!markersReadyRef.current) return;
    const target = stores.find((s) => s.id === selectedId);
    if (!target) return;
    if (lastFocusedIdRef.current === selectedId) return;
    focusOnStore(target);
  }, [focusOnStore, ready, selectedId, stores, viewMode]);

  useEffect(() => {
    if (resetToken > 0) {
      setDrillLevel('province');
      setActiveProvince(null);
      setActiveProvinceAdcode(null);
      setActiveCity(null);
      clearRegionOverlays();
      hasInitialCenteredRef.current = false;
      // 如果当前没有选中的门店，则回到全国视图；
      // 有选中门店时交给 selectedId 的下钻逻辑，避免互相抢视野
      if (!selectedId) {
        recenter();
      }
    }
  }, [resetToken, recenter, clearRegionOverlays, selectedId]);

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

  const borderRadius = isFullscreen ? 'rounded-none' : 'rounded-[28px]';
  const controlsTop = isFullscreen ? 'top-[214px]' : 'top-4';

  return (
    <div className={`relative w-full h-full ${borderRadius} ${isFullscreen ? '' : 'shadow-[0_16px_44px_rgba(15,23,42,0.08)] bg-gradient-to-b from-[#f9fafc] to-[#eef1f7] border border-white'} overflow-hidden isolate`}>
      <div className={`absolute inset-0 ${borderRadius} overflow-hidden`}>
        {!isFullscreen && <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(15,23,42,0.06),transparent_25%),radial-gradient(circle_at_80%_40%,rgba(254,230,0,0.18),transparent_30%)] pointer-events-none z-0" />}
        <div
          id={mapId}
          ref={containerRef}
          className="absolute inset-0 z-[1]"
          style={{ minHeight: '100%', minWidth: '100%' }}
        />
      </div>
      {showControls && (
        <div className={`absolute ${controlsTop} right-4 z-10 flex flex-col gap-2`}>
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
      {showNavSelector && selectedStore && (
        <div className="absolute inset-0 z-30 bg-black/30 backdrop-blur-sm flex items-center justify-center px-4">
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
        <div className="absolute inset-0 z-30 bg-white/85 backdrop-blur-sm flex flex-col items-center justify-center text-center px-6 text-sm text-slate-600 gap-2">
          <p className="font-semibold text-slate-900">地图暂时无法加载</p>
          <p>{loadError}</p>
          <p className="text-xs text-slate-400">请检查高德 Key 设置或网络连接后重试。</p>
        </div>
      )}
      {viewMode === 'stores' && drillLevel === 'city' && activeProvince && !activeCity && !selectedStore && (
        <div
          className="absolute left-4 right-4 z-20 pointer-events-none"
          style={{ bottom: isFullscreen ? '104px' : '16px' }}
        >
          <div className="bg-white rounded-2xl shadow-xl border border-slate-100 p-3 pointer-events-auto max-w-[360px] mx-auto">
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
      {viewMode === 'stores' && drillLevel === 'city' && activeProvince && activeCity && !selectedStore && (
        <div
          className="absolute left-4 right-4 z-20 pointer-events-none"
          style={{ bottom: isFullscreen ? '104px' : '16px' }}
        >
          <div className="bg-white rounded-2xl shadow-xl border border-slate-100 p-3 pointer-events-auto max-w-[360px] mx-auto">
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
      {showPopup && viewMode === 'stores' && selectedStore && (
        <div
          ref={popupRef}
          className="absolute left-4 right-4 z-30 animate-slide-up pointer-events-auto max-h-[50vh] overflow-y-auto"
          style={{ willChange: 'transform', bottom: isFullscreen ? '110px' : '16px' }}
        >
          <div className="bg-white rounded-2xl shadow-xl border border-slate-100 relative overflow-hidden pointer-events-auto">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onSelect('');
                // 关闭门店卡片后，回到全国视图
                setDrillLevel('province');
                setActiveProvince(null);
                setActiveProvinceAdcode(null);
                setActiveCity(null);
                recenter();
              }}
              className="absolute top-2 right-2 p-1 hover:bg-slate-100 transition-colors z-10"
            >
              <X className="w-4 h-4 text-slate-400" />
            </button>
            <div className="pt-3 pb-3">
              <div className="flex gap-3 items-start mb-2 px-3 pr-8">
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
                      <span className="px-2 py-[1px] rounded-full text-[9px] font-semibold bg-[#ef4444] text-white shadow-sm relative -top-[1px]">
                        NEW
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-slate-500 line-clamp-1">{selectedStore.address}</div>
                </div>
              </div>
              <div className="border-t border-slate-100 my-2"></div>
              <div className="flex gap-2 px-3">
                <button
                  className={`flex-1 h-[30px] rounded-full text-xs font-bold border transition-colors flex items-center justify-center gap-1.5 ${favoriteBtnClass}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleFavorite?.(selectedStore.id);
                  }}
                >
                  <Star
                    className={`w-4 h-4 ${
                      isFavorite(selectedStore.id)
                        ? 'fill-current text-inherit stroke-inherit'
                        : 'text-slate-900 stroke-slate-900'
                    }`}
                  />
                  收藏
                </button>
                <button
                  className="flex-1 h-[30px] rounded-full bg-slate-100 text-slate-900 text-xs font-bold border border-slate-200 hover:bg-slate-200 active:bg-slate-300 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (telLink) window.location.href = telLink;
                  }}
                  disabled={!telLink}
                >
                  拨打电话
                </button>
                <button
                  className="flex-1 h-[30px] rounded-full bg-slate-100 text-slate-900 text-xs font-bold border border-slate-200 hover:bg-slate-200 active:bg-slate-300 transition-colors disabled:opacity-40"
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
      {showLegend && (
        <div
          className={`absolute flex items-center gap-2 bg-white/80 backdrop-blur-sm rounded-full px-2.5 py-1.5 shadow-sm pointer-events-none z-10 ${
            isFullscreen ? 'left-4 bottom-[110px]' : 'left-3 top-3'
          }`}
        >
          <div className="flex items-center gap-1">
            <span className="store-marker store-marker--insta store-marker--new store-marker--insta-new">
              <img src={instaLogoYellow} alt="Insta360 新增" className="store-marker__logo store-marker__logo--full" />
            </span>
            <span className="text-[10px] text-slate-600">新增</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="store-marker store-marker--dji store-marker--new store-marker--dji-new">
              <img src={djiLogoWhite} alt="DJI 新增" className="store-marker__logo" />
            </span>
            <span className="text-[10px] text-slate-600">新增</span>
          </div>
        </div>
      )}
    </div>
  );
}
