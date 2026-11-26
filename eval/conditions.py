"""Condition specifications for controlled, compute-matched benchmark comparisons.

Defines 4 primary systems + 4 component ablations on identical isolated
workspaces and identical executor models:
  - B0_bare          : Minimal coding agent, no gates, no review
  - B1_evibound      : Pre-exec schema approval + post-exec artifact existence check
  - B2_aris          : Cross-model advisory review loop (receives executor summary, non-blocking)
  - Ours_full        : Pre-registered claims (G1-G7) + trace_numbers + audit_code +
                       blocking path-only cross-model independent review
  - Ours_no_gates    : Ablation — path-only cross-model review, no mechanical gates
  - Ours_gates_only  : Ablation — mechanical gates (claims + trace + audit_code) only, no LLM review
  - Ours_ccr         : Ablation — same-model fresh session (CCR) instead of cross-model (XMR)
  - Ours_with_summary: Ablation — reviewer receives executor summary instead of pure paths
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ConditionSpec:
    name: str
    description: str
    pre_register: bool
    existence_gate_only: bool
    hard_mechanical_gates: bool
    reviewer_mode: str         # "none" | "advisory" | "blocking"
    reviewer_family: str       # "none" | "same" | "cross"
    pass_executor_summary: bool


CONDITIONS = {
    "B0_bare": ConditionSpec(
        name="B0_bare",
        description="Bare coding/ReAct executor with no gates and no independent reviewer",
        pre_register=False,
        existence_gate_only=False,
        hard_mechanical_gates=False,
        reviewer_mode="none",
        reviewer_family="none",
        pass_executor_summary=False,
    ),
    "B1_evibound": ConditionSpec(
        name="B1_evibound",
        description="EviBound-style dual existence gates (pre-exec schema + post-exec artifact existence)",
        pre_register=True,
        existence_gate_only=True,
        hard_mechanical_gates=False,
        reviewer_mode="none",
        reviewer_family="none",
        pass_executor_summary=False,
    ),
    "B2_aris": ConditionSpec(
        name="B2_aris",
        description="ARIS-style cross-model advisory review loop (passes executor summary, non-blocking)",
        pre_register=False,
        existence_gate_only=False,
        hard_mechanical_gates=False,
        reviewer_mode="advisory",
        reviewer_family="cross",
        pass_executor_summary=True,
    ),
    "Ours_full": ConditionSpec(
        name="Ours_full",
        description="Full research-loop: pre-registered claims + hard G1-G7/trace/AST gates + path-only cross-model audit",
        pre_register=True,
        existence_gate_only=False,
        hard_mechanical_gates=True,
        reviewer_mode="blocking",
        reviewer_family="cross",
        pass_executor_summary=False,
    ),
    "Ours_no_gates": ConditionSpec(
        name="Ours_no_gates",
        description="Ablation: path-only cross-model blocking audit without mechanical gates",
        pre_register=False,
        existence_gate_only=False,
        hard_mechanical_gates=False,
        reviewer_mode="blocking",
        reviewer_family="cross",
        pass_executor_summary=False,
    ),
    "Ours_gates_only": ConditionSpec(
        name="Ours_gates_only",
        description="Ablation: mechanical gates (claims + trace_numbers + audit_code) only, 0 LLM reviewer calls",
        pre_register=True,
        existence_gate_only=False,
        hard_mechanical_gates=True,
        reviewer_mode="none",
        reviewer_family="none",
        pass_executor_summary=False,
    ),
    "Ours_ccr": ConditionSpec(
        name="Ours_ccr",
        description="Ablation: full hard gates + same-model fresh-session (CCR) path-only audit",
        pre_register=True,
        existence_gate_only=False,
        hard_mechanical_gates=True,
        reviewer_mode="blocking",
        reviewer_family="same",
        pass_executor_summary=False,
    ),
    "Ours_with_summary": ConditionSpec(
        name="Ours_with_summary",
        description="Ablation: full hard gates + cross-model audit handed executor summary (tests framing bias)",
        pre_register=True,
        existence_gate_only=False,
        hard_mechanical_gates=True,
        reviewer_mode="blocking",
        reviewer_family="cross",
        pass_executor_summary=True,
    ),
}

PRIMARY_FOUR = ["B0_bare", "B1_evibound", "B2_aris", "Ours_full"]
ALL_CONDITIONS = list(CONDITIONS.keys())
