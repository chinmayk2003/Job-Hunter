"use client";

import { useEffect, useState } from "react";
import { 
  Server, 
  Cpu, 
  Database, 
  Activity, 
  ExternalLink, 
  CheckCircle2, 
  AlertCircle,
  Briefcase,
  Layers,
  ShieldAlert
} from "lucide-react";

interface ServiceStatus {
  status: "loading" | "online" | "offline";
  details?: string;
}

export default function Home() {
  const [backendStatus, setBackendStatus] = useState<ServiceStatus>({ status: "loading" });

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch("/api/v1/health");
        if (res.ok) {
          const data = await res.json();
          setBackendStatus({ status: "online", details: data.message || "FastAPI is running smoothly" });
        } else {
          setBackendStatus({ status: "offline", details: `Error: ${res.status}` });
        }
      } catch (err) {
        setBackendStatus({ status: "offline", details: "Unable to reach backend service" });
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between p-6 md:p-12 relative overflow-hidden select-none">
      {/* Background Gradients */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[60%] rounded-full bg-violet-900/20 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[60%] rounded-full bg-blue-900/20 blur-[120px] pointer-events-none" />

      {/* Header */}
      <header className="flex justify-between items-center z-10">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
            <Briefcase className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-slate-400">
            JobHunter <span className="text-violet-500">AI</span>
          </span>
        </div>
        <div className="flex gap-4">
          <a
            href="/flower"
            target="_blank"
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-slate-300 hover:text-white glass-panel rounded-full transition-all duration-200"
            id="flower-link"
          >
            Flower Dashboard <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </header>

      {/* Hero Body */}
      <div className="max-w-4xl mx-auto w-full my-auto py-12 z-10 flex flex-col items-center text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-violet-500/30 bg-violet-500/10 text-violet-400 text-xs font-semibold uppercase tracking-wider mb-6 animate-pulse">
          <Activity className="w-3.5 h-3.5" /> Development Environment Ready
        </div>

        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-6 bg-clip-text text-transparent bg-gradient-to-b from-white to-slate-400">
          The Production-Grade AI <br />
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-violet-400 via-fuchsia-500 to-indigo-400">
            Job Hunting Engine
          </span>
        </h1>

        <p className="text-slate-400 text-lg md:text-xl max-w-2xl mb-12">
          Full stack microservices boilerplate initialized. Scalable layout featuring Clerk Authentication, Cloudflare R2, PostgreSQL, Redis, and Celery.
        </p>

        {/* Live Service Status Checks */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 w-full max-w-3xl mb-12">
          {/* Frontend Card */}
          <div className="glass-panel p-6 rounded-2xl flex flex-col items-start text-left glass-card-hover">
            <div className="p-3 bg-blue-500/10 text-blue-400 rounded-xl mb-4">
              <Layers className="w-6 h-6" />
            </div>
            <h3 className="font-semibold text-lg mb-1">Frontend App</h3>
            <p className="text-xs text-slate-400 mb-4">Next.js 14 App Router, Zustand, React Query</p>
            <div className="flex items-center gap-1.5 mt-auto text-xs text-green-400 font-semibold bg-green-500/10 px-2 py-1 rounded-full">
              <CheckCircle2 className="w-3.5 h-3.5" /> Online
            </div>
          </div>

          {/* Backend Card */}
          <div className="glass-panel p-6 rounded-2xl flex flex-col items-start text-left glass-card-hover">
            <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl mb-4">
              <Server className="w-6 h-6" />
            </div>
            <h3 className="font-semibold text-lg mb-1">FastAPI Backend</h3>
            <p className="text-xs text-slate-400 mb-4">FastAPI Uvicorn server connected to DB</p>
            {backendStatus.status === "online" ? (
              <div className="flex items-center gap-1.5 mt-auto text-xs text-green-400 font-semibold bg-green-500/10 px-2 py-1 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" /> Online
              </div>
            ) : backendStatus.status === "loading" ? (
              <div className="flex items-center gap-1.5 mt-auto text-xs text-amber-400 font-semibold bg-amber-500/10 px-2 py-1 rounded-full animate-pulse">
                <Activity className="w-3.5 h-3.5" /> Checking Connection
              </div>
            ) : (
              <div className="flex items-center gap-1.5 mt-auto text-xs text-rose-400 font-semibold bg-rose-500/10 px-2 py-1 rounded-full">
                <AlertCircle className="w-3.5 h-3.5" /> Offline
              </div>
            )}
          </div>

          {/* Celery Workers Card */}
          <div className="glass-panel p-6 rounded-2xl flex flex-col items-start text-left glass-card-hover">
            <div className="p-3 bg-purple-500/10 text-purple-400 rounded-xl mb-4">
              <Cpu className="w-6 h-6" />
            </div>
            <h3 className="font-semibold text-lg mb-1">Celery Workers</h3>
            <p className="text-xs text-slate-400 mb-4">Background task runners via Redis Broker</p>
            <div className="flex items-center gap-1.5 mt-auto text-xs text-amber-400 font-semibold bg-amber-500/10 px-2 py-1 rounded-full">
              <Database className="w-3.5 h-3.5" /> Active (via Broker)
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="w-full text-center text-xs text-slate-500 border-t border-slate-900 pt-6 mt-12 z-10 flex flex-col sm:flex-row justify-between items-center gap-4">
        <p>© 2026 JobHunter AI. All rights reserved.</p>
        <div className="flex gap-4">
          <span>PostgreSQL & Redis Status: Ready</span>
          <span className="text-slate-700">|</span>
          <span>Docker Sandbox Deployment</span>
        </div>
      </footer>
    </main>
  );
}
