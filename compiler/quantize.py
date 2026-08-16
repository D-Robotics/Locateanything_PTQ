#!/usr/bin/env python3
"""Orchestrate LocateAnything preparation, calibration, and build stages.

The numerical calibration, BC export, HBDK compilation, and model algorithms
live in ``compiler/pipeline`` and ``compiler/model``.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPILER_ROOT = PROJECT_ROOT / "compiler"
PIPELINE_ROOT = COMPILER_ROOT / "pipeline"
DEFAULT_CONFIG = COMPILER_ROOT / "config" / "quantization.yaml"
BUILD_ADAPTER = COMPILER_ROOT / "build_adapter.py"
CONFIG_DIR_KEY = "__config_dir__"
COMPONENTS = ("vision", "language", "all")
BUILD_TARGETS = ("bc", "hbm")
if str(COMPILER_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPILER_ROOT))

from configuration import ConfigurationFileError, load_config_file  # noqa: E402
from model.graphs import LANGUAGE_GRAPHS  # noqa: E402
from pipeline.progress import (  # noqa: E402
    PROGRESS_MODES,
    format_status_line,
    print_console_line,
)
from model.contract import (  # noqa: E402
    HIDDEN_SIZE,
    IMAGE_TOKEN_ID,
    PATCH_SIZE,
    PBD_QUERY_LEN,
    SPATIAL_MERGE,
    derive_vision_profile,
)
CONVERGENCE_CHECKPOINTS = (64, 128, 256, 512)


class ConfigurationError(ValueError):
    """Raised when a build config violates the fixed LocateAnything specification."""


@dataclass(frozen=True)
class PlanStep:
    label: str
    command: tuple[str, ...]
    cwd: Path = PROJECT_ROOT
    env: Mapping[str, str] = field(default_factory=dict)
    note: str | None = None


def _mapping(value: Any, name: str) -> dict[str, Any]:
    """
    Function:
        Require a configuration value to be a mapping.

    Args:
        value: Parsed configuration value.
        name: Field name used in the error message.

    Returns:
        The mapping value.
    """
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be a mapping")
    return value


def load_config(path: Path) -> dict[str, Any]:
    """
    Function:
        Load and validate the complete compiler configuration.

    Args:
        path: YAML configuration path.

    Returns:
        Validated configuration with its directory recorded internally.
    """
    path = path.resolve()
    try:
        config = load_config_file(path)
    except ConfigurationFileError as exc:
        raise ConfigurationError(str(exc)) from exc
    validate_config(config)
    config[CONFIG_DIR_KEY] = path.parent
    return config


def _positive_int(value: Any, name: str) -> int:
    """
    Function:
        Validate a positive integer configuration field.

    Args:
        value: Candidate value.
        name: Field name used in the error message.

    Returns:
        The validated integer.
    """
    if type(value) is not int or value <= 0:
        raise ConfigurationError(f"{name} must be a positive integer")
    return value


def validate_config(config: Mapping[str, Any]) -> None:
    """
    Function:
        Validate the fixed LocateAnything compiler configuration schema.

    Args:
        config: Parsed configuration mapping.

    Returns:
        None.
    """
    required_sections = {
        "paths", "outputs", "calibration", "vision", "language", "quantization", "build",
    }
    optional_sections = {"runtime"}
    missing_sections = sorted(required_sections - config.keys())
    extra_sections = sorted(set(config) - required_sections - optional_sections)
    if missing_sections:
        raise ConfigurationError(f"config is missing: {', '.join(missing_sections)}")
    if extra_sections:
        raise ConfigurationError(f"config contains unknown sections: {', '.join(extra_sections)}")

    paths = _mapping(config.get("paths"), "paths")
    required_paths = {
        "checkpoint", "calibration_data", "output_dir",
    }
    missing_paths = sorted(required_paths - set(paths))
    if missing_paths:
        raise ConfigurationError(f"paths is missing: {', '.join(missing_paths)}")
    extra_paths = sorted(set(paths) - required_paths)
    if extra_paths:
        raise ConfigurationError(f"paths contains unknown fields: {', '.join(extra_paths)}")

    outputs = _mapping(config.get("outputs"), "outputs")
    required_outputs = {"vision_hbm", "language_hbm", "embedding_bin"}
    if set(outputs) != required_outputs:
        missing = sorted(required_outputs - set(outputs))
        extra = sorted(set(outputs) - required_outputs)
        details = [*(f"missing {name}" for name in missing), *(f"unknown {name}" for name in extra)]
        raise ConfigurationError("invalid outputs fields: " + ", ".join(details))
    for name, suffix in (
        ("vision_hbm", ".hbm"),
        ("language_hbm", ".hbm"),
        ("embedding_bin", ".bin"),
    ):
        value = outputs.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"outputs.{name} must be a non-empty filename")
        filename = Path(value)
        if filename.name != value or filename.is_absolute() or value in {".", ".."}:
            raise ConfigurationError(f"outputs.{name} must be a filename, not a path")
        if filename.suffix.lower() != suffix:
            raise ConfigurationError(f"outputs.{name} must end with {suffix}")

    calibration = _mapping(config.get("calibration"), "calibration")
    required_calibration = {
        "slow_samples", "max_new_tokens", "seed", "prepare_dtype", "statistics_dtype",
        "detailed_statistics",
    }
    if set(calibration) != required_calibration:
        missing = sorted(required_calibration - set(calibration))
        extra = sorted(set(calibration) - required_calibration)
        details = [*(f"missing {name}" for name in missing), *(f"unknown {name}" for name in extra)]
        raise ConfigurationError("invalid calibration fields: " + ", ".join(details))
    _positive_int(calibration.get("slow_samples"), "calibration.slow_samples")
    _positive_int(calibration.get("max_new_tokens"), "calibration.max_new_tokens")
    if type(calibration.get("seed")) is not int:
        raise ConfigurationError("calibration.seed must be an integer")
    if calibration.get("prepare_dtype") not in {"bfloat16", "float16"}:
        raise ConfigurationError("calibration.prepare_dtype must be bfloat16 or float16")
    if calibration.get("statistics_dtype") not in {"float16", "bfloat16"}:
        raise ConfigurationError("calibration.statistics_dtype must be float16 or bfloat16")
    if type(calibration.get("detailed_statistics")) is not bool:
        raise ConfigurationError("calibration.detailed_statistics must be true or false")

    vision = _mapping(config.get("vision"), "vision")
    required_vision = {
        "image_width", "image_height", "resize_mode", "letterbox_fill",
    }
    if set(vision) != required_vision:
        missing = sorted(required_vision - set(vision))
        extra = sorted(set(vision) - required_vision)
        details = [*(f"missing {name}" for name in missing), *(f"unknown {name}" for name in extra)]
        raise ConfigurationError("invalid vision fields: " + ", ".join(details))
    try:
        vision_profile = derive_vision_profile(
            vision.get("image_width"),
            vision.get("image_height"),
            resize_mode=vision.get("resize_mode"),
            letterbox_fill=vision.get("letterbox_fill"),
        )
    except ValueError as exc:
        raise ConfigurationError(f"invalid vision profile: {exc}") from exc

    language = _mapping(config.get("language"), "language")
    required_language = {"chunk_size", "cache_len"}
    boolean_language = {"compact_logits", "fuse_initial_pbd"}
    optional_language = {*boolean_language, "batch_size"}
    if (
        not required_language <= set(language)
        or set(language) - required_language - optional_language
    ):
        missing = sorted(required_language - set(language))
        extra = sorted(set(language) - required_language - optional_language)
        details = [*(f"missing {name}" for name in missing), *(f"unknown {name}" for name in extra)]
        raise ConfigurationError("invalid language fields: " + ", ".join(details))
    chunk_size = _positive_int(language.get("chunk_size"), "language.chunk_size")
    cache_len = _positive_int(language.get("cache_len"), "language.cache_len")
    for name in sorted(boolean_language):
        if name in language and type(language[name]) is not bool:
            raise ConfigurationError(f"language.{name} must be true or false")
    batch_size = _positive_int(language.get("batch_size", 1), "language.batch_size")
    if batch_size not in {1, 2}:
        raise ConfigurationError("language.batch_size must be 1 or 2")
    if not 128 <= chunk_size <= 2048 or not 256 <= cache_len <= 4096:
        raise ConfigurationError(
            "language.chunk_size must be in [128, 2048] and cache_len in [256, 4096]"
        )
    if chunk_size % 64 or cache_len % 64 or cache_len <= chunk_size:
        raise ConfigurationError(
            "language.chunk_size and language.cache_len must be multiples of 64, "
            "with cache_len greater than chunk_size"
        )
    if vision_profile["visual_token_count"] >= chunk_size:
        raise ConfigurationError(
            f"vision produces {vision_profile['visual_token_count']} visual tokens, "
            f"leaving no text capacity in language.chunk_size={chunk_size}"
        )

    runtime = config.get("runtime")
    if runtime is not None:
        runtime = _mapping(runtime, "runtime")
        if set(runtime) != {"max_new_tokens"}:
            missing = sorted({"max_new_tokens"} - set(runtime))
            extra = sorted(set(runtime) - {"max_new_tokens"})
            details = [*(f"missing {name}" for name in missing), *(f"unknown {name}" for name in extra)]
            raise ConfigurationError("invalid runtime fields: " + ", ".join(details))
        runtime_max_new_tokens = _positive_int(
            runtime.get("max_new_tokens"), "runtime.max_new_tokens"
        )
        if chunk_size + runtime_max_new_tokens > cache_len:
            raise ConfigurationError(
                "language.chunk_size + runtime.max_new_tokens must not exceed "
                f"language.cache_len ({chunk_size} + {runtime_max_new_tokens} > {cache_len})"
            )
    quantization = _mapping(config.get("quantization"), "quantization")
    required_quantization = {
        "vision_weight_bits", "language_weight_bits", "lm_head_weight_bits"
    }
    if set(quantization) != required_quantization:
        missing = sorted(required_quantization - set(quantization))
        extra = sorted(set(quantization) - required_quantization)
        details = [*(f"missing {name}" for name in missing), *(f"unknown {name}" for name in extra)]
        raise ConfigurationError("invalid quantization fields: " + ", ".join(details))
    if quantization.get("vision_weight_bits") not in {8}:
        raise ConfigurationError("quantization.vision_weight_bits currently supports 8")
    for name in ("language_weight_bits", "lm_head_weight_bits"):
        if quantization.get(name) not in {4, 8}:
            raise ConfigurationError(f"quantization.{name} must be 4 or 8")

    build = _mapping(config.get("build"), "build")
    required_build = {"march", "device", "jobs", "cores"}
    if set(build) != required_build:
        missing = sorted(required_build - set(build))
        extra = sorted(set(build) - required_build)
        details = [*(f"missing {name}" for name in missing), *(f"unknown {name}" for name in extra)]
        raise ConfigurationError("invalid build fields: " + ", ".join(details))
    if not str(build.get("device") or "").strip():
        raise ConfigurationError("build.device must not be empty")
    if not str(build.get("march") or "").strip():
        raise ConfigurationError("build.march must not be empty")
    _positive_int(build.get("jobs"), "build.jobs")
    cores = _mapping(build.get("cores"), "build.cores")
    for name in ("vision", "prefill", "pbd", "ar"):
        if cores.get(name) not in {1, 2, 4}:
            raise ConfigurationError(f"build.cores.{name} must be 1, 2, or 4")

def _resolve_config_path(config_dir: Path, raw: Any) -> Path:
    """
    Function:
        Resolve a config-relative or explicitly absolute path.

    Args:
        config_dir: Directory containing the configuration file.
        raw: Raw path value from YAML.

    Returns:
        Resolved filesystem path.
    """
    expanded = Path(os.path.expanduser(str(raw)))
    if expanded.is_absolute():
        return expanded.resolve()
    return (config_dir / expanded).resolve()


def resolve_path(config: Mapping[str, Any], key: str) -> Path:
    """
    Function:
        Resolve one named project path derived from the configuration.

    Args:
        config: Validated configuration mapping.
        key: Internal resolved-path key.

    Returns:
        Resolved path for the requested artifact.
    """
    config_dir = Path(config[CONFIG_DIR_KEY])
    paths = _mapping(config["paths"], "paths")
    checkpoint = _resolve_config_path(config_dir, paths["checkpoint"])
    calibration_data = _resolve_config_path(config_dir, paths["calibration_data"])
    output_dir = _resolve_config_path(config_dir, paths["output_dir"])
    resolved = {
        "model": checkpoint,
        "selected_jsonl": calibration_data / "selected.jsonl",
        "generated_dir": output_dir / "calibration" / "generated",
        "generated_jsonl": output_dir / "calibration" / "generated" / "generated.jsonl",
        "calibration_dir": output_dir / "calibration" / "statistics",
        "scale_manifest": output_dir / "calibration" / "statistics" / "calibration_scale_manifest.json",
        "coverage_json": output_dir / "calibration" / "statistics" / "calibration_graph_coverage.json",
        "build_root": output_dir / "build",
        "log_root": output_dir / "logs",
    }
    return resolved[key].resolve()


def jsonl_record_count(path: Path) -> int:
    """
    Function:
        Count non-empty records in a JSONL calibration manifest.

    Args:
        path: JSONL manifest path.

    Returns:
        Number of non-empty records.
    """
    try:
        count = sum(
            bool(line.strip())
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    except OSError as exc:
        raise ConfigurationError(f"cannot read calibration data {path}: {exc}") from exc
    if count == 0:
        raise ConfigurationError(f"calibration data is empty: {path}")
    return count


def calibration_sample_count(
    config: Mapping[str, Any], manifest: Path, override: int | None = None
) -> int:
    """
    Function:
        Resolve the requested calibration sample count.

    Args:
        config: Validated compiler configuration.
        manifest: Generated calibration JSONL path.
        override: Optional command-line sample limit.

    Returns:
        Positive sample count.
    """
    if override is not None:
        return _positive_int(override, "--max-samples")
    del config
    return jsonl_record_count(manifest)


def calibration_checkpoint(
    config: Mapping[str, Any], sample_count: int, override: int | None = None
) -> int:
    """
    Function:
        Select a convergence checkpoint below the sample count.

    Args:
        config: Validated compiler configuration.
        sample_count: Number of calibration samples.
        override: Optional explicit checkpoint.

    Returns:
        Checkpoint sample count.
    """
    del config
    configured = _positive_int(override, "--checkpoint-samples") if override is not None else None
    if sample_count < 2:
        raise ConfigurationError("activation calibration requires at least two samples")
    if configured is None:
        eligible = [value for value in CONVERGENCE_CHECKPOINTS if value < sample_count]
        configured = max(eligible, default=max(1, sample_count // 2))
    if configured >= sample_count:
        raise ConfigurationError("checkpoint samples must be smaller than sample count")
    return configured


def select_components(value: str) -> tuple[str, ...]:
    """
    Function:
        Expand the public component selector into build components.

    Args:
        value: ``vision``, ``language`` or ``all``.

    Returns:
        Tuple of requested component names.
    """
    return ("vision", "language") if value == "all" else (value,)


def python_command(config: Mapping[str, Any]) -> str:
    """
    Function:
        Select the Python interpreter running the orchestrator.

    Args:
        config: Validated compiler configuration (unused).

    Returns:
        Current interpreter path.
    """
    del config
    return sys.executable


def bash_command() -> str:
    """
    Function:
        Locate Bash used by the portable pipeline wrappers.

    Args:
        None.

    Returns:
        Bash executable name or path.
    """
    return shutil.which("bash") or "bash"


def common_env(config: Mapping[str, Any], progress: str) -> dict[str, str]:
    """
    Function:
        Build shared environment values for one pipeline step.

    Args:
        config: Validated compiler configuration.
        progress: Console progress mode.

    Returns:
        Environment overrides for the child script.
    """
    env = {
        "REPO_ROOT": str(PROJECT_ROOT),
        "PYTHON_BIN": python_command(config),
        "PYTHONUNBUFFERED": "1",
        "LA_PROGRESS": progress,
    }
    if progress == "bar":
        env["TQDM_DISABLE"] = "0"
    elif progress in {"log", "off"}:
        env["TQDM_DISABLE"] = "1"
    return env


def configured_vision_profile(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return tensor shapes derived from the YAML Vision canvas."""

    vision = _mapping(config["vision"], "vision")
    return derive_vision_profile(
        vision["image_width"],
        vision["image_height"],
        resize_mode=vision["resize_mode"],
        letterbox_fill=vision["letterbox_fill"],
    )


def prepare_plan(args: argparse.Namespace, config: Mapping[str, Any]) -> list[PlanStep]:
    """
    Function:
        Create the calibration-input preparation step.

    Args:
        args: Parsed prepare arguments.
        config: Validated compiler configuration.

    Returns:
        One planned preparation step.
    """
    calibration = _mapping(config["calibration"], "calibration")
    language = _mapping(config["language"], "language")
    build = _mapping(config["build"], "build")
    vision = configured_vision_profile(config)
    selected = resolve_path(config, "selected_jsonl")
    output_dir = resolve_path(config, "generated_dir")
    log_root = resolve_path(config, "log_root")
    env = common_env(config, args.progress)
    env.update({
        "SELECTED_JSONL": str(selected),
        "OUTPUT_DIR": str(output_dir),
        "MODEL_PATH": str(resolve_path(config, "model")),
        "DEVICE": str(build["device"]),
        "DTYPE": str(calibration["prepare_dtype"]),
        "IMAGE_WIDTH": str(vision["image_width"]),
        "IMAGE_HEIGHT": str(vision["image_height"]),
        "RESIZE_MODE": str(vision["resize_mode"]),
        "LETTERBOX_FILL": str(vision["letterbox_fill"]),
        "PATCH_SIZE": str(PATCH_SIZE),
        "MERGE_SIZE": str(SPATIAL_MERGE),
        "HIDDEN_SIZE": str(HIDDEN_SIZE),
        "PREFILL_LIMIT": str(language["chunk_size"]),
        "MAX_NEW_TOKENS": str(calibration["max_new_tokens"]),
        "SLOW_SAMPLES": str(calibration["slow_samples"]),
        "SEED": str(calibration["seed"]),
        "LOG_PATH": str(log_root / "prepare.log"),
        "EXIT_PATH": str(log_root / "prepare.exit.txt"),
        "PID_PATH": str(log_root / "prepare.pid"),
        "LAUNCH_LOG": str(log_root / "prepare.launcher.log"),
        "RESUME": "1" if args.resume else "0",
    })
    command = (bash_command(), str(PIPELINE_ROOT / "run_prepare.sh"))
    return [PlanStep("prepare calibration tensors", command, env=env)]


def calibrate_plan(args: argparse.Namespace, config: Mapping[str, Any]) -> list[PlanStep]:
    """
    Function:
        Create the activation calibration step.

    Args:
        args: Parsed calibration arguments.
        config: Validated compiler configuration.

    Returns:
        One planned calibration step.
    """
    calibration = _mapping(config["calibration"], "calibration")
    language = _mapping(config["language"], "language")
    quantization = _mapping(config["quantization"], "quantization")
    build = _mapping(config["build"], "build")
    vision = configured_vision_profile(config)
    generated_jsonl = resolve_path(config, "generated_jsonl")
    requested_samples = calibration_sample_count(config, generated_jsonl, args.max_samples)
    requested_checkpoint = calibration_checkpoint(
        config, requested_samples, args.checkpoint_samples
    )
    log_root = resolve_path(config, "log_root")
    env = common_env(config, args.progress)
    env.update({
        "GENERATED_JSONL": str(generated_jsonl),
        "SELECTED_JSONL": str(resolve_path(config, "selected_jsonl")),
        "MODEL_PATH": str(resolve_path(config, "model")),
        "OUTPUT_DIR": str(resolve_path(config, "calibration_dir")),
        "DEVICE": str(build["device"]),
        "DTYPE": str(calibration["statistics_dtype"]),
        "CALIBRATION_COMPONENT": "all" if args.component == "all" else args.component,
        "CHUNK_SIZE": str(language["chunk_size"]),
        "CACHE_LEN": str(language["cache_len"]),
        "IMAGE_WIDTH": str(vision["image_width"]),
        "IMAGE_HEIGHT": str(vision["image_height"]),
        "RESIZE_MODE": str(vision["resize_mode"]),
        "LETTERBOX_FILL": str(vision["letterbox_fill"]),
        "VISION_W_BITS": str(quantization["vision_weight_bits"]),
        "LANGUAGE_W_BITS": str(quantization["language_weight_bits"]),
        "LM_HEAD_W_BITS": str(quantization["lm_head_weight_bits"]),
        "COMPACT_LOGITS": "1" if language.get("compact_logits", False) else "0",
        "FUSE_INITIAL_PBD": "1" if language.get("fuse_initial_pbd", False) else "0",
        "DETAILED_STATISTICS": "1" if calibration["detailed_statistics"] else "0",
        "MAX_SAMPLES": str(requested_samples),
        "CHECKPOINT_SAMPLES": str(requested_checkpoint),
        "IMAGE_TOKEN_ID": str(IMAGE_TOKEN_ID),
        "REPLAY_SEED": str(calibration["seed"]),
        "LOG_PATH": str(log_root / "calibrate.log"),
        "EXIT_PATH": str(log_root / "calibrate.exit.txt"),
        "META_PATH": str(log_root / "calibrate.metadata.json"),
        "PID_PATH": str(log_root / "calibrate.pid"),
        "LAUNCH_LOG": str(log_root / "calibrate.launcher.log"),
        "RESUME": "1" if args.resume else "0",
    })
    note = None
    if args.resume:
        note = "calibration replay is atomic; only completed statistics are reused"
    command = (bash_command(), str(PIPELINE_ROOT / "run_calibrate.sh"))
    return [PlanStep("collect activation statistics", command, env=env, note=note)]


def build_plan(args: argparse.Namespace, config: Mapping[str, Any]) -> list[PlanStep]:
    """
    Function:
        Create Vision and/or Language BC/HBM build steps.

    Args:
        args: Parsed build arguments.
        config: Validated compiler configuration.

    Returns:
        Ordered build steps for the requested components.
    """
    build = _mapping(config["build"], "build")
    language = _mapping(config["language"], "language")
    quantization = _mapping(config["quantization"], "quantization")
    outputs = _mapping(config["outputs"], "outputs")
    vision = configured_vision_profile(config)
    cores = _mapping(build["cores"], "build.cores")
    build_root = resolve_path(config, "build_root")
    log_root = resolve_path(config, "log_root")
    build_in_use = build_root.is_dir() and any(build_root.rglob("*"))
    if not args.resume and not args.dry_run and build_in_use:
        entries = sorted(
            path.relative_to(build_root).as_posix()
            for path in build_root.rglob("*")
            if path.is_file()
        )
        preview = ", ".join(entries[:6]) or "existing directories"
        suffix = " ..." if len(entries) > 6 else ""
        raise ConfigurationError(
            "build output directory is already in use: "
            f"{build_root} ({preview}{suffix}). "
            "Use --resume to continue it, or change paths.output_dir to a new "
            "last-level directory."
        )
    bash = bash_command()
    steps: list[PlanStep] = []
    for component in select_components(args.component):
        output = build_root / component
        env = common_env(config, args.progress)
        env.update({
            "INPUT_MODEL_PATH": str(resolve_path(config, "model")),
            "OUTPUT_MODEL_PATH": str(output),
            "VISION_HBM_NAME": str(outputs["vision_hbm"]),
            "LANGUAGE_HBM_NAME": str(outputs["language_hbm"]),
            "EMBEDDING_NAME": str(outputs["embedding_bin"]),
            "CALIBRATION_SCALE_MANIFEST": str(resolve_path(config, "scale_manifest")),
            "DEVICE": str(build["device"]),
            "MARCH": str(build["march"]),
            "JOBS": str(build["jobs"]),
            "CHUNK_SIZE": str(language["chunk_size"]),
            "CACHE_LEN": str(language["cache_len"]),
            "BATCH_SIZE": str(language.get("batch_size", 1)),
            "DECODE_SEQ_LEN": str(PBD_QUERY_LEN),
            "LM_HEAD_W_BITS": str(quantization["lm_head_weight_bits"]),
            "EXPORT_ONLY": "1" if args.target == "bc" else "0",
            "RESUME": "1" if args.resume else "0",
            "BUILD_TARGET": args.target,
            "WAIT": "1",
            "DETACH": "0",
            "LOG_DIR": str(log_root),
            "LOG_FILE": str(log_root / f"build_{component}_{args.target}.log"),
            "BUILD_ADAPTER": str(BUILD_ADAPTER),
        })
        if component == "vision":
            env.update({
                "W_BITS": str(quantization["vision_weight_bits"]),
                "VIT_CORE_NUM": str(cores["vision"]),
                "IMAGE_WIDTH": str(vision["image_width"]),
                "IMAGE_HEIGHT": str(vision["image_height"]),
                "RESIZE_MODE": str(vision["resize_mode"]),
                "LETTERBOX_FILL": str(vision["letterbox_fill"]),
            })
            script = PIPELINE_ROOT / "build_vision.sh"
        else:
            env.update({
                "W_BITS": str(quantization["language_weight_bits"]),
                "PREFILL_CORE_NUM": str(cores["prefill"]),
                "DECODE_CORE_NUM": str(cores["pbd"]),
                "AR_CORE_NUM": str(cores["ar"]),
                "COMPACT_LOGITS": "1" if language.get("compact_logits", False) else "0",
                "FUSE_INITIAL_PBD": "1" if language.get("fuse_initial_pbd", False) else "0",
            })
            script = PIPELINE_ROOT / "build_language.sh"
        steps.append(
            PlanStep(
                f"{component.capitalize()} -> {args.target.upper()}",
                (bash, str(script)),
                env=env,
            )
        )
    return steps


def quote_command(command: Iterable[str]) -> str:
    """
    Function:
        Render a command sequence safely for terminal display.

    Args:
        command: Command arguments.

    Returns:
        Shell-escaped command string.
    """
    return shlex.join(str(part) for part in command)


def print_build_summary(config: Mapping[str, Any]) -> None:
    """
    Function:
        Print the compact stable compiler configuration summary.

    Args:
        config: Validated compiler configuration.

    Returns:
        None.
    """
    language = _mapping(config["language"], "language")
    quantization = _mapping(config["quantization"], "quantization")
    vision = configured_vision_profile(config)
    payload = {
        "image": f"{vision['image_width']}x{vision['image_height']}",
        "visual_tokens": vision["visual_token_count"],
        "vision_w_bits": quantization["vision_weight_bits"],
        "chunk_size": language["chunk_size"],
        "cache_len": language["cache_len"],
        "batch_size": language.get("batch_size", 1),
        "language_w_bits": quantization["language_weight_bits"],
        "lm_head_w_bits": quantization["lm_head_weight_bits"],
        "language_graph_count": len(LANGUAGE_GRAPHS),
        "sampling": "host",
        "compact_logits": language.get("compact_logits", False),
        "fuse_initial_pbd": language.get("fuse_initial_pbd", False),
    }
    details = "  ".join(f"{key}={value}" for key, value in payload.items())
    print_console_line(
        format_status_line(
            "build", None, None, "CONFIG", "Resolved configuration", details=details
        )
    )


def run_plan(steps: list[PlanStep], args: argparse.Namespace, config: Mapping[str, Any]) -> int:
    """
    Function:
        Execute the planned pipeline steps in order.

    Args:
        steps: Ordered pipeline steps.
        args: Parsed command-line options.
        config: Validated compiler configuration.

    Returns:
        Zero on success, otherwise the failed child exit status.
    """
    print_build_summary(config)
    if args.dry_run:
        for index, step in enumerate(steps, 1):
            print(f"[plan {index}/{len(steps)}] {step.label}")
            print(f"  cwd: {step.cwd}")
            if step.env:
                visible = " ".join(
                    f"{key}={value}" for key, value in sorted(step.env.items())
                )
                print(f"  env: {visible}")
            print(f"  command: {quote_command(step.command)}")
            if step.note:
                print(f"  note: {step.note}")
        print("[dry-run] no command executed")
        return 0

    run_started = time.monotonic()
    for index, step in enumerate(steps, 1):
        stage_started = time.monotonic()
        print_console_line(
            format_status_line(
                "BUILD", index, len(steps), "START", step.label
            )
        )
        if step.note:
            print(f"  {step.note}", flush=True)
        executable = step.command[0]
        if not Path(executable).is_file() and shutil.which(executable) is None:
            raise RuntimeError(f"required executable not found: {executable}")
        env = os.environ.copy()
        env.update(step.env)
        completed = subprocess.run(step.command, cwd=step.cwd, env=env, check=False)
        if completed.returncode:
            elapsed = time.monotonic() - stage_started
            print_console_line(
                format_status_line(
                    "BUILD",
                    index,
                    len(steps),
                    "FAILED",
                    step.label,
                    details=(
                        f"elapsed={elapsed:.1f}s exit={completed.returncode}"
                    ),
                )
            )
            return int(completed.returncode)
        elapsed = time.monotonic() - stage_started
        print_console_line(
            format_status_line(
                "BUILD",
                index,
                len(steps),
                "COMPLETE",
                step.label,
                details=f"elapsed={elapsed:.1f}s",
            )
        )
    print_console_line(
        format_status_line(
            "BUILD",
            None,
            None,
            "COMPLETE",
            "All requested components",
            details=f"elapsed={time.monotonic() - run_started:.1f}s",
        )
    )
    return 0


def add_common_options(parser: argparse.ArgumentParser) -> None:
    """
    Function:
        Add progress, resume and dry-run controls to a subparser.

    Args:
        parser: Target argparse subparser.

    Returns:
        None.
    """
    parser.add_argument("--progress", choices=PROGRESS_MODES, default="auto")
    parser.add_argument("--resume", action="store_true", help="reuse complete compatible outputs")
    parser.add_argument("--dry-run", action="store_true", help="print the resolved plan only")


def build_parser() -> argparse.ArgumentParser:
    """
    Function:
        Construct the public prepare/calibrate/build command parser.

    Args:
        None.

    Returns:
        Configured argparse parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "LocateAnything prepare -> calibrate -> build orchestrator"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="materialize Float calibration tensors")
    add_common_options(prepare)
    calibrate = subparsers.add_parser("calibrate", help="collect activation scales")
    add_common_options(calibrate)
    calibrate.add_argument("--component", choices=COMPONENTS, default="all")
    calibrate.add_argument("--max-samples", type=int)
    calibrate.add_argument("--checkpoint-samples", type=int)

    build = subparsers.add_parser("build", help="export BC or build through HBO/HBM")
    add_common_options(build)
    build.add_argument("--component", choices=COMPONENTS, default="all")
    build.add_argument("--target", choices=BUILD_TARGETS, default="hbm")

    return parser


def main(argv: list[str] | None = None) -> int:
    """
    Function:
        Dispatch one compiler pipeline command.

    Args:
        argv: Optional command-line argument list.

    Returns:
        Process exit status.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config.resolve())
        if args.command == "prepare":
            steps = prepare_plan(args, config)
        elif args.command == "calibrate":
            steps = calibrate_plan(args, config)
        elif args.command == "build":
            steps = build_plan(args, config)
        else:
            parser.error(f"unknown command: {args.command}")
        return run_plan(steps, args, config)
    except (ConfigurationError, RuntimeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
