# Privacy and sequence upload consent

- Default behavior: **no upload**.
- Current Toolkit workflows read local supplied files, with no automatic database lookup. Separate public-record CLI requests require `--allow-network`; environment connectivity requires `--check-online`. Sequence-like keywords/accessions are rejected before HTTP. Addgene/BLAST hints do not retrieve records or run off-target searches. Legacy consent-bound URL generation is not automatic submission or proof of human authorization. C2 manual import/local-off-target Kit operations remain outside this checkpoint.
- Any request that sends DNA/RNA/gRNA/PCR/plasmid sequence to an external
  service requires explicit, per-request user consent.
- The consent prompt must state destination, sequence scope, purpose, retention
  policy where known, and a local alternative when one exists.
- Consent is recorded as metadata only; full sequences and credentials are not
  written into ordinary logs or packages.
- See `scripts/sequence_upload_consent.py` for the consent state machine.
