import { create } from "zustand";
import type { QueryHistoryItem, UCEEvent } from "../types/uce";

interface UCEState {
  history: QueryHistoryItem[];
  events: UCEEvent[];
  addHistory: (item: QueryHistoryItem) => void;
  addEvent: (event: UCEEvent) => void;
  clearHistory: () => void;
}

export const useUCEStore = create<UCEState>((set) => ({
  history: JSON.parse(localStorage.getItem("uce.queryHistory") ?? "[]"),
  events: [],
  addHistory: (item) =>
    set((state) => {
      const history = [item, ...state.history.filter((entry) => entry.query_id !== item.query_id)].slice(0, 20);
      localStorage.setItem("uce.queryHistory", JSON.stringify(history));
      return { history };
    }),
  addEvent: (event) =>
    set((state) => ({
      events: [event, ...state.events.filter((entry) => entry.id !== event.id)].slice(0, 100),
    })),
  clearHistory: () => {
    localStorage.removeItem("uce.queryHistory");
    set({ history: [] });
  },
}));

