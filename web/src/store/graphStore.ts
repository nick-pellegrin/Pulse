import { create } from "zustand";

interface GraphStore {
  selectedNodeId: string | null;
  isPanelOpen: boolean;
  setSelectedNode: (id: string) => void;
  closePanel: () => void;
}

export const useGraphStore = create<GraphStore>((set) => ({
  selectedNodeId: null,
  isPanelOpen: false,
  setSelectedNode: (id) => set({ selectedNodeId: id, isPanelOpen: true }),
  closePanel: () => set({ isPanelOpen: false, selectedNodeId: null }),
}));
