// StreamBridge — Validate that this machine is the active one for a license.
// Replaces the client's former direct REST access to the `licenses` table, so
// the table can stay fully locked down (anon/publishable key has no access).
//
// Deploy: supabase functions deploy check-license --no-verify-jwt
// Secrets needed: SUPABASE_SERVICE_ROLE_KEY
//
// Request body: { username: string, machine_id: string, machine_name?: string }
//   - `username` may be an email (new flow) or a legacy username (no "@").
//
// Always responds HTTP 200 for logical outcomes so the client can tell a
// definitive failure ({ valid: false, error }) apart from a transient
// network/server error (HTTP 5xx / connection error -> client allows offline use).

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { username, machine_id, machine_name } = await req.json();

    if (!username || typeof username !== "string") {
      return json({ valid: false, error: "License not found in server" });
    }

    const clean = username.trim().toLowerCase();
    const field = clean.includes("@") ? "email" : "username";

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, serviceKey);

    const { data: license, error: fetchError } = await supabase
      .from("licenses")
      .select("machine_id, machine_name, active")
      .eq(field, clean)
      .maybeSingle();

    if (fetchError) {
      // Treat as a transient server error -> client allows offline use.
      console.error("Fetch error:", fetchError);
      return json({ valid: false, error: "Server error" }, 500);
    }

    if (!license) {
      return json({ valid: false, error: "License not found in server" });
    }

    // active defaults to true: only an explicit false blocks.
    if (license.active === false) {
      return json({ valid: false, error: "License has been deactivated. Contact support." });
    }

    const storedMachineId = license.machine_id || "";
    const storedMachineName = license.machine_name || "";

    if (storedMachineId && storedMachineId !== machine_id) {
      return json({
        valid: false,
        error:
          `License is active on another computer: ${storedMachineName}\n` +
          `Deactivate it there first, or re-activate here.`,
      });
    }

    // Machine matches (or none stored yet) -> refresh last_seen, optionally bind name.
    const update: Record<string, unknown> = { last_seen: new Date().toISOString() };
    if (machine_name && machine_name !== storedMachineName) {
      update.machine_name = machine_name;
    }
    await supabase.from("licenses").update(update).eq(field, clean);

    return json({ valid: true });
  } catch (err) {
    console.error("Unexpected error:", err);
    // Transient -> client allows offline use.
    return json({ valid: false, error: "Unexpected error" }, 500);
  }
});
