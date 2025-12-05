import { Search, Moon, Sun, Bell } from 'lucide-react';
import { useTheme } from '../theme/ThemeProvider';

export function TopBar() {
  const { theme, setTheme } = useTheme();

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  return (
    <header className="h-16 bg-neutral-0 dark:bg-neutral-0 border-b border-neutral-2 dark:border-neutral-2 flex items-center justify-between px-8 sticky top-0 z-10 transition-colors duration-200">
      <div className="flex-1 max-w-xl">
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-neutral-4" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-3 py-2 border border-neutral-3 dark:border-neutral-3 rounded-xl leading-5 bg-neutral-1 dark:bg-neutral-1 text-neutral-10 dark:text-neutral-10 placeholder-neutral-4 focus:outline-none focus:bg-neutral-0 dark:focus:bg-neutral-0 focus:ring-2 focus:ring-neutral-10 focus:border-transparent sm:text-sm transition-all"
            placeholder="搜索门店、商场或城市..."
          />
        </div>
      </div>

      <div className="flex items-center space-x-4 ml-4">
        <button
          onClick={toggleTheme}
          className="p-2 text-neutral-5 hover:text-neutral-10 rounded-lg hover:bg-neutral-1 transition-colors"
        >
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
        <button className="p-2 text-neutral-5 hover:text-neutral-10 rounded-lg hover:bg-neutral-1 transition-colors relative">
          <Bell className="h-5 w-5" />
          <span className="absolute top-2 right-2 block h-2 w-2 rounded-full bg-red-5 ring-2 ring-neutral-0" />
        </button>
        <div className="w-8 h-8 rounded-full bg-neutral-2 border border-neutral-3" />
      </div>
    </header>
  );
}
