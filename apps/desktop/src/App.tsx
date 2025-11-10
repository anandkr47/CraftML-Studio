import { BrowserRouter, Routes, Route } from "react-router-dom";
import React from "react";
import EnhancedDashboard from "./pages/EnhancedDashboard";
import HardwareDetection from "./pages/HardwareDetection";
import DatasetManager from "./pages/DatasetManager";
import CrawlerManager from "./pages/CrawlerManager";
import EnhancedTrainingConsole from "./pages/EnhancedTrainingConsole";
import TrainingJobView from "./pages/TrainingJobView";
import CompressionPlayground from "./pages/CompressionPlayground";
import DeploymentConsole from "./pages/DeploymentConsole";
import Playground from "./pages/Playground";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";
import Sidebar from "./layout/Sidebar";
import Header from "./layout/Header";
import { ThemeProvider } from "./providers/ThemeProvider";
import { ToastContainer } from "./components/ui/Toast";
import UpdatePrompt from "./components/UpdatePrompt";

function App() {
  return (
    <ThemeProvider defaultTheme="system">
      <BrowserRouter>
        <div className="flex h-screen bg-neutral-50 dark:bg-neutral-950 transition-colors duration-200">
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden">
            <Header />
            <main className="flex-1 overflow-y-auto bg-neutral-50 dark:bg-neutral-900">
              <Routes>
                <Route path="/" element={<EnhancedDashboard />} />
                <Route path="/hardware" element={<HardwareDetection />} />
                <Route path="/datasets" element={<DatasetManager />} />
                <Route path="/crawler" element={<CrawlerManager />} />
                <Route path="/train" element={<EnhancedTrainingConsole />} />
                <Route path="/train/job/:jobId" element={<TrainingJobView />} />
                <Route path="/compress" element={<CompressionPlayground />} />
                <Route path="/deploy" element={<DeploymentConsole />} />
                <Route path="/playground" element={<Playground />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </main>
          </div>
        </div>
        <ToastContainer />
        <UpdatePrompt />
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
