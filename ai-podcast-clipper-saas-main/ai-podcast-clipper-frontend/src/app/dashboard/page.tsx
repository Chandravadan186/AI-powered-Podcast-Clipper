export const dynamic = "force-dynamic";

import { DashboardClient } from "~/components/dashboard-client";
import { db } from "~/server/db";

export default async function DashboardPage() {
  // Get uploaded files with clips
  const uploadedFilesRaw = await db.uploadedFile.findMany({
    orderBy: { createdAt: "desc" },
    include: {
      clips: true,
    },
  });

  // Format files for frontend
  const formattedFiles = uploadedFilesRaw.map((file) => ({
    id: file.id,
    s3Key: file.s3Key,
    filename: file.displayName ?? "Untitled",
    status: file.status,
    clipsCount: file.clips.length,
    createdAt: file.createdAt.toISOString(), // Serialize Date
  }));

  // Get all clips
  const clips = await db.clip.findMany({
    orderBy: { createdAt: "desc" },
  });
  
  // Serialize clips
  const formattedClips = clips.map((clip) => ({
    ...clip,
    createdAt: clip.createdAt.toISOString(),
    updatedAt: clip.updatedAt.toISOString(),
  }));
  console.log("Dashboard data loaded", {
    uploadedFilesCount: formattedFiles.length,
    clipsCount: formattedClips.length,
  });

  return (
    <DashboardClient
      uploadedFiles={formattedFiles}
      clips={formattedClips}
    />
  );
}
