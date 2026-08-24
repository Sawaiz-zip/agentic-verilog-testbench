import os
from enum import Enum
from dataclasses import dataclass, field


class AblationMode(str, Enum):
    BASELINE = "baseline"          # no repair loop
    # Control arm: one extra generation with NO diagnostic information.
    # Every repairing mode gets a second sample from the LLM that BASELINE never
    # gets, so a gain over BASELINE could come from the extra sample rather than
    # from the feedback. RETRY_ONLY isolates that: same extra sample, zero
    # diagnostics. Any mode must beat RETRY_ONLY to claim its feedback works.
    RETRY_ONLY = "retry_only"
    COMPILER_ONLY = "compiler_only"  # repair on iverilog errors only
    PYVERILOG_ONLY = "pyverilog_only"  # repair on static analysis errors only
    HYBRID = "hybrid"              # both sources trigger repair


@dataclass
class PipelineConfig:
    mode: AblationMode = AblationMode.HYBRID
    max_repair_iter: int = 3
    simulation_timeout_s: int = 30
    num_mutants: int = 5           # for Eval2
    results_dir: str = "results"
    prompts_dir: str = "prompts"
    # Sampling temperature (Constitution IV, amended v1.1.0): configurable,
    # default 0.7, overridable via LLM_TEMPERATURE env. Not forced to 0.
    default_temperature: float = field(
        default_factory=lambda: float(os.environ.get("LLM_TEMPERATURE", "0.7"))
    )
    # Models
    model_cheap: str = "claude-haiku-4-5-20251001"   # classify, scenarios, mutants
    model_strong: str = "claude-sonnet-4-6"          # spec, driver, checker, repair, reasoning
