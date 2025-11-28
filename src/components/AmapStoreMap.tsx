// 用高德 JS API 重写门店地图，复刻原有交互和视觉
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Crosshair, Minus, Plus, Star, X } from 'lucide-react';
import type { Store } from '../types/store';
import { loadAmap } from '../utils/loadAmap';
import djiLogoWhite from '../assets/dji_logo_white_small.svg';
import instaLogoYellow from '../assets/insta360_logo_yellow_small.svg';
import type { Store as StoreType } from '../types/store';
import { isNewThisMonth } from '../utils/storeRules';

type Props = {
  stores: Store[];
  selectedId?: string;
  onSelect: (id: string) => void;
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
};

const DEFAULT_CENTER: [number, number] = [35.5, 103.5];
const DEFAULT_ZOOM = 4;
const MIN_FOCUS_ZOOM = 11;

const toLngLat = (store: Store): [number, number] | null => {
  const lat = (store as Store & { lat?: number }).lat ?? store.latitude;
  const lng = (store as Store & { lng?: number }).lng ?? store.longitude;
  if (typeof lat !== 'number' || typeof lng !== 'number') return null;
  return [lng, lat];
};

const isInChinaRough = (store: StoreType): boolean => {
  const lat = (store as any).lat ?? store.latitude;
  const lng = (store as any).lng ?? store.longitude;
  if (typeof lat !== 'number' || typeof lng !== 'number') return false;
  // 中国大致范围：纬度 18-54，经度 73-135
  return lat >= 18 && lat <= 54 && lng >= 73 && lng <= 135;
};

export function AmapStoreMap({
  stores,
  selectedId,
  onSelect,
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
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<AMap.Map | null>(null);
  const markersRef = useRef<AMap.Marker[]>([]);
  const userMarkerRef = useRef<AMap.Marker | null>(null);
  const amapRef = useRef<typeof AMap | null>(null);
  const clusterRef = useRef<AMap.MarkerCluster | AMap.MarkerClusterer | null>(null);
  const favoritesSet = useMemo(() => new Set(favorites), [favorites]);
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const normalizedCenter = useMemo<[number, number]>(() => {
    const [lat = DEFAULT_CENTER[0], lng = DEFAULT_CENTER[1]] = initialCenter ?? DEFAULT_CENTER;
    return [lng, lat];
  }, [initialCenter]);
  const selectedStore = useMemo(() => (selectedId && selectedId.trim() ? stores.find((s) => s.id === selectedId) : null), [stores, selectedId]);
  const [showNavSelector, setShowNavSelector] = useState(false);
  useEffect(() => {
    setShowNavSelector(false);
  }, [selectedId]);

  const destroyMap = useCallback(() => {
    const cluster = clusterRef.current as AMap.MarkerCluster | AMap.MarkerClusterer | null;
    if (cluster) {
      if (typeof (cluster as any).clearMarkers === 'function') {
        (cluster as any).clearMarkers();
      } else if (typeof (cluster as any).setData === 'function') {
        (cluster as any).setData([]);
      }
      if (typeof cluster.setMap === 'function') {
        cluster.setMap(null as unknown as AMap.Map);
      }
      clusterRef.current = null;
    }
    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current = [];
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

  const recenter = useCallback(() => {
    if (!mapRef.current) return;
    mapRef.current.setZoomAndCenter(initialZoom, normalizedCenter, true);
  }, [initialZoom, normalizedCenter]);

  useEffect(() => {
    if (!ready || !mapRef.current || !amapRef.current) return;
    const cluster = clusterRef.current as AMap.MarkerCluster | AMap.MarkerClusterer | null;
    if (cluster) {
      if (typeof (cluster as any).clearMarkers === 'function') {
        (cluster as any).clearMarkers();
      } else if (typeof (cluster as any).setData === 'function') {
        (cluster as any).setData([]);
      }
      if (typeof cluster.setMap === 'function') {
        cluster.setMap(null as unknown as AMap.Map);
      }
      clusterRef.current = null;
    }
    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current = [];

    const AMapLib = amapRef.current;
    const nextMarkers: AMap.Marker[] = [];

    stores.forEach((store) => {
      // 只绘制中国境内门店，避免越界点干扰视图
      if (!isInChinaRough(store)) return;
      const point = toLngLat(store);
      if (!point) return;
      const isFavorite = favoritesSet.has(store.id);
      const isSelected = selectedId === store.id;
      const isNew = isNewThisMonth(store);
      const markerEl = document.createElement('div');
      let markerClass = 'store-marker';
      if (isNew) {
        markerClass += ' store-marker--new';
      } else {
        markerClass += store.brand === 'DJI' ? ' store-marker--dji' : ' store-marker--insta';
      }
      if (isFavorite) {
        markerClass += ' store-marker--favorite';
        if (isNew) {
          markerClass += ' store-marker--favorite-new';
        } else {
          markerClass += store.brand === 'DJI' ? ' store-marker--favorite-dji' : ' store-marker--favorite-insta';
        }
      }
      markerEl.className = markerClass.trim();
      if (isSelected) markerEl.classList.add('store-marker--selected');
      markerEl.title = store.storeName;

      const marker = new AMapLib.Marker({
        position: point,
        content: markerEl,
        offset: new AMapLib.Pixel(-7, -7),
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

    markersRef.current = nextMarkers;
    (window as any).__storeMarkers = nextMarkers;
    console.info('[Map] markers prepared:', nextMarkers.length);

    const adjustView = () => {
      const shouldFitAll = !selectedId && (fitToStores || autoFitOnClear);
      if (mapRef.current && nextMarkers.length && shouldFitAll) {
        mapRef.current.setFitView(nextMarkers, false, [80, 40, 80, 80]);
      } else if (!nextMarkers.length) {
        recenter();
      }
    };

    // 暂时禁用聚合，直接渲染所有点，保证可见性
    if (nextMarkers.length && mapRef.current) {
      nextMarkers.forEach((marker) => marker.setMap(mapRef.current!));
      adjustView();
    } else {
      recenter();
    }
  }, [ready, stores, favoritesSet, selectedId, autoFitOnClear, fitToStores, onSelect, recenter]);

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
        offset: new amapRef.current.Pixel(-7, -7),
      });
      userMarkerRef.current.setMap(mapRef.current);
    }
  }, [ready, userPos]);

  useEffect(() => {
    if (!ready || !selectedId || !mapRef.current) return;
    const target = stores.find((s) => s.id === selectedId);
    const point = target ? toLngLat(target) : null;
    if (!point) return;
    const currentZoom = mapRef.current.getZoom();
    if (currentZoom < MIN_FOCUS_ZOOM) {
      mapRef.current.setZoom(MIN_FOCUS_ZOOM, true);
    }
    mapRef.current.setCenter(point, true);
  }, [ready, selectedId, stores]);

  useEffect(() => {
    if (resetToken > 0) {
      recenter();
    }
  }, [resetToken, recenter]);

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
      {showPopup && selectedStore && (
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
