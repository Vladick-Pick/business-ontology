# Input fixture

Synthetic long-session trace fixture: a resident-agent session spanning ten
capture-loop rounds (30+ trace events). Each round mines a fact, validates it,
and only then marks the staged proposal ready for review.

The expected artifact is the trace itself. Discipline must not degrade near
the end of a long session: the last proposal-ready events in the trace are
still preceded by a passing validation event, exactly like the first ones.
