#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""LLM vision playtest harness for Duke Nukem 3D headless captures."""

from __future__ import annotations

import argparse
import asyncio
import base64
import datetime
import email.utils
import io
import json
import logging
import os
import random
import socket
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import aiohttp
from pydantic import BaseModel, Field, ValidationError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from frame_analyzer import load_frame

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")
DEFAULT_FRAMES_DIR = os.path.join(PROJECT_ROOT, "captures")
DEFAULT_MODEL = "gpt-4o"
API_VERSION = "2024-02-15-preview"
INFERENCE_API_VERSION = "2024-05-01-preview"
RESPONSES_API_VERSION = "2025-04-01-preview"
MAX_RETRIES = 3
MAX_BACKOFF = 8.0
PASS_CONFIDENCE = 0.7

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.INFO)


class FrameVerdict(BaseModel):
    renders_ok: bool
    hud_visible: bool
    geometry_coherent: bool
    no_error_overlays: bool
    confidence: float = Field(ge=0.0, le=1.0)
    description: str

    @property
    def passes(self) -> bool:
        return (
            self.renders_ok
            and self.hud_visible
            and self.geometry_coherent
            and self.no_error_overlays
            and self.confidence >= PASS_CONFIDENCE
        )


class HarnessError(Exception):
    """Raised for harness/configuration failures."""


def _redact_hostname(hostname: str) -> str:
    """Redact a hostname for logging."""
    if not hostname:
        return "***"
    try:
        first_label = hostname.split(".")[0]
        return f"{first_label}.***"
    except Exception:
        return "***"


def _redact_endpoint(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        host = _redact_hostname(parsed.hostname or "")
        return f"{parsed.scheme}://{host}"
    except Exception:
        return "***"


def load_env(path: str) -> Dict[str, str]:
    """Load simple KEY=VALUE entries from .env, overlaid by process env."""
    env: Dict[str, str] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    env.update(os.environ)
    return env


def validate_llm_config(endpoint: str, api_key: str) -> Tuple[bool, str]:
    """Validate Azure OpenAI endpoint and API key without crashing on unset env."""
    if not api_key:
        return False, "LLM_PLAYTEST_API_KEY not set (use --stub for offline CI)"
    if len(api_key) < 16:
        return False, "LLM_PLAYTEST_API_KEY too short (min 16 chars)"
    if not endpoint:
        return False, "LLM_PLAYTEST_ENDPOINT not set"

    try:
        parsed = urllib.parse.urlparse(endpoint)
    except Exception as exc:
        return False, f"LLM_PLAYTEST_ENDPOINT URL parse failed: {exc}"
    if parsed.scheme != "https":
        return False, f"LLM_PLAYTEST_ENDPOINT must use https (got {parsed.scheme})"
    if not parsed.hostname:
        return False, "LLM_PLAYTEST_ENDPOINT has no hostname"

    try:
        socket.gethostbyname(parsed.hostname)
    except socket.gaierror as exc:
        return False, (
            "LLM_PLAYTEST_ENDPOINT hostname not resolvable "
            f"({_redact_hostname(parsed.hostname)}): {exc}"
        )
    except socket.timeout:
        return False, (
            "LLM_PLAYTEST_ENDPOINT DNS lookup timed out "
            f"({_redact_hostname(parsed.hostname)})"
        )
    except Exception as exc:
        return False, f"LLM_PLAYTEST_ENDPOINT DNS check failed: {exc}"
    return True, ""


def _append_unique(urls: List[str], url: str) -> None:
    if url and url not in urls:
        urls.append(url)


def build_chat_urls(endpoint: str, model: str) -> List[str]:
    """Return ordered endpoint candidates (responses/chat variants)."""
    endpoint = endpoint.strip()
    parsed = urllib.parse.urlsplit(endpoint)
    path = parsed.path.rstrip("/")
    base = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    deployment = urllib.parse.quote(model, safe="")
    urls: List[str] = []

    chat_base = base
    if "/responses" in path:
        if parsed.query:
            _append_unique(urls, endpoint)
        else:
            _append_unique(
                urls,
                f"{base}?api-version={RESPONSES_API_VERSION}",
            )
        if path.endswith("/responses"):
            chat_base = base[: -len("/responses")]

    if "/chat/completions" in path:
        _append_unique(urls, endpoint)
        return urls

    if "/openai/deployments/" in chat_base:
        _append_unique(urls, f"{chat_base}/chat/completions?api-version={API_VERSION}")
    else:
        _append_unique(
            urls,
            f"{chat_base}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={API_VERSION}",
        )

    if "/openai/v1" in chat_base:
        _append_unique(urls, f"{chat_base}/chat/completions")
    else:
        _append_unique(urls, f"{chat_base}/openai/v1/chat/completions")

    if chat_base.endswith("/models"):
        _append_unique(
            urls,
            f"{chat_base}/chat/completions?api-version={INFERENCE_API_VERSION}",
        )
    else:
        _append_unique(
            urls,
            f"{chat_base}/models/chat/completions?api-version={INFERENCE_API_VERSION}",
        )
    return urls


def _extract_response_text(data: Dict[str, Any]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text

    raise HarnessError("invalid responses API response: missing output text")


def parse_retry_after(header_value: str, max_wait: float = 60.0) -> Optional[float]:
    """Parse Retry-After seconds or HTTP-date, capped at max_wait."""
    if not header_value:
        return None
    value = header_value.strip()
    try:
        return min(float(int(value)), max_wait)
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt:
            now = datetime.datetime.now(datetime.timezone.utc)
            wait_seconds = (dt - now).total_seconds()
            if wait_seconds > 0:
                return min(wait_seconds, max_wait)
    except (TypeError, ValueError):
        pass
    return None


def discover_frames(frames_dir: str) -> List[Path]:
    directory = Path(frames_dir)
    if not directory.is_dir():
        raise HarnessError(f"frames directory not found: {directory}")
    frames = sorted(directory.glob("*.bmp"))
    if not frames:
        raise HarnessError(f"no BMP frames found in {directory}")
    return frames


def sample_frames(
    frames: Sequence[Path], strategy: str = "first-middle-last", count: int = 3
) -> List[Path]:
    """Sample frame paths using the requested strategy."""
    if count < 1:
        raise HarnessError("sample count must be >= 1")
    if strategy == "all":
        return list(frames)
    if len(frames) <= count:
        return list(frames)
    if strategy == "first-middle-last":
        indexes = [0, len(frames) // 2, len(frames) - 1]
        if count != 3:
            indexes = _even_indexes(len(frames), count)
    elif strategy == "evenly":
        indexes = _even_indexes(len(frames), count)
    else:
        raise HarnessError(f"unknown sample strategy: {strategy}")

    selected: List[Path] = []
    seen = set()
    for idx in indexes:
        idx = max(0, min(len(frames) - 1, idx))
        if idx not in seen:
            selected.append(frames[idx])
            seen.add(idx)
    return selected


def _even_indexes(length: int, count: int) -> List[int]:
    if count == 1:
        return [0]
    return [round(i * (length - 1) / (count - 1)) for i in range(count)]


def load_and_encode_frames(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    """Validate sampled BMPs with Pillow and return base64 payload records."""
    encoded = []
    for path in paths:
        try:
            img = load_frame(str(path))
        except Exception as exc:
            raise HarnessError(
                f"failed to load frame {path}: {type(exc).__name__}: {exc}"
            ) from exc
        # Some providers reject BMP uploads in vision endpoints. Normalize to PNG.
        with io.BytesIO() as png_buffer:
            img.convert("RGB").save(png_buffer, format="PNG")
            frame_b64 = base64.b64encode(png_buffer.getvalue()).decode("ascii")
        encoded.append({
            "path": str(path),
            "width": img.width,
            "height": img.height,
            "mime_type": "image/png",
            "b64": frame_b64,
        })
    return encoded


def frame_prompt(index: int, total: int) -> str:
    return (
        "You are judging a Duke Nukem 3D headless-render frame. "
        "Return only JSON with keys renders_ok, hud_visible, geometry_coherent, "
        "no_error_overlays, confidence, description. Mark renders_ok false for "
        "black screens, garbage, or all-one-color output; hud_visible true only "
        "when a status bar or weapon/icon is visible; geometry_coherent true only "
        "when walls/floor/ceiling or level structure are identifiable; "
        "no_error_overlays false for SDL popups, tracebacks, or debug dumps. "
        f"This is sampled frame {index + 1} of {total}."
    )


async def request_frame_verdict(
    session: aiohttp.ClientSession,
    url: str,
    api_key: str,
    model: str,
    frame: Dict[str, Any],
    index: int,
    total: int,
) -> FrameVerdict:
    """Call Azure OpenAI vision API for one frame with retry on rate limits."""
    use_responses_api = "/responses" in urllib.parse.urlsplit(url).path
    headers = {
        "api-key": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if use_responses_api:
        payload = {
            "model": model,
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": frame_prompt(index, total)},
                    {
                        "type": "input_image",
                        "image_url": (
                            f"data:{frame.get('mime_type', 'image/png')};"
                            f"base64,{frame['b64']}"
                        ),
                    },
                ],
            }],
            "temperature": 0,
            "max_output_tokens": 300,
            "text": {"format": {"type": "json_object"}},
        }
    else:
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": frame_prompt(index, total)},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{frame.get('mime_type', 'image/png')};base64,{frame['b64']}",
                            "detail": "low",
                        },
                    },
                ],
            }],
            "temperature": 0,
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        }

    backoff = 1.0
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                text = await resp.text()
                if resp.status == 200:
                    data = json.loads(text)
                    if use_responses_api:
                        content = _extract_response_text(data)
                    else:
                        content = data["choices"][0]["message"]["content"]
                    verdict_data = content if isinstance(content, dict) else json.loads(content)
                    return FrameVerdict.model_validate(verdict_data)

                if resp.status == 429 and attempt < MAX_RETRIES:
                    retry_after = parse_retry_after(resp.headers.get("Retry-After", ""))
                    if retry_after is None:
                        jitter = random.uniform(0, 0.5 * backoff)
                        retry_after = backoff + jitter
                        backoff = min(backoff * 2, MAX_BACKOFF)
                    logger.info(
                        "Vision API rate limited; retry %s/%s after %.2fs",
                        attempt + 1,
                        MAX_RETRIES,
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status >= 500 and attempt < MAX_RETRIES:
                    jitter = random.uniform(0, 0.5 * backoff)
                    sleep_time = backoff + jitter
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    logger.info(
                        "Vision API server error %s; retry %s/%s after %.2fs",
                        resp.status,
                        attempt + 1,
                        MAX_RETRIES,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                    continue

                if (
                    resp.status == 400
                    and "max_tokens" in text
                    and "max_completion_tokens" in text
                    and "max_completion_tokens" not in payload
                ):
                    payload.pop("max_tokens", None)
                    payload["max_completion_tokens"] = 300
                    logger.info(
                        "Vision API rejected max_tokens; retrying with max_completion_tokens"
                    )
                    continue

                raise HarnessError(
                    f"vision API returned HTTP {resp.status}: {text[:300]}"
                )
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if attempt < MAX_RETRIES:
                jitter = random.uniform(0, 0.5 * backoff)
                sleep_time = backoff + jitter
                backoff = min(backoff * 2, MAX_BACKOFF)
                logger.info(
                    "Vision API request failed (%s); retry %s/%s after %.2fs",
                    type(exc).__name__,
                    attempt + 1,
                    MAX_RETRIES,
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)
                continue
            raise HarnessError(f"vision API request failed: {exc}") from exc
        except (KeyError, json.JSONDecodeError, ValidationError) as exc:
            raise HarnessError(f"invalid vision API response: {exc}") from exc

    raise HarnessError("vision API retries exhausted")


async def live_verdicts(
    encoded_frames: Sequence[Dict[str, Any]], endpoint: str, api_key: str, model: str
) -> List[FrameVerdict]:
    urls = build_chat_urls(endpoint, model)
    if not urls:
        raise HarnessError("unable to derive chat completions endpoint from config")

    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        verdicts: List[FrameVerdict] = []
        selected_url: Optional[str] = None
        last_fallback_error: Optional[HarnessError] = None

        for candidate in urls:
            try:
                first_verdict = await request_frame_verdict(
                    session,
                    candidate,
                    api_key,
                    model,
                    encoded_frames[0],
                    0,
                    len(encoded_frames),
                )
                verdicts.append(first_verdict)
                selected_url = candidate
                break
            except HarnessError as exc:
                message = str(exc)
                if "HTTP 404" in message or "Resource not found" in message:
                    logger.info(
                        "Vision endpoint unavailable at %s; trying fallback",
                        _redact_endpoint(candidate),
                    )
                    last_fallback_error = exc
                    continue
                raise

        if selected_url is None:
            if last_fallback_error:
                raise last_fallback_error
            raise HarnessError("all chat endpoint candidates failed")

        for idx, frame in enumerate(encoded_frames[1:], start=1):
            verdicts.append(
                await request_frame_verdict(
                    session,
                    selected_url,
                    api_key,
                    model,
                    frame,
                    idx,
                    len(encoded_frames),
                )
            )
        return verdicts


def stub_verdicts(encoded_frames: Sequence[Dict[str, Any]]) -> List[FrameVerdict]:
    return [
        FrameVerdict(
            renders_ok=True,
            hud_visible=True,
            geometry_coherent=True,
            no_error_overlays=True,
            confidence=0.95,
            description=(
                "Stub verdict: frame loaded successfully and is treated as playable."
            ),
        )
        for _ in encoded_frames
    ]


def aggregate(verdicts: Sequence[FrameVerdict]) -> Tuple[bool, int, int]:
    passing = sum(1 for verdict in verdicts if verdict.passes)
    total = len(verdicts)
    required = ((2 * total) + 2) // 3 if total >= 3 else total
    return passing >= required, passing, required


def build_report(
    frames: Sequence[Dict[str, Any]],
    verdicts: Sequence[FrameVerdict],
    stub: bool,
    model: str,
) -> Dict[str, Any]:
    overall_pass, passing, required = aggregate(verdicts)
    return {
        "schema_version": "1.0",
        "mode": "stub" if stub else "live",
        "model": model,
        "overall_pass": overall_pass,
        "pass": overall_pass,
        "passing_frames": passing,
        "required_passing_frames": required,
        "frame_count": len(verdicts),
        "criteria": {
            "per_frame": (
                "all four booleans true and confidence >= "
                f"{PASS_CONFIDENCE}"
            ),
            "overall": "at least two thirds of sampled frames pass",
        },
        "frames": [
            {
                "path": frame["path"],
                "width": frame["width"],
                "height": frame["height"],
                "passes": verdict.passes,
                "verdict": verdict.model_dump(),
            }
            for frame, verdict in zip(frames, verdicts)
        ],
    }


def build_error_report(message: str) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "mode": "error",
        "overall_pass": False,
        "pass": False,
        "error": message,
        "frames": [],
    }


def write_report(path: Optional[str], report: Dict[str, Any]) -> None:
    if not path:
        return
    report_path = Path(path)
    if report_path.parent:
        report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = report_path.with_name(report_path.name + ".tmp")
    tmp_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, report_path)


def run(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    env = load_env(ENV_FILE)
    endpoint = env.get("LLM_PLAYTEST_ENDPOINT", "")
    model = env.get("LLM_PLAYTEST_MODEL", DEFAULT_MODEL)
    api_key = env.get("LLM_PLAYTEST_API_KEY", "")

    if not args.stub:
        valid, reason = validate_llm_config(endpoint, api_key)
        if not valid:
            raise HarnessError(f"{reason}; rerun with --stub for offline validation")

    frames = discover_frames(args.frames_dir)
    sampled = sample_frames(frames, args.sample_strategy, args.sample_count)
    encoded = load_and_encode_frames(sampled)

    if args.stub:
        verdicts = stub_verdicts(encoded)
    else:
        print(f"Using LLM vision model {model} at {_redact_endpoint(endpoint)}")
        verdicts = asyncio.run(live_verdicts(encoded, endpoint, api_key, model))

    report = build_report(encoded, verdicts, args.stub, model)
    return 0 if report["overall_pass"] else 1, report


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM vision playtest for Duke3D")
    parser.add_argument(
        "--frames-dir",
        default=DEFAULT_FRAMES_DIR,
        help="Directory containing BMP captures (default: captures/)",
    )
    parser.add_argument(
        "--sample-strategy",
        choices=("first-middle-last", "evenly", "all"),
        default="first-middle-last",
        help="Frame sampling strategy (default: first-middle-last)",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=3,
        help="Number of frames for non-all sampling strategies (default: 3)",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Validate frames and return a canned PASS without API calls",
    )
    parser.add_argument("--report", help="Write JSON verdict report to path")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        exit_code, report = run(args)
        write_report(args.report, report)
        status = "PASS" if exit_code == 0 else "FAIL"
        print(
            f"LLM playtest {status}: {report['passing_frames']}/"
            f"{report['frame_count']} sampled frames passed"
        )
        return exit_code
    except HarnessError as exc:
        message = str(exc)
        print(f"LLM playtest harness error: {message}", file=sys.stderr)
        try:
            write_report(args.report, build_error_report(message))
        except Exception as report_exc:
            print(f"Failed to write error report: {report_exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
