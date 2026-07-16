# Observer protocol

Capture during the live test:

- OpenClaw session id;
- Telegram inbound message ids;
- tool calls and tool results;
- workspace files created by the agent;
- authorization steps reached;
- source cursor state;
- the final `Ready for the first ontology session` message.

Stop the test if the agent asks for secrets in Telegram, stores raw payloads,
claims accepted truth without human review, claims GitHub write access without a
real selected-repository access path, marks Telegram active without host capture
and scheduling, or attempts to author accepted model changes instead of preparing
a branch or pull request.
