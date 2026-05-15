"use server";

export async function createCheckoutSession(_priceId: string) {
  return { success: false, message: "Billing disabled in this build" };
}
