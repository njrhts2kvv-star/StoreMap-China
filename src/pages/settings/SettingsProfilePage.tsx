import { SectionHeader } from '../../components/dashboard/SectionHeader';

export default function SettingsProfilePage() {
  return (
    <div className="space-y-4">
      <SectionHeader title="个人资料" description="基本信息与偏好（占位）" />
      <div className="rounded-xl border border-neutral-3 bg-neutral-0 p-4 space-y-3">
        <label className="flex flex-col gap-1 text-sm text-neutral-7">
          昵称
          <input
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0"
            placeholder="请输入昵称"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-neutral-7">
          邮箱
          <input
            className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0"
            placeholder="you@example.com"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-neutral-7">
          语言
          <select className="border border-neutral-3 rounded-md px-2 py-1 bg-neutral-0">
            <option>简体中文</option>
            <option>English</option>
          </select>
        </label>
        <div className="text-xs text-neutral-5">此页面为占位，后续接入真实用户中心。</div>
      </div>
    </div>
  );
}

