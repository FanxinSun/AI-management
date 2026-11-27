#!/usr/bin/env python3
"""Pre-flight linter for handovers, sub-plans, review reports, and statistical Python scripts.

Catches concrete defect classes observed in multi-agent physics/software workflows on 2026-11-24:
  - META_CONTRACT: interface specs using prose ("the command-line contract is exact") with no flags.
  - RETIRED_PATH: references to removed pre-reorganization AI-management paths.
  - APPROVAL_PICKER_PATTERN: TUI dialog "(Recommended)" snippets in approval quotes or un-audited relays.
  - ADDENDUM_HEADER_DRIFT: reports with Addenda/Errata whose header still asserts superseded claims.
  - NORM_CDF_TAIL: `1 - stats.norm.cdf(z)` (direct or via temp variable) float64 cancellation to 0.0
    for z >= 8.29 (use `.sf`).
  - CDF_TAIL: the same upper-tail cancellation for any other distribution, `1 - <dist>.cdf(x)`, direct or
    through a temporary (use `.sf` / `.logsf`). Comments and string literals are never findings.
  - HARDCODED_PY_MINOR_SITE: hardcoded `.local/lib/python3.<N>/site-packages`.
  - SPLITLINES_LINE_NUM: `.splitlines(` usage (splits on form feeds `\x0c`; violates Rule 9).
  - FIXED_BOUND_MINIMIZE: unexpanded hardcoded `minimize_scalar(..., method='bounded', bounds=(...))`.
  - PLAN_LAYOUT: a Markdown file that is a plan file by name (`plan` or `subplan` as a whole word of the
    name) but does not sit where The Project Planning Rule puts plan files (added 2026-11-26).

`--plan-layout` makes only the PLAN_LAYOUT check, on every Markdown file under the given directories and
on the given file paths, existing or planned; exit 0 when every plan file is canonical, 1 otherwise.

`--hook` reads a Claude Code PreToolUse JSON on stdin and exits 10 with one line of reason when a
Write/Edit/MultiEdit of a .py file ADDS a NORM_CDF_TAIL, CDF_TAIL or HARDCODED_PY_MINOR_SITE finding
(comments, docstrings, `1 - cdf` string literals, hunks/lines that already had the finding, and lines
marked `handover-lint: allow` are let through; path literals in code remain checked for
HARDCODED_PY_MINOR_SITE).
"""

import argparse
import ast
import difflib
import io
import json
import os
import re
import sys
import tempfile
import tokenize
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class Finding:
    severity: str  # ERROR | WARN
    code: str
    path: str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.severity} [{self.code}] {self.path}:{self.line}: {self.message}"


META_CONTRACT_RE = re.compile(
    r"\b(?:command-line|CLI|gate|interface|API)\s+contract\s+is\s+(?:exact|fixed|unchanged)\b",
    re.IGNORECASE,
)
CLI_OPTION_RE = re.compile(r"(?:^|[\s`\"'(])--[A-Za-z][A-Za-z0-9_-]*")

# Flag retired repo paths while allowing runtime `~/.claude/agy-bridge/` and repo subfolder labels (`rules-gate/`).
RETIRED_PATH_RE = re.compile(
    r"(?:(?:~|\$HOME|\$\{HOME\}|/home/[A-Za-z0-9_.-]+)?/AI-management/"
    r"(?:agy-bridge|rules-gate|executor-rules|download-ui-template)/[A-Za-z0-9_.*-]*"
    r"|(?<![A-Za-z0-9_/.~-])(?:agy-bridge|rules-gate|executor-rules|download-ui-template)/[A-Za-z0-9_.*-]+"
    r"|How_to_Control_Other_Agy_Sessions(?:_WSL|_macOS)?\.md)"
)

PICKER_QUOTE_RE = re.compile(r'["\'][^"\']*\(Recommended\)[^"\']*["\']')
NO_REASK_RE = re.compile(r"\bDo not ask the user again\b", re.IGNORECASE)
TIMESTAMP_RE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}|\d{2}:\d{2}:\d{2}|\d{2}:\d{2}\s*(?:UTC|Z|local|CST))\b")

ADDENDUM_HEADING_RE = re.compile(r"^#{1,3}\s+(?:Addendum|Erratum)\b", re.IGNORECASE)
HEADER_ABS_CLAIM_RE = re.compile(
    r"(?:reads?\s+no\s+[\w\s.-]+\s+file|opened\s+no\s+[\w\s.-]+|nothing\s+is\s+changed)",
    re.IGNORECASE,
)
HEADER_NOTE_RE = re.compile(
    r"\b(?:superseded|amended|withdrawn|updated\s+below|addendum\s*\d*\s+governs|erratum\s+below)\b",
    re.IGNORECASE,
)

HARDCODED_PY_SITE_RE = re.compile(r"\.local/lib/python3\.\d+/site-packages")

# A hold that keeps a session from its work until another session acts (2026-11-27, planner rule 18): it must name
# the user's direct instruction as what lifts it. Text in backticks or quotation marks, and quoted (">") lines, are
# quotations, not holds.
HOLD_UNTIL_RE = re.compile(r"\b(?:until|till|before|waits?\s+for|awaiting)\b[^.;]*\b(?:handover|hand-over|committee|manager|planner|router|nudge)", re.IGNORECASE)
HOLD_BAN_RE = re.compile(
    r"\b(?:change|edit|touch|modify|write|build|start|run)\s+(?:no|nothing)\b"
    r"|\bno\s+(?:file|files|change|changes|edit|edits|code)\b"
    r"|\b(?:do|does|must|may)\s+not\s+(?:change|edit|touch|modify|write|build|start|run)\b"
    r"|\bfrozen\b|\bon\s+hold\b|\b(?:stays?|remains?)\s+(?:idle|paused|held)\b|\bwaits?\s+(?:for|until)\b",
    re.IGNORECASE,
)
HOLD_USER_RE = re.compile(r"\buser'?s?\b", re.IGNORECASE)
QUOTED_RE = re.compile(r"`[^`]*`|\"[^\"]*\"|\u201c[^\u201d]*\u201d")
NOT_A_HOLD_RE = re.compile(r"\b(?:do|does|must|need)\s+not\s+wait\w*|\b(?:don't|doesn't|never)\s+wait\w*|\bwithout\s+waiting\b|\bno\s+need\s+to\s+wait\b", re.IGNORECASE)
SPLITLINES_RE = re.compile(r"\.splitlines\s*\(")


def strip_fenced_blocks(lines: List[str]) -> List[tuple]:
    """Return list of (1-based line_no, text) outside fenced code blocks."""
    out = []
    in_fence = False
    for idx, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((idx, line))
    return out


def lint_markdown(path: Path, text: str) -> List[Finding]:
    findings: List[Finding] = []
    lines = text.split("\n")
    has_cli_flag = bool(CLI_OPTION_RE.search(text))

    for idx, line in enumerate(lines, 1):
        if META_CONTRACT_RE.search(line) and not has_cli_flag:
            findings.append(Finding(
                "ERROR", "META_CONTRACT", str(path), idx,
                "States interface/CLI contract is exact without specifying any `--flag` option name in the file.",
            ))
        if RETIRED_PATH_RE.search(line):
            findings.append(Finding(
                "ERROR", "RETIRED_PATH", str(path), idx,
                "References retired pre-reorganization AI-management path; use the canonical `general/`, `claude/`, or `agy/` path.",
            ))
        if PICKER_QUOTE_RE.search(line) and re.search(r"\bapprove|cap|hold|recommend", line, re.IGNORECASE):
            findings.append(Finding(
                "WARN", "APPROVAL_PICKER_PATTERN", str(path), idx,
                "Contains a quoted `(Recommended)` dialog option in an approval record; verify plain-text user provenance.",
            ))

    for idx, line in strip_fenced_blocks(lines):
        if line.lstrip().startswith(">"):
            continue
        bare = NOT_A_HOLD_RE.sub("", QUOTED_RE.sub("", line))
        if HOLD_UNTIL_RE.search(bare) and HOLD_BAN_RE.search(bare) and not HOLD_USER_RE.search(bare):
            findings.append(Finding(
                "WARN", "HOLD_WITHOUT_USER", str(path), idx,
                "Holds a session from its work until another session acts, without naming the user's direct instruction "
                "as what lifts the hold (planner rule 18; the user, 2026-11-27).",
            ))

    if NO_REASK_RE.search(text) and not TIMESTAMP_RE.search(text):
        for idx, line in enumerate(lines, 1):
            if NO_REASK_RE.search(line):
                findings.append(Finding(
                    "WARN", "APPROVAL_PICKER_PATTERN", str(path), idx,
                    "`Do not ask the user again` without an audited approval timestamp (HH:MM / ISO UTC) and source session/log.",
                ))
                break

    non_fenced = strip_fenced_blocks(lines)
    addendum_lines = [idx for idx, ln in non_fenced if ADDENDUM_HEADING_RE.match(ln.strip())]
    if addendum_lines:
        first_add = addendum_lines[0]
        header_window = [(idx, ln) for idx, ln in non_fenced if idx <= min(30, first_add - 1)]
        has_annotation = any(HEADER_NOTE_RE.search(ln) for _, ln in header_window)
        if not has_annotation:
            for idx, ln in header_window:
                if idx <= 15 and HEADER_ABS_CLAIM_RE.search(ln):
                    findings.append(Finding(
                        "WARN", "ADDENDUM_HEADER_DRIFT", str(path), idx,
                        "Document has an Addendum/Erratum below, while this header still makes an unannotated absolute claim (`reads no ... file` / `Limits kept`).",
                    ))
                    break

    return findings


def _is_norm_cdf_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    if isinstance(fn, ast.Attribute):
        if fn.attr == "ndtr":
            return True
        if fn.attr == "cdf" and isinstance(fn.value, ast.Attribute) and fn.value.attr == "norm":
            return True
        if fn.attr == "cdf" and isinstance(fn.value, ast.Name) and fn.value.id == "norm":
            return True
    elif isinstance(fn, ast.Name) and fn.id == "ndtr":
        return True
    return False


def _is_one_const(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and node.value == 1


def _is_const_num(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_const_num(node.operand)
    return False


TAIL_MESSAGES = {
    "NORM_CDF_TAIL": "`1 - norm.cdf(...)` cancels to 0.0 in float64 for z >= 8.29; use `stats.norm.sf(...)`.",
    "CDF_TAIL": (
        "`1 - <dist>.cdf(...)` loses the upper tail to float64 cancellation (7% off near 8 sigma, then exactly 0.0); "
        "use the distribution's `.sf(...)` or `.logsf(...)`."
    ),
}


def _cdf_kind(node: ast.AST) -> str:
    """Finding code for `1 - <node>` when node is a CDF call, else ''."""
    if not isinstance(node, ast.Call):
        return ""
    if _is_norm_cdf_call(node):
        return "NORM_CDF_TAIL"
    fn = node.func
    if isinstance(fn, ast.Attribute) and fn.attr == "cdf":
        return "CDF_TAIL"
    if isinstance(fn, ast.Name) and fn.id == "cdf":
        return "CDF_TAIL"
    return ""


_Env = Dict[str, Set[str]]


def _copy_env(env: _Env) -> _Env:
    return {k: set(v) for k, v in env.items()}


def _merge_envs(*envs: _Env) -> _Env:
    merged: _Env = {}
    for env in envs:
        for k, kinds in env.items():
            if kinds:
                merged.setdefault(k, set()).update(kinds)
    return merged


def _expr_tail_kinds(node: Optional[ast.AST], env: _Env) -> Set[str]:
    if node is None:
        return set()
    kind = _cdf_kind(node)
    if kind:
        return {kind}
    if isinstance(node, ast.Name):
        return set(env.get(node.id, ()))
    if isinstance(node, ast.IfExp):
        return _expr_tail_kinds(node.body, env) | _expr_tail_kinds(node.orelse, env)
    if isinstance(node, ast.NamedExpr):
        return _expr_tail_kinds(node.value, env)
    return set()


def _clear_target_names(target: ast.AST, out_env: _Env) -> None:
    if isinstance(target, ast.Name):
        out_env.pop(target.id, None)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            _clear_target_names(elt, out_env)
    elif isinstance(target, ast.Starred):
        _clear_target_names(target.value, out_env)


def _bind_target(target: ast.AST, value: Optional[ast.AST], read_env: _Env, out_env: _Env) -> None:
    if isinstance(target, ast.Name):
        kinds = _expr_tail_kinds(value, read_env)
        if kinds:
            out_env[target.id] = kinds
        else:
            out_env.pop(target.id, None)
        return
    if (
        isinstance(target, (ast.Tuple, ast.List))
        and isinstance(value, (ast.Tuple, ast.List))
        and len(target.elts) == len(value.elts)
        and not any(isinstance(e, ast.Starred) for e in target.elts)
        and not any(isinstance(e, ast.Starred) for e in value.elts)
    ):
        for sub_t, sub_v in zip(target.elts, value.elts):
            _bind_target(sub_t, sub_v, read_env, out_env)
        return
    _clear_target_names(target, out_env)


def _pattern_bound_names(pattern: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for node in ast.walk(pattern):
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
    return names


def _is_unguarded_wildcard(case: ast.AST) -> bool:
    if getattr(case, "guard", None) is not None:
        return False
    pat = getattr(case, "pattern", None)
    return isinstance(pat, ast.MatchAs) and pat.pattern is None


def _docstring_ids(tree: ast.Module) -> Set[int]:
    ids: Set[int] = set()
    doc_owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for owner in ast.walk(tree):
        if isinstance(owner, doc_owners) and owner.body:
            first = owner.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                ids.add(id(first.value))
    return ids


def _analyze_ast(
    path: Path, tree: ast.Module
) -> Tuple[List[Finding], Dict[int, str]]:
    """Walk statements and expressions forward, returning AST findings and splitlines lines."""
    found: Dict[Tuple[int, int, str], Finding] = {}
    splitlines_lines: Dict[int, str] = {}

    def scan_target_exprs(target: ast.AST, env: _Env) -> None:
        if isinstance(target, ast.Subscript):
            scan_expr(target.value, env)
            scan_expr(target.slice, env)
        elif isinstance(target, ast.Attribute):
            scan_expr(target.value, env)
        elif isinstance(target, ast.Starred):
            scan_target_exprs(target.value, env)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                scan_target_exprs(elt, env)

    def scan_func_header(fn: ast.AST, env: _Env) -> None:
        for dec in getattr(fn, "decorator_list", ()):
            scan_expr(dec, env)
        args = fn.args
        for d in args.defaults:
            scan_expr(d, env)
        for d in args.kw_defaults:
            if d is not None:
                scan_expr(d, env)
        for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            if a.annotation is not None:
                scan_expr(a.annotation, env)
        for special in (args.vararg, args.kwarg):
            if special is not None and special.annotation is not None:
                scan_expr(special.annotation, env)
        if getattr(fn, "returns", None) is not None:
            scan_expr(fn.returns, env)

    def scan_expr(node: Optional[ast.AST], env: _Env) -> None:
        if node is None:
            return
        if isinstance(node, ast.Lambda):
            for d in node.args.defaults:
                scan_expr(d, env)
            for d in node.args.kw_defaults:
                if d is not None:
                    scan_expr(d, env)
            scan_expr(node.body, {})
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            comp_env = _copy_env(env)
            for gen in node.generators:
                scan_expr(gen.iter, comp_env)
                _clear_target_names(gen.target, comp_env)
                for cond in gen.ifs:
                    scan_expr(cond, comp_env)
            if isinstance(node, ast.DictComp):
                scan_expr(node.key, comp_env)
                scan_expr(node.value, comp_env)
            else:
                scan_expr(node.elt, comp_env)
            return
        if isinstance(node, ast.IfExp):
            scan_expr(node.test, env)
            b_env = _copy_env(env)
            e_env = _copy_env(env)
            scan_expr(node.body, b_env)
            scan_expr(node.orelse, e_env)
            merged = _merge_envs(b_env, e_env)
            env.clear()
            env.update(merged)
            return
        if isinstance(node, ast.NamedExpr):
            scan_expr(node.value, env)
            _bind_target(node.target, node.value, _copy_env(env), env)
            return
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub) and _is_one_const(node.left):
            scan_expr(node.left, env)
            scan_expr(node.right, env)
            kinds = _expr_tail_kinds(node.right, env)
            if kinds:
                kind = "NORM_CDF_TAIL" if kinds == {"NORM_CDF_TAIL"} else "CDF_TAIL"
                found[(node.lineno, node.col_offset, kind)] = Finding(
                    "ERROR", kind, str(path), node.lineno, TAIL_MESSAGES[kind],
                )
            return
        if isinstance(node, ast.Call):
            fn = node.func
            fname = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
            if isinstance(fn, ast.Attribute) and fn.attr == "splitlines":
                sl_line = getattr(fn, "end_lineno", None) or node.lineno
                splitlines_lines.setdefault(sl_line, "SPLITLINES_LINE_NUM")
            if fname == "minimize_scalar":
                kw = {k.arg: k.value for k in node.keywords if k.arg}
                mnode = kw.get("method")
                bnode = kw.get("bounds")
                is_bounded = isinstance(mnode, ast.Constant) and mnode.value == "bounded"
                if (
                    is_bounded
                    and isinstance(bnode, ast.Tuple)
                    and len(bnode.elts) == 2
                    and all(_is_const_num(e) for e in bnode.elts)
                ):
                    found[(node.lineno, node.col_offset, "FIXED_BOUND_MINIMIZE")] = Finding(
                        "WARN", "FIXED_BOUND_MINIMIZE", str(path), node.lineno,
                        "`minimize_scalar(..., method='bounded', bounds=(const, const))` silently clamps extreme excesses/deficits unless adaptively expanded.",
                    )
        for child in ast.iter_child_nodes(node):
            scan_expr(child, env)

    def walk_block(
        stmts: List[ast.stmt],
        start_env: _Env,
        breaks: Optional[List[_Env]] = None,
        continues: Optional[List[_Env]] = None,
    ) -> Tuple[_Env, bool]:
        cur = _copy_env(start_env)
        for stmt in stmts:
            if isinstance(stmt, ast.Assign):
                scan_expr(stmt.value, cur)
                snap = _copy_env(cur)
                for tgt in stmt.targets:
                    scan_target_exprs(tgt, snap)
                    _bind_target(tgt, stmt.value, snap, cur)
            elif isinstance(stmt, ast.AnnAssign):
                scan_expr(stmt.annotation, cur)
                if stmt.value is not None:
                    scan_expr(stmt.value, cur)
                    snap = _copy_env(cur)
                    scan_target_exprs(stmt.target, snap)
                    _bind_target(stmt.target, stmt.value, snap, cur)
                else:
                    scan_target_exprs(stmt.target, cur)
            elif isinstance(stmt, ast.AugAssign):
                scan_target_exprs(stmt.target, cur)
                scan_expr(stmt.value, cur)
                _clear_target_names(stmt.target, cur)
            elif isinstance(stmt, ast.Delete):
                for tgt in stmt.targets:
                    scan_target_exprs(tgt, cur)
                    _clear_target_names(tgt, cur)
            elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
                for alias in stmt.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    if bound != "*":
                        cur.pop(bound, None)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scan_func_header(stmt, cur)
                cur.pop(stmt.name, None)
                walk_block(stmt.body, {})
            elif isinstance(stmt, ast.ClassDef):
                for dec in stmt.decorator_list:
                    scan_expr(dec, cur)
                for base in stmt.bases:
                    scan_expr(base, cur)
                for kw in stmt.keywords:
                    scan_expr(kw.value, cur)
                cur.pop(stmt.name, None)
                walk_block(stmt.body, {})
            elif isinstance(stmt, ast.If):
                scan_expr(stmt.test, cur)
                then_env, then_term = walk_block(stmt.body, cur, breaks, continues)
                else_env, else_term = walk_block(stmt.orelse, cur, breaks, continues)
                if then_term and else_term:
                    return {}, True
                if then_term:
                    cur = else_env
                elif else_term:
                    cur = then_env
                else:
                    cur = _merge_envs(then_env, else_env)
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                if isinstance(stmt, (ast.For, ast.AsyncFor)):
                    scan_expr(stmt.iter, cur)
                head_env = _copy_env(cur)
                loop_breaks: List[_Env] = []
                for _ in range(2):
                    loop_breaks = []
                    loop_conts: List[_Env] = []
                    body_in = _copy_env(head_env)
                    if isinstance(stmt, (ast.For, ast.AsyncFor)):
                        scan_target_exprs(stmt.target, body_in)
                        _clear_target_names(stmt.target, body_in)
                    else:
                        scan_expr(stmt.test, body_in)
                    body_out, body_term = walk_block(stmt.body, body_in, loop_breaks, loop_conts)
                    back_envs = ([] if body_term else [body_out]) + loop_conts
                    next_head = _merge_envs(head_env, *back_envs)
                    if next_head == head_env:
                        break
                    head_env = next_head
                if stmt.orelse:
                    else_out, else_term = walk_block(stmt.orelse, head_env, breaks, continues)
                    normal_exit = [] if else_term else [else_out]
                else:
                    normal_exit = [head_env]
                after_envs = loop_breaks + normal_exit
                if not after_envs:
                    return {}, True
                cur = _merge_envs(*after_envs)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    scan_expr(item.context_expr, cur)
                    if item.optional_vars is not None:
                        scan_target_exprs(item.optional_vars, cur)
                        _clear_target_names(item.optional_vars, cur)
                cur, body_term = walk_block(stmt.body, cur, breaks, continues)
                if body_term:
                    return {}, True
            elif isinstance(stmt, ast.Try) or (hasattr(ast, "TryStar") and isinstance(stmt, ast.TryStar)):
                try_out, try_term = walk_block(stmt.body, cur, breaks, continues)
                handler_in = _merge_envs(cur, try_out)
                fallthroughs: List[_Env] = []
                if not try_term:
                    if stmt.orelse:
                        else_out, else_term = walk_block(stmt.orelse, try_out, breaks, continues)
                        if not else_term:
                            fallthroughs.append(else_out)
                    else:
                        fallthroughs.append(try_out)
                handler_outs: List[_Env] = []
                for h in stmt.handlers:
                    h_in = _copy_env(handler_in)
                    if h.type is not None:
                        scan_expr(h.type, h_in)
                    if h.name:
                        h_in.pop(h.name, None)
                    h_out, h_term = walk_block(h.body, h_in, breaks, continues)
                    handler_outs.append(h_out)
                    if not h_term:
                        fallthroughs.append(h_out)
                if stmt.finalbody:
                    if not fallthroughs:
                        fin_in = _merge_envs(handler_in, *handler_outs)
                        walk_block(stmt.finalbody, fin_in, breaks, continues)
                        return {}, True
                    if try_term or len(handler_outs) > len(fallthroughs) - (0 if try_term else 1):
                        walk_block(stmt.finalbody, _merge_envs(handler_in, *handler_outs), breaks, continues)
                    fin_out, fin_term = walk_block(stmt.finalbody, _merge_envs(*fallthroughs), breaks, continues)
                    if fin_term:
                        return {}, True
                    cur = fin_out
                else:
                    if not fallthroughs:
                        return {}, True
                    cur = _merge_envs(*fallthroughs)
            elif hasattr(ast, "Match") and isinstance(stmt, ast.Match):
                scan_expr(stmt.subject, cur)
                fallthroughs = []
                has_default = False
                for case in stmt.cases:
                    if _is_unguarded_wildcard(case):
                        has_default = True
                    c_in = _copy_env(cur)
                    for name in _pattern_bound_names(case.pattern):
                        c_in.pop(name, None)
                    if case.guard is not None:
                        scan_expr(case.guard, c_in)
                    c_out, c_term = walk_block(case.body, c_in, breaks, continues)
                    if not c_term:
                        fallthroughs.append(c_out)
                if not has_default:
                    fallthroughs.append(cur)
                if not fallthroughs:
                    return {}, True
                cur = _merge_envs(*fallthroughs)
            elif isinstance(stmt, ast.Return):
                scan_expr(stmt.value, cur)
                return cur, True
            elif isinstance(stmt, ast.Raise):
                scan_expr(stmt.exc, cur)
                scan_expr(stmt.cause, cur)
                return cur, True
            elif isinstance(stmt, ast.Break):
                if breaks is not None:
                    breaks.append(_copy_env(cur))
                return cur, True
            elif isinstance(stmt, ast.Continue):
                if continues is not None:
                    continues.append(_copy_env(cur))
                return cur, True
            else:
                for child in ast.iter_child_nodes(stmt):
                    scan_expr(child, cur)
        return cur, False

    walk_block(tree.body, {})
    return [found[key] for key in sorted(found)], splitlines_lines


def _ast_python_findings(path: Path, text: str, tree: Optional[ast.Module] = None) -> List[Finding]:
    if tree is None:
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            return []
    findings, _ = _analyze_ast(path, tree)
    return findings


def _token_site_and_splitlines(path: Path, text: str, lines: List[str]) -> List[Finding]:
    """Token fallback for unparseable Python files: skips `#` comments."""
    findings: List[Finding] = []
    seen_site: Set[int] = set()
    seen_split: Set[int] = set()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError):
        return []
    for idx, tok in enumerate(tokens):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and HARDCODED_PY_SITE_RE.search(tok.string):
            s_ln = tok.start[0]
            e_ln = tok.end[0]
            matched = [ln for ln in range(s_ln, e_ln + 1) if 1 <= ln <= len(lines) and HARDCODED_PY_SITE_RE.search(lines[ln - 1])]
            for ln in (matched or [s_ln]):
                if ln not in seen_site:
                    seen_site.add(ln)
                    findings.append(Finding(
                        "ERROR", "HARDCODED_PY_MINOR_SITE", str(path), ln,
                        "Hardcoded Python minor-version site-packages path breaks 10-year portability; use `site.getusersitepackages()` or `sysconfig`.",
                    ))
        if (
            tok.type == tokenize.NAME
            and tok.string == "splitlines"
            and idx > 0
            and tokens[idx - 1].type == tokenize.OP
            and tokens[idx - 1].string == "."
            and idx + 1 < len(tokens)
            and tokens[idx + 1].type == tokenize.OP
            and tokens[idx + 1].string == "("
            and tok.start[0] not in seen_split
        ):
            seen_split.add(tok.start[0])
            findings.append(Finding(
                "WARN", "SPLITLINES_LINE_NUM", str(path), tok.start[0],
                "`.splitlines()` also splits on form feeds (`\\x0c`); use `.split('\\n')` when counting file/PDF lines (Executor Rule 9).",
            ))
    return findings


def lint_python(path: Path, text: str) -> List[Finding]:
    if path.name == "check_spec.py":
        return []
    lines = text.split("\n")
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return _token_site_and_splitlines(path, text, lines)

    findings, splitlines_lines = _analyze_ast(path, tree)
    doc_ids = _docstring_ids(tree)
    seen_site: Set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and id(node) not in doc_ids and isinstance(node.value, str):
            if HARDCODED_PY_SITE_RE.search(node.value):
                end_ln = getattr(node, "end_lineno", None) or node.lineno
                matched = [
                    ln for ln in range(node.lineno, end_ln + 1)
                    if 1 <= ln <= len(lines) and HARDCODED_PY_SITE_RE.search(lines[ln - 1])
                ]
                for ln in (matched or [node.lineno]):
                    if ln not in seen_site:
                        seen_site.add(ln)
                        findings.append(Finding(
                            "ERROR", "HARDCODED_PY_MINOR_SITE", str(path), ln,
                            "Hardcoded Python minor-version site-packages path breaks 10-year portability; use `site.getusersitepackages()` or `sysconfig`.",
                        ))
    for ln in sorted(splitlines_lines):
        findings.append(Finding(
            "WARN", "SPLITLINES_LINE_NUM", str(path), ln,
            "`.splitlines()` also splits on form feeds (`\\x0c`); use `.split('\\n')` when counting file/PDF lines (Executor Rule 9).",
        ))
    findings.sort(key=lambda f: (f.line, f.code))
    return findings


SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", ".system_generated", "assets"}
SKIP_DOC_BASENAMES = {
    "The_Executor_Regulations.md",
    "The_Claude_Thought_Chain_Rule.md",
    "PLAN.md",
}
ALLOW_MARKER = "handover-lint: allow"


# ---- Plan-file layout: general/rules/project-planning/The_Project_Planning_Rule.md ----
# One PLAN.md per project (project root, or <project>/plan/), plan/PLAN_lane<N>.md per lane, step files
# <X>-<n>.md in subplan_<X>/ directories; a directory with its own .git is its own project. The verdict is
# the one the Claude Code plan-file guard gives on the rule's home machine, so that every agent can run it.
PLAN_NAME_RE = re.compile(r"(^|[_.-])(sub)?plan([_.-]|$)", re.IGNORECASE)
PLAN_LANE_RE = re.compile(r"^PLAN_lane[0-9]+\.md$")
PLAN_SCRATCH_DIRS = {
    ".claude", ".codex", ".gemini", ".cache", ".local", "miniconda", "site-packages", "node_modules", ".git",
}


def _is_markdown_name(name: str) -> bool:
    return name.endswith(".md") or name.endswith(".MD")


def is_plan_named(name: str) -> bool:
    """True for a Markdown file name with `plan` or `subplan` as a whole word (words split at `_`, `-`, `.`)."""
    return _is_markdown_name(name) and bool(PLAN_NAME_RE.search(name))


def _plan_scratch_path(path: str) -> bool:
    """Agent configuration, caches, installed packages and temp/scratch dirs are not project space."""
    tmp_prefixes = (
        "/tmp/",
        "/private/tmp/",
        os.path.abspath(tempfile.gettempdir()).rstrip("/") + "/",
        os.path.realpath(tempfile.gettempdir()).rstrip("/") + "/",
    )
    return path.startswith(tmp_prefixes) or any(
        part in PLAN_SCRATCH_DIRS for part in Path(path).parts[:-1]
    )


def _plan_root_above(start: str) -> bool:
    """True when `start`, or a directory above it inside the same git repository, holds a plan root."""
    home = os.path.expanduser("~")
    d = start
    while d not in ("/", home, "/mnt") and not re.fullmatch(r"/mnt/.", d):
        if os.path.isfile(os.path.join(d, "PLAN.md")) or os.path.isfile(os.path.join(d, "plan", "PLAN.md")):
            return True
        if os.path.exists(os.path.join(d, ".git")):
            return False  # repository root: what lies above belongs to another project
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent
    return False


def plan_layout_verdict(path: str, honor_scratch: bool = True) -> str:
    """'' when a Markdown file at `path` (existing or planned) is not a plan file by name, or sits where the
    rule puts plan files; otherwise the reason why it is not canonical."""
    p = os.path.abspath(path)
    name = os.path.basename(p)
    if not _is_markdown_name(name):
        return ""
    if honor_scratch and _plan_scratch_path(p):
        return ""
    d = os.path.dirname(p)
    in_plan_dir = os.path.basename(d) == "plan"
    if name == "PLAN.md":
        if in_plan_dir:
            project = os.path.dirname(d)
            other = os.path.join(project, "PLAN.md")
        else:
            project = d
            other = os.path.join(d, "plan", "PLAN.md")
        if os.path.isfile(other):
            return f"this project already has {other}: one layout only, never both PLAN.md and plan/PLAN.md"
        if os.path.exists(os.path.join(project, ".git")):
            return ""  # its own git repository (a submodule, for example) is its own project
        if _plan_root_above(os.path.dirname(project)):
            return (
                "a plan root already exists above this directory in the same git repository: a project has one "
                "and only one PLAN.md (use plan/PLAN_lane<N>.md and sub-plan step files; a submodule may hold "
                "its own PLAN.md once it is its own git repository)"
            )
        return ""
    if PLAN_LANE_RE.match(name):
        if in_plan_dir and os.path.isfile(os.path.join(os.path.dirname(d), "PLAN.md")):
            return ""
        return "PLAN_lane<N>.md lives only directly inside plan/, beside the project's root PLAN.md"
    if PLAN_NAME_RE.search(name):
        return f"'{name}' is not a canonical plan file name"
    return ""


def iter_markdown(root: Path) -> Iterable[Path]:
    for cur, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in PLAN_SCRATCH_DIRS and d != "__pycache__")
        for fn in sorted(files):
            if _is_markdown_name(fn):
                yield Path(cur) / fn


def plan_layout_findings(paths: Iterable[str]) -> Tuple[int, int, List[Finding]]:
    """(Markdown files checked, plan files by name, findings) for directories and for existing or planned files.

    The paths are checked because they were named, so the scratch-space exemption is not applied to them;
    directories of that kind are still not entered below a named directory."""
    n_md = n_named = 0
    findings: List[Finding] = []
    for raw in paths:
        p = Path(raw)
        for fp in (iter_markdown(p) if p.is_dir() else [p]):
            if not _is_markdown_name(fp.name):
                continue
            n_md += 1
            n_named += int(is_plan_named(fp.name))
            reason = plan_layout_verdict(str(fp), honor_scratch=False)
            if reason:
                findings.append(Finding("ERROR", "PLAN_LAYOUT", str(fp), 1, reason))
    return n_md, n_named, findings


def iter_targets(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIR_NAMES)
                for fn in sorted(files):
                    fp = Path(root) / fn
                    if fp.suffix.lower() in (".md", ".py"):
                        yield fp


def lint_path(path: Path, honor_scratch: bool = True) -> List[Finding]:
    # The plan-file layout is a matter of the path alone, and no marker in the text waives it.
    layout: List[Finding] = []
    if path.suffix.lower() == ".md":
        reason = plan_layout_verdict(str(path), honor_scratch)
        if reason:
            layout.append(Finding("ERROR", "PLAN_LAYOUT", str(path), 1, reason))
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return layout + [Finding("ERROR", "READ_ERROR", str(path), 1, str(exc))]
    if path.suffix.lower() == ".md":
        if path.name in SKIP_DOC_BASENAMES:
            return layout
        raw = lint_markdown(path, text)
    elif path.suffix.lower() == ".py":
        raw = lint_python(path, text)
    else:
        return []
    lines = text.split("\n")
    return layout + [f for f in raw if ALLOW_MARKER not in lines[f.line - 1]]


HOOK_CODES = ("NORM_CDF_TAIL", "CDF_TAIL", "HARDCODED_PY_MINOR_SITE")
HOOK_MAX_BYTES = 2_000_000


def _hygiene_findings(path: Path, text: str) -> List[Finding]:
    lines = text.split("\n")
    return [
        f for f in lint_python(path, text)
        if f.code in HOOK_CODES and 1 <= f.line <= len(lines) and ALLOW_MARKER not in lines[f.line - 1]
    ]


def _text_after_edit(old: str, tool: str, tin: dict):
    """The text the file would hold after the tool call, or None when that cannot be worked out."""
    if tool == "Write":
        content = tin.get("content")
        return content if isinstance(content, str) else None
    edits = [tin] if tool == "Edit" else (tin.get("edits") or [])
    new = old
    for edit in edits:
        o, n = edit.get("old_string"), edit.get("new_string")
        if not isinstance(o, str) or not isinstance(n, str):
            return None
        if o == "":
            if new:
                return None
            new = n
        elif o not in new:
            return None
        else:
            new = new.replace(o, n) if edit.get("replace_all") else new.replace(o, n, 1)
    return new


def hook_decide(data: dict) -> str:
    """For a PreToolUse hook: '' to let a Write/Edit/MultiEdit through, or the reason to refuse it.

    Only an edit that ADDS a hygiene finding in a changed hunk (or newly taints an unchanged line)
    is refused: comments, docstrings, `1 - cdf` strings, hunks/lines that already had the finding,
    and lines marked `handover-lint: allow` are left alone. Path literals in code remain checked for
    `HARDCODED_PY_MINOR_SITE`. Any doubt lets the edit through.
    """
    try:
        tool = data.get("tool_name", "")
        tin = data.get("tool_input") or {}
        fp = tin.get("file_path") or ""
        if tool not in ("Write", "Edit", "MultiEdit") or not fp.endswith(".py"):
            return ""
        path = Path(fp)
        if path.name == "check_spec.py":
            return ""
        old = ""
        if path.is_file():
            if path.stat().st_size > HOOK_MAX_BYTES:
                return ""
            old = path.read_text(encoding="utf-8", errors="replace")
        new = _text_after_edit(old, tool, tin)
        if new is None or len(new) > HOOK_MAX_BYTES:
            return ""
        try:
            ast.parse(new)
        except (SyntaxError, ValueError, RecursionError):
            return ""
        before = _hygiene_findings(path, old)
        after = _hygiene_findings(path, new)
        old_lines, new_lines = old.split("\n"), new.split("\n")
        old_seq = old_lines if old else []
        new_seq = new_lines if new else []

        before_by_cl: Dict[Tuple[str, int], List[Finding]] = defaultdict(list)
        after_by_cl: Dict[Tuple[str, int], List[Finding]] = defaultdict(list)
        for f in before:
            before_by_cl[(f.code, f.line)].append(f)
        for f in after:
            after_by_cl[(f.code, f.line)].append(f)

        added: List[Finding] = []
        seen_keys: Set[Tuple[int, str]] = set()

        def record(f: Finding) -> None:
            k = (f.line, f.code)
            if k not in seen_keys:
                seen_keys.add(k)
                added.append(f)

        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old_seq, new_seq, autojunk=False).get_opcodes():
            if tag == "equal":
                for off in range(i2 - i1):
                    old_ln, new_ln = i1 + 1 + off, j1 + 1 + off
                    for code in HOOK_CODES:
                        b_ln = before_by_cl.get((code, old_ln), ())
                        a_ln = after_by_cl.get((code, new_ln), ())
                        if len(a_ln) > len(b_ln):
                            for f in a_ln[len(b_ln):]:
                                record(f)
            else:
                for code in HOOK_CODES:
                    b_hunk = [f for ln in range(i1 + 1, i2 + 1) for f in before_by_cl.get((code, ln), ())]
                    a_hunk = [f for ln in range(j1 + 1, j2 + 1) for f in after_by_cl.get((code, ln), ())]
                    if len(a_hunk) > len(b_hunk):
                        known = {
                            old_lines[f.line - 1].strip()
                            for f in b_hunk
                            if 1 <= f.line <= len(old_lines)
                        }
                        fresh = [
                            f for f in a_hunk
                            if 1 <= f.line <= len(new_lines) and new_lines[f.line - 1].strip() not in known
                        ] or a_hunk[len(b_hunk):]
                        record(fresh[0])
        added.sort(key=lambda f: (f.line, f.code))
    except Exception:
        return ""
    if not added:
        return ""
    return (
        "; ".join(f"line {f.line}: {f.message}" for f in added)
        + " This edit adds it (a line that already had it is left alone). A deliberate exception: end the line with"
        + " `# handover-lint: allow` and the reason."
    )


def hook_main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    reason = hook_decide(data if isinstance(data, dict) else {})
    if reason:
        print(reason)
        return 10
    return 0


def selftest() -> int:
    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        f1 = tmp / "bad_meta.md"
        f1.write_text("# 5a-1\nThe command-line contract is exact. No digit is printed.\n", encoding="utf-8")
        codes1 = {x.code for x in lint_path(f1)}
        check("catches META_CONTRACT when no flags given", "META_CONTRACT" in codes1, str(codes1))

        f2 = tmp / "good_cli.md"
        f2.write_text("# 5a-1\nThe command-line contract is exact: `--first-look <dir> --gate <file>`.\n", encoding="utf-8")
        codes2 = {x.code for x in lint_path(f2)}
        check("allows concrete CLI contract with --flags", "META_CONTRACT" not in codes2, str(codes2))

        f3 = tmp / "bad_report.md"
        f3.write_text(
            "# Reply\n- Limits kept: ran a script that reads no E1 file.\nSee `~/AI-management/agy-bridge/send_to_tty.sh`.\n"
            "Any fix comes as an addendum later.\n"
            "Do not ask the user again; answered \"Approve, cap 9,000 s (Recommended)\".\n\n## Addendum\nActually read 24 dumps.\n",
            encoding="utf-8",
        )
        codes3 = {x.code for x in lint_path(f3)}
        check(
            "catches RETIRED_PATH, APPROVAL_PICKER_PATTERN, ADDENDUM_HEADER_DRIFT",
            {"RETIRED_PATH", "APPROVAL_PICKER_PATTERN", "ADDENDUM_HEADER_DRIFT"}.issubset(codes3),
            str(codes3),
        )

        fh = tmp / "hold.md"
        fh.write_text(
            "# Notice\n- **Executor:** change no file in `tools/` until the Committee's handover.\n"
            "- **Executor:** change no file in `tools/` until the Committee's handover, or until your own user tells you directly.\n"
            "- My notice said \"change no file in tools/ until the Committee's handover\", and that was wrong.\n"
            "> change no file until the manager's handover\n"
            "```\nchange no file until the manager's handover\n```\n"
            "Never delete raw downloads until the Manager/Committee's independent check records the file.\n"
            "The executor stays idle and waits for the planner's nudge.\n"
            "Blocks A and B run in one go. Do not wait for the Committee between them.\n",
            encoding="utf-8",
        )
        hold = [x.line for x in lint_path(fh) if x.code == "HOLD_WITHOUT_USER"]
        check("HOLD_WITHOUT_USER: flags a hold that names no user (lines 2 and 10), and passes one that does, quotations, "
              "a fenced block, a deletion gate and \"do not wait for the Committee\"", hold == [2, 10], str(hold))

        f4 = tmp / "runtime_ok.md"
        f4.write_text("Runtime state lives in `~/.claude/agy-bridge/state/`, see [`rules-gate/`](claude/hooks/rules-gate/install.sh).\n", encoding="utf-8")
        codes4 = {x.code for x in lint_path(f4)}
        check("allows ~/.claude/agy-bridge/ and prose subfolder labels", "RETIRED_PATH" not in codes4, str(codes4))

        f5 = tmp / "bad_stats.py"
        f5.write_text(
            "from pathlib import Path\n"
            "USER_SITE = Path.home() / '.local/lib/python3.14/site-packages'\n"
            "def f(n, q, qa, sqa):\n"
            "    p_b = stats.norm.cdf((q - qa) / (2 * sqa))\n"
            "    r = optimize.minimize_scalar(g, bounds=(-5.0, 20.0), method='bounded')\n"
            "    lines = txt.splitlines()\n"
            "    return p_sb / (1 - p_b)\n",
            encoding="utf-8",
        )
        codes5 = {x.code for x in lint_path(f5)}
        check(
            "catches two-line NORM_CDF_TAIL, HARDCODED_PY_MINOR_SITE, SPLITLINES_LINE_NUM, FIXED_BOUND_MINIMIZE",
            {"NORM_CDF_TAIL", "HARDCODED_PY_MINOR_SITE", "SPLITLINES_LINE_NUM", "FIXED_BOUND_MINIMIZE"}.issubset(codes5),
            str(codes5),
        )

        f6 = tmp / "good_stats.py"
        f6.write_text(
            "import site\nfrom scipy import stats\n"
            "def cls_tail(x, y):\n"
            "    return float(stats.norm.sf(x) / stats.norm.sf(-y))\n",
            encoding="utf-8",
        )
        res6 = lint_path(f6)
        check("clean script has 0 findings", len(res6) == 0, str(res6))

        f7 = tmp / "mentions_only.py"
        f7.write_text(
            "# never write 1 - norm.cdf(x); use norm.sf(x)\n"
            "BAD = \"q = 1 - norm.cdf(z)\"\n"
            "p = stats.norm.sf(z)\n"
            "cov = 2 * norm.cdf(x) - 1\n",
            encoding="utf-8",
        )
        res7 = lint_path(f7)
        check("comments, strings and 2*cdf - 1 are not tail findings", len(res7) == 0, str(res7))

        f8 = tmp / "other_dists.py"
        f8.write_text(
            "def g(q, z):\n"
            "    a = 1 - stats.chi2.cdf(q, 1)\n"
            "    b = 1.0 - norm(0, 1).cdf(z)\n"
            "    c = stats.poisson.cdf(3, 2.0)\n"
            "    d = 1 - c\n"
            "    c = 0.5\n"
            "    e = 1 - c\n"
            "    p = stats.norm.cdf(z)\n"
            "    p = 1 - p\n"
            "    return a, b, d, e, p\n",
            encoding="utf-8",
        )
        res8 = lint_path(f8)
        got8 = sorted((x.line, x.code) for x in res8)
        want8 = [(2, "CDF_TAIL"), (3, "CDF_TAIL"), (5, "CDF_TAIL"), (9, "NORM_CDF_TAIL")]
        check("catches 1 - cdf for any distribution, follows a temporary, stops after reassignment", got8 == want8, str(got8))

        f9 = tmp / "in_class.py"
        f9.write_text("class K:\n    def m(self, z):\n        return 1 - stats.norm.cdf(z)\n", encoding="utf-8")
        res9 = lint_path(f9)
        check("one finding per occurrence inside a class method", len(res9) == 1, str(res9))

        tgt = tmp / "edit_me.py"
        tgt.write_text("def f(x):\n    return 1 - norm.cdf(x)  # two sided\n", encoding="utf-8")

        def hook(tool, **tin):
            return hook_decide({"tool_name": tool, "tool_input": tin})

        r_new = hook("Write", file_path=str(tmp / "new.py"), content="p = 1 - stats.norm.cdf(z)\n")
        r_touch = hook("Edit", file_path=str(tgt), old_string="# two sided", new_string="# one-sided")
        r_add = hook("Edit", file_path=str(tgt), old_string="def f(x):",
                     new_string="def g(q):\n    return 1 - chi2.cdf(q, 1)\n\n\ndef f(x):")
        r_multi = hook("MultiEdit", file_path=str(tgt), edits=[
            {"old_string": "# two sided", "new_string": "# upper"},
            {"old_string": "def f(x):", "new_string": "SITE = '.local/lib/python3.14/site-packages'\n\n\ndef f(x):"},
        ])
        r_allow = hook("Write", file_path=str(tmp / "t.py"),
                       content="p = 1 - dist.cdf(z)  # handover-lint: allow (this class has no sf)\n")
        r_comment = hook("Write", file_path=str(tmp / "c.py"), content="# never write 1 - norm.cdf(x)\nX = '1 - ndtr(z)'\n")
        r_md = hook("Write", file_path=str(tmp / "n.md"), content="p = 1 - stats.norm.cdf(z)\n")
        r_fix = hook("Edit", file_path=str(tgt), old_string="1 - norm.cdf(x)", new_string="norm.sf(x)")
        check(
            "hook: a new tail bug is refused; touching an old line, the allow marker, comments, non-.py and a fix pass",
            bool(r_new) and bool(r_add) and bool(r_multi)
            and not (r_touch or r_allow or r_comment or r_md or r_fix),
            repr([bool(x) for x in (r_new, r_touch, r_add, r_multi, r_allow, r_comment, r_md, r_fix)]),
        )

        f10 = tmp / "unpacking.py"
        f10.write_text(
            "def cls_tail(sq, sqa):\n"
            "    p_sb, p_b = stats.norm.sf(sq), stats.norm.cdf(sq - sqa)\n"
            "    return float(p_sb / (1 - p_b)) if p_b < 1 else 0.0\n"
            "def swap_test(z):\n"
            "    a = stats.norm.cdf(z)\n"
            "    a, b = 0.0, a\n"
            "    return 1 - a, 1 - b\n",
            encoding="utf-8",
        )
        got10 = sorted((x.line, x.code) for x in lint_path(f10))
        check(
            "tuple unpacking and swaps preserve cdf taint accurately",
            got10 == [(3, "NORM_CDF_TAIL"), (7, "NORM_CDF_TAIL")],
            str(got10),
        )

        f11 = tmp / "branches.py"
        f11.write_text(
            "def sibling_if(cond, z):\n"
            "    if cond:\n"
            "        p_b = stats.norm.cdf(z)\n"
            "    else:\n"
            "        p_b = 0.0\n"
            "    return 1 - p_b\n"
            "def try_branch(z):\n"
            "    try:\n"
            "        p = stats.norm.cdf(z)\n"
            "    except ValueError:\n"
            "        p = 0.0\n"
            "    return 1 - p\n"
            "def cleared_both(cond, z):\n"
            "    p = stats.norm.cdf(z)\n"
            "    if cond:\n"
            "        p = 0.1\n"
            "    else:\n"
            "        p = 0.2\n"
            "    return 1 - p\n",
            encoding="utf-8",
        )
        got11 = sorted((x.line, x.code) for x in lint_path(f11))
        check(
            "sibling if/else and try/except preserve branch taint; both-branch overwrite clears it",
            got11 == [(6, "NORM_CDF_TAIL"), (12, "NORM_CDF_TAIL")],
            str(got11),
        )

        f12 = tmp / "comments_docstrings.py"
        f12.write_text(
            '"""Never use ~/.local/lib/python3.14/site-packages or txt.splitlines()."""\n'
            "# Nor in a comment: ~/.local/lib/python3.14/site-packages or txt.splitlines()\n"
            "def helper(home):\n"
            '    """Docstring: .local/lib/python3.14/site-packages."""\n'
            '    msg = "txt.splitlines()"\n'
            "    p1 = '.local/lib/python3.14/site-packages'\n"
            "    p2 = f'{home}/.local/lib/python3.14/site-packages'\n"
            "    return p1, p2\n",
            encoding="utf-8",
        )
        got12 = sorted((x.line, x.code) for x in lint_path(f12))
        check(
            "comments and docstrings are ignored while string/f-string path literals in code are flagged",
            got12 == [(6, "HARDCODED_PY_MINOR_SITE"), (7, "HARDCODED_PY_MINOR_SITE")],
            str(got12),
        )

        swap_tgt = tmp / "swap_funcs.py"
        swap_tgt.write_text(
            "def func_a(x):\n"
            "    return 1 - stats.norm.cdf(x)\n"
            "\n"
            "def func_b(z):\n"
            "    return stats.norm.sf(z)\n",
            encoding="utf-8",
        )
        r_swap_multi = hook("MultiEdit", file_path=str(swap_tgt), edits=[
            {"old_string": "1 - stats.norm.cdf(x)", "new_string": "stats.norm.sf(x)"},
            {"old_string": "stats.norm.sf(z)", "new_string": "1 - stats.norm.cdf(z)"},
        ])
        r_swap_write = hook(
            "Write",
            file_path=str(swap_tgt),
            content="def func_a(x):\n    return stats.norm.sf(x)\n\ndef func_b(z):\n    return 1 - stats.norm.cdf(z)\n",
        )

        taint_tgt = tmp / "taint_unchanged.py"
        taint_tgt.write_text(
            "def h(z):\n"
            "    p = 0.0\n"
            "    # unrelated\n"
            "    return 1 - p\n",
            encoding="utf-8",
        )
        r_taint_earlier = hook("Edit", file_path=str(taint_tgt), old_string="p = 0.0", new_string="p = stats.norm.cdf(z)")
        r_site_comment = hook("Write", file_path=str(tmp / "sc.py"), content="# ~/.local/lib/python3.14/site-packages\n")
        r_site_doc = hook(
            "Write",
            file_path=str(tmp / "sd.py"),
            content='"""Never use ~/.local/lib/python3.14/site-packages."""\nimport site\n',
        )
        check(
            "hook: per-hunk swap and earlier-taint are refused; site comments/docstrings pass",
            bool(r_swap_multi) and bool(r_swap_write) and bool(r_taint_earlier)
            and not (r_site_comment or r_site_doc),
            repr([bool(x) for x in (r_swap_multi, r_swap_write, r_taint_earlier, r_site_comment, r_site_doc)]),
        )

        # Plan-file layout. The fixture lives in the temporary directory, which is scratch space to the rule,
        # so these calls set honor_scratch=False (plan_layout_findings always does).
        tree = tmp / "plantree"
        canonical = [
            "multi/PLAN.md", "multi/plan/PLAN_lane0.md", "multi/plan/PLAN_lane1.md",
            "multi/plan/lane0_subplan_A/A-0.md", "multi/plan/lane0_subplan_A/subplan_A-0/A-0-0.md",
            "multi/docs/planning-notes.md", "multi/module/PLAN.md",
            "single/plan/PLAN.md", "single/plan/subplan_A/A-0.md",
        ]
        not_canonical = [
            "multi/PLAN_v2.md", "multi/docs/test-plan.md", "multi/PLAN_lane2.md", "multi/tools/PLAN.md",
            "single/plan/PLAN_lane0.md", "both/PLAN.md", "both/plan/PLAN.md",
        ]
        for repo in ("multi", "multi/module", "single", "both"):
            (tree / repo / ".git").mkdir(parents=True)
        for rel in canonical + not_canonical:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            (tree / rel).write_text("# fixture\n", encoding="utf-8")
        n_md, n_named, layout = plan_layout_findings([str(tree)])
        got_layout = sorted(os.path.relpath(x.path, str(tree)) for x in layout)
        check(
            "plan layout: a second plan file, a nested plan root, both layouts and a stray lane file are found; "
            "the canonical tree and a submodule's own PLAN.md pass",
            # plan files by name: the 5 canonical ones (3 PLAN.md, 2 lane files) and all 7 that are not canonical
            got_layout == sorted(not_canonical) and n_md == len(canonical) + len(not_canonical) and n_named == 12,
            f"{got_layout} md={n_md} named={n_named}",
        )
        planned_ok = plan_layout_verdict(str(tree / "multi/plan/PLAN_lane7.md"), honor_scratch=False)
        planned_bad = plan_layout_verdict(str(tree / "multi/notes/sub-plan.md"), honor_scratch=False)
        in_tmp = plan_layout_verdict(str(tree / "multi/PLAN_v2.md"))
        in_agent_cfg = plan_layout_verdict(os.path.join(os.path.expanduser("~"), ".claude", "handover", "x-plan-v2.md"))
        not_md = plan_layout_verdict(str(tree / "multi/plan.txt"), honor_scratch=False)
        check(
            "plan layout: a planned path is judged before it exists; scratch space and non-Markdown files are left alone",
            planned_ok == "" and bool(planned_bad) and in_tmp == "" and in_agent_cfg == "" and not_md == "",
            repr([planned_ok, bool(planned_bad), in_tmp, in_agent_cfg, not_md]),
        )
        lint_bad = [x.code for x in lint_path(tree / "multi/PLAN_v2.md", honor_scratch=False)]
        lint_good = lint_path(tree / "multi/PLAN.md", honor_scratch=False)
        (tree / "multi/docs/waived-plan.md").write_text("<!-- handover-lint: allow -->\n", encoding="utf-8")
        lint_waived = [x.code for x in lint_path(tree / "multi/docs/waived-plan.md", honor_scratch=False)]
        check(
            "plan layout: the ordinary lint of a Markdown file reports it, and the allow marker does not waive it",
            lint_bad == ["PLAN_LAYOUT"] and lint_good == [] and lint_waived == ["PLAN_LAYOUT"],
            repr([lint_bad, lint_good, lint_waived]),
        )

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-flight linter for handovers, sub-plans, reports, and stats scripts.")
    ap.add_argument("--selftest", action="store_true", help="Run built-in unit tests and exit.")
    ap.add_argument("--strict", action="store_true", help="Treat warnings as non-zero exit.")
    ap.add_argument("--hook", action="store_true",
                    help="Read a Claude Code PreToolUse JSON on stdin; exit 10 with a reason if the edit adds a hygiene finding.")
    ap.add_argument("--plan-layout", action="store_true",
                    help="Check only the plan-file layout (The Project Planning Rule): every Markdown file under the "
                         "given directories, and the given file paths, existing or planned. Exit 0 if all canonical, 1 if not.")
    ap.add_argument("paths", nargs="*", help="Files or directories to check.")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.hook:
        return hook_main()
    if not args.paths:
        ap.error("provide at least one path or --selftest")

    if args.plan_layout:
        n_md, n_named, layout = plan_layout_findings(args.paths)
        for f in layout:
            print(f.format())
        print(f"Checked {n_md} markdown file(s): {n_named} plan file(s) by name, {len(layout)} not canonical")
        return 1 if layout else 0

    targets = [Path(p) for p in args.paths]
    all_findings: List[Finding] = []
    n_files = 0
    for fp in iter_targets(targets):
        n_files += 1
        all_findings.extend(lint_path(fp))

    for f in all_findings:
        print(f.format())

    n_err = sum(1 for f in all_findings if f.severity == "ERROR")
    n_warn = sum(1 for f in all_findings if f.severity == "WARN")
    print(f"Checked {n_files} file(s): {n_err} error(s), {n_warn} warning(s)")
    if n_err > 0 or (args.strict and n_warn > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
