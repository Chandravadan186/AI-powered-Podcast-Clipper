
import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { pipeline } from "stream";
import { promisify } from "util";

const pump = promisify(pipeline);

export async function PUT(req: NextRequest) {
  const searchParams = req.nextUrl.searchParams;
  const filename = searchParams.get("filename");

  if (!filename) {
    return NextResponse.json({ error: "Filename required" }, { status: 400 });
  }

  // Ensure uploads directory exists
  const uploadDir = path.join(process.cwd(), "public", "uploads");
  if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
  }

  const filePath = path.join(uploadDir, filename);
  
  // Create a write stream
  const fileStream = fs.createWriteStream(filePath);

  // @ts-ignore
  if (req.body) {
    // @ts-ignore
    await pump(req.body, fileStream);
  }

  return NextResponse.json({ success: true, path: filePath });
}
