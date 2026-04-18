from __future__ import annotations

from pathlib import Path


def collect_artifact_paths(output_dir: str) -> dict:
    base = Path(output_dir)
    return {
        "video_dir": str(base / "video"),
        "trace_path": str(base / "traces" / "trace.zip"),
        "screenshot_dir": str(base / "screenshots"),
    }


def demo_recording_note() -> str:
    return (
        "Playwright video recording is enabled for the browser context. "
        "If the saved browser-context video is insufficient for presentation, run the script in headed mode "
        "and use the operating system screen recorder to capture the same session."
    )

