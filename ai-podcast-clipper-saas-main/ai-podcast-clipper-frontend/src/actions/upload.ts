"use server";

import { db } from "~/server/db";
import { revalidatePath } from "next/cache";
import { createClient } from "@supabase/supabase-js";
import { env } from "~/env";

export async function uploadToSupabaseAndRecord(params: {
  fileBuffer: ArrayBuffer;
  fileName: string;
  contentType: string;
}) {
  const supabase = createClient(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  );

  const path = `podcasts/${Date.now()}-${params.fileName}`;
  const blob = new Blob([params.fileBuffer], { type: params.contentType });

  const { data, error } = await supabase.storage
    .from("uploads")
    .upload(path, blob);

  if (error) {
    throw new Error(error.message);
  }

  const record = await db.uploadedFile.create({
    data: {
      storagePath: data.path,
      fileName: params.fileName,
      fileSize: blob.size,
      s3Key: data.path,
      uploaded: true,
      status: "processed",
    },
    select: { id: true },
  });

  revalidatePath("/dashboard");
  return { success: true, uploadedFileId: record.id, storagePath: data.path };
}
export async function createUploadRecord(fileInfo: {
  filename: string;
  contentType: string;
}) {
  const uploadedFile = await db.uploadedFile.create({
    data: {
      s3Key: "pending_upload",
      fileName: fileInfo.filename,
      displayName: fileInfo.filename,
      uploaded: false,
      status: "processing",
    },
    select: {
      id: true,
    },
  });

  return {
    success: true,
    uploadedFileId: uploadedFile.id,
  };
}

export async function completeProcessing(
  uploadedFileId: string,
  result: any // Relaxed type to handle backend response flexibility
) {
  await db.uploadedFile.update({
    where: {
      id: uploadedFileId,
    },
    data: {
      uploaded: true,
      status: "processed",
    },
  });

  // Create clip records
  if (result.clips && result.clips.length > 0) {
    await db.clip.createMany({
      data: result.clips.map((clip: any) => ({
        s3Key: clip.s3Key, // Ensure we use s3Key from backend response
        clipType: clip.clipType ?? "long",
        uploadedFileId: uploadedFileId,
      })),
    });
  }

  revalidatePath("/dashboard");
  return { success: true };
}
