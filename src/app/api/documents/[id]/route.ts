import { NextResponse } from "next/server";
import { getManifest } from "@/lib/services/manifest-service";
import { deleteDocument } from "@/lib/services/document-ingestion";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const manifest = await getManifest();
    const doc = manifest.find(m => m.id === id);
    if (!doc) {
      return NextResponse.json({ error: { code: "NOT_FOUND", message: "Document not found." } }, { status: 404 });
    }
    return NextResponse.json(doc);
  } catch (err: any) {
    return NextResponse.json({ error: { code: "INTERNAL_ERROR", message: err.message } }, { status: 500 });
  }
}

export async function DELETE(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const accessKey = process.env.UPLOAD_ACCESS_KEY;
    const isDev = process.env.NODE_ENV === "development";
    if (!accessKey && !isDev) {
      return NextResponse.json({ error: { code: "FORBIDDEN", message: "Deletions are disabled." } }, { status: 403 });
    }
    if (accessKey) {
      const providedKey = req.headers.get("x-access-key");
      if (providedKey !== accessKey) {
        return NextResponse.json({ error: { code: "UNAUTHORIZED", message: "Invalid access key." } }, { status: 401 });
      }
    }

    const { id } = await params;
    await deleteDocument(id);
    return new NextResponse(null, { status: 204 });
  } catch (err: any) {
    return NextResponse.json({ error: { code: "INTERNAL_ERROR", message: err.message } }, { status: 500 });
  }
}
