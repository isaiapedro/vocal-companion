#!/usr/bin/env python3
"""Create a private vocal-development assessment and LLM routine prompt."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from vocal_practice import (
    Archive,
    EVIDENCE,
    archive_root_or_error,
    canonical_archive_root,
    account_name_or_error,
    parse_time,
    split_values,
    validate_evidence_catalog,
)


OPTIONS = {
    "target_audience": ["self_guided_hobbyist", "developing_performer", "semi_professional", "professional_voice_user"],
    "development_level": ["beginner", "foundation", "intermediate", "advanced", "returning_after_break"],
    "objectives": ["coordination", "registration_range", "intonation", "repertoire", "performance_preparation", "endurance", "style_development", "sustainable_practice"],
}


def choose(label: str, explanation: str, values: list[str], multiple: bool = False) -> list[str] | str:
    print(f"\n{label}\n{explanation}")
    for index, value in enumerate(values, 1):
        print(f"  {index}. {value}")
    answer = input("Your choice" + "s (comma-separated)" if multiple else "Your choice" + ": ").strip()
    selected = [values[int(part.strip()) - 1] for part in answer.split(",")]
    return selected if multiple else selected[0]


def roadmap(audience: str, level: str, objectives: list[str]) -> list[str]:
    steps = ["establish a personal readiness and recovery baseline", "use short standardized transfer checks"]
    if level in {"beginner", "foundation", "returning_after_break"}:
        steps.insert(0, "prioritize consistent easy-to-moderate coordination practice")
    else:
        steps.insert(0, "progress one user-reviewed load variable at a time")
    if audience in {"semi_professional", "professional_voice_user"}:
        steps.append("include non-practice voice-use and performance-demand context")
    if "performance_preparation" in objectives:
        steps.append("add standardized repertoire transfer and listener assessment")
    if "sustainable_practice" in objectives:
        steps.append("review incomplete recovery before increasing demand")
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=canonical_archive_root(),
                        help="fixed canonical Personal archive; other paths are rejected")
    parser.add_argument("--at")
    parser.add_argument("--available-minutes", type=int, default=20)
    parser.add_argument("--account-name", default="default",
                        help="local profile label only; it is not authentication")
    parser.add_argument("--llm-processing", choices=["local_only", "external_user_approved"],
                        default="local_only",
                        help="the CLI never transmits this prompt; external handling needs explicit confirmation")
    parser.add_argument("--confirm-external-llm", action="store_true",
                        help="required with --llm-processing external_user_approved")
    args = parser.parse_args()
    try:
        if args.llm_processing == "external_user_approved" and not args.confirm_external_llm:
            raise ValueError("--confirm-external-llm is required before preparing a prompt for external handling")
        validate_evidence_catalog()
        account_name = account_name_or_error(args.account_name)
        print("\nLet’s build the context for your singing-development plan.")
        print("There are no right answers. This does not classify or diagnose your voice;")
        print("it helps the routine stay relevant to your goals, experience, and constraints.\n")
        audience = choose(
            "Who is this plan for?",
            "This sets the kind of practice context we consider—for example, a hobbyist\n"
            "building consistency versus a performer balancing rehearsal demands.",
            OPTIONS["target_audience"],
        )
        level = choose(
            "Where do you feel you are in your current development?",
            "This is your own description, not a judgment. It helps us decide whether to\n"
            "emphasize foundations, stable skill transfer, or carefully reviewed progression.",
            OPTIONS["development_level"],
        )
        objectives = choose(
            "What would make practice feel useful right now?",
            "Choose every area that matters. The routine will prioritize these rather than\n"
            "trying to improve everything in one session.",
            OPTIONS["objectives"], multiple=True,
        )
        styles = split_values(input("\nWhich styles or genres do you want this plan to serve?\n"
                                   "A comma-separated answer is perfect; this keeps technique and repertoire context-specific: "))
        history = input("\nTell me briefly about your training or practice history.\n"
                        "For example: lessons, choir, self-guided work, or a recent break. This gives the plan a starting point: ").strip() or "not provided"
        weekly = input("\nHow much practice time is realistically available in a usual week?\n"
                       "An honest estimate helps us make a plan you can sustain instead of an idealized one: ").strip() or "not provided"
        voice_use = input("\nWhat is your voice doing outside practice?\n"
                          "Work, teaching, calls, rehearsals, performances, or little speaking demand can all affect recovery context: ").strip() or "not provided"
        teacher = input("\nIs there teacher-provided guidance, a current restriction, or a preference you want the plan to respect?\n"
                        "This is recorded as your provided context—not as automatically verified evidence: ").strip() or "none provided"
        practice_pattern = input("\nWhat currently makes practice easier to keep consistent?\n"
                                 "For example: a time of day, a short routine, accompaniment, or accountability: ").strip() or "not provided"
        challenge = input("\nWhat is the most specific non-medical practice challenge you want the next routine to address?\n"
                          "For example: matching pitch in a phrase, comfortable transitions, rhythm, or confidence: ").strip() or "not provided"
        recovery = input("\nWhat self-reported signal tells you to reduce or pause practice?\n"
                         "For example: discomfort, unusual effort, fatigue after heavy voice use, or teacher guidance: ").strip() or "not provided"
        repertoire = input("\nWhich song, artist, exercise, or repertoire situation should the plan serve?\n"
                           "This is optional and can stay broad: ").strip() or "not provided"
        steps = roadmap(audience, level, objectives)
        reference_time = parse_time(args.at)
        archive = Archive(archive_root_or_error(args.data_dir))
        profile = archive.append("profile", {
            "account_name": account_name, "target_audience": audience, "development_level": level, "objectives": objectives,
            "goals": objectives, "styles": styles, "training_history": history,
            "weekly_practice": weekly, "usual_voice_use": voice_use,
            "teacher_constraints": teacher, "possible_steps": steps,
            "practice_consistency_support": practice_pattern,
            "specific_practice_challenge": challenge,
            "self_reported_reduce_or_pause_signal": recovery,
            "repertoire_context": repertoire,
            "consent": {"audio_storage": False,
                        "remote_processing": args.llm_processing == "external_user_approved"},
        }, reference_time)
        template = (Path(__file__).parent / "prompts" / "routine_generation.md").read_text(encoding="utf-8")
        evidence = "\n".join(f"- {key}: {value['scope']}" for key, value in EVIDENCE.items())
        replacements = {
            "account_name": account_name, "target_audience": audience, "development_level": level, "objectives": ", ".join(objectives),
            "styles": ", ".join(styles) or "not provided", "training_history": history,
            "weekly_practice": weekly, "usual_voice_use": voice_use, "teacher_constraints": teacher,
            "practice_consistency_support": practice_pattern,
            "specific_practice_challenge": challenge,
            "self_reported_reduce_or_pause_signal": recovery,
            "repertoire_context": repertoire,
            "available_minutes": str(args.available_minutes), "possible_steps": "; ".join(steps),
            "readiness_context": "Collected by practice_session.py immediately before practice.",
            "evidence_references": evidence,
        }
        for key, value in replacements.items():
            template = template.replace("{{" + key + "}}", value)
        digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
        request_dir = archive.root / "routine_requests"
        request_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = request_dir / f"{profile['event_id']}.md"
        prompt_path.write_text(template, encoding="utf-8")
        archive.append("routine_generation_request", {
            "profile_id": profile["event_id"], "prompt_path": str(prompt_path.relative_to(archive.root)),
            "prompt_sha256": digest, "prompt_text": template,
            "llm_execution": args.llm_processing,
        }, reference_time, [profile["event_id"]])
        print(f"Assessment archived for local profile '{account_name}'.")
        print("Possible next steps:")
        for step in steps:
            print(f"- {step}")
        print(f"LLM routine prompt saved to: {prompt_path}")
        return 0
    except (ValueError, IndexError) as exc:
        print(f"error: invalid selection: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
