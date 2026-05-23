"use client";

import { Activity, ServerCrash, RefreshCw, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface BackendDownProps {
  onRetry: () => void;
  isRetrying?: boolean;
  detail?: string | null;
}

export function BackendDown({ onRetry, isRetrying, detail }: BackendDownProps) {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-12">
      <div className="flex items-center gap-3 mb-8">
        <div className="rounded-xl bg-accent/20 p-2">
          <Activity className="h-5 w-5 text-accent" />
        </div>
        <h1 className="text-xl font-bold">
          Alpha<span className="text-accent">Oracle</span>
        </h1>
      </div>

      <div className="w-full max-w-md rounded-2xl border border-red-500/30 bg-red-500/5 p-8 text-center space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-500/15">
          <ServerCrash className="h-6 w-6 text-red-400" />
        </div>

        <div className="space-y-1.5">
          <h2 className="text-lg font-semibold text-red-400">Can&apos;t reach the backend</h2>
          <p className="text-sm text-muted-foreground">
            The dashboard couldn&apos;t connect to the API server. Make sure it&apos;s running, then retry.
          </p>
        </div>

        <div className="rounded-lg bg-black/30 p-3 text-left">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
            Start the backend
          </p>
          <code className="block font-mono text-xs text-zinc-300 break-all">
            cd backend &amp;&amp; uvicorn app.main:app --reload --port 8000
          </code>
        </div>

        {detail && (
          <p className="text-[10px] text-red-400/60 font-mono break-all">{detail}</p>
        )}

        <button
          onClick={onRetry}
          disabled={isRetrying}
          className={cn(
            "inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-all",
            "bg-accent text-white hover:bg-accent/90 active:scale-[0.98] disabled:opacity-50"
          )}
        >
          {isRetrying ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          {isRetrying ? "Retrying…" : "Retry connection"}
        </button>
      </div>
    </div>
  );
}
