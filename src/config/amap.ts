// 收口高德 Web JS API Key，方便后续统一替换或通过环境变量注入
// 优先级：环境变量 > 代码中的 key > 占位符
const PLACEHOLDER_KEY = '<a0470c5af7971b0bb14f9664591e9a79>';

// 如果需要在代码中直接设置 key（不推荐，但可用于部署），请在这里设置
// 注意：这会暴露在代码中，建议使用环境变量
const HARDCODED_KEY = '';

const envKey = import.meta.env.VITE_AMAP_KEY?.trim();
const finalKey = envKey || HARDCODED_KEY || PLACEHOLDER_KEY;
export const AMAP_KEY = finalKey;
export const IS_AMAP_KEY_PLACEHOLDER = !envKey && !HARDCODED_KEY && PLACEHOLDER_KEY.startsWith('<');
