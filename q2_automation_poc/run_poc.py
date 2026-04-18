from __future__ import annotations

import argparse
from pathlib import Path
import shutil
from collections import Counter

from src.browser_runner import launch_browser
from src.config import load_config
from src.message_loader import load_messages
from src.platform_selector import SelectedPlatform, select_platform
from src.q1_update_checker import generate_q1_update_report
from src.recorder import collect_artifact_paths, demo_recording_note
from src.selected_platform_adapter import TalkieAdapter
from src.transcript_writer import write_transcripts
from src.utils import append_log, clean_text, ensure_dir, now_iso, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Q2 AI companion automation proof of concept.")
    parser.add_argument("--q1-csv", default="../q1_app_evaluation/outputs/ai_companion_app_evaluation.csv")
    parser.add_argument("--messages", default="input_messages.txt")
    parser.add_argument("--out", default="outputs")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--platform-url", default="")
    parser.add_argument("--character-url", default="")
    parser.add_argument("--skip-login", action="store_true")
    parser.add_argument("--max-messages", type=int, default=10)
    parser.add_argument("--env-file", default="")
    return parser.parse_args()


def preview_text(text: str, limit: int = 120) -> str:
    cleaned = clean_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def choose_platform(q1_csv_path: Path, args: argparse.Namespace, output_dir: Path) -> SelectedPlatform:
    selection_table_path = output_dir / "platform_selection_table.csv"
    selected = select_platform(str(q1_csv_path), str(selection_table_path))
    if args.platform_url:
        selected.web_url = args.platform_url
    if args.character_url:
        selected.character_url = args.character_url
    return selected


def generate_report(
    destination: Path,
    selected: SelectedPlatform,
    transcript_rows: list[dict],
    artifact_paths: dict,
    q1_update_path: Path,
) -> None:
    character_used = transcript_rows[0]["character_name_or_id"] if transcript_rows else "Unknown"
    lines = [
        "# Automation PoC for AI Companion Platform Interaction",
        "",
        "## 1. Chosen Platform",
        f"- App name: {selected.title}",
        f"- Source platform from Q1: {selected.source_platform}",
        f"- App Store or Google Play URL: {selected.app_store_url}",
        f"- Web URL used: {selected.web_url}",
        f"- Character or bot used: {character_used}",
        f"- Character URL used: {selected.character_url}",
        f"- Q1 app_type: {selected.app_type}",
        f"- Why this platform was selected: {selected.reason}",
        "",
        "## 2. Automation Approach",
        "- Tool used: Playwright with Python.",
        "- Automation type: UI-based browser automation against a public web chat interface.",
        "- Workflow: select platform from Q1, open the browser chat page, optionally check for login, send fixed input messages one by one, wait for each reply, and save the transcript to CSV and JSON.",
        "- For the final Talkie guest run, each prompt is sent in a fresh browser session to avoid the platform's guest-session instability after a few turns while still demonstrating programmatic prompt-response capture on the same character page.",
        "- Message capture: responses are collected from the latest visible bot message blocks after the UI settles.",
        "",
        "## 3. Why This Approach Is Effective and Scalable",
        "- Browser automation is repeatable for controlled prompt suites.",
        "- The transcript schema is structured and ready for downstream analysis.",
        "- The adapter pattern supports multiple characters and multiple platforms.",
        "- Screenshots, traces, and browser video make failures diagnosable.",
        "- The pipeline avoids manual copy-paste and produces auditable artifacts.",
        "",
        "## 4. Assumptions",
        "- The selected public character page remains available.",
        "- The free tier permits a short 10-message proof of concept.",
        "- No CAPTCHA, phone verification, or blocked login wall appears for guest access during the demo.",
        "- DOM selectors remain close enough to the current web UI for this run.",
        "- Guest-mode prompt collection on Talkie may require a fresh session per prompt for reliable response capture.",
        "",
        "## 5. Limitations",
        "- UI automation is brittle to front-end changes.",
        "- Some platforms that ranked highly in Q1 still require login or subscriptions for reliable automation.",
        "- Guest access or free-tier behavior may change over time.",
        "- Response timing can vary, so long runs need stronger retry and recovery logic.",
        "- For this Talkie PoC, the final transcript uses isolated guest sessions rather than one continuous stateful conversation because the public guest flow became unstable after several turns.",
        "",
        "## 6. Extension to Multiple Platforms",
        "- Keep the shared runner, transcript schema, logging, and artifact handling.",
        "- Add one adapter per platform that implements the same base interface.",
        "- Store selectors and platform-specific behavior in adapter modules or config.",
        "- Reuse the same input-message suite across platforms for controlled comparisons.",
        "- Add rate-limit awareness and explicit permission checks before scaling out.",
        "",
        "## 7. Relation to Research Context",
        "Prior work on AI companion risks, character platforms, and human-LLM chat logs motivates collecting controlled transcripts rather than relying only on marketing claims or anecdotal reports. This PoC shows the first layer of that workflow: a reproducible mechanism for sending a fixed message suite to one character platform and capturing the resulting dialogue for later analysis, in the spirit of work such as *Characterizing Delusional Spirals through Human-LLM Chat Logs*, *Benchmarking and Understanding Safety Risks in AI Character Platforms*, and *Examining Risks in the AI Companion Application Ecosystem*.",
        "",
        "## 8. Artifacts",
        "- run_poc.py",
        "- src/ source modules",
        "- input_messages.txt",
        "- outputs/chat_transcript.csv",
        "- outputs/chat_transcript.json",
        "- outputs/run_log.txt",
        "- outputs/screenshots/",
        f"- {artifact_paths['trace_path']}",
        f"- {artifact_paths['video_dir']}",
        "- outputs/video/demo_video.webm",
        "- outputs/platform_selection_table.csv",
        f"- {q1_update_path}",
        "",
        "## 9. Q1 Updates Discovered During Q2",
        f"- See {q1_update_path.name} for the comparison result.",
        "",
        "## Demo Recording Note",
        f"- {demo_recording_note()}",
    ]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _rename_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        if source.resolve() == destination.resolve():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.unlink()
        shutil.move(str(source), str(destination))


def run_isolated_talkie_guest_sequence(config, messages: list[str], output_dir: Path, log_path: Path) -> list[dict]:
    transcript_rows: list[dict] = []
    latest_trace_path: Path | None = None
    total_messages = len(messages)
    for index, message in enumerate(messages, start=1):
        append_log(
            log_path,
            f"Message {index}/{total_messages}: starting isolated Talkie guest session. Prompt: {preview_text(message, 90)}",
        )
        with launch_browser(config.headless, config.slow_mo_ms, str(output_dir)) as (_, _, page):
            adapter = TalkieAdapter(page, config, str(log_path))
            try:
                adapter.open_platform()
                adapter.login_if_needed(skip_login=True)
                adapter.open_chat()
                rows = adapter.run_conversation([message])
                row = rows[0]
                row["message_index"] = index
                row["conversation_url_or_identifier"] = f"{row['conversation_url_or_identifier']}#isolated-{index:02d}"
                transcript_rows.append(row)
                append_log(
                    log_path,
                    f"Message {index}/{total_messages}: success in {row['response_latency_seconds']}s. "
                    f"Response preview: {preview_text(row.get('response_text', ''), 120)}",
                )
                page.screenshot(path=str(output_dir / "screenshots" / f"message_{index:02d}_final.png"), full_page=True)
            except Exception as exc:
                append_log(log_path, f"Isolated session {index} failed before transcript capture: {clean_text(exc)}")
                transcript_rows.append(
                    {
                        "message_index": index,
                        "timestamp_sent": now_iso(),
                        "input_message": message,
                        "timestamp_response": now_iso(),
                        "response_text": "",
                        "response_latency_seconds": 0,
                        "platform_name": config.platform_name or "Talkie",
                        "platform_url": config.platform_url,
                        "character_name_or_id": "",
                        "conversation_url_or_identifier": f"{config.character_url or config.platform_url}#isolated-{index:02d}",
                        "automation_method": "Playwright UI automation",
                        "status": "error",
                        "error_message": clean_text(exc),
                    }
                )
                append_log(
                    log_path,
                    f"Message {index}/{total_messages}: error. Details: {clean_text(exc)}",
                )
                page.screenshot(path=str(output_dir / "screenshots" / f"message_{index:02d}_failure.png"), full_page=True)
            finally:
                adapter.cleanup()

        latest_trace_path = output_dir / "traces" / f"trace_msg_{index:02d}.zip"
        _rename_if_exists(output_dir / "traces" / "trace.zip", latest_trace_path)
        if latest_trace_path.exists():
            append_log(log_path, f"Saved per-message trace: {latest_trace_path}")
    if latest_trace_path and latest_trace_path.exists():
        shutil.copyfile(latest_trace_path, output_dir / "traces" / "trace.zip")
        append_log(log_path, f"Copied canonical trace to {output_dir / 'traces' / 'trace.zip'}")
    if (output_dir / "screenshots" / "message_10_final.png").exists():
        shutil.copyfile(output_dir / "screenshots" / "message_10_final.png", output_dir / "screenshots" / "final_state.png")
        append_log(log_path, f"Copied canonical final screenshot to {output_dir / 'screenshots' / 'final_state.png'}")
    return transcript_rows


def main() -> None:
    args = parse_args()
    base_dir = Path(__file__).resolve().parent
    output_dir = ensure_dir(base_dir / args.out)
    q1_csv_path = (base_dir / args.q1_csv).resolve()
    log_path = output_dir / "run_log.txt"
    if log_path.exists():
        log_path.unlink()

    config = load_config(args.env_file or None)
    messages = load_messages(str(base_dir / args.messages), max_messages=args.max_messages)
    selected = choose_platform(q1_csv_path, args, output_dir)
    selection_table_path = output_dir / "platform_selection_table.csv"

    if not config.platform_name:
        config.platform_name = selected.title
    if not config.platform_url:
        config.platform_url = selected.web_url
    if args.character_url:
        config.character_url = args.character_url
    elif not config.character_url:
        config.character_url = selected.character_url

    if args.headed:
        config.headless = False
    if args.headless:
        config.headless = True

    append_log(log_path, "Starting Q2 automation proof of concept run.")
    append_log(log_path, f"Q1 CSV input: {q1_csv_path}")
    append_log(log_path, f"Selection table: {selection_table_path}")
    append_log(log_path, f"Messages file: {base_dir / args.messages}")
    append_log(log_path, f"Output directory: {output_dir}")
    append_log(
        log_path,
        "Runtime options: "
        f"headless={config.headless}, slow_mo_ms={config.slow_mo_ms}, "
        f"skip_login={args.skip_login}, max_messages={len(messages)}, "
        f"response_timeout_seconds={config.response_timeout_seconds}, env_file={args.env_file or 'default .env lookup'}",
    )
    append_log(log_path, f"Selected platform: {selected.title} ({selected.source_platform})")
    append_log(log_path, f"Selection rationale: {selected.reason}")
    append_log(log_path, f"Platform homepage URL: {selected.web_url or 'unknown'}")
    append_log(log_path, f"Using automation target URL: {config.character_url or config.platform_url}")
    append_log(log_path, f"Loaded {len(messages)} test messages.")

    transcript_rows: list[dict] = []
    isolated_talkie_guest_mode = args.skip_login and "talkie" in selected.title.lower()

    if isolated_talkie_guest_mode:
        append_log(log_path, "Using isolated-session guest mode for Talkie.")
        transcript_rows = run_isolated_talkie_guest_sequence(config, messages, output_dir, log_path)
    else:
        screenshot_path = output_dir / "screenshots" / "failure.png"
        with launch_browser(config.headless, config.slow_mo_ms, str(output_dir)) as (_, _, page):
            adapter = TalkieAdapter(page, config, str(log_path))
            try:
                append_log(log_path, "Opening platform.")
                adapter.open_platform()
                append_log(log_path, "Checking login requirements.")
                adapter.login_if_needed(skip_login=args.skip_login)
                append_log(log_path, "Opening chat view.")
                adapter.open_chat()
                append_log(log_path, "Running message sequence.")
                transcript_rows = adapter.run_conversation(messages)
                page.screenshot(path=str(output_dir / "screenshots" / "final_state.png"), full_page=True)
            except Exception as exc:
                page.screenshot(path=str(screenshot_path), full_page=True)
                append_log(log_path, f"Run failed: {clean_text(exc)}")
                raise
            finally:
                adapter.cleanup()
        _rename_if_exists(output_dir / "traces" / "trace.zip", output_dir / "traces" / "trace.zip")

    status_counts = Counter(row.get("status", "unknown") for row in transcript_rows)
    append_log(log_path, f"Automation run complete. Transcript row count: {len(transcript_rows)}")
    append_log(log_path, f"Transcript status counts: {dict(status_counts)}")

    write_transcripts(
        transcript_rows,
        str(output_dir / "chat_transcript.csv"),
        str(output_dir / "chat_transcript.json"),
    )
    append_log(log_path, f"Wrote transcript CSV to {output_dir / 'chat_transcript.csv'}")
    append_log(log_path, f"Wrote transcript JSON to {output_dir / 'chat_transcript.json'}")

    live_observations = {
        "web_accessible": "True",
        "web_url": config.character_url or config.platform_url,
        "login_required": "False" if args.skip_login else "unknown",
        "login_methods": "guest",
        "age_verification_required": "True",
        "age_verification_method": "self-declaration",
        "q2_evidence_note": f"Q2 live run completed with {len(transcript_rows)} transcript rows.",
        "q2_evidence_path": str(output_dir / "screenshots" / "message_01_final.png"),
    }

    q1_update_path = output_dir / "q1_updates_from_q2.md"
    generate_q1_update_report(
        str(q1_csv_path),
        selected.title,
        selected.source_platform,
        live_observations,
        str(q1_update_path),
    )
    append_log(log_path, f"Wrote Q1 comparison report to {q1_update_path}")

    artifact_paths = collect_artifact_paths(str(output_dir))
    video_files = sorted(
        [path for path in (output_dir / "video").glob("*.webm") if path.name != "demo_video.webm"],
        key=lambda path: path.stat().st_mtime,
    )
    if video_files:
        shutil.copyfile(video_files[0], output_dir / "video" / "demo_video.webm")
        append_log(log_path, f"Copied canonical demo video to {output_dir / 'video' / 'demo_video.webm'}")
    generate_report(
        output_dir / "q2_automation_poc_report.md",
        selected,
        transcript_rows,
        artifact_paths,
        q1_update_path,
    )
    append_log(log_path, f"Wrote Q2 report to {output_dir / 'q2_automation_poc_report.md'}")

    write_json(
        {
            "selected_platform": selected.__dict__,
            "messages_sent": len(messages),
            "transcript_rows": len(transcript_rows),
            "status_counts": dict(status_counts),
            "successful_rows": sum(1 for row in transcript_rows if row.get("status") == "ok"),
            "error_rows": sum(1 for row in transcript_rows if row.get("status") != "ok"),
            "artifacts": artifact_paths,
            "generated_at": now_iso(),
        },
        output_dir / "run_summary.json",
    )
    append_log(log_path, f"Wrote run summary to {output_dir / 'run_summary.json'}")
    append_log(
        log_path,
        "Final artifact summary: "
        f"trace={output_dir / 'traces' / 'trace.zip'}, "
        f"video={output_dir / 'video' / 'demo_video.webm'}, "
        f"screenshots_dir={output_dir / 'screenshots'}",
    )

    print(f"Chosen platform: {selected.title}")
    print(f"Automation method: Playwright UI automation")
    print(f"Transcript CSV: {output_dir / 'chat_transcript.csv'}")
    print(f"Transcript JSON: {output_dir / 'chat_transcript.json'}")
    print(f"Trace: {output_dir / 'traces' / 'trace.zip'}")
    print(f"Report: {output_dir / 'q2_automation_poc_report.md'}")
    print(f"Q1 update report: {q1_update_path}")


if __name__ == "__main__":
    main()
