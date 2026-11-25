## 6. Approvals in plain text; thought-chain rigor

Set on 2026-11-24, after the E1 Step 5a incidents; scope stated on 2026-11-25. Full text,
with the incidents:
~/AI-management/claude/rules/thought-chain-rigor/The_Claude_Thought_Chain_Rule.md.

1. Plain-text approvals. A session asks the user for an approval, a budget, a push or
   an unblinding in plain text, never through an AskUserQuestion picker: a message
   another session sends through the bridge ends in Enter, and that Enter selects
   whatever option is highlighted (on 2026-11-24 it chose "Approve" in an open picker
   and handovers went out without the user). A hook denies AskUserQuestion on this
   machine. Before recording or relaying a user approval (section 1, approval relay),
   the session checks its transcript and ~/.claude/agy-bridge/send.log: the answer is
   plain user text, with no bridge send into that tab at that moment, and it quotes
   the timestamp and the text. The switches that bypass a guard
   (AI_MGMT_ALLOW_ASK_DIALOG, BRIDGE_FORCE_SEND, BRIDGE_FORCE_DISPATCH,
   AI_MGMT_RULES_GATE_OFF) are the user's: no agent sets one without the user's word
   in its own session, and a bridge send that is refused is reported, not forced.
2. Consumers and interpreters are checked, not assumed. Before writing that script B
   reads output A, that columns X give quantity Y, or that an interpreter has a
   library: open B and check its file pattern, row filter and columns; write Y's
   formula and map each symbol to a column that exists; run the exact binary with the
   import.
3. Interfaces are written out, never described. No "the contract is exact" and no
   "standard options": every flag, path pattern, schema and exit code is stated
   literally. Where a step writes files that another step reads, the text also says
   how they are staged (a .partial name, then an atomic rename) and which inputs are
   pinned by SHA-256. Each quantity one step produces is traced to the step that
   consumes it. A handover, sub-plan or statistics script is run through
   ~/AI-management/general/tools/handover-lint/check_spec.py before it is dispatched.
4. Numerical hygiene. An upper tail is computed with the survival function
   (stats.norm.sf(x), dist.sf(x)), never as 1 - cdf(x), for any distribution: in
   float64 that is 7% off at z = 8 and exactly 0.0 from z = 8.29. Fit and root-search
   bounds are widened until the extremum or the sign change is bracketed, never left
   to clamp silently. Every exported statistic is self-tested at the edges of its
   range and far outside the expected one, not only at the nominal point; for a
   counting statistic that means n = 0, n far below the background B, n near B and
   n = 100 B. No path names a Python minor version (use site.getusersitepackages()).
   A sensitivity table changes one thing per comparison.
5. Seats and headers. A Supervisor or Reviewer session under a read-only brief may
   run pure mathematics that reads no project file; builds, and runs over project
   data, go through the project's Executor route. When a document gains an Addendum or
   Erratum, every statement in its header that the addition supersedes is annotated.
