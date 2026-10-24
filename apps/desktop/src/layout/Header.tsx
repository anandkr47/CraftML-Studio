/**
 * Header Component
 * App title and theme toggle
 */

import { Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "../providers/ThemeProvider";

const THEME_ORDER = ["light", "dark", "system"] as const;
const THEME_ICONS = { light: Sun, dark: Moon, system: Monitor };

const Header = () => {
  const { theme, setTheme, actualTheme } = useTheme();
  const ThemeIcon = THEME_ICONS[theme];

  const cycleTheme = () => {
    setTheme(THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length]);
  };

  return (
    <header className="h-14 bg-white dark:bg-neutral-900 border-b border-neutral-200 dark:border-neutral-800 flex items-center justify-between px-6">
      <div>
        <h1 className="text-lg font-bold text-neutral-900 dark:text-neutral-100">CraftML Studio</h1>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">Local AI Engine</p>
      </div>

      <button
        onClick={cycleTheme}
        className="p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-600 dark:text-neutral-400 transition-colors"
        aria-label={`Current theme: ${theme}. Click to change.`}
        title={`Current: ${theme} (${actualTheme})`}
      >
        <ThemeIcon className="w-5 h-5" />
      </button>
    </header>
  );
};

export default Header;
