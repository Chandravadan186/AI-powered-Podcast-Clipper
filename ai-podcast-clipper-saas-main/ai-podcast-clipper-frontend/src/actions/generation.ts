"use server";

import { revalidatePath } from "next/cache";
import { env } from "~/env";
// import { inngest } from "~/inngest/client";
import { auth } from "~/server/auth";
import { db } from "~/server/db";

// Deprecated: We are now using direct backend upload and processing
export async function processVideo(uploadedFileId: string) {
  /*
  const uploadedVideo = await db.uploadedFile.findUniqueOrThrow({
    where: {
      id: uploadedFileId,
    },
    select: {
      uploaded: true,
      id: true,
      userId: true,
    },
  });

  if (uploadedVideo.uploaded) return;

  await inngest.send({
    name: "process-video-events",
    data: { uploadedFileId: uploadedVideo.id, userId: uploadedVideo.userId },
  });

  await db.uploadedFile.update({
    where: {
      id: uploadedFileId,
    },
    data: {
      uploaded: true,
    },
  });

  revalidatePath("/dashboard");
  */
 console.log("processVideo called but deprecated in favor of direct backend processing");
}

export async function getClipPlayUrl(
  clipId: string,
): Promise<{ succes: boolean; url?: string; error?: string }> {
  const session = await auth();
  
  // Allow local user without auth check if needed, or stick to session check
  // if (!session?.user?.id) {
  //   return { succes: false, error: "Unauthorized" };
  // }

  try {
    const clip = await db.clip.findUniqueOrThrow({
      where: {
        id: clipId,
        // userId: session?.user?.id, // Optional: restore ownership check if needed
      },
    });

    // If the key is a full URL (Supabase Public URL), return it directly
    if (clip.s3Key.startsWith("http")) {
        return { succes: true, url: clip.s3Key };
    }

    // Fallback for legacy paths or local testing
    return { succes: true, url: clip.s3Key };

  } catch (error) {
    return { succes: false, error: "Failed to generate play URL." };
  }
}

