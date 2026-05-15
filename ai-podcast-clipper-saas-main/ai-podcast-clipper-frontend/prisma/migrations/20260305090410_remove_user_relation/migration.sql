/*
  Warnings:

  - You are about to drop the column `userId` on the `Clip` table. All the data in the column will be lost.
  - You are about to drop the column `userId` on the `UploadedFile` table. All the data in the column will be lost.

*/
-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Clip" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "s3Key" TEXT NOT NULL,
    "clipType" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "uploadedFileId" TEXT,
    CONSTRAINT "Clip_uploadedFileId_fkey" FOREIGN KEY ("uploadedFileId") REFERENCES "UploadedFile" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_Clip" ("clipType", "createdAt", "id", "s3Key", "updatedAt", "uploadedFileId") SELECT "clipType", "createdAt", "id", "s3Key", "updatedAt", "uploadedFileId" FROM "Clip";
DROP TABLE "Clip";
ALTER TABLE "new_Clip" RENAME TO "Clip";
CREATE INDEX "Clip_s3Key_idx" ON "Clip"("s3Key");
CREATE TABLE "new_UploadedFile" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "s3Key" TEXT NOT NULL,
    "storagePath" TEXT,
    "fileName" TEXT,
    "fileSize" INTEGER,
    "displayName" TEXT,
    "uploaded" BOOLEAN NOT NULL DEFAULT false,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);
INSERT INTO "new_UploadedFile" ("createdAt", "displayName", "id", "s3Key", "status", "updatedAt", "uploaded") SELECT "createdAt", "displayName", "id", "s3Key", "status", "updatedAt", "uploaded" FROM "UploadedFile";
DROP TABLE "UploadedFile";
ALTER TABLE "new_UploadedFile" RENAME TO "UploadedFile";
CREATE INDEX "UploadedFile_s3Key_idx" ON "UploadedFile"("s3Key");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
