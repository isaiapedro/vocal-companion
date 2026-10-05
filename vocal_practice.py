#!/usr/bin/env python3
"""Invocation-scoped, local-only vocal-practice companion.

The archive is append-only JSONL. This module intentionally has no network,
database server, scheduler, container integration, or background worker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "0.1.0"
ALGORITHM_VERSION = "0.1.0"
INTENSITY_WEIGHT = {"easy": 1.0, "moderate": 1.5, "strong": 2.0}
EVIDENCE = {
    "vocal-exercises-singers-scoping-review": {
        "path": "knowledge/arts/wiki/papers/vocal-exercises-singers-scoping-review.md",
        "scope": "Curated exercise-literature reference; it does not establish a universal dose.",
    },
    "toward-a-consensus-description-of-vocal-effort-vocal-load-vocal-loading-and-voca": {
        "path": "knowledge/arts/wiki/papers/toward-a-consensus-description-of-vocal-effort-vocal-load-vocal-loading-and-voca.md",
        "scope": "Curated terminology reference; personal load remains an individual observation.",
    },
    "immediate-sovte-warmup-singers": {
        "path": "knowledge/arts/wiki/papers/immediate-sovte-warmup-singers.md",
        "scope": "Singer-specific short-term warm-up evidence only; it does not establish long-term effects or dose.",
    },
    "physiological-traditional-warmup-ccm-singers": {
        "path": "knowledge/arts/wiki/papers/physiological-traditional-warmup-ccm-singers.md",
        "scope": "Style-specific warm-up comparison in CCM singers; it is not universal genre guidance.",
    },
    "singing-ability-is-rooted-in-vocal-motor-control-of-pitch": {
        "path": "knowledge/arts/wiki/papers/singing-ability-is-rooted-in-vocal-motor-control-of-pitch.md",
        "scope": "Pitch-control research reference; the local note does not validate a particular exercise dose or tool.",
    },
}


def workspace_root() -> Path:
    """Return the resolved workspace root without relying on the caller's CWD."""
    return Path(__file__).resolve().parents[2]


def canonical_archive_root() -> Path:
    return (workspace_root() / "personal" / "vocal_practice").resolve()


def archive_root_or_error(value: Path | str) -> Path:
    """Accept only the declared Personal-domain archive, including symlink targets."""
    candidate = Path(value).expanduser().resolve()
    allowed = canonical_archive_root()
    if candidate != allowed:
        raise ValueError(
            f"--data-dir must be the canonical private archive: {allowed}"
        )
    return candidate


def validate_evidence_catalog() -> None:
    """Verify that every cited evidence ID resolves to its declared local source."""
    evidence_root = (workspace_root() / "knowledge" / "arts" / "wiki" / "papers").resolve()
    for document_id, item in EVIDENCE.items():
        candidate = (workspace_root() / item["path"]).resolve()
        if evidence_root not in candidate.parents or not candidate.is_file():
            raise RuntimeError(
                f"curated evidence '{document_id}' does not resolve to a local knowledge file"
            )
        header = candidate.read_text(encoding="utf-8").split("---", 2)
        if len(header) < 3 or f"id: {document_id}" not in header[1]:
            raise RuntimeError(
                f"curated evidence '{document_id}' has a missing or mismatched local document ID"
            )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: str | None) -> str:
    if not value:
        return utc_now()
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("reference timestamps require an explicit timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def split_values(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def account_name_or_error(value: str) -> str:
    """Validate a local grouping label without treating it as authentication."""
    name = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}", name):
        raise ValueError("account name must be 1–64 letters, numbers, spaces, '.', '_', or '-'")
    return name


class Archive:
    """Append-only local archive with a verifiable chain of event digests."""

    def __init__(self, root: Path):
        self.root = root
        self.path = root / "archive" / "events.jsonl"

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"archive contains invalid JSON at line {line_number}") from exc
        return records

    @staticmethod
    def digest(record: dict[str, Any]) -> str:
        body = {key: value for key, value in record.items() if key != "digest"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify(self) -> tuple[bool, str]:
        previous = None
        for index, record in enumerate(self.events(), 1):
            if record.get("previous_digest") != previous:
                return False, f"event {index} has a broken previous_digest link"
            if record.get("digest") != self.digest(record):
                return False, f"event {index} digest does not match its content"
            previous = record["digest"]
        return True, f"verified {index if 'index' in locals() else 0} event(s)"

    def append(self, event_type: str, payload: dict[str, Any], reference_timestamp: str,
               source_event_ids: Iterable[str] = ()) -> dict[str, Any]:
        valid, detail = self.verify()
        if not valid:
            raise RuntimeError(f"refusing to append: {detail}")
        existing = self.events()
        previous = existing[-1]["digest"] if existing else None
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "reference_timestamp": reference_timestamp,
            "recorded_timestamp": utc_now(),
            "timezone": "UTC",
            "schema_version": SCHEMA_VERSION,
            "source_interface": "local_cli",
            "source_event_ids": list(source_event_ids),
            "previous_digest": previous,
            "payload": payload,
        }
        event["digest"] = self.digest(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event


def latest(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    return next((event for event in reversed(events) if event["event_type"] == event_type), None)


def profile_or_error(archive: Archive) -> dict[str, Any]:
    profile = latest(archive.events(), "profile")
    if not profile:
        raise RuntimeError("no profile exists; run `onboard` first")
    return profile


def profile_for_account_or_error(archive: Archive, account_name: str) -> dict[str, Any]:
    profile = next((event for event in reversed(archive.events())
                    if event["event_type"] == "profile"
                    and event["payload"].get("account_name", "default") == account_name), None)
    if not profile:
        raise RuntimeError(f"no profile exists for local account '{account_name}'; run profile_intake.py first")
    return profile


def session_or_error(archive: Archive, session_id: str) -> dict[str, Any]:
    session = next((event for event in archive.events()
                    if event["event_type"] == "practice_session"
                    and event["payload"]["session_id"] == session_id), None)
    if not session:
        raise RuntimeError(f"session not found: {session_id}")
    return session


def safety_state(args: argparse.Namespace) -> tuple[str, list[str]]:
    red: list[str] = []
    yellow: list[str] = []
    if args.pain > 0:
        red.append("pain during phonation was reported")
    if args.sudden_voice_change:
        red.append("sudden substantial voice change was reported")
    if args.breathing_difficulty:
        red.append("breathing difficulty was reported")
    if args.worsening:
        red.append("rapidly worsening symptoms were reported")
    if args.readiness <= 4:
        yellow.append("readiness is below the personal normal-practice range")
    if args.singing_effort >= 6 or args.speaking_effort >= 6:
        yellow.append("reported effort is elevated")
    if args.discomfort >= 4 or args.reduced_range:
        yellow.append("reported discomfort or range change merits a reduced session")
    return ("red", red) if red else (("yellow", yellow) if yellow else ("green", []))


def ask_number(prompt: str, default: float = 0) -> float:
    answer = input(f"{prompt} [{default}]: ").strip()
    return default if not answer else float(answer)


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    marker = "Y/n" if default else "y/N"
    answer = input(f"{prompt} ({marker}): ").strip().lower()
    return default if not answer else answer in {"y", "yes"}


def collect_start_interaction(args: argparse.Namespace) -> None:
    """Collect the readiness check during an explicitly requested terminal session."""
    print("Vocal practice check-in. Press Enter to keep the shown default.")
    args.available_minutes = int(ask_number("Available practice minutes", 20))
    args.readiness = ask_number("Readiness (0–10)", 5)
    args.speaking_effort = ask_number("Speaking-voice effort (0–10)", 0)
    args.singing_effort = ask_number("Gentle singing effort (0–10)", 0)
    args.discomfort = ask_number("Discomfort (0–10)", 0)
    args.pain = ask_number("Pain during phonation (0–10)", 0)
    args.reduced_range = ask_yes_no("Comfortable range reduced", False)
    args.heavy_voice_use = int(ask_number("Recent heavy voice-use minutes", 0))
    args.sudden_voice_change = ask_yes_no("Sudden substantial voice change", False)
    args.breathing_difficulty = ask_yes_no("Breathing difficulty", False)
    args.worsening = ask_yes_no("Symptoms rapidly worsening", False)
    args.symptoms = input("Optional relevant symptoms: ").strip()


def propose_routine(profile: dict[str, Any], args: argparse.Namespace, state: str,
                    reasons: list[str]) -> dict[str, Any]:
    available = max(5, args.available_minutes)
    goals = profile["payload"].get("goals", [])
    constraints = profile["payload"].get("teacher_constraints", "")
    intensity = "easy" if state == "yellow" else "moderate"
    blocks = [
        {"exercise": "gentle warm-up", "intended_skill": "coordination", "minutes": min(5, available),
         "intensity": "easy", "range_zone": "middle"},
        {"exercise": "straw glides", "intended_skill": "registration transition", "minutes": min(6, max(3, available // 3)),
         "intensity": intensity, "range_zone": "transition"},
        {"exercise": "target phrase", "intended_skill": ", ".join(goals[:2]) or "repertoire transfer",
         "minutes": min(8, max(2, available - 8)), "intensity": intensity, "range_zone": "middle"},
    ]
    if state == "yellow":
        blocks[-1]["exercise"] = "easy repertoire or mental rehearsal"
        blocks[-1]["intensity"] = "easy"
    return {
        "available_minutes": available,
        "decision_state": state,
        "blocks": blocks,
        "basis": {
            "goals": goals,
            "teacher_constraints": constraints,
            "reported_state_reasons": reasons,
            "evidence_ids": list(EVIDENCE),
            "evidence_limits": [item["scope"] for item in EVIDENCE.values()],
        },
        "editable": True,
        "automatic_prescription": False,
    }


def load_generated_routine(path_value: str, available_minutes: int) -> dict[str, Any]:
    """Validate an LLM-produced proposal before it can become personal archive data."""
    validate_evidence_catalog()
    path = Path(path_value).expanduser().resolve()
    routine = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(routine, dict) or not isinstance(routine.get("blocks"), list) or not routine["blocks"]:
        raise ValueError("routine file must be JSON with a non-empty blocks list")
    allowed_phases = {"warm_up", "coordination", "technique", "repertoire", "cool_down", "mental_rehearsal"}
    allowed_ranges = {"low", "middle", "transition", "high"}
    total = 0.0
    blocks = []
    for index, block in enumerate(routine["blocks"], 1):
        required = {"phase", "exercise", "intended_skill", "planned_minutes", "intensity", "range_zone"}
        if not isinstance(block, dict) or required - set(block):
            raise ValueError(f"routine block {index} is missing required fields")
        if block["phase"] not in allowed_phases or block["intensity"] not in INTENSITY_WEIGHT or block["range_zone"] not in allowed_ranges:
            raise ValueError(f"routine block {index} uses an unsupported phase, intensity, or range zone")
        evidence_basis = block.get("evidence_basis")
        if not isinstance(evidence_basis, list) or not evidence_basis:
            raise ValueError(f"routine block {index} must disclose at least one evidence basis or an explicit evidence gap")
        for basis in evidence_basis:
            document_id = basis.get("document_id") if isinstance(basis, dict) else None
            if document_id != "none" and document_id not in EVIDENCE:
                raise ValueError(f"routine block {index} cites evidence outside the curated local catalog")
            if not isinstance(basis, dict) or not basis.get("affirmation") or not basis.get("limitation"):
                raise ValueError(f"routine block {index} evidence basis requires an affirmation and limitation")
        if not isinstance(block.get("instructions"), list) or not block["instructions"]:
            raise ValueError(f"routine block {index} requires clear instructions")
        if not isinstance(block.get("benefits"), list) or not block["benefits"]:
            raise ValueError(f"routine block {index} requires stated practical benefits")
        if not isinstance(block.get("singing_areas"), list) or not block["singing_areas"]:
            raise ValueError(f"routine block {index} requires named singing areas")
        long_term = block.get("long_term_role")
        if not isinstance(long_term, dict) or not all(long_term.get(key) for key in ("purpose", "continue_when", "adjust_or_pause_when")):
            raise ValueError(f"routine block {index} requires a long-term role and review signals")
        minutes = float(block["planned_minutes"])
        if minutes <= 0:
            raise ValueError(f"routine block {index} must have positive planned_minutes")
        total += minutes
        blocks.append(dict(block))
    if total > available_minutes:
        raise ValueError("routine exceeds the available session time")
    evidence_ids = routine.get("evidence_ids", [])
    if not isinstance(evidence_ids, list) or any(item not in EVIDENCE for item in evidence_ids):
        raise ValueError("routine uses evidence IDs outside the curated local catalog")
    if routine.get("decision") == "defer_for_professional_guidance":
        raise ValueError("the generated routine defers practice; do not start a loading session")
    return {
        "routine_title": routine.get("routine_title", "Imported routine"),
        "decision": routine.get("decision", "propose"),
        "rationale": routine.get("rationale", []),
        "blocks": blocks,
        "transfer_check": routine.get("transfer_check", ""),
        "basis": {"evidence_ids": evidence_ids, "generated_file": str(path), "llm_output_unverified": True},
        "editable": True,
        "automatic_prescription": False,
    }


def blocks_for_session(events: list[dict[str, Any]], session_id: str) -> list[dict[str, Any]]:
    return [event for event in events if event["event_type"] == "practice_block"
            and event["payload"]["session_id"] == session_id]


def session_summary(archive: Archive, session_id: str, reference_time: str) -> dict[str, Any]:
    events = archive.events()
    session = session_or_error(archive, session_id)
    blocks = blocks_for_session(events, session_id)
    total_minutes = sum(block["payload"]["minutes"] for block in blocks)
    actual_phonation_minutes = sum(block["payload"].get("actual_phonation_minutes", block["payload"]["minutes"]) for block in blocks)
    elapsed_minutes = sum(block["payload"].get("elapsed_minutes", block["payload"]["minutes"]) for block in blocks)
    by_intensity = Counter(block["payload"]["intensity"] for block in blocks)
    by_phase = Counter(block["payload"].get("phase", "unspecified") for block in blocks)
    load_index = sum(block["payload"]["minutes"] * INTENSITY_WEIGHT[block["payload"]["intensity"]]
                     for block in blocks)
    source_ids = [session["event_id"]] + [block["event_id"] for block in blocks]
    return archive.append("synthesis_snapshot", {
        "kind": "post_session",
        "session_id": session_id,
        "known_data_window": {"start": session["reference_timestamp"], "end": reference_time},
        "algorithm_version": ALGORITHM_VERSION,
        "source_count": len(source_ids),
        "findings": {
            "actual_vocal_minutes": total_minutes,
            "actual_phonation_minutes": actual_phonation_minutes,
            "elapsed_block_minutes": elapsed_minutes,
            "minutes_by_intensity": dict(by_intensity),
            "blocks_by_phase": dict(by_phase),
            "personal_load_index": round(load_index, 2),
            "label": "Organizational personal index, not a medically validated dose.",
        },
    }, reference_time, source_ids)


def week_key(reference_time: str) -> str:
    current = timestamp(reference_time)
    return f"{current.isocalendar().year}-W{current.isocalendar().week:02d}"


def weekly_review(archive: Archive, reference_time: str, force: bool = False) -> dict[str, Any] | None:
    events = archive.events()
    key = week_key(reference_time)
    if not force and any(event["event_type"] == "weekly_review" and event["payload"]["week"] == key for event in events):
        return None
    start = timestamp(reference_time) - timedelta(days=7)
    selected = [event for event in events if start <= timestamp(event["reference_timestamp"]) <= timestamp(reference_time)]
    blocks = [event for event in selected if event["event_type"] == "practice_block"]
    recoveries = [event for event in selected if event["event_type"] == "recovery_check"]
    minutes = sum(event["payload"].get("actual_phonation_minutes", event["payload"]["minutes"]) for event in blocks)
    intensity = Counter(event["payload"]["intensity"] for event in blocks)
    phases = Counter(event["payload"].get("phase", "unspecified") for event in blocks)
    recovery_states = Counter(event["payload"]["classification"] for event in recoveries)
    source_ids = [event["event_id"] for event in selected]
    return archive.append("weekly_review", {
        "week": key,
        "known_data_window": {"start": start.isoformat(), "end": reference_time},
        "algorithm_version": ALGORITHM_VERSION,
        "findings": {
            "vocal_minutes": minutes,
            "minutes_by_intensity": dict(intensity),
            "blocks_by_phase": dict(phases),
            "recovery_classifications": dict(recovery_states),
            "note": "Descriptive within-person summary; it does not establish causation or safety.",
        },
    }, reference_time, source_ids)


def command_onboard(args: argparse.Namespace, archive: Archive, reference_time: str) -> None:
    event = archive.append("profile", {
        "goals": split_values(args.goals),
        "styles": split_values(args.styles),
        "training_history": args.training_history,
        "teacher_constraints": args.teacher_constraints,
        "usual_voice_use": args.usual_voice_use,
        "consent": {"audio_storage": False, "remote_processing": False},
    }, reference_time)
    print(f"Profile archived: {event['event_id']}")


def command_start(args: argparse.Namespace, archive: Archive, reference_time: str) -> None:
    if args.interactive:
        collect_start_interaction(args)
    if args.available_minutes is None or args.readiness is None:
        raise ValueError("--available-minutes and --readiness are required unless --interactive is used")
    profile = profile_or_error(archive)
    state, reasons = safety_state(args)
    readiness = archive.append("readiness_check", {
        "readiness": args.readiness, "speaking_effort": args.speaking_effort,
        "singing_effort": args.singing_effort, "discomfort": args.discomfort,
        "pain": args.pain, "reduced_range": args.reduced_range,
        "symptoms": split_values(args.symptoms), "heavy_voice_use_minutes": args.heavy_voice_use,
        "decision_state": state, "decision_reasons": reasons,
    }, reference_time, [profile["event_id"]])
    if state == "red":
        archive.append("safety_event", {"trigger": reasons, "action": "stop vocal loading and seek appropriate professional guidance"}, reference_time, [readiness["event_id"]])
        print("RED: stop vocal loading. Seek appropriate professional guidance. Readiness and safety events were archived.")
        return
    proposal = load_generated_routine(args.routine_file, args.available_minutes) if args.routine_file else propose_routine(profile, args, state, reasons)
    print(json.dumps(proposal, indent=2, ensure_ascii=False))
    if args.interactive:
        args.accept = ask_yes_no("Accept this editable routine and start the session", False)
    if not args.accept:
        print("Proposal only. Re-run with --accept to create a session.")
        return
    proposal_event = archive.append("routine_proposal", proposal, reference_time, [profile["event_id"], readiness["event_id"]])
    session_id = str(uuid.uuid4())
    archive.append("practice_session", {"session_id": session_id, "routine_proposal_id": proposal_event["event_id"], "status": "active"}, reference_time, [proposal_event["event_id"], readiness["event_id"]])
    review = weekly_review(archive, reference_time)
    print(f"Session started: {session_id}")
    if review:
        print(f"Due weekly review archived: {review['event_id']}")


def command_log_block(args: argparse.Namespace, archive: Archive, reference_time: str) -> None:
    session = session_or_error(archive, args.session_id)
    if args.minutes <= 0:
        raise ValueError("--minutes must be greater than zero")
    event = archive.append("practice_block", {
        "session_id": args.session_id, "exercise": args.exercise, "intended_skill": args.skill,
        "minutes": args.minutes, "intensity": args.intensity, "range_zone": args.range_zone,
        "phase": args.phase, "elapsed_minutes": args.elapsed_minutes or args.minutes,
        "actual_phonation_minutes": args.actual_phonation_minutes if args.actual_phonation_minutes is not None else args.minutes,
        "break_minutes": args.break_minutes, "repetitions": args.repetitions,
        "feedback_source": args.feedback_source, "task_difficulty": args.difficulty,
        "result": args.result, "note": args.note,
    }, reference_time, [session["event_id"]])
    print(f"Practice block archived: {event['event_id']}")


def command_finish(args: argparse.Namespace, archive: Archive, reference_time: str) -> None:
    session = session_or_error(archive, args.session_id)
    response = archive.append("immediate_response", {
        "session_id": args.session_id, "post_effort": args.post_effort, "discomfort": args.discomfort,
        "ease": args.ease, "coordination": args.coordination, "range_change": args.range_change,
        "repeat_workload": args.repeat_workload, "note": args.note,
    }, reference_time, [session["event_id"]])
    summary = session_summary(archive, args.session_id, reference_time)
    review = weekly_review(archive, reference_time)
    print(f"Session response archived: {response['event_id']}")
    print(f"Post-session synthesis archived: {summary['event_id']}")
    if review:
        print(f"Due weekly review archived: {review['event_id']}")


def command_recovery(args: argparse.Namespace, archive: Archive, reference_time: str) -> None:
    session = session_or_error(archive, args.session)
    classification = "recovered" if args.speaking == args.singing == args.range == "normal" and args.discomfort == 0 else "partially_recovered"
    if args.worsening:
        classification = "worsening"
    event = archive.append("recovery_check", {
        "session_id": args.session, "speaking": args.speaking, "singing": args.singing,
        "range": args.range, "discomfort": args.discomfort, "ready_for_normal_practice": args.ready,
        "classification": classification,
    }, reference_time, [session["event_id"]])
    print(f"Recovery check archived ({classification}): {event['event_id']}")


def command_voice_observation(args: argparse.Namespace, archive: Archive, reference_time: str) -> None:
    """Store an explicitly supplied, non-diagnostic voice observation."""
    account_name = account_name_or_error(args.account_name)
    profile = profile_for_account_or_error(archive, account_name)
    if not 0 <= args.ease <= 10 or not 0 <= args.effort <= 10 or not 0 <= args.discomfort <= 10:
        raise ValueError("--ease, --effort, and --discomfort must be between 0 and 10")
    event = archive.append("voice_observation", {
        "account_name": account_name,
        "context": args.context,
        "perceived_ease": args.ease,
        "perceived_effort": args.effort,
        "discomfort": args.discomfort,
        "range_state": args.range_state,
        "note": args.note,
        "audio_recorded": False,
        "interpretation": "Self-reported observation only; it is not diagnosis or automated voice analysis.",
    }, reference_time, [profile["event_id"]])
    print(f"Voice observation archived: {event['event_id']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=canonical_archive_root(),
                        help="fixed canonical Personal archive; other paths are rejected")
    parser.add_argument("--at", help="ISO-8601 reference timestamp with timezone")
    commands = parser.add_subparsers(dest="command", required=True)
    onboard = commands.add_parser("onboard")
    onboard.add_argument("--goals", default="")
    onboard.add_argument("--styles", default="")
    onboard.add_argument("--training-history", default="unknown")
    onboard.add_argument("--teacher-constraints", default="")
    onboard.add_argument("--usual-voice-use", default="")
    start = commands.add_parser("start")
    start.add_argument("--available-minutes", type=int)
    start.add_argument("--readiness", type=float)
    start.add_argument("--speaking-effort", type=float, default=0)
    start.add_argument("--singing-effort", type=float, default=0)
    start.add_argument("--discomfort", type=float, default=0)
    start.add_argument("--pain", type=float, default=0)
    start.add_argument("--reduced-range", action="store_true")
    start.add_argument("--symptoms", default="")
    start.add_argument("--heavy-voice-use", type=int, default=0)
    start.add_argument("--sudden-voice-change", action="store_true")
    start.add_argument("--breathing-difficulty", action="store_true")
    start.add_argument("--worsening", action="store_true")
    start.add_argument("--interactive", action="store_true", help="ask the readiness questions in this terminal invocation")
    start.add_argument("--accept", action="store_true")
    start.add_argument("--routine-file", help="validated JSON proposal produced from the stored LLM prompt")
    block = commands.add_parser("log-block")
    block.add_argument("session_id")
    block.add_argument("--exercise", required=True)
    block.add_argument("--skill", required=True)
    block.add_argument("--minutes", type=float, required=True)
    block.add_argument("--intensity", choices=INTENSITY_WEIGHT, required=True)
    block.add_argument("--range-zone", choices=["low", "middle", "transition", "high"], required=True)
    block.add_argument("--phase", choices=["warm_up", "coordination", "technique", "repertoire", "cool_down", "mental_rehearsal"], default="technique")
    block.add_argument("--elapsed-minutes", type=float)
    block.add_argument("--actual-phonation-minutes", type=float)
    block.add_argument("--break-minutes", type=float, default=0)
    block.add_argument("--repetitions", type=int)
    block.add_argument("--feedback-source", choices=["self", "teacher", "recording", "tuner", "none"], default="self")
    block.add_argument("--difficulty", type=float, default=0)
    block.add_argument("--result", choices=["easier", "unchanged", "harder"], default="unchanged")
    block.add_argument("--note", default="")
    finish = commands.add_parser("finish")
    finish.add_argument("session_id")
    finish.add_argument("--post-effort", type=float, required=True)
    finish.add_argument("--discomfort", type=float, required=True)
    finish.add_argument("--ease", type=float, required=True)
    finish.add_argument("--coordination", type=float, default=0)
    finish.add_argument("--range-change", choices=["normal", "reduced", "greatly_reduced"], default="normal")
    finish.add_argument("--repeat-workload", choices=["yes", "maybe", "no"], default="maybe")
    finish.add_argument("--note", default="")
    recovery = commands.add_parser("recovery")
    recovery.add_argument("--session", required=True)
    recovery.add_argument("--speaking", choices=["normal", "changed"], required=True)
    recovery.add_argument("--singing", choices=["normal", "changed"], required=True)
    recovery.add_argument("--range", choices=["normal", "reduced", "greatly_reduced"], required=True)
    recovery.add_argument("--discomfort", type=float, required=True)
    recovery.add_argument("--ready", choices=["yes", "maybe", "no"], default="maybe")
    recovery.add_argument("--worsening", action="store_true")
    voice = commands.add_parser("voice-observation", help="archive a self-reported voice observation; no audio is captured")
    voice.add_argument("--account-name", required=True, help="local profile label created by profile_intake.py")
    voice.add_argument("--context", choices=["before_practice", "after_practice", "daily_check_in", "performance"], required=True)
    voice.add_argument("--ease", type=float, required=True, help="self-reported 0–10")
    voice.add_argument("--effort", type=float, required=True, help="self-reported 0–10")
    voice.add_argument("--discomfort", type=float, required=True, help="self-reported 0–10")
    voice.add_argument("--range-state", choices=["normal", "reduced", "greatly_reduced", "not_checked"], default="not_checked")
    voice.add_argument("--note", default="")
    weekly = commands.add_parser("weekly-review")
    weekly.add_argument("--force", action="store_true")
    visual = commands.add_parser("visual-reference-queries", help="print user-run visual-reference searches from a routine JSON file")
    visual.add_argument("routine_file")
    explain = commands.add_parser("explain-routine", help="print clear execution, learning, and evidence guidance for a routine")
    explain.add_argument("routine_file")
    resource = commands.add_parser("attach-resource", help="archive a user/teacher-saved link or local image reference without fetching it")
    resource.add_argument("--title", required=True)
    resource.add_argument("--kind", choices=["article", "video", "image", "document"], required=True)
    location = resource.add_mutually_exclusive_group(required=True)
    location.add_argument("--url")
    location.add_argument("--local-path")
    resource.add_argument("--review-status", choices=["user_saved", "teacher_recommended", "reviewed"], default="user_saved")
    resource.add_argument("--note", default="")
    commands.add_parser("verify-archive")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        reference_time = parse_time(args.at)
        archive = Archive(archive_root_or_error(args.data_dir))
        if args.command == "onboard": command_onboard(args, archive, reference_time)
        elif args.command == "start": command_start(args, archive, reference_time)
        elif args.command == "log-block": command_log_block(args, archive, reference_time)
        elif args.command == "finish": command_finish(args, archive, reference_time)
        elif args.command == "recovery": command_recovery(args, archive, reference_time)
        elif args.command == "voice-observation": command_voice_observation(args, archive, reference_time)
        elif args.command == "weekly-review":
            event = weekly_review(archive, reference_time, args.force)
            print(f"Weekly review archived: {event['event_id']}" if event else "Weekly review already exists for this week.")
        elif args.command == "visual-reference-queries":
            routine = json.loads(Path(args.routine_file).expanduser().read_text(encoding="utf-8"))
            for block in routine.get("blocks", []):
                query = block.get("visual_reference_search")
                if query:
                    print(f"{block.get('phase', 'practice')}: {query}")
        elif args.command == "explain-routine":
            routine = json.loads(Path(args.routine_file).expanduser().read_text(encoding="utf-8"))
            print(routine.get("routine_title", "Routine"))
            for block in routine.get("blocks", []):
                print(f"\n{block.get('phase', 'practice').replace('_', ' ').title()} — {block.get('exercise', '')}")
                print("How:")
                for number, instruction in enumerate(block.get("instructions", []), 1):
                    print(f"  {number}. {instruction}")
                print("Benefits: " + "; ".join(block.get("benefits", [])))
                print("Areas: " + ", ".join(block.get("singing_areas", [])))
                role = block.get("long_term_role", {})
                if role:
                    print("Long-term role: " + role.get("purpose", ""))
                    print("Review: " + role.get("continue_when", ""))
                    print("Adjust/pause: " + role.get("adjust_or_pause_when", ""))
                for basis in block.get("evidence_basis", []):
                    print(f"Evidence [{basis.get('document_id')}]: {basis.get('affirmation')}")
                    print(f"Limit: {basis.get('limitation')}")
        elif args.command == "attach-resource":
            payload = {"title": args.title, "kind": args.kind, "review_status": args.review_status, "note": args.note}
            if args.url:
                payload["url"] = args.url
            else:
                candidate = Path(args.local_path).expanduser().resolve()
                assets_root = (archive.root / "assets").resolve()
                if not candidate.is_file() or assets_root not in candidate.parents:
                    raise ValueError("--local-path must be an existing file under personal/vocal_practice/assets/")
                payload["local_path"] = str(candidate.relative_to(archive.root))
            event = archive.append("learning_resource_reference", payload, reference_time)
            print(f"Learning resource reference archived: {event['event_id']}")
        elif args.command == "verify-archive":
            valid, detail = archive.verify()
            print(detail)
            return 0 if valid else 1
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
