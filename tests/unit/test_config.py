"""Unit tests for PipelineConfig and AblationMode."""

from pipeline.config import AblationMode, PipelineConfig


def test_ablation_modes_defined():
    modes = {m.value for m in AblationMode}
    assert modes == {
        "baseline", "retry_only", "compiler_only", "pyverilog_only", "hybrid",
    }


def test_pipeline_config_defaults():
    cfg = PipelineConfig()
    assert cfg.mode == AblationMode.HYBRID
    assert cfg.max_repair_iter == 3
    assert cfg.simulation_timeout_s == 30


def test_pipeline_config_override():
    cfg = PipelineConfig(mode=AblationMode.BASELINE, max_repair_iter=1)
    assert cfg.mode == AblationMode.BASELINE
    assert cfg.max_repair_iter == 1
