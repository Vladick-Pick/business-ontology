import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

import { createOwnerChatGuardHandlers } from "./guard.js";

const PLUGIN_ID = "business-ontology-owner-chat-guard";

export default definePluginEntry({
  id: PLUGIN_ID,
  name: "Business Ontology Owner Chat Guard",
  description:
    "Revises or suppresses unsafe resident-analyst owner chat without changing technical artifacts.",
  register(api) {
    const handlers = createOwnerChatGuardHandlers(api.pluginConfig);

    api.on("before_agent_run", handlers.beforeAgentRun, {
      priority: 100,
      timeoutMs: 1_000,
    });
    api.on("before_agent_finalize", handlers.beforeAgentFinalize, {
      priority: 100,
      timeoutMs: 1_000,
    });
    api.on("message_sending", handlers.messageSending, {
      priority: 100,
      timeoutMs: 1_000,
    });
  },
});
