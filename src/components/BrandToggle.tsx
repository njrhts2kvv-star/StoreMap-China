import type { Brand } from '../types/store';
import { getNextBrandSelection } from '../utils/brandSelection';

type Props = { value: Brand[]; onChange: (v: Brand[]) => void };

export default function BrandToggle({ value, onChange }: Props) {
  const toggle = (b: Brand) => {
    onChange(getNextBrandSelection(value, b));
  };
  return (
    <div className="flex gap-2">
      {(['DJI', 'Insta360'] as Brand[]).map((b) => (
        <button
          key={b}
          onClick={() => toggle(b)}
          className={`px-3 py-2 rounded-2xl text-sm font-semibold transition shadow-sm ${
            value.includes(b)
              ? b === 'DJI'
                ? 'bg-slate-900 text-white shadow-[0_10px_24px_rgba(15,23,42,0.25)]'
                : 'bg-[#fee600] text-slate-900 shadow-[0_10px_24px_rgba(253,224,71,0.3)]'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          {b}
        </button>
      ))}
    </div>
  );
}
