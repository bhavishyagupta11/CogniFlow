import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
    return twMerge(clsx(inputs));
}

/**
 * Defensively normalizes any input to an array of non-empty strings.
 * - arrays remain arrays (with null/undefined filtered and items stringified)
 * - strings become single-item arrays
 * - null / undefined become []
 * - objects are safely converted to an array of their string values
 */
export function normalizeArray(val) {
    if (val === null || val === undefined) {
        return [];
    }
    if (Array.isArray(val)) {
        return val
            .flatMap((item) => (item !== null && item !== undefined ? normalizeArray(item) : []))
            .filter(Boolean);
    }
    if (typeof val === "string") {
        const trimmed = val.trim();
        return trimmed ? [trimmed] : [];
    }
    if (typeof val === "object") {
        try {
            return Object.values(val)
                .flatMap((item) => (item !== null && item !== undefined ? normalizeArray(item) : []))
                .filter(Boolean);
        } catch {
            return [];
        }
    }
    const str = String(val).trim();
    return str ? [str] : [];
}

