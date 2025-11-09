
import React, { useEffect, useState } from "react";
import { fetchSystemMetrics } from "../api/monitor";
// Chart.js example import (replace with actual chart component if available)
// import { Line } from 'react-chartjs-2';
import ResourceMonitor from "../components/ResourceMonitor";
import { fetchJobCounts } from "../api/jobs";

const Dashboard: React.FC = () => {
  const [jobCounts, setJobCounts] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [systemMetrics, setSystemMetrics] = useState<any>(null);
  // Removed unused metricsLoading state

  useEffect(() => {
    fetchJobCounts()
      .then(setJobCounts)
      .catch(() => setError("Failed to load job counts"))
      .finally(() => setLoading(false));
    fetchSystemMetrics()
      .then(setSystemMetrics)
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-100 py-10 px-2">
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-10">
        {/* Active Jobs Widget */}
        <div className="bg-white rounded-2xl shadow-xl p-8 flex flex-col gap-6 border border-purple-100">
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-2xl font-extrabold text-purple-700 tracking-tight">Active Jobs</h2>
            <span className="ml-auto text-xs text-gray-500">{loading ? "Loading..." : error ? error : "Live"}</span>
          </div>
          <ul className="text-lg text-gray-700 font-mono space-y-2">
            <li>Training: <span className="text-purple-700 font-bold">{jobCounts ? jobCounts.training : "-"} running</span></li>
            <li>Crawling: <span className="text-purple-700 font-bold">{jobCounts ? jobCounts.crawling : "-"} running</span></li>
            <li>Compression: <span className="text-purple-700 font-bold">{jobCounts ? jobCounts.compression : "-"} running</span></li>
          </ul>
          <div className="bg-purple-50 rounded-xl p-4 mt-2">
            {/* Jobs chart using real data */}
            {jobCounts ? (
              <div className="h-32 flex items-center justify-center">
                <svg width="100%" height="100" viewBox="0 0 300 100">
                  <rect x="20" y={100 - jobCounts.training * 10} width="40" height={jobCounts.training * 10} fill="#a78bfa" />
                  <rect x="80" y={100 - jobCounts.crawling * 10} width="40" height={jobCounts.crawling * 10} fill="#7c3aed" />
                  <rect x="140" y={100 - jobCounts.compression * 10} width="40" height={jobCounts.compression * 10} fill="#c4b5fd" />
                  <text x="20" y="95" fontSize="12" fill="#6d28d9">Train</text>
                  <text x="80" y="95" fontSize="12" fill="#6d28d9">Crawl</text>
                  <text x="140" y="95" fontSize="12" fill="#6d28d9">Compress</text>
                </svg>
              </div>
            ) : (
              <div className="h-32 flex items-center justify-center text-purple-300 text-lg">Jobs chart coming soon</div>
            )}
          </div>
          <button className="mt-4 bg-purple-600 text-white px-4 py-2 rounded-xl shadow hover:bg-purple-700 transition font-semibold">View All Jobs</button>
        </div>
        {/* Resource Monitor Widget */}
        <div className="flex flex-col gap-8">
          <ResourceMonitor />
          <div className="bg-white rounded-2xl shadow-xl p-8 border border-blue-100">
            <h2 className="text-2xl font-extrabold text-blue-700 mb-4">System Metrics</h2>
            {/* System metrics chart using real data */}
            {systemMetrics ? (
              <div className="h-32 flex items-center justify-center">
                <svg width="100%" height="100" viewBox="0 0 300 100">
                  <rect x="20" y={100 - systemMetrics.cpu * 100} width="40" height={systemMetrics.cpu * 100} fill="#60a5fa" />
                  <rect x="80" y={100 - systemMetrics.memory * 100} width="40" height={systemMetrics.memory * 100} fill="#2563eb" />
                  <rect x="140" y={100 - systemMetrics.gpu * 100} width="40" height={systemMetrics.gpu * 100} fill="#93c5fd" />
                  <text x="20" y="95" fontSize="12" fill="#1e3a8a">CPU</text>
                  <text x="80" y="95" fontSize="12" fill="#1e3a8a">Memory</text>
                  <text x="140" y="95" fontSize="12" fill="#1e3a8a">GPU</text>
                </svg>
              </div>
            ) : (
              <div className="h-32 flex items-center justify-center text-blue-300 text-lg">System chart coming soon</div>
            )}
            <div className="mt-4 flex gap-3">
              <button className="bg-blue-600 text-white px-4 py-2 rounded-xl shadow hover:bg-blue-700 transition font-semibold">Export Metrics</button>
              <button className="bg-gray-600 text-white px-4 py-2 rounded-xl shadow hover:bg-gray-700 transition font-semibold">View Details</button>
            </div>
          </div>
        </div>
        {/* Quick Links Widget */}
        <div className="bg-white rounded-2xl shadow-xl p-8 flex flex-col gap-6 border border-green-100">
          <h2 className="text-2xl font-extrabold text-green-700 mb-2">Quick Links</h2>
          <ul className="text-lg text-green-700 space-y-2">
            <li><a href="/datasets" className="hover:underline font-semibold">Manage Datasets</a></li>
            <li><a href="/train" className="hover:underline font-semibold">Start Training</a></li>
            <li><a href="/deploy" className="hover:underline font-semibold">Deploy Model</a></li>
          </ul>
          <div className="bg-green-50 rounded-xl p-4 mt-2">
            {/* Example chart placeholder */}
            <div className="h-32 flex items-center justify-center text-green-300 text-lg">Links chart coming soon</div>
            {/* <Line data={...} /> */}
          </div>
          <button className="mt-4 bg-green-600 text-white px-4 py-2 rounded-xl shadow hover:bg-green-700 transition font-semibold">New Project</button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
