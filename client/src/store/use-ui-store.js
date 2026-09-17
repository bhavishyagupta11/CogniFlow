import { create } from "zustand";
export const useUIStore = create((set) => ({
    archOpen: false,
    setArchOpen: (archOpen) => set({ archOpen }),
    kbOpen: false,
    setKbOpen: (kbOpen) => set({ kbOpen }),
    pdfSource: null,
    setPdfSource: (pdfSource) => set({ pdfSource }),
}));
