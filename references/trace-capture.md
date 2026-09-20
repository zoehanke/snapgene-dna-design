# Capture while doing the task

Read only for note submission or a custom command. Detailed organization belongs at handoff in [evidence-trace.md](evidence-trace.md).

Standard tools capture their own calls with the shared `--trace-dir`. For an independent script, wrap the command before it runs:

```text
python scripts/trace_run.py --trace-dir build/trace --input-file source.gb --output-file build/result.gb -- python local_design.py
```

Repeat input/output flags for multiple files. Include the script as an input when its version matters. Use `--role document` for a report, `qc` for a verification design, or `preview` for a preview. A successful script is a recorded operation, not Core Validation or authoritative delivery. Existing unchanged files remain presence observations. Failed commands retain errors and residual-file observations. Direct Python callers can use the same `evidence_trace.runtime.trace_file_call` with explicit inputs, expected outputs and a callable returning output paths.

For a real choice, submit only a brief public note with the design response. Example bundle:

```json
{"nodes":[{"id":"D1","kind":"decision","text":"Use the supplied fragment unchanged","rationale":"Its actual sequence meets the requested boundaries","decision_actor":"ai","explanation_origin":"ai_concurrent"}]}
```

Save the bundle and run `python scripts/trace_design.py record --trace-dir build/trace --input choice.json`. Use observed record references in `basis_refs` where available. This rationale is a public statement, not authenticated hidden reasoning. If written later, retain it as a separate later explanation using the handoff reference. User requests use `kind: requirement`; compliance is not an AI choice.

Source text can be preserved using `trace_design.py observe --input material.json`, with `{"kind":"local_text","path":"paper-excerpt.txt"}` or `{"kind":"submitted_text","text":"actual supplied text"}`. Record only relevant excerpts and source location. Unobserved searches remain unobserved.
