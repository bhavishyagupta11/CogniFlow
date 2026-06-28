import { promises as fs } from "fs";
import * as path from "path";

export interface ManifestEntry {
  schemaVersion: number;
  id: string;
  filename: string;
  originalFilename: string;
  mimeType: string;
  size: number;
  uploadedAt: string; // ISO string
  lastModified: string; // ISO string
  chunkCount: number;
  chunkIds: string[];
  processingStatus: "queued" | "uploading" | "extracting" | "chunking" | "embedding" | "indexing" | "completed" | "failed";
  embeddingStatus: "pending" | "completed" | "failed";
  hash: string;
  errorMessage: string | null;
}

const DATA_DIR = path.join(process.cwd(), "data");
const MANIFEST_PATH = path.join(DATA_DIR, "manifest.json");

// Simple in-memory promise chain lock to prevent concurrent read/writes to the manifest
let manifestLock: Promise<void> = Promise.resolve();

async function withLock<T>(fn: () => Promise<T>): Promise<T> {
  const currentLock = manifestLock;
  let release: () => void;
  const nextLock = new Promise<void>((resolve) => {
    release = resolve;
  });
  manifestLock = currentLock.then(() => nextLock);

  try {
    await currentLock;
    return await fn();
  } finally {
    release!();
  }
}

export async function getManifest(): Promise<ManifestEntry[]> {
  return withLock(async () => {
    try {
      const data = await fs.readFile(MANIFEST_PATH, "utf-8");
      return JSON.parse(data) as ManifestEntry[];
    } catch (err: any) {
      if (err.code === "ENOENT") {
        return [];
      }
      // Handle corruption: log warning, backup, return empty array
      console.warn("[ManifestService] Manifest corrupted. Backing up and starting fresh.", err);
      try {
        await fs.rename(MANIFEST_PATH, `${MANIFEST_PATH}.corrupted-${Date.now()}`);
      } catch (e) {
        // Ignore backup error
      }
      return [];
    }
  });
}

export async function updateManifest(updateFn: (entries: ManifestEntry[]) => void | Promise<void>): Promise<ManifestEntry[]> {
  return withLock(async () => {
    // We already hold the lock, so we can't call getManifest() directly as it would deadlock.
    // Let's read directly here instead.
    await fs.mkdir(DATA_DIR, { recursive: true });
    
    let entries: ManifestEntry[] = [];
    try {
      const data = await fs.readFile(MANIFEST_PATH, "utf-8");
      entries = JSON.parse(data) as ManifestEntry[];
    } catch (err: any) {
      if (err.code !== "ENOENT") {
        console.warn("[ManifestService] Manifest corrupted. Starting fresh.", err);
      }
    }

    await updateFn(entries);
    
    // Atomic write
    const tempPath = `${MANIFEST_PATH}.tmp`;
    await fs.writeFile(tempPath, JSON.stringify(entries, null, 2), "utf-8");
    await fs.rename(tempPath, MANIFEST_PATH);
    
    return entries;
  });
}
