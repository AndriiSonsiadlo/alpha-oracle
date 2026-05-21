"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { StrategyConfig } from "@/lib/api";
import { Settings2, Save, X } from "lucide-react";
import { cn } from "@/lib/utils";

const CATEGORY_PRESETS = [
  "politics",
  "crypto",
  "sports",
  "economy",
  "tech",
  "science",
  "entertainment",
  "world",
];

interface StrategyFormProps {
  current: StrategyConfig;
  onSave: (config: StrategyConfig, description: string) => void;
  isSaving?: boolean;
}

export function StrategyForm({ current, onSave, isSaving }: StrategyFormProps) {
  const [config, setConfig] = useState<StrategyConfig>({ ...current });
  const [description, setDescription] = useState("");
  const [customInput, setCustomInput] = useState("");

  const toggleCategory = (cat: string) => {
    const c = cat.trim().toLowerCase();
    if (!c) return;
    setConfig((prev) => ({
      ...prev,
      categories: prev.categories.includes(c)
        ? prev.categories.filter((x) => x !== c)
        : [...prev.categories, c],
    }));
  };

  // Accept comma / space / newline separated custom categories.
  const addCustom = () => {
    const parts = customInput
      .split(/[,\s]+/)
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
    if (parts.length) {
      setConfig((prev) => ({
        ...prev,
        categories: Array.from(new Set([...prev.categories, ...parts])),
      }));
    }
    setCustomInput("");
  };

  const handleCustomKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addCustom();
    }
  };

  const customCategories = config.categories.filter(
    (c) => !CATEGORY_PRESETS.includes(c)
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(config, description);
    setDescription("");
  };

  const hasChanges =
    config.kelly_fraction !== current.kelly_fraction ||
    config.max_bet_pct !== current.max_bet_pct ||
    config.min_edge !== current.min_edge ||
    config.min_confidence !== current.min_confidence ||
    config.model_name !== current.model_name ||
    config.provider !== current.provider ||
    config.categories.join(",") !== current.categories.join(",");

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Settings2 className="h-4 w-4 text-accent" />
          <CardTitle>Strategy Config</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Kelly Fraction
              </span>
              <input
                type="number"
                step="0.05"
                min="0.05"
                max="1"
                value={config.kelly_fraction}
                onChange={(e) =>
                  setConfig({ ...config, kelly_fraction: parseFloat(e.target.value) || 0.25 })
                }
                className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm font-mono focus:border-accent focus:outline-none"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Max Bet %
              </span>
              <input
                type="number"
                step="0.01"
                min="0.01"
                max="0.5"
                value={config.max_bet_pct}
                onChange={(e) =>
                  setConfig({ ...config, max_bet_pct: parseFloat(e.target.value) || 0.1 })
                }
                className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm font-mono focus:border-accent focus:outline-none"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Min Edge
              </span>
              <input
                type="number"
                step="0.01"
                min="0.01"
                max="0.5"
                value={config.min_edge}
                onChange={(e) =>
                  setConfig({ ...config, min_edge: parseFloat(e.target.value) || 0.05 })
                }
                className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm font-mono focus:border-accent focus:outline-none"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Min Confidence
              </span>
              <input
                type="number"
                step="0.05"
                min="0.1"
                max="1"
                value={config.min_confidence}
                onChange={(e) =>
                  setConfig({ ...config, min_confidence: parseFloat(e.target.value) || 0.6 })
                }
                className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm font-mono focus:border-accent focus:outline-none"
              />
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              Model
            </span>
            <select
              value={config.model_name}
              onChange={(e) => setConfig({ ...config, model_name: e.target.value })}
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            >
              <option value="llama-3.1-8b-instant">llama-3.1-8b-instant (default)</option>
              <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile</option>
              <option value="openai/gpt-oss-20b">openai/gpt-oss-20b</option>
              <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
              <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
              <option value="gpt-4o">GPT-4o</option>
              <option value="gpt-4o-mini">GPT-4o Mini (cheaper)</option>
              <option value="gpt-4-turbo">GPT-4 Turbo</option>
              <option value="gpt-5-mini">GPT-5 Mini</option>
              <option value="gpt-5.4-nano">GPT-5.4 Nano</option>
              <option value="claude-opus-4-8">Claude Opus 4.8</option>
              <option value="claude-sonnet-4-6">Claude Sonnet 4.6</option>
              <option value="claude-haiku-4-5">Claude Haiku 4.5</option>
            </select>
          </label>

          <label className="block space-y-1">
            <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              Provider
            </span>
            <select
              value={config.provider ?? "auto"}
              onChange={(e) => setConfig({ ...config, provider: e.target.value })}
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            >
              <option value="auto">Auto (detect from model)</option>
              <option value="groq">Groq</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="google">Google (Gemini)</option>
            </select>
          </label>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Categories to follow
              </span>
              <span className="text-[10px] text-muted-foreground">
                {config.categories.length === 0
                  ? "none = all markets"
                  : `${config.categories.length} selected`}
              </span>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {CATEGORY_PRESETS.map((cat) => {
                const active = config.categories.includes(cat);
                return (
                  <button
                    type="button"
                    key={cat}
                    onClick={() => toggleCategory(cat)}
                    className={cn(
                      "rounded-full border px-2.5 py-1 text-xs font-medium capitalize transition-all",
                      active
                        ? "border-accent bg-accent/15 text-accent"
                        : "border-border bg-background text-muted-foreground hover:border-accent/50 hover:text-foreground"
                    )}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>

            {customCategories.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {customCategories.map((cat) => (
                  <span
                    key={cat}
                    className="inline-flex items-center gap-1 rounded-full border border-accent bg-accent/15 px-2.5 py-1 text-xs font-medium capitalize text-accent"
                  >
                    {cat}
                    <button
                      type="button"
                      onClick={() => toggleCategory(cat)}
                      className="text-accent/70 hover:text-accent"
                      aria-label={`Remove ${cat}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}

            <input
              type="text"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              onKeyDown={handleCustomKeyDown}
              onBlur={addCustom}
              placeholder="Add custom category, then Enter"
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none"
            />
          </div>

          <label className="block space-y-1">
            <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
              Commit Message
            </span>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what changed..."
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
            />
          </label>

          <button
            type="submit"
            disabled={!hasChanges || isSaving}
            className={cn(
              "inline-flex w-full items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-all",
              hasChanges
                ? "bg-accent text-white hover:bg-accent/90 active:scale-[0.98]"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
          >
            <Save className="h-3.5 w-3.5" />
            {isSaving ? "Saving..." : "Commit New Version"}
          </button>
        </form>
      </CardContent>
    </Card>
  );
}
