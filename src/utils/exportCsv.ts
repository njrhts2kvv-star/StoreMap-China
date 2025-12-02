import type { Store, Mall } from '../types/store';

/**
 * 导出门店清单为 CSV
 * 包含字段：store_id, brand, name, address, city, province, mall_name, store_type, opened_at, status
 */
export function exportStoresToCsv(stores: Store[], filename = 'Store_Master_Cleaned.csv') {
  const headers = ['store_id', 'brand', 'name', 'address', 'city', 'province', 'mall_name', 'store_type', 'opened_at', 'status'];
  
  const rows = stores.map((store) => [
    store.id || '',
    store.brand || '',
    store.storeName || '',
    store.address || '',
    store.city || '',
    store.province || '',
    store.mallName || '',
    store.storeType || '',
    store.openedAt || '',
    store.status || '',
  ]);

  downloadCsv(headers, rows, filename);
}

/**
 * 导出商场清单为 CSV
 * 包含字段：mall_id, mall_name, city, province
 */
export function exportMallsToCsv(malls: Mall[], filename = 'Mall_Master_Cleaned.csv') {
  const headers = ['mall_id', 'mall_name', 'city', 'province'];
  
  const rows = malls.map((mall) => [
    mall.mallId || '',
    mall.mallName || '',
    mall.city || '',
    mall.province || '',
  ]);

  downloadCsv(headers, rows, filename);
}

/**
 * 导出门店变化日志为 CSV
 * 包含字段：store_id, brand, store_name, province, city, change_type, timestamp
 */
export function exportChangeLogsToCsv(
  logs: Array<{
    storeId: string;
    brand: string;
    storeName: string;
    province: string;
    city: string;
    changeType: string;
    timestamp: string;
  }>,
  filename = 'Store_Change_Logs.csv'
) {
  const headers = ['store_id', 'brand', 'store_name', 'province', 'city', 'change_type', 'timestamp'];
  
  const rows = logs.map((log) => [
    log.storeId || '',
    log.brand || '',
    log.storeName || '',
    log.province || '',
    log.city || '',
    log.changeType || '',
    log.timestamp || '',
  ]);

  downloadCsv(headers, rows, filename);
}

/**
 * 通用 CSV 下载函数
 */
function downloadCsv(headers: string[], rows: string[][], filename: string) {
  // 转义 CSV 字段（处理逗号、引号、换行）
  const escapeField = (field: string) => {
    if (field.includes(',') || field.includes('"') || field.includes('\n')) {
      return `"${field.replace(/"/g, '""')}"`;
    }
    return field;
  };

  const csvContent = [
    headers.join(','),
    ...rows.map((row) => row.map(escapeField).join(',')),
  ].join('\n');

  // 添加 BOM 以确保 Excel 正确识别 UTF-8
  const bom = '\uFEFF';
  const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=utf-8;' });
  
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

