"use client";

import { cn } from "@/lib/cn";

export type AgentState = "idle" | "speaking" | "listening" | "processing";

interface SoundWaveProps {
    state: AgentState;
    barCount?: number;
    className?: string;
}

const stateColors: Record<AgentState, string> = {
    idle: "bg-slate-600",
    speaking: "bg-teal-400",
    listening: "bg-amber-400",
    processing: "bg-teal-300",
};

const stateAnims: Record<AgentState, string> = {
    idle: "idle-bar",
    speaking: "speak-bar",
    listening: "listen-bar",
    processing: "idle-bar",
};

export function SoundWave({ state, barCount = 24, className }: SoundWaveProps) {
    const bars = Array.from({ length: barCount }, (_, i) => i);

    return (
        <div className={cn("flex items-center justify-center gap-[3px]", className)}>
            {bars.map((i) => {
                const center = barCount / 2;
                const dist = Math.abs(i - center) / center;
                const delay = dist * 0.3 + Math.random() * 0.08;
                const maxScale = 1.0 - dist * 0.4;

                return (
                    <div
                        key={i}
                        className={cn(
                            "w-[3px] rounded-full transition-colors duration-300",
                            stateColors[state],
                            stateAnims[state],
                        )}
                        style={{
                            height: `${28 + (1 - dist) * 32}px`,
                            animationDelay: `${delay}s`,
                            animationDuration: state === "speaking" ? `${0.4 + Math.random() * 0.35}s` : undefined,
                            maxHeight: `${maxScale * 60}px`,
                        }}
                    />
                );
            })}
        </div>
    );
}

export function AgentStatusText({ state }: { state: AgentState }) {
    const labels: Record<AgentState, string> = {
        idle: "Ready",
        speaking: "Speaking…",
        listening: "Listening…",
        processing: "Thinking…",
    };

    const dotColors: Record<AgentState, string> = {
        idle: "bg-slate-400",
        speaking: "bg-teal-400",
        listening: "bg-amber-400",
        processing: "bg-teal-300",
    };

    return (
        <div className="flex items-center gap-2 text-sm text-slate-400">
            <div className={cn("w-2 h-2 rounded-full pulse-dot", dotColors[state])} />
            <span>{labels[state]}</span>
        </div>
    );
}