import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function bloomColor(level: 1 | 2 | 3 | 4 | 5): string {
  return {
    1: "text-bloom-1 bg-bloom-1/10 border-bloom-1/30",
    2: "text-bloom-2 bg-bloom-2/10 border-bloom-2/30",
    3: "text-bloom-3 bg-bloom-3/10 border-bloom-3/30",
    4: "text-bloom-4 bg-bloom-4/10 border-bloom-4/30",
    5: "text-bloom-5 bg-bloom-5/10 border-bloom-5/30",
  }[level];
}

export function severityColor(severity: number): string {
  if (severity >= 0.7) return "text-red-400 bg-red-500/10 border-red-500/30";
  if (severity >= 0.4) return "text-amber-400 bg-amber-500/10 border-amber-500/30";
  return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
}