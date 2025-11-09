
import React, { useEffect, useState } from "react";
import { fetchSystemMetrics } from "../api/monitor";
import { FiCpu, FiHardDrive, FiServer, FiActivity } from "react-icons/fi";

const ResourceMonitor: React.FC = () => {
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchSystemMetrics()
      .then(setMetrics)
      .catch(() => setError("Failed to load metrics"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-2xl shadow-2xl p-8 flex flex-col gap-6 border border-blue-100">
      <div className="flex items-center gap-3 mb-4">
        <FiActivity size={28} className="text-blue-500" />
        <span className="text-2xl font-extrabold text-blue-700 tracking-tight drop-shadow">System Resources</span>
        <span className="ml-auto text-xs text-gray-500">{loading ? "Loading..." : error ? error : "Live"}</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow-lg p-6 flex flex-col items-center border border-blue-100">
          <FiCpu size={24} className="text-blue-400 mb-2" />
          <span className="text-base text-gray-500 font-semibold">CPU Usage</span>
          <span className="text-2xl font-mono text-blue-600 mb-2">{metrics ? `${metrics.cpu?.cpu_percent?.toFixed?.(1) ?? 0}%` : "-"}</span>
          <div className="w-full bg-blue-100 rounded h-2">
            <div className="bg-blue-500 h-2 rounded" style={{ width: metrics ? `${metrics.cpu?.cpu_percent ?? 0}%` : "0%" }}></div>
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-lg p-6 flex flex-col items-center border border-blue-100">
          <FiServer size={24} className="text-green-400 mb-2" />
          <span className="text-base text-gray-500 font-semibold">Memory Usage</span>
          <span className="text-2xl font-mono text-green-600 mb-2">{metrics ? `${metrics.memory?.percent?.toFixed?.(1) ?? 0}%` : "-"}</span>
          <div className="w-full bg-green-100 rounded h-2">
            <div className="bg-green-500 h-2 rounded" style={{ width: metrics ? `${metrics.memory?.percent ?? 0}%` : "0%" }}></div>
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-lg p-6 flex flex-col items-center border border-blue-100">
          <FiHardDrive size={24} className="text-purple-400 mb-2" />
          <span className="text-base text-gray-500 font-semibold">Disk Usage</span>
          <span className="text-2xl font-mono text-purple-600 mb-2">{metrics ? `${metrics.disk?.percent?.toFixed?.(1) ?? 0}%` : "-"}</span>
          <div className="w-full bg-purple-100 rounded h-2">
            <div className="bg-purple-500 h-2 rounded" style={{ width: metrics ? `${metrics.disk?.percent ?? 0}%` : "0%" }}></div>
          </div>
        </div>
      </div>
      {metrics && metrics.gpus && metrics.gpus.length > 0 && (
        <div className="mt-6">
          <div className="text-base font-bold mb-3 text-blue-700 flex items-center gap-2">
            <FiServer size={20} className="text-blue-400" /> GPU(s)
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {metrics.gpus.map((gpu: any) => (
              <div key={gpu.id} className="bg-white rounded-xl shadow-lg p-4 flex flex-col border border-blue-100">
                <span className="text-base text-gray-500 font-semibold mb-1">{gpu.name}</span>
                <span className="text-sm">Load: <span className="font-mono text-blue-600">{Number(gpu.gpu_util ?? 0).toFixed(1)}%</span></span>
                <div className="w-full bg-blue-100 rounded h-2 my-1">
                  <div className="bg-blue-500 h-2 rounded" style={{ width: `${Number(gpu.gpu_util ?? 0).toFixed(1)}%` }}></div>
                </div>
                <span className="text-sm">Memory: <span className="font-mono text-green-600">{Number(gpu.memory_util ?? 0).toFixed(1)}%</span></span>
                <div className="w-full bg-green-100 rounded h-2 my-1">
                  <div className="bg-green-500 h-2 rounded" style={{ width: `${Number(gpu.memory_util ?? 0).toFixed(1)}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ResourceMonitor;
