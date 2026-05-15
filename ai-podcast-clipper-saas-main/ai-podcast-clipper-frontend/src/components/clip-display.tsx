"use client";

import { createClient } from "@supabase/supabase-js";
import { Button } from "./ui/button";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export function ClipDisplay({ clips }: { clips: any[] }) {
  if (!clips || clips.length === 0) {
    return <p>No clips yet.</p>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {clips.map((clip) => {
        const { data } = supabase.storage
          .from("podcast-uploads")
          .getPublicUrl(clip.s3Key);

        const videoUrl = data.publicUrl;

        return (
          <div
            key={clip.id}
            className="border rounded-lg p-3 space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">
                {clip.clipType === "long" ? "LONG" : "SHORT"}
              </span>
            </div>
            <video
              src={videoUrl}
              controls
              className="w-full rounded"
            />

            <a href={videoUrl} download>
              <Button className="w-full">Download</Button>
            </a>
          </div>
        );
      })}
    </div>
  );
}
