// 动态引入高德 JS SDK，避免首屏阻塞
import { AMAP_KEY, IS_AMAP_KEY_PLACEHOLDER } from '../config/amap';

let amapPromise: Promise<typeof window.AMap> | null = null;

export function loadAmap(): Promise<typeof window.AMap> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('AMap can only be loaded in browser'));
  }

  if (IS_AMAP_KEY_PLACEHOLDER) {
    return Promise.reject(new Error('高德 Web JS API Key 未配置，请在 .env.local 中设置 VITE_AMAP_KEY'));
  }

  if (window.AMap) {
    return Promise.resolve(window.AMap);
  }

  if (!amapPromise) {
    amapPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = `https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}`;
      script.async = true;
      script.onload = () => {
        if (window.AMap) {
          resolve(window.AMap);
        } else {
          reject(new Error('AMap not available'));
        }
      };
      script.onerror = () => reject(new Error('无法加载高德地图 SDK，请检查网络或 Key 设置'));
      document.head.appendChild(script);
    });
  }

  return amapPromise;
}
