import assert from "node:assert/strict";
import test from "node:test";

import {
  countOwnerQuestions,
  createOwnerChatGuardHandlers,
  explicitTechnicalViewRequested,
  hasTechnicalViewPayload,
  inspectOwnerChat,
} from "./guard.js";

const AGENT_ID = "business-analyst-interlab";

test("safe owner chat keeps one question", () => {
  const message = `The handoff rule changed in Thursday's meeting.

Should I fix the new rule into the model?

Recommendation: keep the old rule in history.

Consequence: the prior state remains available for audit.`;

  assert.equal(countOwnerQuestions(message), 1);
  assert.deepEqual(inspectOwnerChat(message), []);
});

test("question counting catches punctuation and unpunctuated owner lists", () => {
  assert.equal(countOwnerQuestions("Is this production? Which owner confirms it?"), 2);
  assert.equal(
    countOwnerQuestions("What I need from you:\n1. Confirm the current owner\n2. Choose the effective date"),
    2,
  );
  assert.equal(countOwnerQuestions("How the system works\n\nThis is an explanatory heading."), 0);
});

test("owner questions require explicit recommendation and consequence in English and Russian", () => {
  assert.deepEqual(inspectOwnerChat("Should I keep the rule?"), [
    "missing_recommendation",
    "missing_consequence",
  ]);
  assert.deepEqual(
    inspectOwnerChat(
      "Подтвердить текущее правило?\n\nРекомендация: подтвердить его.\n\nПоследствие: правило останется действующим.",
    ),
    [],
  );
  assert.deepEqual(
    inspectOwnerChat(
      "Should I keep the rule?\n\nRecommendation: keep it.\n\nConsequence: the current workflow remains unchanged.",
    ),
    [],
  );
});

test("web viewer URLs are allowed while local html paths are not", () => {
  assert.deepEqual(
    inspectOwnerChat("Model view: https://viewer.example.com/model/index.html?item=if-lead"),
    [],
  );
  assert.deepEqual(inspectOwnerChat("Open viewer/model/index.html"), ["machine_path"]);
});

test("technical markers are classified without changing their source text", () => {
  const message =
    "mcpkg-change-1 at runtime/jobs/run.py used propose-change with status: candidate and claimKind=agent-inference";
  const original = message;
  const violations = inspectOwnerChat(message);

  assert.equal(message, original);
  assert.deepEqual(violations, [
    "machine_id",
    "machine_path",
    "tool_name",
    "raw_status",
    "schema_field",
  ]);
});

test("visible host tool failures are blocked even in technical view", () => {
  const failure = "⚠️ 🛠️ Bash failed: `search in .` (agent)";
  assert.deepEqual(inspectOwnerChat(failure), ["tool_failure"]);

  const handlers = createOwnerChatGuardHandlers({ agentIds: [AGENT_ID] });
  const event = {
    runId: "run-technical-tool-failure",
    sessionKey: `agent:${AGENT_ID}:main`,
    lastAssistantMessage: `mcpkg-change-1\n${failure}`,
    messages: [{ role: "user", content: "Show me the technical details." }],
  };
  const result = handlers.beforeAgentFinalize(event, {
    agentId: AGENT_ID,
    sessionKey: event.sessionKey,
  });
  assert.equal(result.action, "revise");
});

test("empty install-time configuration is inert", () => {
  const handlers = createOwnerChatGuardHandlers({});
  const event = {
    runId: "install-probe",
    lastAssistantMessage: "First question? Second question?",
  };
  const context = { agentId: AGENT_ID, sessionKey: `agent:${AGENT_ID}:main` };

  assert.equal(handlers.beforeAgentFinalize(event, context), undefined);
  assert.equal(
    handlers.messageSending({ to: "owner", content: event.lastAssistantMessage }, context),
    undefined,
  );
});

test("before finalize grants one bounded rewrite only for configured agents", () => {
  const handlers = createOwnerChatGuardHandlers({ agentIds: [AGENT_ID] });
  const event = {
    runId: "run-1",
    sessionId: "session-1",
    lastAssistantMessage: "First question? Second question?",
  };

  const result = handlers.beforeAgentFinalize(event, { agentId: AGENT_ID });
  assert.equal(result.action, "revise");
  assert.equal(result.retry.maxAttempts, 1);
  assert.equal(result.retry.idempotencyKey, "business-ontology-owner-chat-guard:run-1");
  assert.match(result.retry.instruction, /leave technical artifacts unchanged/u);
  assert.equal(handlers.beforeAgentFinalize(event, { agentId: "unrelated" }), undefined);
});

test("message sending cancels unsafe target delivery and never rewrites artifacts", () => {
  const handlers = createOwnerChatGuardHandlers({ agentIds: [AGENT_ID] });
  const unsafe = { to: "owner", content: "Use skills/mine-materials/SKILL.md. Ready? Continue?" };
  const context = { sessionKey: `agent:${AGENT_ID}:telegram:group:42` };

  const result = handlers.messageSending(unsafe, context);
  assert.equal(result.cancel, true);
  assert.equal(result.cancelReason, "business-ontology-owner-chat-policy");
  assert.equal(Object.hasOwn(result, "content"), false);
  assert.deepEqual(result.metadata.violations, [
    "multiple_questions",
    "missing_recommendation",
    "missing_consequence",
    "machine_path",
    "tool_name",
  ]);

  assert.equal(
    handlers.messageSending(
      {
        to: "owner",
        content:
          "Should I keep the current rule?\n\nRecommendation: keep it.\n\nConsequence: the current workflow stays unchanged.",
      },
      context,
    ),
    undefined,
  );
  assert.equal(
    handlers.messageSending(unsafe, { sessionKey: "agent:unrelated:telegram:group:42" }),
    undefined,
  );
});

test("explicit technical view gets one exact correlated delivery exemption", () => {
  const handlers = createOwnerChatGuardHandlers({ agentIds: [AGENT_ID] });
  const content = "Technical record: mcpkg-change-1 in runtime/jobs/run.py, status: candidate.";
  const event = {
    runId: "run-technical",
    sessionId: "session-technical",
    sessionKey: `agent:${AGENT_ID}:main`,
    lastAssistantMessage: content,
    messages: [{ role: "user", content: "Show me the technical details and ids." }],
  };
  const context = { agentId: AGENT_ID, sessionKey: event.sessionKey };

  assert.equal(explicitTechnicalViewRequested(event.messages), true);
  assert.equal(handlers.beforeAgentFinalize(event, context), undefined);
  assert.equal(handlers.messageSending({ to: "owner", content }, context), undefined);

  const secondDelivery = handlers.messageSending({ to: "owner", content }, context);
  assert.equal(secondDelivery.cancel, true);
});

test("technical view request survives a host envelope in the latest user turn", () => {
  assert.equal(
    explicitTechnicalViewRequested([
      {
        role: "user",
        content:
          "[OpenClaw inbound envelope]\nПокажи технический вид полей id и status дословно.",
      },
    ]),
    true,
  );
});

test("technical view omission gets one rewrite and then fails closed", () => {
  const handlers = createOwnerChatGuardHandlers({ agentIds: [AGENT_ID] });
  const sessionKey = `agent:${AGENT_ID}:technical-omission`;
  const content = "This is the owner chat guard version 0.1.2.";
  const event = {
    runId: "run-technical-omission",
    sessionKey,
    lastAssistantMessage: content,
    messages: [{ role: "user", content: "Show me the technical details and ids." }],
  };
  const context = { agentId: AGENT_ID, sessionKey };

  assert.equal(hasTechnicalViewPayload(content), false);
  const revision = handlers.beforeAgentFinalize(event, context);
  assert.equal(revision.action, "revise");
  assert.match(revision.retry.instruction, /Copy only the requested exact keys and values/u);

  const delivery = handlers.messageSending({ to: "owner", content }, context);
  assert.equal(delivery.cancel, true);
  assert.deepEqual(delivery.metadata.violations, ["technical_view_omitted"]);
});

test("technical view permits an explicit unavailable result without diagnostics", () => {
  const handlers = createOwnerChatGuardHandlers({ agentIds: [AGENT_ID] });
  const sessionKey = `agent:${AGENT_ID}:technical-unavailable`;
  const content = "The requested artifact could not be read.";
  const event = {
    runId: "run-technical-unavailable",
    sessionKey,
    lastAssistantMessage: content,
    messages: [{ role: "user", content: "Show me the technical details." }],
  };
  const context = { agentId: AGENT_ID, sessionKey };

  assert.equal(hasTechnicalViewPayload(content), true);
  assert.equal(handlers.beforeAgentFinalize(event, context), undefined);
  assert.equal(handlers.messageSending({ to: "owner", content }, context), undefined);
});

test("technical exemption never bypasses question shape or a different payload", () => {
  const handlers = createOwnerChatGuardHandlers({ agentIds: [AGENT_ID] });
  const sessionKey = `agent:${AGENT_ID}:main`;
  const context = { agentId: AGENT_ID, sessionKey };
  const content = "mcpkg-change-1 is pending.";

  assert.equal(
    handlers.beforeAgentFinalize(
      {
        runId: "run-technical-mismatch",
        sessionId: "session-technical",
        sessionKey,
        lastAssistantMessage: content,
        messages: [{ role: "user", content: [{ type: "text", text: "Покажи технические детали." }] }],
      },
      context,
    ),
    undefined,
  );
  assert.equal(
    handlers.messageSending({ to: "owner", content: `${content} Extra technical line.` }, context).cancel,
    true,
  );

  const questionResult = handlers.beforeAgentFinalize(
    {
      runId: "run-technical-question",
      sessionId: "session-technical",
      sessionKey,
      lastAssistantMessage: "First technical question? Second technical question?",
      messages: [{ role: "user", content: "Technical view please." }],
    },
    context,
  );
  assert.equal(questionResult.action, "revise");
});
