import { promises as fs } from "fs";
import * as path from "path";
import crypto from "crypto";

export const MAX_FILE_SIZE_MB = 25;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
export const MAX_TOTAL_STORAGE_MB = 500;
export const MAX_TOTAL_STORAGE_BYTES = MAX_TOTAL_STORAGE_MB * 1024 * 1024;
export const MIN_EXTRACTED_TEXT_LENGTH = 20;

const DATA_DIR = path.join(process.cwd(), "data");
const UPLOADS_DIR = path.join(DATA_DIR, "uploads");
const EXTRACTED_DIR = path.join(DATA_DIR, "extracted");

export const ALLOWED_MIME_TYPES = {
  "application/pdf": ".pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
  "text/plain": ".txt",
  "text/markdown": ".md"
};

export async function computeHash(buffer: Buffer): Promise<string> {
  const hash = crypto.createHash("sha256");
  hash.update(buffer);
  return hash.digest("hex");
}

export async function validateAndSaveUpload(
  buffer: Buffer, 
  originalFilename: string, 
  mimeType: string,
  docId: string
): Promise<{ size: number, ext: string }> {
  // 1. Extension check
  const ext = path.extname(originalFilename).toLowerCase();
  const allowedExts = Object.values(ALLOWED_MIME_TYPES);
  if (!allowedExts.includes(ext)) {
    throw new Error(`Unsupported file extension: ${ext}`);
  }

  // 2. MIME type check
  if (!Object.keys(ALLOWED_MIME_TYPES).includes(mimeType)) {
    throw new Error(`Unsupported MIME type: ${mimeType}`);
  }
  
  if (ALLOWED_MIME_TYPES[mimeType as keyof typeof ALLOWED_MIME_TYPES] !== ext) {
    throw new Error(`MIME type ${mimeType} does not match extension ${ext}`);
  }

  // 3. Empty file check
  if (buffer.length === 0) {
    throw new Error("File is empty.");
  }

  // 4. Maximum file size
  if (buffer.length > MAX_FILE_SIZE_BYTES) {
    throw new Error(`File exceeds ${MAX_FILE_SIZE_MB} MB limit.`);
  }

  // 5. Total storage quota
  await fs.mkdir(UPLOADS_DIR, { recursive: true });
  await fs.mkdir(EXTRACTED_DIR, { recursive: true });
  
  const files = await fs.readdir(UPLOADS_DIR);
  let totalSize = 0;
  for (const file of files) {
    const stat = await fs.stat(path.join(UPLOADS_DIR, file));
    totalSize += stat.size;
  }
  
  if (totalSize + buffer.length > MAX_TOTAL_STORAGE_BYTES) {
    const currentMB = (totalSize / (1024 * 1024)).toFixed(1);
    throw new Error(`Storage quota exceeded. Currently using ${currentMB}MB of ${MAX_TOTAL_STORAGE_MB}MB.`);
  }

  // Save original file
  const destPath = path.join(UPLOADS_DIR, `${docId}${ext}`);
  await fs.writeFile(destPath, buffer);

  return { size: buffer.length, ext };
}

export async function extractText(docId: string, ext: string): Promise<string> {
  const filePath = path.join(UPLOADS_DIR, `${docId}${ext}`);
  const buffer = await fs.readFile(filePath);
  
  let text = "";
  
  try {
    if (ext === ".pdf") {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const pdf = require("pdf-parse");
      const data = await pdf(buffer);
      text = data.text;
    } else if (ext === ".docx") {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const mammoth = require("mammoth");
      const result = await mammoth.extractRawText({ buffer });
      text = result.value;
    } else if (ext === ".txt" || ext === ".md") {
      text = buffer.toString("utf-8");
    }
  } catch (err: any) {
    throw new Error(`Failed to extract text: ${err.message}`);
  }

  text = text.trim();
  
  if (text.length < MIN_EXTRACTED_TEXT_LENGTH) {
    throw new Error("No extractable text found — file may be a scanned/image-only PDF or corrupted.");
  }

  // Save extracted text
  const extractedPath = path.join(EXTRACTED_DIR, `${docId}.txt`);
  await fs.writeFile(extractedPath, text, "utf-8");
  
  return text;
}

export async function deleteDocumentFiles(docId: string, ext: string) {
  try {
    await fs.unlink(path.join(UPLOADS_DIR, `${docId}${ext}`));
  } catch (e) {
    // Ignore if already deleted
  }
  try {
    await fs.unlink(path.join(EXTRACTED_DIR, `${docId}.txt`));
  } catch (e) {
    // Ignore
  }
}
