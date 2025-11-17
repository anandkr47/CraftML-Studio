import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
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
import LoadingScreen from "./components/LoadingScreen";
import { invoke } from "@tauri-apps/api/core";

function App() {
  const [isBackendReady, setIsBackendReady] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [isWindowShown, setIsWindowShown] = useState(false);

  // Show window once React is ready to render
  useEffect(() => {
    const showWindow = async () => {
      try {
        // Dynamically import to avoid build-time issues
        const { getCurrentWindow } = await import("@tauri-apps/api/window");
        const appWindow = getCurrentWindow();
        await appWindow.show();
        setIsWindowShown(true);
      } catch (error) {
        console.error("Failed to show window:", error);
        // Continue anyway - window might already be visible
        setIsWindowShown(true);
      }
    };
    
    // Small delay to ensure React has rendered
    const timer = setTimeout(showWindow, 50);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const checkBackendHealth = async () => {
      let attempts = 0;
      const maxAttempts = 150; // 30 seconds (150 * 200ms)

      const check = async () => {
        try {
          // Check if backend process is running
          const status = await invoke<string>("backend_status");
          
          if (status.includes("running")) {
            // Try to ping health endpoint
            try {
              const controller = new AbortController();
              const timeoutId = setTimeout(() => controller.abort(), 1000);
              const response = await fetch("http://127.0.0.1:5000/api/health", {
                method: "GET",
                signal: controller.signal,
              });
              clearTimeout(timeoutId);
              
              if (response.ok) {
                setIsBackendReady(true);
                setIsChecking(false);
                return;
              }
            } catch (error) {
              // Backend not ready yet, continue checking
            }
          }

          attempts++;
          if (attempts < maxAttempts) {
            setTimeout(check, 200); // Check every 200ms
          } else {
            // Timeout - show app anyway after 30 seconds
            setIsBackendReady(true);
            setIsChecking(false);
          }
        } catch (error) {
          attempts++;
          if (attempts < maxAttempts) {
            setTimeout(check, 200);
          } else {
            setIsBackendReady(true);
            setIsChecking(false);
          }
        }
      };

      // Start checking after a small delay
      setTimeout(check, 500);
    };

    checkBackendHealth();
  }, []);

  // Don't render anything until window is shown to avoid white flash
  if (!isWindowShown) {
    return null;
  }

  if (isChecking || !isBackendReady) {
    return <LoadingScreen />;
  }

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
