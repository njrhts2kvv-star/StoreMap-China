import { SectionHeader } from '../../components/dashboard/SectionHeader';

export default function SettingsSystemPage() {
  return (
    <div className="space-y-4">
      <SectionHeader title="系统配置" description="城市等级映射等说明占位" />
      <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 space-y-3 text-sm text-neutral-7">
        <div className="font-semibold text-neutral-9">城市等级映射</div>
        <p>T1、新一线、T2、T3+ 的判定规则占位，可连接后端配置。</p>
        <div className="font-semibold text-neutral-9">数据模式</div>
        <p>当前为 API 优先模式，仍保留 mock 兜底；可在 env 中切换生产/测试。</p>
      </div>
    </div>
  );
}

