import { getManifest, updateManifest, ManifestEntry } from "./manifest-service";
import { extractText, deleteDocumentFiles } from "./upload-service";
import { chunkDocument } from "../rag/chunker";
import { getVectorStore, KNOWLEDGE_BASE } from "../rag/vector-store";
import { promises as fs } from "fs";
import * as path from "path";

const DATA_DIR = path.join(process.cwd(), "data");
const EXTRACTED_DIR = path.join(DATA_DIR, "extracted");
const UPLOADS_DIR = path.join(DATA_DIR, "uploads");

export async function rebuildVectorStoreFromManifest() {
  const manifest = await getManifest();
  const completedDocs = manifest.filter(m => m.processingStatus === "completed");
  
  const customDocs = [];
  
  for (const entry of completedDocs) {
    const extPath = path.join(EXTRACTED_DIR, `${entry.id}.txt`);
    try {
      const content = await fs.readFile(extPath, "utf-8");
      customDocs.push({
        id: entry.id,
        title: entry.originalFilename,
        authors: "Uploaded Document",
        year: new Date(entry.uploadedAt).getFullYear(),
        source: "User Upload",
        content: content
      });
    } catch (err) {
      // If extracted text is missing, attempt to re-extract from source
      try {
        console.warn(`[Ingestion] Extracted text missing for ${entry.id}. Attempting re-extraction.`);
        const ext = path.extname(entry.filename);
        const content = await extractText(entry.id, ext);
        customDocs.push({
          id: entry.id,
          title: entry.originalFilename,
          authors: "Uploaded Document",
          year: new Date(entry.uploadedAt).getFullYear(),
          source: "User Upload",
          content: content
        });
      } catch (extractErr) {
        console.warn(`[Ingestion] Re-extraction failed for ${entry.id}. Marking as failed.`);
        await updateManifest(entries => {
          const mEntry = entries.find(e => e.id === entry.id);
          if (mEntry) {
            mEntry.processingStatus = "failed";
            mEntry.errorMessage = "Source file missing or extraction failed on recovery.";
          }
        });
      }
    }
  }

  const store = await getVectorStore();
  store.build([...KNOWLEDGE_BASE, ...customDocs]);
}

export async function processDocument(entryId: string) {
  // Extracting
  await updateManifest(entries => {
    const entry = entries.find(e => e.id === entryId);
    if (entry) entry.processingStatus = "extracting";
  });

  let text = "";
  try {
    const entries = await getManifest();
    const entry = entries.find(e => e.id === entryId);
    if (!entry) throw new Error("Manifest entry not found.");
    
    const ext = path.extname(entry.filename);
    text = await extractText(entryId, ext);
  } catch (err: any) {
    await updateManifest(entries => {
      const entry = entries.find(e => e.id === entryId);
      if (entry) {
        entry.processingStatus = "failed";
        entry.errorMessage = err.message;
      }
    });
    return;
  }

  // Chunking
  await updateManifest(entries => {
    const entry = entries.find(e => e.id === entryId);
    if (entry) entry.processingStatus = "chunking";
  });

  let chunkIds: string[] = [];
  try {
    const entries = await getManifest();
    const entry = entries.find(e => e.id === entryId);
    if (!entry) throw new Error("Manifest entry not found.");
    
    const chunks = chunkDocument(entry.id, entry.originalFilename, text);
    chunkIds = chunks.map(c => c.id);
  } catch (err: any) {
    await updateManifest(entries => {
      const entry = entries.find(e => e.id === entryId);
      if (entry) {
        entry.processingStatus = "failed";
        entry.errorMessage = err.message;
      }
    });
    return;
  }

  // Embedding
  await updateManifest(entries => {
    const entry = entries.find(e => e.id === entryId);
    if (entry) {
      entry.processingStatus = "embedding";
      entry.chunkCount = chunkIds.length;
      entry.chunkIds = chunkIds;
    }
  });

  try {
    // A rebuild handles the embeddings via TfidfEmbedder internally.
    // However, to follow the UI status strictly, we update to "completed" AFTER rebuild.
    
    // To allow the UI to see "embedding", we already updated the manifest.
    // Now we update to "indexing" (or updating vector store) if needed, but we can just rebuild.
    await updateManifest(entries => {
      const entry = entries.find(e => e.id === entryId);
      if (entry) {
        // Mock a state change for the UI to see
        entry.processingStatus = "completed"; // we will temporarily use indexing if we want, but completed is fine because rebuild is synchronous.
      }
    });

    await updateManifest(entries => {
      const entry = entries.find(e => e.id === entryId);
      if (entry) entry.processingStatus = "completed"; // Must be completed for rebuild to pick it up
    });

    await rebuildVectorStoreFromManifest();
  } catch (err: any) {
    await updateManifest(entries => {
      const entry = entries.find(e => e.id === entryId);
      if (entry) {
        entry.processingStatus = "failed";
        entry.errorMessage = "Failed to update vector store: " + err.message;
      }
    });
    return;
  }

  // Completed
  await updateManifest(entries => {
    const entry = entries.find(e => e.id === entryId);
    if (entry) {
      entry.processingStatus = "completed";
      entry.embeddingStatus = "completed";
    }
  });
}

export async function deleteDocument(entryId: string) {
  let deletedExt = "";
  await updateManifest(entries => {
    const index = entries.findIndex(e => e.id === entryId);
    if (index !== -1) {
      deletedExt = path.extname(entries[index].filename);
      entries.splice(index, 1);
    }
  });
  
  if (deletedExt) {
    await deleteDocumentFiles(entryId, deletedExt);
    await rebuildVectorStoreFromManifest();
  }
}
