# Privacy and sequence upload consent

- Default behavior: **no upload**.
- Any request that sends DNA/RNA/gRNA/PCR/plasmid sequence to an external
  service requires explicit, per-request user consent.
- The consent prompt must state destination, sequence scope, purpose, retention
  policy where known, and a local alternative when one exists.
- Consent is recorded as metadata only; full sequences and credentials are not
  written into ordinary logs or packages.
- See `scripts/sequence_upload_consent.py` for the consent state machine.
