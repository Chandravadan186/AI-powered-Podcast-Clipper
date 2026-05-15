import { env } from "~/env";
import { inngest } from "./client";
import { db } from "~/server/db";
// import { ListObjectsV2Command, S3Client } from "@aws-sdk/client-s3";

export const processVideo = inngest.createFunction(
  {
    id: "process-video",
    retries: 1,
    concurrency: {
      limit: 1,
      key: "event.data.userId",
    },
  },
  { event: "process-video-events" },
  async ({ event, step }) => {
    // Deprecated implementation
    return { success: false, message: "Deprecated" };
    /*
    const { uploadedFileId } = event.data as {
      uploadedFileId: string;
      userId: string;
    };
    // ... existing code ...
    */
  }
);
