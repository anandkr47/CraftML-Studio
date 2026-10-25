import { useState, useEffect } from "react";
import { fetchBackendLogs, type BackendLogs, type BackendPhase } from "../api/backend";

interface Feature {
  icon: string;
  title: string;
  description: string;
}

const features: Feature[] = [
  {
    icon: "💬",
    title: "Chat Studio",
    description: "Chat with local models, tune sampling parameters, and ground answers in your own documents"
  },
  {
    icon: "🧠",
    title: "Fine-Tune",
    description: "No-code LoRA and QLoRA fine-tuning with live loss curves and automatic checkpoints"
  },
  {
    icon: "🗜️",
    title: "Compress",
    description: "Quantize models to GGUF, INT4/INT8, GPTQ or AWQ and compare size, quality and speed"
  },
  {
    icon: "📚",
    title: "Knowledge Base",
    description: "Drop in PDFs, Markdown, text and Word files — embedded and searched entirely on your machine"
  },
  {
    icon: "🚀",
    title: "Deploy & Endpoints",
    description: "Serve models through a local OpenAI-compatible API or publish them to Hugging Face"
  },
  {
    icon: "📊",
    title: "System Monitor",
    description: "Live CPU, RAM and GPU usage with alerts before you run out of memory"
  }
];

interface LoadingScreenProps {
  phase: Exclude<BackendPhase, { kind: "ready" }>;
  onRetry: () => void;
}

export default function LoadingScreen({ phase, onRetry }: LoadingScreenProps) {
  const [currentFeatureIndex, setCurrentFeatureIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<BackendLogs | null>(null);
  const failed = phase.kind === "failed";

  useEffect(() => {
    if (failed) return;
    // Rotate through features and ease the (indicative) progress bar towards 90%.
    const featureInterval = setInterval(() => {
      setCurrentFeatureIndex((prev) => (prev + 1) % features.length);
    }, 2500);
    const progressInterval = setInterval(() => {
      setProgress((p) => (p < 90 ? p + (90 - p) * 0.03 : p));
    }, 150);
    return () => {
      clearInterval(featureInterval);
      clearInterval(progressInterval);
    };
  }, [failed]);

  useEffect(() => {
    if (failed) fetchBackendLogs().then(setLogs);
    else setLogs(null);
  }, [failed]);

  const status = failed ? "The backend could not start" : phase.detail;
  const logTail = logs ? (logs.stderr.trim() || logs.stdout.trim()).split("\n").slice(-40).join("\n") : "";

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
                {!failed && <div className="w-3 h-3 bg-blue-500 rounded-full animate-ping absolute" />}
                <div className={`w-3 h-3 rounded-full relative ${failed ? "bg-red-500" : "bg-blue-500"}`} />
              </div>
              <span className="text-neutral-200 text-sm font-medium">{status}</span>
            </div>
          </div>

          {/* Progress Bar */}
          {!failed && (
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
          )}

          {failed && (
            <div className="bg-red-950/40 rounded-xl p-6 border border-red-800/50 text-left">
              <p className="text-red-200 text-sm mb-4 whitespace-pre-wrap">{phase.error}</p>
              {logTail && (
                <pre className="max-h-56 overflow-auto text-xs text-neutral-300 bg-neutral-950/70 rounded-lg p-3 mb-4 whitespace-pre-wrap">
                  {logTail}
                </pre>
              )}
              {logs && <p className="text-neutral-400 text-xs mb-4 break-all">Logs: {logs.log_dir}</p>}
              <button
                onClick={onRetry}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium"
              >
                Retry
              </button>
            </div>
          )}

          {/* Feature Showcase */}
          {!failed && (
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
          )}
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

