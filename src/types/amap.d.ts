declare namespace AMap {
  type LngLatLike = [number, number];

  interface MapOptions {
    viewMode?: '2D' | '3D';
    resizeEnable?: boolean;
    dragEnable?: boolean;
    zoomEnable?: boolean;
    zoom?: number;
    center?: LngLatLike;
    mapStyle?: string;
  }

  class Map {
    constructor(container: string | HTMLElement, opts?: MapOptions);
    setZoomAndCenter(zoom: number, center: LngLatLike, immediately?: boolean): void;
    setZoom(zoom: number, immediately?: boolean): void;
    setCenter(center: LngLatLike, immediately?: boolean): void;
    setFitView(overlays?: Array<Marker | MarkerClusterer>, immediately?: boolean, padding?: [number, number, number, number]): void;
    getZoom(): number;
    getZooms(): [number, number];
    destroy(): void;
  }

  class Pixel {
    constructor(x: number, y: number);
    getX(): number;
    getY(): number;
  }

  interface MarkerOptions {
    position: LngLatLike;
    content?: HTMLElement | string;
    offset?: Pixel;
    zIndex?: number;
  }

  type EventHandler = (event: unknown) => void;

  class Marker {
    constructor(opts: MarkerOptions);
    setMap(map: Map | null): void;
    on(event: string, handler: EventHandler): void;
    setExtData(data: unknown): void;
    setPosition(position: LngLatLike): void;
    setContent(content: HTMLElement | string): void;
    getPosition(): LngLatLike;
  }

  interface MarkerClustererOptions {
    gridSize?: number;
    renderClusterMarker?: (context: { marker: Marker; count: number; cluster: unknown }) => void;
  }

  class MarkerClusterer {
    constructor(map: Map, markers: Marker[], options?: MarkerClustererOptions);
    addMarkers(markers: Marker[], isClear?: boolean): void;
    clearMarkers(): void;
    setMap(map: Map | null): void;
    setData?: (data: Marker[]) => void;
  }

  class MarkerCluster {
    constructor(map: Map, markers: Marker[], options?: MarkerClustererOptions);
    addMarkers(markers: Marker[], isClear?: boolean): void;
    clearMarkers(): void;
    setMap(map: Map | null): void;
    setData?: (data: Marker[]) => void;
  }

  interface AMapStatic {
    Map: typeof Map;
    Marker: typeof Marker;
    Pixel: typeof Pixel;
    MarkerClusterer?: typeof MarkerClusterer;
    MarkerCluster?: typeof MarkerCluster;
    plugin: (pluginName: string | string[], callback: () => void) => void;
  }
}

declare const AMap: AMap.AMapStatic;

interface Window {
  AMap: typeof AMap;
}
