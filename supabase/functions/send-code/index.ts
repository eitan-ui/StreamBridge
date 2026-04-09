// StreamBridge — Generate activation code for email registration
// Deploy: supabase functions deploy send-code --no-verify-jwt

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { email } = await req.json();

    // Validate email
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return new Response(
        JSON.stringify({ success: false, error: "Invalid email address" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const cleanEmail = email.trim().toLowerCase();

    // Init Supabase with service role
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, serviceKey);

    // Look up license — email MUST be pre-authorized (paid user)
    const { data: existing } = await supabase
      .from("licenses")
      .select("active, authorized, code_expires_at, code_request_count, code_request_window")
      .eq("email", cleanEmail)
      .maybeSingle();

    if (!existing) {
      return new Response(
        JSON.stringify({ success: false, error: "This email is not registered. Please contact support to purchase a license." }),
        { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    if (!existing.authorized) {
      return new Response(
        JSON.stringify({ success: false, error: "This email is not authorized. Please contact support to activate your license." }),
        { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    if (!existing.active) {
      return new Response(
        JSON.stringify({ success: false, error: "This license has been deactivated. Contact support." }),
        { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Check rate limit
    if (existing) {
      const now = Date.now();
      const windowStart = existing.code_request_window ? new Date(existing.code_request_window).getTime() : 0;
      const windowMs = 15 * 60 * 1000; // 15 minutes
      const count = existing.code_request_count || 0;

      if (now - windowStart < windowMs && count >= 5) {
        const retryAfter = Math.ceil((windowMs - (now - windowStart)) / 1000);
        return new Response(
          JSON.stringify({ success: false, error: `Too many requests. Try again in ${Math.ceil(retryAfter / 60)} minutes.` }),
          { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
    }

    // Generate random 12-char code using crypto-secure PRNG: XXXX-XXXX-XXXX
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    const randomValues = new Uint32Array(12);
    crypto.getRandomValues(randomValues);
    let code = "";
    for (let i = 0; i < 12; i++) {
      code += chars[randomValues[i] % chars.length];
    }
    const formattedCode = `${code.slice(0, 4)}-${code.slice(4, 8)}-${code.slice(8, 12)}`;

    const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();

    // Rate limit tracking: reset window if expired, increment counter
    const now = new Date();
    const windowMs = 15 * 60 * 1000;
    const currentWindow = existing?.code_request_window ? new Date(existing.code_request_window).getTime() : 0;
    const windowExpired = (now.getTime() - currentWindow) >= windowMs;
    const newCount = windowExpired ? 1 : (existing?.code_request_count || 0) + 1;
    const newWindow = windowExpired ? now.toISOString() : (existing?.code_request_window || now.toISOString());

    // Update license with new code (email already exists + authorized)
    const { error: dbError } = await supabase
      .from("licenses")
      .update({
        activation_code: formattedCode,
        code_expires_at: expiresAt,
        code_verified: false,
        code_request_count: newCount,
        code_request_window: newWindow,
      })
      .eq("email", cleanEmail);

    if (dbError) {
      console.error("DB error:", dbError);
      return new Response(
        JSON.stringify({ success: false, error: "Server error. Please try again." }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Return code directly (no email sending)
    return new Response(
      JSON.stringify({ success: true, code: formattedCode }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (err) {
    console.error("Unexpected error:", err);
    return new Response(
      JSON.stringify({ success: false, error: "Unexpected error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
