import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

interface Feature {
  icon: string;
  title: string;
  description: string;
}

const features: Feature[] = [
  {
    icon: "🚀",
    title: "Model Training",
    description: "Fine-tune LLMs with LoRA, QLoRA, and full fine-tuning on your local hardware"
  },
  {
    icon: "🧠",
    title: "AI Playground",
    description: "Test and interact with trained models in real-time with an intuitive interface"
  },
  {
    icon: "📊",
    title: "Dataset Management",
    description: "Create, manage, and prepare datasets for training with advanced preprocessing"
  },
  {
    icon: "🕷️",
    title: "Web Crawler",
    description: "Automatically collect and process web data for training datasets"
  },
  {
    icon: "🗜️",
    title: "Model Compression",
    description: "Optimize model size with quantization and pruning techniques"
  },
  {
    icon: "🚢",
    title: "Deployment",
    description: "Deploy your models to production with Docker and cloud integration"
  },
  {
    icon: "📈",
    title: "Job Monitoring",
    description: "Track training progress, view logs, and manage multiple training jobs"
  },
  {
    icon: "⚡",
    title: "Hardware Detection",
    description: "Automatic GPU detection and optimization for maximum performance"
  }
];

export default function LoadingScreen() {
  const [currentFeatureIndex, setCurrentFeatureIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("Initializing backend server...");

  useEffect(() => {
    // Rotate through features every 2 seconds
    const featureInterval = setInterval(() => {
      setCurrentFeatureIndex((prev) => (prev + 1) % features.length);
    }, 2000);

    // Progress simulation (smooth progress bar)
    let progressValue = 0;
    const progressInterval = setInterval(() => {
      if (progressValue < 85) {
        progressValue += 0.5;
        setProgress(progressValue);
      }
    }, 100);

    // Check backend status
    const checkBackend = async () => {
      try {
        const backendStatus = await invoke<string>("backend_status");
        
        if (backendStatus.includes("not running")) {
          setStatus("Launching backend process...");
          setProgress(10);
        } else if (backendStatus.includes("running")) {
          setStatus("Starting API server...");
          setProgress(60);
          
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
              setProgress(100);
              setStatus("Backend ready!");
              clearInterval(featureInterval);
              clearInterval(progressInterval);
            } else {
              setStatus("Initializing API endpoints...");
              setProgress(75);
            }
          } catch {
            // Backend not ready yet
            setStatus("Waiting for API server...");
            setProgress(70);
          }
        } else {
          setStatus("Initializing...");
        }
      } catch (error) {
        setStatus("Starting up...");
      }
    };

    const statusInterval = setInterval(checkBackend, 500);

    return () => {
      clearInterval(featureInterval);
      clearInterval(progressInterval);
      clearInterval(statusInterval);
    };
  }, []);

  const currentFeature = features[currentFeatureIndex];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gradient-to-br from-neutral-900 via-neutral-800 to-neutral-900">
      {/* Animated background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-1/2 -left-1/2 w-full h-full bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-pink-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute top-1/2 right-1/2 w-full h-full bg-gradient-to-br from-cyan-500/10 via-blue-500/10 to-indigo-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
      </div>

      <div className="relative z-10 w-full max-w-4xl mx-auto px-6">
        {/* Logo/Title */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-white mb-4 bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
            CraftML Studio
          </h1>
          <p className="text-neutral-400 text-lg">Local-first AI Infrastructure Platform</p>
        </div>

        {/* Main Content Card */}
        <div className="bg-neutral-800/80 backdrop-blur-xl rounded-2xl p-8 shadow-2xl border border-neutral-700/50">
          {/* Status */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-3 px-4 py-2 bg-neutral-700/50 rounded-full">
              <div className="relative">
                <div className="w-3 h-3 bg-blue-500 rounded-full animate-ping absolute" />
                <div className="w-3 h-3 bg-blue-500 rounded-full relative" />
              </div>
              <span className="text-neutral-200 text-sm font-medium">{status}</span>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mb-8">
            <div className="h-2 bg-neutral-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 rounded-full transition-all duration-300 ease-out relative"
                style={{ width: `${progress}%` }}
              >
                <div className="absolute inset-0 bg-white/20 animate-shimmer" />
              </div>
            </div>
            <div className="flex justify-between mt-2 text-xs text-neutral-400">
              <span>Loading...</span>
              <span>{Math.round(progress)}%</span>
            </div>
          </div>

          {/* Feature Showcase */}
          <div className="bg-neutral-900/50 rounded-xl p-6 border border-neutral-700/30">
            <div
              key={currentFeatureIndex}
              className="text-center animate-fade-in"
            >
              <div className="text-5xl mb-4 animate-bounce-slow">{currentFeature.icon}</div>
              <h3 className="text-2xl font-semibold text-white mb-2">
                {currentFeature.title}
              </h3>
              <p className="text-neutral-300 text-sm leading-relaxed">
                {currentFeature.description}
              </p>
            </div>

            {/* Feature Indicators */}
            <div className="flex justify-center gap-2 mt-6">
              {features.map((_, index) => (
                <div
                  key={index}
                  className={`h-2 rounded-full transition-all duration-300 ${
                    index === currentFeatureIndex
                      ? "w-8 bg-blue-500"
                      : "w-2 bg-neutral-600"
                  }`}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-8">
          <p className="text-neutral-500 text-sm">
            Powered by FastAPI • Built with Tauri • Optimized for Performance
          </p>
        </div>
      </div>

      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        @keyframes bounce-slow {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-shimmer {
          animation: shimmer 2s infinite;
        }
        .animate-bounce-slow {
          animation: bounce-slow 2s ease-in-out infinite;
        }
        .animate-fade-in {
          animation: fade-in 0.5s ease-out;
        }
      `}</style>
    </div>
  );
}

