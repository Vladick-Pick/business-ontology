const MACHINE_ID_RE = /\b(?:mcpkg|srcevt|rev|chg|sysres|prop|hreq|mtgpk)-[a-z0-9][a-z0-9._-]*\b|\bif-[a-z0-9][a-z0-9-]{2,}\b/iu;

const SCHEMA_FIELD_RE = /\b(?:claimKind|evidenceGrade|sourceRisk|trustFloor|slaBand|reviewEvidenceMode|sourceAdequacy|ontologyRevision|decisionImpact|blastRadius|overallAction|highRiskReasons|packageId|messageRef)\b/u;

const TOOL_NAME_RE = /\b(?:connect-source|mine-materials|extract-from-input|propose-change|promote-digest|drift-sweep|synthesize-digest|meeting-transcript-ingest|meeting-recorder|links_validate(?:\.py)?|run_evals(?:\.py)?|assert_model_write_scope(?:\.py)?|web_search|exec_command|apply_patch|sessions_send)\b|\bopenclaw\s+(?:plugins|hooks|cron|gateway|agent|sessions)\b|\b(?:tool|skill)\s+(?:called\s+)?[`'"]?[a-z0-9_.-]+/iu;

const RAW_STATUS_RE = /\b(?:staged-proposal-ready|proposal-ready|review-source-of-truth|needs-info|human-review|open-review|write-staged|write-accepted|live-proven|source-connected|pending-owner-selection|supplies-to|measured-by|source-of-truth|governed-by)\b|\bstatus\s*[:=]\s*(?:candidate|hypothesis|conflict|accepted|implemented|pending|superseded|deprecated)\b|`(?:candidate|hypothesis|conflict|accepted|implemented|pending|superseded|deprecated)`/iu;

const ARTIFACT_TERM_RE = /\b(?:model-change package|review package|source event)\b/iu;
const TOOL_FAILURE_RE = /(?:^|\n)\s*(?:⚠️\s*)?(?:🛠️\s*)?(?:bash|shell|exec|read|write|search|tool)\s+(?:failed|error)\s*:/iu;
const TECHNICAL_BLOCK_RE = /```[^\n]*\n[\s\S]*?(?:["'`]?[A-Za-z][A-Za-z0-9_.-]*["'`]?\s*[:=])[\s\S]*?```/u;
const TECHNICAL_UNAVAILABLE_RE = /\b(?:artifact|file|source)\b[^.\n]{0,80}\b(?:could not be read|is unavailable|was not found)\b|(?:артефакт|файл|источник)[^.\n]{0,80}(?:не удалось прочитать|недоступен|не найден)/iu;

const HTTP_URL_RE = /https?:\/\/[^\s<>()\[\]{}"'`]+/giu;
const RECOMMENDATION_RE = /(?:^|\n)\s*(?:recommendation|рекомендация)\s*:/iu;
const CONSEQUENCE_RE = /(?:^|\n)\s*(?:consequence|последствие)\s*:/iu;
const TECHNICAL_VIEW_REQUEST_RES = [
  /^\s*(?:please\s+)?(?:show|give|send|include|display)\s+(?:me\s+)?(?:the\s+)?(?:technical (?:view|details?)|ids?|identifiers?|raw statuses?|file paths?)(?:\s|[.!?]|$)/iu,
  /^\s*(?:technical (?:view|details?)|ids?|identifiers?)(?:\s+please)?\s*[.!?]?\s*$/iu,
  /^\s*(?:покажи|пришли|дай|выведи)\s+(?:мне\s+)?(?:техническ(?:ий вид|ие подробности|ие детали|ую версию)|идентификаторы|id|сырые статусы|пути к файлам)(?:\s|[.!?]|$)/iu,
  /^\s*(?:техническ(?:ий вид|ие подробности|ие детали|ая версия)|идентификаторы|id)\s*[.!?]?\s*$/iu,
];

const PATH_RES = [
  /(?:^|[\s("'`])(?:~\/|\.{1,2}\/)[^\s)"'`]+/mu,
  /(?:^|[\s("'`])\/(?:[^\s/]+\/)+[^\s)"'`]*/mu,
  /\b[A-Za-z]:\\(?:[^\\\s]+\\)+[^\s]*/u,
  /<(?:workspace|model-root|package-root)>\/[A-Za-z0-9._/-]+/iu,
  /\b(?:agent-os|skills|templates|adapters|runtime|scripts|schemas|product|plans|staged|raw)\/[A-Za-z0-9._/-]+/iu,
  /\b(?:[A-Za-z0-9_.-]+\/)+(?:[A-Za-z0-9_.-]+\.(?:md|json|jsonl|yaml|yml|toml|py|js|mjs|cjs|ts|tsx|sh|sql|html|htm))\b/iu,
];

const OWNER_SECTION_RE = /^\s*(?:what i need from you|what i need|question for you|your decision|что мне нужно от вас|что нужно от вас|нужен ваш ответ|вопрос к вам|ваше решение)\s*:\s*$/iu;
const SECTION_HEADING_RE = /^\s*[^.!?？]{1,80}:\s*$/u;
const LIST_ITEM_RE = /^\s*(?:[-*]|\d+[.)])\s+\S/u;

function hasMachinePath(text) {
  const withoutUrls = text.replace(HTTP_URL_RE, "");
  return PATH_RES.some((pattern) => pattern.test(withoutUrls));
}

function withoutUrlsAndCode(text) {
  return text
    .replace(HTTP_URL_RE, "")
    .replace(/```[\s\S]*?```/gu, "")
    .replace(/`[^`\n]*`/gu, "");
}

function ownerSectionItemCount(lines) {
  let inOwnerSection = false;
  let count = 0;

  for (const line of lines) {
    if (OWNER_SECTION_RE.test(line)) {
      inOwnerSection = true;
      continue;
    }
    if (!inOwnerSection) {
      continue;
    }
    if (SECTION_HEADING_RE.test(line) && !OWNER_SECTION_RE.test(line)) {
      break;
    }
    if (LIST_ITEM_RE.test(line)) {
      count += 1;
    }
  }
  return count;
}

export function countOwnerQuestions(content) {
  const text = withoutUrlsAndCode(String(content ?? ""));
  const punctuationCount = (text.match(/[?？]/gu) ?? []).length;
  const lines = text.split(/\r?\n/u);
  return Math.max(punctuationCount, ownerSectionItemCount(lines));
}

export function inspectOwnerChat(content) {
  const text = String(content ?? "");
  const textWithoutUrls = text.replace(HTTP_URL_RE, "");
  const violations = [];
  const questionCount = countOwnerQuestions(text);

  if (questionCount > 1) {
    violations.push("multiple_questions");
  }
  if (questionCount > 0 && !RECOMMENDATION_RE.test(text)) {
    violations.push("missing_recommendation");
  }
  if (questionCount > 0 && !CONSEQUENCE_RE.test(text)) {
    violations.push("missing_consequence");
  }
  if (MACHINE_ID_RE.test(textWithoutUrls)) {
    violations.push("machine_id");
  }
  if (hasMachinePath(text)) {
    violations.push("machine_path");
  }
  if (TOOL_NAME_RE.test(textWithoutUrls)) {
    violations.push("tool_name");
  }
  if (RAW_STATUS_RE.test(textWithoutUrls) || ARTIFACT_TERM_RE.test(textWithoutUrls)) {
    violations.push("raw_status");
  }
  if (SCHEMA_FIELD_RE.test(textWithoutUrls)) {
    violations.push("schema_field");
  }
  if (TOOL_FAILURE_RE.test(textWithoutUrls)) {
    violations.push("tool_failure");
  }

  return violations;
}

function messageText(message) {
  if (!message || typeof message !== "object") {
    return "";
  }
  if (typeof message.content === "string") {
    return message.content;
  }
  if (!Array.isArray(message.content)) {
    return "";
  }
  return message.content
    .map((part) => {
      if (typeof part === "string") {
        return part;
      }
      return part && typeof part === "object" && typeof part.text === "string" ? part.text : "";
    })
    .filter(Boolean)
    .join("\n");
}

export function explicitTechnicalViewRequested(messages) {
  if (!Array.isArray(messages)) {
    return false;
  }
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (!message || typeof message !== "object" || message.role !== "user") {
      continue;
    }
    const text = messageText(message).trim();
    return TECHNICAL_VIEW_REQUEST_RES.some((pattern) => pattern.test(text));
  }
  return false;
}

export function hasTechnicalViewPayload(content) {
  const text = String(content ?? "");
  const textWithoutUrls = text.replace(HTTP_URL_RE, "");
  return (
    MACHINE_ID_RE.test(textWithoutUrls) ||
    RAW_STATUS_RE.test(textWithoutUrls) ||
    SCHEMA_FIELD_RE.test(textWithoutUrls) ||
    hasMachinePath(text) ||
    TECHNICAL_BLOCK_RE.test(text) ||
    TECHNICAL_UNAVAILABLE_RE.test(text)
  );
}

export function agentIdFromSessionKey(sessionKey) {
  const match = /^agent:([^:]+):/u.exec(String(sessionKey ?? ""));
  return match?.[1];
}

function metadataAgentId(metadata) {
  if (!metadata || typeof metadata !== "object") {
    return undefined;
  }
  return typeof metadata.agentId === "string" ? metadata.agentId : undefined;
}

function isGuardedAgent(agentIds, event, context) {
  const agentId =
    (typeof context?.agentId === "string" ? context.agentId : undefined) ??
    agentIdFromSessionKey(context?.sessionKey) ??
    metadataAgentId(event?.metadata);
  return Boolean(agentId && agentIds.has(agentId));
}

function revisionKey(event) {
  const turnKey = event?.runId ?? event?.turnId ?? event?.sessionId ?? "unknown-turn";
  return `business-ontology-owner-chat-guard:${turnKey}`;
}

export function createOwnerChatGuardHandlers(config) {
  const configured = Array.isArray(config?.agentIds) ? config.agentIds : [];
  const agentIds = new Set(configured.filter((item) => typeof item === "string" && item));
  const technicalExemptions = new Map();
  const technicalViolationNames = new Set([
    "machine_id",
    "machine_path",
    "tool_name",
    "raw_status",
    "schema_field",
  ]);

  function exemptionKey(event, context) {
    const sessionKey = context?.sessionKey ?? event?.sessionKey;
    return typeof sessionKey === "string" && sessionKey ? sessionKey : undefined;
  }

  function rememberTechnicalExemption(event, context, content) {
    const key = exemptionKey(event, context);
    if (!key) {
      return;
    }
    const now = Date.now();
    for (const [storedKey, exemption] of technicalExemptions) {
      if (exemption.expiresAt <= now) {
        technicalExemptions.delete(storedKey);
      }
    }
    technicalExemptions.set(key, {
      content,
      technicalViewRequired: true,
      expiresAt: now + 30_000,
    });
  }

  function takeTechnicalExemption(event, context) {
    const key = exemptionKey(event, context);
    if (!key) {
      return undefined;
    }
    const exemption = technicalExemptions.get(key);
    technicalExemptions.delete(key);
    return exemption && exemption.expiresAt > Date.now() ? exemption : undefined;
  }

  function onlyTechnicalViolations(violations) {
    return violations.length > 0 && violations.every((item) => technicalViolationNames.has(item));
  }

  return {
    beforeAgentFinalize(event, context) {
      if (!isGuardedAgent(agentIds, event, context)) {
        return undefined;
      }
      const technicalViewRequested = explicitTechnicalViewRequested(event?.messages);
      if (technicalViewRequested && !hasTechnicalViewPayload(event?.lastAssistantMessage)) {
        rememberTechnicalExemption(event, context, undefined);
        return {
          action: "revise",
          reason: "owner chat policy: technical_view_omitted",
          retry: {
            instruction:
              "The human explicitly requested a technical view. A successful file-read result is private tool context, not a delivered answer. Copy only the requested exact keys and values into the final response, preferably in a fenced code block. Do not translate, paraphrase, summarize, or add a recommendation. If the read actually failed or was empty, state that plainly without exposing tool diagnostics.",
            idempotencyKey: revisionKey(event),
            maxAttempts: 1,
          },
        };
      }
      const violations = inspectOwnerChat(event?.lastAssistantMessage);
      if (violations.length === 0) {
        if (technicalViewRequested) {
          rememberTechnicalExemption(event, context, event?.lastAssistantMessage);
        }
        return undefined;
      }
      if (technicalViewRequested && onlyTechnicalViolations(violations)) {
        rememberTechnicalExemption(event, context, event?.lastAssistantMessage);
        return undefined;
      }
      return {
        action: "revise",
        reason: `owner chat policy: ${violations.join(",")}`,
        retry: {
          instruction:
            "Rewrite only the visible owner-chat rendering. Preserve the artifact's meaning and leave technical artifacts unchanged. Ask at most one owner question, choosing the oldest blocking or high-risk request first. Keep one recommendation and consequence. Remove machine ids, machine paths, internal tool or skill names, schema fields, artifact terms, and raw status codes.",
          idempotencyKey: revisionKey(event),
          maxAttempts: 1,
        },
      };
    },

    messageSending(event, context) {
      if (!isGuardedAgent(agentIds, event, context)) {
        return undefined;
      }
      const violations = inspectOwnerChat(event?.content);
      const exemption = takeTechnicalExemption(event, context);
      if (
        exemption?.technicalViewRequired === true &&
        exemption.content !== event?.content
      ) {
        return {
          cancel: true,
          cancelReason: "business-ontology-owner-chat-policy",
          metadata: {
            policy: "business-ontology-owner-chat",
            violations: ["technical_view_omitted"],
          },
        };
      }
      if (violations.length === 0) {
        return undefined;
      }
      if (
        exemption?.content === event?.content &&
        onlyTechnicalViolations(violations)
      ) {
        return undefined;
      }
      return {
        cancel: true,
        cancelReason: "business-ontology-owner-chat-policy",
        metadata: {
          policy: "business-ontology-owner-chat",
          violations,
        },
      };
    },
  };
}
