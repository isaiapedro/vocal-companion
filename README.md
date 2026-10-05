# PIOS Vocal Practice Companion

Local, invocation-scoped CLI for personal singing-practice tracking. It uses
only the Python standard library, starts no server, and writes its append-only
archive only to `personal/vocal_practice/`.

The workflow is deliberately split: profile discovery happens before routine
generation, while practice tracking happens only after a reviewed routine is
available.

Run from the workspace root:

```sh
python3 services/vocal_practice_companion/profile_intake.py --account-name "Pedro"
```

This conversational assessment stores a private prompt under
`personal/vocal_practice/routine_requests/`. It defaults to `local_only` LLM
handling. The CLI never transmits the prompt; preparing it for an external LLM
requires `--llm-processing external_user_approved --confirm-external-llm` and
is a deliberate user-controlled disclosure. Save its JSON-only result locally as
`routine.json`, review/edit it, then begin tracking:

```sh
python3 services/vocal_practice_companion/practice_session.py start --routine-file routine.json --available-minutes 20 --readiness 7 --accept
python3 services/vocal_practice_companion/practice_session.py log-block SESSION_ID --phase warm_up --exercise "straw glides" --skill "gentle coordination" --minutes 4 --actual-phonation-minutes 3 --intensity easy --range-zone middle --result easier
python3 services/vocal_practice_companion/practice_session.py finish SESSION_ID --post-effort 3 --discomfort 0 --ease 7
python3 services/vocal_practice_companion/practice_session.py recovery --session SESSION_ID --speaking normal --singing normal --range normal --discomfort 0
```

`practice_session.py start --interactive` remains available for a deterministic
fallback routine, but an LLM-generated routine must use `--routine-file`.

Each routine block can include a plain-language explanation and an optional
visual-reference search query. To print the queries for a routine without making
any network request, run:

```sh
python3 services/vocal_practice_companion/vocal_practice.py visual-reference-queries personal/vocal_practice/routines/foundation_mpb_jazz_20min.json
```

Search manually and prefer demonstrations from a qualified teacher consistent
with your current instruction. A visual reference is contextual learning aid,
not a diagnosis or replacement for teacher feedback.

For a full practical explanation of every block—how to do it, intended benefits,
singing areas, long-term review signals, evidence claim, and evidence limit—run:

```sh
python3 services/vocal_practice_companion/vocal_practice.py explain-routine personal/vocal_practice/routines/foundation_mpb_jazz_20min.json
```

To retain an external article, video, or image reference without fetching it or
sending personal data anywhere, save an image under
`personal/vocal_practice/assets/` or keep a URL, then archive only its metadata:

```sh
python3 services/vocal_practice_companion/vocal_practice.py attach-resource --title "Teacher's straw-glide demonstration" --kind video --url "https://example.com" --review-status teacher_recommended
```

The app never opens, downloads, ranks, or validates an external resource. A
resource is marked `user_saved`, `teacher_recommended`, or `reviewed` so its
provenance remains clear.

`--data-dir` is intentionally fixed to `personal/vocal_practice`; alternate
paths, including `/tmp`, are rejected to preserve the Personal-domain write
boundary.
`verify-archive` checks the append-only hash chain; `weekly-review` produces a
provenance-linked review only while explicitly invoked.

To add a later self-reported voice check to the same private archive (without
recording audio), run:

```sh
python3 services/vocal_practice_companion/vocal_practice.py voice-observation --account-name "Pedro" --context daily_check_in --ease 7 --effort 2 --discomfort 0 --range-state normal --note "Comfortable speaking voice today."
```
