import { create } from "zustand";
export const useUIStore = create((set) => ({
    archOpen: false,
    setArchOpen: (archOpen) => set({ archOpen }),
    kbOpen: false,
    setKbOpen: (kbOpen) => set({ kbOpen }),
    activeDocument: null,
    setActiveDocument: (activeDocument) => set({ activeDocument, pdfSource: activeDocument }),
    pdfSource: null,
    setPdfSource: (pdfSource) => set({ pdfSource, activeDocument: pdfSource }),
    traceOpen: true,
    setTraceOpen: (traceOpen) => set({ traceOpen }),
}));
