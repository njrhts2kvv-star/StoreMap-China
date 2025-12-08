type MapPlaceholderProps = {
  title: string;
  height?: number;
  note?: string;
};

export function MapPlaceholder({ title, height = 280, note }: MapPlaceholderProps) {
  return (
    <div className="rounded-xl border border-neutral-3 bg-neutral-0 shadow-sm p-4 flex flex-col gap-2">
      <div className="text-sm font-semibold text-neutral-9">{title}</div>
      <div
        className="w-full rounded-lg border border-dashed border-neutral-3 bg-neutral-1/60 text-neutral-5 flex items-center justify-center text-xs"
        style={{ height }}
      >
        地图占位（可接高德 JS SDK）
      </div>
      {note && <div className="text-[11px] text-neutral-5">{note}</div>}
    </div>
  );
}

