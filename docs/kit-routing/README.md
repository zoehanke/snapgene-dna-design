# Developer-authored routing materials

These materials contain four natural-language requests per Kit, including an ambiguous/unsupported request and a request belonging to another Kit. Developers have not executed them as routing tests.

- requests.json contains request text only.
- expected.json contains manager-owned expected choices and boundary reasons.

The separately arranged evaluator must be a developer-independent isolated agent. Freeze the tested package/commit and material versions first. Give the execution agent only requests.json, the public installed Skill and construction-only inputs needed for the request; do not give expected.json, developer rubrics, reference answers, outputs or case feedback. Missing material should prompt clarification, not invented coordinates or sequences.

The manager checks actual selected entry, required gates, output files and retained errors. Keep each original/repeated attempt and human intervention separate. Clarification and refusal are valid expected outcomes where the task is undefined or scientifically unsupported; they are not successful biological runs.

These developer-authored files are public and are **not heldout**. Report prior exposure and contamination if present. A new conversation or shared working directory is not isolation. No routing success rate, autonomous host success or generalization claim follows from writing or reviewing this material. It is excluded from runtime packages and the selected official source directory.
