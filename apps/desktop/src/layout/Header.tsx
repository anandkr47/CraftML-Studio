/**
 * Header Component
 * Top navigation bar with theme toggle and system stats
 */

import { useEffect, useState } from "react";
import { Moon, Sun, Monitor, Cpu, Activity } from "lucide-react";
import { useTheme } from "../providers/ThemeProvider";
import { Badge } from "../components/ui/Badge";
import { apiService } from "../services/api.service";

const Header = () => {
  const { theme, setTheme, actualTheme } = useTheme();
  const [gpuInfo, setGpuInfo] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchSystemInfo = async () => {
      try {
        const metrics = await apiService.getSystemMetrics();
        if (metrics.gpus && metrics.gpus.length > 0) {
          setGpuInfo(metrics.gpus[0]);
        }
      } catch (error) {
        console.error("Failed to fetch system info:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSystemInfo();
    // Refresh every 5 seconds
    const interval = setInterval(fetchSystemInfo, 5000);
    return () => clearInterval(interval);
  }, []);

  const themeIcons = {
    light: Sun,
    dark: Moon,
    system: Monitor,
  };

  const ThemeIcon = themeIcons[theme];

  const cycleTheme = () => {
    const themes: Array<'light' | 'dark' | 'system'> = ['light', 'dark', 'system'];
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };

  return (
    <header className="h-16 bg-white dark:bg-neutral-900 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between px-6">
      {/* Left Section */}
      <div className="flex items-center gap-4">
        <div>
          <h1 className="text-xl font-bold text-neutral-900 dark:text-neutral-100">
            CraftML Studio
          </h1>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            Local-first AI Infrastructure
          </p>
        </div>
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-4">
        {/* System Stats */}
        {!isLoading && gpuInfo && (
          <div className="hidden md:flex items-center gap-3 px-3 py-2 bg-neutral-50 dark:bg-neutral-800 rounded-lg">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-brand-500" />
              <div className="text-xs">
                <p className="font-medium text-neutral-700 dark:text-neutral-300">
                  {gpuInfo.name}
                </p>
                <p className="text-neutral-500 dark:text-neutral-400">
                  VRAM: {Math.round(gpuInfo.memory_util)}%
                </p>
              </div>
            </div>
            <div className="w-px h-8 bg-neutral-200 dark:bg-neutral-700" />
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-success-500" />
              <div className="text-xs">
                <p className="font-medium text-neutral-700 dark:text-neutral-300">GPU Load</p>
                <p className="text-neutral-500 dark:text-neutral-400">
                  {Math.round(gpuInfo.gpu_util)}%
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Status Badge */}
        <Badge variant="success" dot>
          Online
        </Badge>

        {/* Theme Toggle */}
        <button
          onClick={cycleTheme}
          className="p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-600 dark:text-neutral-400 transition-colors"
          aria-label={`Current theme: ${theme}. Click to change.`}
          title={`Current: ${theme} (${actualTheme})`}
        >
          <ThemeIcon className="w-5 h-5" />
        </button>

        {/* User Avatar */}
        <div className="flex items-center gap-2 pl-3 border-l border-neutral-200 dark:border-neutral-800">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center">
            <span className="text-white text-sm font-semibold">U</span>
          </div>
          <div className="hidden lg:block">
            <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100">User</p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">Local Admin</p>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
