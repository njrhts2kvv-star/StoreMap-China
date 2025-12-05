import { useState } from 'react';
import HomePage from './pages/HomePage';
import { ThemeProvider } from './components/theme/ThemeProvider';
import { DashboardShell } from './components/layout/DashboardShell';

export default function App() {
  const [activePage, setActivePage] = useState<'overview' | 'competition' | 'map' | 'list' | 'log' | 'settings'>('overview');

  return (
    <ThemeProvider defaultTheme="light">
      <DashboardShell activePage={activePage} onNavigate={(page) => setActivePage(page as any)}>
        <HomePage activeTabOverride={activePage === 'settings' ? 'overview' : activePage} onActiveTabChange={(tab) => setActivePage(tab as any)} />
      </DashboardShell>
    </ThemeProvider>
  );
}
