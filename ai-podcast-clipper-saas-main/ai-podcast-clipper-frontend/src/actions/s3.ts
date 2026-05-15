"use server";

// import { PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
// import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { env } from "~/env";
import { auth } from "~/server/auth";
import { v4 as uuidv4 } from "uuid";
import { db } from "~/server/db";

export async function generateUploadUrl(fileInfo: {
  filename: string;
  contentType: string;
}): Promise<{
  success: boolean;
  signedUrl: string;
  key: string;
  uploadedFileId: string;
}> {
  throw new Error("This action is deprecated. Please use direct backend upload.");
  /*
  const session = await auth();
  // if (!session) throw new Error("Unauthorized");

  // Local development override
  if (process.env.NODE_ENV !== "production") {
     const uniqueId = uuidv4();
     const key = `local_file:${uniqueId}_${fileInfo.filename}`;
     const localUploadUrl = `${env.BASE_URL}/api/upload?filename=${uniqueId}_${fileInfo.filename}`;

     const uploadedFileDbRecord = await db.uploadedFile.create({
      data: {
        userId: session?.user?.id ?? "local-user",
        s3Key: key,
        displayName: fileInfo.filename,
        uploaded: false,
      },
      select: {
        id: true,
      },
    });

    return {
      success: true,
      signedUrl: localUploadUrl,
      key,
      uploadedFileId: uploadedFileDbRecord.id,
    };
  }

  const s3Client = new S3Client({
    region: env.AWS_REGION,
    credentials: {
      accessKeyId: env.AWS_ACCESS_KEY_ID,
      secretAccessKey: env.AWS_SECRET_ACCESS_KEY,
    },
  });

  const fileExtension = fileInfo.filename.split(".").pop() ?? "";

  const uniqueId = uuidv4();
  const key = `${uniqueId}/original.${fileExtension}`;

  const command = new PutObjectCommand({
    Bucket: env.S3_BUCKET_NAME,
    Key: key,
    ContentType: fileInfo.contentType,
  });

  const signedUrl = await getSignedUrl(s3Client, command, { expiresIn: 600 });

  const uploadedFileDbRecord = await db.uploadedFile.create({
    data: {
      userId: session.user.id,
      s3Key: key,
      displayName: fileInfo.filename,
      uploaded: false,
    },
    select: {
      id: true,
    },
  });

  return {
    success: true,
    signedUrl,
    key,
    uploadedFileId: uploadedFileDbRecord.id,
  };
  */
}

