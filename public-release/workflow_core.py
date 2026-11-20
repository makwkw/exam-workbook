"""Shared CLI wrappers, schemas, JSON/JSONL I/O helpers, and local PDF export."""

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from jsonschema import ValidationError

from pdf_export import export_pdf


CODEX_MODEL = "gpt-6.2-sol"
CODEX_EFFORT = "high"
GEMINI_MODEL = "gemini-4-neon-high"
DEFAULT_AGY = "agy"
TEXT = {"type": "string", "minLength": 1}
POSITIVE_INT = {"type": "integer", "minimum": 1}
STAGE_LOGS_DIR = "stage-logs"
MAX_AGY_PROMPT_CHARS = 16000

WORKFLOW_ERRORS = (
    OSError, ValueError, RuntimeError, KeyError, ValidationError, subprocess.TimeoutExpired,
)


def _npm_native_codex(base_dir):
    """Return the vendored native Windows codex.exe under an npm prefix if present."""
    for pkg, triple in (
        ("codex-win32-x64", "x86_64-pc-windows-msvc"),
        ("codex-win32-arm64", "aarch64-pc-windows-msvc"),
    ):
        candidate = (
            Path(base_dir) / "node_modules" / "@openai" / "codex"
            / "node_modules" / "@openai" / pkg / "vendor" / triple / "bin" / "codex.exe"
        )
        if candidate.is_file():
            return candidate.resolve()
    return None


def _codex_version(executable):
    """Return the parsed semver tuple for a Codex CLI binary, or (0, 0, 0) on error."""
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return (0, 0, 0)
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout or "")
    return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)


def resolve_default_codex():
    """Locate the newest native Codex CLI binary, respecting CODEX_BIN override."""
    override = os.environ.get("CODEX_BIN", "").strip()
    if override:
        return override
    if os.name != "nt":
        return shutil.which("codex") or "codex"

    candidates = []
    seen = set()

    def _add(path):
        if path is None or not path.is_file():
            return
        resolved = path.resolve()
        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            candidates.append(resolved)

    appdata = os.environ.get("APPDATA")
    if appdata:
        _add(_npm_native_codex(Path(appdata) / "npm"))

    for entry in os.environ.get("PATH", "").split(os.pathsep):
        cleaned = entry.strip().strip('"')
        if not cleaned:
            continue
        folder = Path(cleaned)
        exe = folder / "codex.exe"
        if exe.is_file():
            _add(exe)
        cmd = folder / "codex.cmd"
        if cmd.is_file():
            _add(_npm_native_codex(folder) or cmd)

    if not candidates:
        return shutil.which("codex") or "codex.exe"
    if len(candidates) == 1:
        return str(candidates[0])
    best = max(candidates, key=lambda path: (_codex_version(path), path.suffix.lower() == ".exe"))
    return str(best)


DEFAULT_CODEX = resolve_default_codex()


def object_schema(fields):
    """Build a strict JSON Schema object requiring all declared fields."""
    return {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }


def json_text(data):
    """Serialize data to readable UTF-8 JSON."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def save(path, text):
    """Atomically write UTF-8 text to path, creating parent directories if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(text, encoding="utf-8")
    pending.replace(path)


def read_json(path):
    """Read and parse a UTF-8 JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def append_jsonl(path, record):
    """Append one JSON record as a single flushed line to a JSONL cache file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path):
    """Read non-empty JSON lines from path, returning [] if path does not exist."""
    path = Path(path)
    if not path.is_file():
        return []
    records = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ValueError(f"缓存文件 {path.name} 第 {lineno} 行 JSON 损坏：{exc}") from exc
    return records


def make_run_dir(prefix=""):
    """Return a timestamped run directory path under runs/."""
    return Path("runs", f"{prefix}{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}").resolve()


def add_cli_arguments(parser):
    """Register shared CLI executable options on an argument parser."""
    parser.add_argument("--codex", default=DEFAULT_CODEX, help="Codex CLI 可执行文件")
    parser.add_argument("--agy", default=DEFAULT_AGY, help="Antigravity CLI 可执行文件")


def logs_dir(directory):
    """Ensure and return the stage-logs directory inside a run directory."""
    target = Path(directory) / STAGE_LOGS_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def invoke(stage, command, directory, prompt=None, *, env=None, timeout=300):
    """Run an external CLI command in directory and record stdout/stderr logs."""
    stage_dir = logs_dir(directory)
    result = subprocess.run(
        command, cwd=directory, input=prompt.encode("utf-8") if prompt else b"",
        capture_output=True, timeout=timeout, check=False, env=env,
    )
    stdout_path = stage_dir / f"{stage}.stdout.log"
    stderr_path = stage_dir / f"{stage}.stderr.log"
    stdout_path.write_bytes(result.stdout)
    stderr_path.write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(
            f"CLI 退出码 {result.returncode}。查看 {STAGE_LOGS_DIR}/{stderr_path.name} 和 "
            f"{STAGE_LOGS_DIR}/{stdout_path.name}"
        )
    return result.stdout


def codex(stage, executable, directory, prompt, schema, *, images=(), timeout=600):
    """Run Codex CLI in read-only sandbox with a strict JSON output schema."""
    directory = Path(directory)
    logs_dir(directory)
    schema_rel = Path(STAGE_LOGS_DIR) / f"{stage}.schema.json"
    output_rel = Path(STAGE_LOGS_DIR) / f"{stage}.response.json"
    save(directory / schema_rel, json_text(schema))
    (directory / output_rel).unlink(missing_ok=True)
    command = [
        executable, "exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check",
        "--ignore-user-config", "--model", CODEX_MODEL,
        "--config", f"model_reasoning_effort={json.dumps(CODEX_EFFORT)}",
        "--output-schema", str(schema_rel), "--output-last-message", str(output_rel),
    ]
    if images:
        command += ["--image", *[str(image) for image in images]]
    invoke(stage, [*command, "--", "-"], directory, prompt, timeout=timeout)
    return read_json(directory / output_rel)


def antigravity(stage, executable, directory, prompt, *options, env=None, timeout=420):
    """Run Antigravity CLI with command-line length protection and return parsed JSON."""
    if len(prompt) > MAX_AGY_PROMPT_CHARS:
        raise ValueError(
            f"阶段 {stage} 命令行提示词长度 ({len(prompt)}) 超过安全阈值 {MAX_AGY_PROMPT_CHARS}，"
            "请将数据写入本地文件后再读取"
        )
    stdout = invoke(stage, [
        executable, "--output-format", "json", "--disable-slash-commands",
        "--model", GEMINI_MODEL, "--print-timeout", f"{timeout}s", *options, f"-p={prompt}",
    ], directory, env=env, timeout=timeout + 60)
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Antigravity 阶段 {stage} 未返回合法 JSON。查看 {STAGE_LOGS_DIR}/{stage}.stdout.log"
        ) from exc
    if result.get("status") != "SUCCESS":
        raise RuntimeError(
            f"Antigravity 未完成阶段 {stage}。查看 {STAGE_LOGS_DIR}/{stage}.stdout.log"
        )
    if result.get("denied_actions"):
        actions = ", ".join(
            item.get("display_name") or item.get("action", "unknown")
            for item in result["denied_actions"]
        )
        raise RuntimeError(
            f"Antigravity 阶段 {stage} 尝试调用被禁止的工具（{actions}）而中断。"
            f"查看 {STAGE_LOGS_DIR}/{stage}.stderr.log 和 {STAGE_LOGS_DIR}/{stage}.stdout.log"
        )
    return result


def gemini(stage, executable, directory, prompt, schema, *, input_data=None, files=(), timeout=420):
    """Run Antigravity non-interactively with file references and JSON Schema enforcement."""
    directory = Path(directory)
    stage_dir = logs_dir(directory)
    schema_rel = Path(STAGE_LOGS_DIR) / f"{stage}.schema.json"
    save(directory / schema_rel, json_text(schema))

    resolved_files = []
    seen = set()

    def _add_file(path):
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = directory / candidate
        resolved = candidate.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Gemini 待读取文件不存在：{resolved}")
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            resolved_files.append(resolved)

    if input_data is not None:
        input_path = stage_dir / f"{stage}.input.json"
        save(input_path, json_text(input_data))
        _add_file(input_path)
    for file_path in files:
        _add_file(file_path)

    no_cmd_rule = (
        "请严格遵守工具限制：只能使用只读文件读取工具（如 read_file；若单个文件较长，可分段指定起止行读取完整内容），"
        "严禁调用终端、Bash、命令执行、脚本运行或任何写入工具"
        "（本运行环境禁止命令执行，尝试调用命令会导致任务直接中断失败）。"
    )
    if resolved_files:
        file_lines = "\n".join(f"- {path}" for path in resolved_files)
        full_prompt = (
            f"{prompt.rstrip()}\n\n"
            f"{no_cmd_rule}请先逐一读取以下本地文件（包含 JSON/JSONL 数据或图片），"
            "完整核对内容后再严格按 JSON Schema 输出最终结果：\n"
            f"{file_lines}\n"
        )
    else:
        full_prompt = f"{prompt.rstrip()}\n\n{no_cmd_rule}\n"

    settings = {"agentMode": "", "toolPermission": "request-review"}
    result = antigravity(
        stage, executable, directory, full_prompt,
        "--settings", json.dumps(settings), "--json-schema", str(schema_rel), timeout=timeout,
    )
    output = result.get("structured_output")
    if output is None:
        raw_response = result.get("response")
        if isinstance(raw_response, str) and raw_response.strip():
            try:
                output = json.loads(raw_response)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Antigravity 阶段 {stage} 响应不是合法 JSON。查看 {STAGE_LOGS_DIR}/{stage}.stdout.log"
                ) from exc
        else:
            raise RuntimeError(
                f"Antigravity 阶段 {stage} 缺少 structured_output。查看 {STAGE_LOGS_DIR}/{stage}.stdout.log"
            )
    save(stage_dir / f"{stage}.response.json", json_text(output))
    return output


def build_workbook_pdf(directory):
    """Compile directory/workbook.md directly to directory/workbook.pdf locally."""
    return export_pdf(directory)
