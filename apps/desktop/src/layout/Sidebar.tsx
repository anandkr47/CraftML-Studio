/**
 * Sidebar Navigation Component
 * Modern, collapsible sidebar with smooth animations
 */

import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  BookOpen,
  PlayCircle,
  Minimize2,
  Send,
  ChevronLeft,
  ChevronRight,
  Zap,
  MessageSquare,
  Cpu as CpuIcon,
  Settings as SettingsIcon,
} from "lucide-react";

const navItems = [
  { name: "Chat", path: "/", icon: MessageSquare },
  { name: "Fine-Tune", path: "/finetune", icon: PlayCircle },
  { name: "Compress", path: "/compress", icon: Minimize2 },
  { name: "Knowledge Base", path: "/kb", icon: BookOpen },
  { name: "Deploy & Endpoints", path: "/deploy", icon: Send },
  { name: "Settings", path: "/settings", icon: SettingsIcon },
];

const Sidebar = () => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`${
        collapsed ? "w-20" : "w-64"
      } bg-white dark:bg-neutral-900 border-r border-neutral-200 dark:border-neutral-800 flex flex-col transition-all duration-300 ease-in-out`}
    >
      {/* Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-neutral-200 dark:border-neutral-800">
        <div
          className={`flex items-center gap-2 overflow-hidden transition-all duration-300 ${
            collapsed ? "opacity-0 w-0" : "opacity-100 w-auto"
          }`}
        >
          <div className="flex items-center justify-center w-8 h-8 bg-gradient-to-br from-brand-500 to-brand-600 rounded-lg">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold text-neutral-900 dark:text-neutral-100 whitespace-nowrap">
            CraftML
          </span>
        </div>
        
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-2 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-600 dark:text-neutral-400 transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg font-medium text-sm transition-all duration-200 group ${
                  isActive
                    ? "bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-300"
                    : "text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={`w-5 h-5 flex-shrink-0 ${
                      isActive
                        ? "text-brand-600 dark:text-brand-400"
                        : "text-neutral-500 dark:text-neutral-400 group-hover:text-neutral-700 dark:group-hover:text-neutral-300"
                    }`}
                  />
                  <span
                    className={`overflow-hidden transition-all duration-300 whitespace-nowrap ${
                      collapsed ? "opacity-0 w-0" : "opacity-100 w-auto"
                    }`}
                  >
                    {item.name}
                  </span>
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-neutral-200 dark:border-neutral-800">
        <div
          className={`flex items-center gap-3 px-3 py-2 rounded-lg bg-neutral-50 dark:bg-neutral-800 overflow-hidden transition-all duration-300 ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <CpuIcon className="w-5 h-5 text-brand-500 flex-shrink-0" />
          <div
            className={`overflow-hidden transition-all duration-300 ${
              collapsed ? "opacity-0 w-0" : "opacity-100 w-auto"
            }`}
          >
            <p className="text-xs font-medium text-neutral-900 dark:text-neutral-100 whitespace-nowrap">
              Local Mode
            </p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 whitespace-nowrap">v{__APP_VERSION__}</p>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
