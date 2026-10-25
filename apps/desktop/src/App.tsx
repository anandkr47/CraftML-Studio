import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import Compress from "./pages/Compress";
import DeploymentConsole from "./pages/DeploymentConsole";
import Chat from "./pages/Chat";
import FineTune from "./pages/FineTune";
import FineTuneJob from "./pages/FineTuneJob";
import KnowledgeBase from "./pages/KnowledgeBase";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";
import Sidebar from "./layout/Sidebar";
import { SystemMonitorBar } from "./components/SystemMonitorBar";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Header from "./layout/Header";
import { ThemeProvider } from "./providers/ThemeProvider";
import { ToastContainer } from "./components/ui/Toast";
import UpdatePrompt from "./components/UpdatePrompt";
import LoadingScreen from "./components/LoadingScreen";
import { useBackendReady } from "./api/backend";

/** Resets the error boundary when the route changes, so navigating away recovers from a crash. */
function RouteBoundary({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary key={location.pathname}>{children}</ErrorBoundary>;
}

function App() {
  const { phase, retry } = useBackendReady();
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

  // Don't render anything until window is shown to avoid white flash
  if (!isWindowShown) {
    return null;
  }

  if (phase.kind !== 'ready') {
    return <LoadingScreen phase={phase} onRetry={retry} />;
  }

  return (
    <ThemeProvider defaultTheme="system">
      <BrowserRouter>
        <div className="flex h-screen bg-neutral-50 dark:bg-neutral-950 transition-colors duration-200">
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden">
            <Header />
            <main className="flex-1 overflow-y-auto bg-neutral-50 dark:bg-neutral-900">
              <RouteBoundary>
              <Routes>
                <Route path="/" element={<Chat />} />
                <Route path="/kb" element={<KnowledgeBase />} />
                <Route path="/finetune" element={<FineTune />} />
                <Route path="/finetune/job/:jobId" element={<FineTuneJob />} />
                <Route path="/compress" element={<Compress />} />
                <Route path="/deploy" element={<DeploymentConsole />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
              </RouteBoundary>
            </main>
            <SystemMonitorBar />
          </div>
        </div>
        <ToastContainer />
        <UpdatePrompt />
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
