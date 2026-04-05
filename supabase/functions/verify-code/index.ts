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

    // Check code matches
    if (license.activation_code !== cleanCode) {
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

    // Activate: update machine_id and mark verified
    const { error: updateError } = await supabase
      .from("licenses")
      .update({
        machine_id: machine_id || null,
        machine_name: machine_name || null,
        code_verified: true,
        last_seen: new Date().toISOString(),
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
