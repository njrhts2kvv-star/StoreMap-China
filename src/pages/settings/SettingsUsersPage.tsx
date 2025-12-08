import { SectionHeader } from '../../components/dashboard/SectionHeader';
import { TableCard } from '../../components/dashboard/TableCard';

const mockUsers = [
  { id: 'u1', name: 'Admin Zhang', role: 'Admin', createdAt: '2025-01-01', lastLogin: '2025-12-07' },
  { id: 'u2', name: 'Analyst Li', role: 'Analyst', createdAt: '2025-03-12', lastLogin: '2025-12-06' },
];

export default function SettingsUsersPage() {
  return (
    <div className="space-y-4">
      <SectionHeader title="系统设置 · 用户 & 角色" description="角色/RBAC 占位（Mock 数据）" />
      <TableCard title="用户列表">
        <table className="min-w-full text-sm">
          <thead className="text-left text-neutral-6">
            <tr>
              <th className="py-2">姓名</th>
              <th className="py-2">角色</th>
              <th className="py-2">创建时间</th>
              <th className="py-2">最后登录</th>
            </tr>
          </thead>
          <tbody>
            {mockUsers.map((u) => (
              <tr key={u.id} className="border-t border-neutral-2">
                <td className="py-2">{u.name}</td>
                <td className="py-2">{u.role}</td>
                <td className="py-2">{u.createdAt}</td>
                <td className="py-2">{u.lastLogin}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableCard>
    </div>
  );
}

