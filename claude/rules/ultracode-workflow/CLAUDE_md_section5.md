
## Dynamic workflows (ultracode): self-started, lower-effort subagents, stoppable

Set by the user on 2026-11-10. Here "ultracode" means a dynamic workflow: one session
orchestrating several subagents through the Workflow tool.

1. Self-start. Even with ultracode toggled off, a session that judges a workflow
   necessary for its work may start one itself, in the middle of its processing, and
   decides itself how many subagents to use and how to work with them. This is the
   user's standing, explicit opt-in to workflows. A session cannot flip the ultracode
   setting itself; starting a workflow is how it turns orchestration on for a task.
2. Lower effort; same or lower model. Every workflow subagent runs at an effort level
   strictly below the main session's (low < medium < high < xhigh < max). With the
   main session at max, subagents run at xhigh at most; how much lower is the main
   session's call. Pass `effort` on every `agent()` call: an agent without it
   inherits the main session's level, which is not lower and breaks this rule. A
   session at low effort has no lower level to give, so it does not start workflows.
   Subagents run the main session's model or a less capable one (Fable > Opus >
   Sonnet > Haiku), never a more capable one: with a Fable main session, Fable or
   Opus subagents are both fine. This overrides any default guidance to let workflow
   agents inherit the session's effort.
3. Stop when no longer needed. During a workflow the main session may turn
   orchestration back off as soon as it finds the subagents no longer needed: it
   stops the run (the TaskStop tool, or `x` in /workflows) and continues
   single-threaded. Completed agents' results are kept, so the run can be relaunched
   later.

If this file has rules about handing work over between sessions, read them together
with this section (amended by the user on 2026-11-10): a manager chooses the route for
settled hands-on work — a handover to a visible executor session, doing it itself, or
a workflow inside its own session under this section. Any session may use a workflow
within its own work, an executor on its handed-over job included. In a manager's
workflow the agents do the hands-on work and collect evidence; the manager still makes
the decisions, checks what comes back, and gives the verdicts.
