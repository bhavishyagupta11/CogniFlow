import { NextResponse } from "next/server";
import { getManifest, updateManifest } from "@/lib/services/manifest-service";
import { validateAndSaveUpload, computeHash } from "@/lib/services/upload-service";
import { processDocument } from "@/lib/services/document-ingestion";
export async function GET() {
  try {
    const manifest = await getManifest();
    return NextResponse.json(manifest);
  } catch (err: any) {
    return NextResponse.json({ error: { code: "INTERNAL_ERROR", message: err.message } }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const accessKey = process.env.UPLOAD_ACCESS_KEY;
    const isDev = process.env.NODE_ENV === "development";
    if (!accessKey && !isDev) {
      return NextResponse.json({ error: { code: "FORBIDDEN", message: "Uploads are disabled." } }, { status: 403 });
    }
    if (accessKey) {
      const providedKey = req.headers.get("x-access-key");
      if (providedKey !== accessKey) {
        return NextResponse.json({ error: { code: "UNAUTHORIZED", message: "Invalid access key." } }, { status: 401 });
      }
    }

    const formData = await req.formData();
    const files = formData.getAll("file") as File[];
    
    if (!files || files.length === 0) {
      return NextResponse.json({ error: { code: "BAD_REQUEST", message: "No files uploaded." } }, { status: 400 });
    }

    const results = [];

    for (const file of files) {
      try {
        const buffer = Buffer.from(await file.arrayBuffer());
        const hash = await computeHash(buffer);
        
        // Duplicate check
        const manifest = await getManifest();
        const existing = manifest.find(m => m.hash === hash && m.processingStatus === "completed");
        if (existing) {
          results.push({
            status: 409,
            error: {
              code: "DUPLICATE",
              message: "File already exists in the knowledge base.",
              existingId: existing.id,
              existingFilename: existing.originalFilename
            }
          });
          continue;
        }

        const docId = crypto.randomUUID();
        const { size, ext } = await validateAndSaveUpload(buffer, file.name, file.type, docId);

        const now = new Date().toISOString();
        
        const newEntry = {
          schemaVersion: 1,
          id: docId,
          filename: `${docId}${ext}`,
          originalFilename: file.name,
          mimeType: file.type,
          size,
          uploadedAt: now,
          lastModified: now,
          chunkCount: 0,
          chunkIds: [],
          processingStatus: "queued" as const,
          embeddingStatus: "pending" as const,
          hash,
          errorMessage: null
        };

        await updateManifest(entries => {
          entries.push(newEntry);
        });

        // Fire and forget background processing
        // Next.js running locally allows background promises
        processDocument(docId).catch(console.error);

        results.push({ status: 201, document: newEntry });

      } catch (fileErr: any) {
        results.push({
          status: 400,
          error: { code: "VALIDATION_ERROR", message: fileErr.message }
        });
      }
    }

    return NextResponse.json({ results });
  } catch (err: any) {
    return NextResponse.json({ error: { code: "INTERNAL_ERROR", message: err.message } }, { status: 500 });
  }
}
