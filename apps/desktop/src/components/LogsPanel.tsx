
import { FiFileText, FiCopy } from "react-icons/fi";
import React from "react";

interface LogsPanelProps {
  logs?: string;
}

const LogsPanel: React.FC<LogsPanelProps> = ({ logs }) => {
  const handleCopy = () => {
    if (logs) {
      navigator.clipboard.writeText(logs);
    }
  };
  return (
    <div className="bg-gradient-to-br from-gray-50 to-blue-100 rounded-2xl shadow-lg p-6 h-56 overflow-y-auto text-xs font-mono border border-blue-100 relative">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 font-bold text-blue-700 text-sm">
          <FiFileText size={18} className="text-blue-400" /> Logs
        </div>
        <button
          className="flex items-center gap-1 px-2 py-1 rounded bg-blue-100 text-blue-700 text-xs font-semibold hover:bg-blue-200 transition"
          onClick={handleCopy}
          title="Copy logs"
        >
          <FiCopy size={14} /> Copy
        </button>
      </div>
      <div className="text-gray-700 whitespace-pre-wrap custom-scrollbar h-full">
        {logs ? logs : <span className="text-gray-400">No logs yet.</span>}
      </div>
      <style>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 8px;
          background: #e0e7ff;
          border-radius: 8px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #60a5fa;
          border-radius: 8px;
        }
      `}</style>
    </div>
  );
};

export default LogsPanel;
