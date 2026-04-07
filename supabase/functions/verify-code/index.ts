// StreamBridge — Verify activation code and bind machine
// Deploy: supabase functions deploy verify-code
// Secrets needed: SUPABASE_SERVICE_ROLE_KEY

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
    const { email, code, machine_id, machine_name } = await req.json();

    if (!email || !code) {
      return new Response(
        JSON.stringify({ success: false, error: "Email and code are required" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const cleanEmail = email.trim().toLowerCase();
    const cleanCode = code.trim().toUpperCase();

    // Init Supabase with service role
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, serviceKey);

    // Look up license by email
    const { data: license, error: fetchError } = await supabase
      .from("licenses")
      .select("*")
      .eq("email", cleanEmail)
      .maybeSingle();

    if (fetchError || !license) {
      return new Response(
        JSON.stringify({ success: false, error: "No activation code found for this email. Request a new code." }),
        { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Check if deactivated
    if (!license.active) {
      return new Response(
        JSON.stringify({ success: false, error: "This license has been deactivated. Contact support." }),
        { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Rate limiting: max 10 failed attempts per email, then lock for 15 minutes
    const failedAttempts = license.failed_verify_count || 0;
    const lastFailedAt = license.last_failed_verify ? new Date(license.last_failed_verify).getTime() : 0;
    const lockoutMs = 15 * 60 * 1000;

    if (failedAttempts >= 10 && (Date.now() - lastFailedAt) < lockoutMs) {
      const retryAfter = Math.ceil((lockoutMs - (Date.now() - lastFailedAt)) / 1000 / 60);
      return new Response(
        JSON.stringify({ success: false, error: `Too many failed attempts. Try again in ${retryAfter} minutes.` }),
        { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Check code matches
    if (license.activation_code !== cleanCode) {
      // Record failed attempt
      const newCount = (Date.now() - lastFailedAt) >= lockoutMs ? 1 : failedAttempts + 1;
      await supabase
        .from("licenses")
        .update({
          failed_verify_count: newCount,
          last_failed_verify: new Date().toISOString(),
        })
        .eq("email", cleanEmail);

      return new Response(
        JSON.stringify({ success: false, error: "Invalid activation code. Check your email and try again." }),
        { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Check expiration
    if (license.code_expires_at) {
      const expiresAt = new Date(license.code_expires_at);
      if (expiresAt < new Date()) {
        return new Response(
          JSON.stringify({ success: false, error: "Code has expired. Request a new one." }),
          { status: 410, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
    }

    // Activate: update machine_id, mark verified, reset failed attempts
    const { error: updateError } = await supabase
      .from("licenses")
      .update({
        machine_id: machine_id || null,
        machine_name: machine_name || null,
        code_verified: true,
        last_seen: new Date().toISOString(),
        failed_verify_count: 0,
        last_failed_verify: null,
      })
      .eq("email", cleanEmail);

    if (updateError) {
      console.error("Update error:", updateError);
      return new Response(
        JSON.stringify({ success: false, error: "Server error. Please try again." }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    return new Response(
      JSON.stringify({ success: true }),
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
