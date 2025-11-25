import { useState } from 'react';
import type { Store } from '../types/store';
import StoreList from './StoreList';

type Props = {
  selectedStore: Store | null;
  stores: Store[];
  totalCount: number;
  favorites: string[];
  onToggleFavorite: (id: string) => void;
  onSelect: (id: string) => void;
  onClearSelection: () => void;
};

/**
 * 底部抽屉：包含筛选入口 + 门店列表 + 选中门店详情
 * - 初始最大高度 45%，可展开到 70%
 * - 简化：不再内置二级筛选，只保留列表与“已选”提示
 */
export default function BottomSheet({
  selectedStore,
  stores,
  totalCount,
  favorites,
  onToggleFavorite,
  onSelect,
  onClearSelection,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const heightClass = expanded ? 'max-h-[70vh]' : 'max-h-[45vh]';

  return (
    <div className={`mt-3 bg-white rounded-t-2xl shadow-md border border-slate-100 overflow-hidden ${heightClass} flex flex-col`}>
      <div className="p-3 border-b border-slate-100 flex items-center justify-between">
        <div className="w-10 h-1 rounded-full bg-slate-300" onClick={() => setExpanded(!expanded)} />
        <div className="text-sm text-slate-600">共 {totalCount} 家</div>
        <div className="text-xs text-blue-600" />
      </div>

      {selectedStore && (
        <div className="px-3 pt-2 flex items-center justify-between text-xs text-slate-600 bg-slate-50">
          <span>已选：{selectedStore.storeName}</span>
          <button className="text-blue-600" onClick={onClearSelection}>
            返回全部
          </button>
        </div>
      )}

      <div className="flex-1 overflow-auto">
        <StoreList
          stores={stores}
          favorites={favorites}
          onToggleFavorite={onToggleFavorite}
          onSelect={onSelect}
          selectedId={selectedStore?.id}
        />
      </div>

      {/* 下方不再渲染大号详情卡片，避免重复信息 */}
    </div>
  );
}
