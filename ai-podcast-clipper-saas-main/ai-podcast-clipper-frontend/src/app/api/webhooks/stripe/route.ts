import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json(
    { success: true, message: "Billing disabled in this build" },
    { status: 200 }
  );
}
