# Data-source inventory, 15 October 2026

Inspected base: `e853413`, Block K phase2, unmerged/unfrozen. This is Block S part 1. 官方 GitLab CI 未执行。

| Existing path / consumer | Network and default | Failure | Trace source coverage |
|---|---|---|---|
| Supplied GenBank/FASTA/native `.dna`, gzip and record/region selectors; `revival/context.py`, four Kits | Local only; no database fallback | Missing/changed/mismatched/ambiguous file or record rejects | `runner.make_trace_bundle` records actual provided sequence files and SHA-256. Verified means file version, not strain identity. |
| NCBI E-utilities, `scripts/online_sources.py` search/fetch | No Kit calls it. Separate CLI now needs `--allow-network`; deliberate Python retrieval calls remain explicit operations | `offline-unverified`, no invented sequence; sequence-like queries/accessions refused before HTTP | Previously no date/hash/source node. Now resolved accession/version, UTC date, response-content SHA-256/status, existing source node in active Trace; exported record has sidecar. Search summaries are not fetched DNA. |
| NCBI BLAST hint and legacy authorized URL helper | No HTTP submit/poll implementation or Kit caller. Default hint contains no sequence; legacy authorized short-query URL can contain sequence but software does not open it | Refusal or link only, never a BLAST result | No retrieved/verified result; link does not establish specificity. |
| Addgene helper | Link only, no request or sequence query | Always `offline-unverified` | No verified record or redistribution rights established. |
| CRISPR `rules/selection.json`; Evidence `rules/conclusions.json`; Core rule/component/protocol catalogs and user rule files | Local tables, not automatic retrieval of their citation URLs | Unsourced rule contributions reject; unknown markers stay unknown/conflicting | Declared sources/Kit-load observations exist, not a separately fetched source node for every citation. Evidence rows cite scope policy, not experimental sufficiency. |
| Evidence inline observations, local CSV and reported genotype results | Local parsing only | Invalid counts/references reject; missing observations remain insufficient/not tested | Request/return observations and CSV identities are recorded. These are not authenticated experimental source nodes. |
| User genome FASTA/2bit directory; `scripts/cas_offinder_adapter.py` | Optional installed local executable; no download. Not yet connected to CRISPR Kit | Missing program/OpenCL/genome explicitly unavailable/incomplete; no online fallback | Adapter returns genome/tool version/hash. No Kit whole-genome workflow is claimed. |
| `crispor_adapter.py` detection/consent skeleton | No current Kit operation or automatic submit | Availability/consent metadata only | No actual result source. C2 manual import/local-off-target integration remains unfinished. |
| Environment `check_env.py:probe_online` | Previously default NCBI probe; now only `--check-online` | Explicit offline connectivity status, independent of core/release dependency decisions | Connectivity probe is not a retrieved sequence; no sequence source is claimed. |
| Optional model parameters/weights and external Primer3/desktop software | Local modules/files/executables, no runtime download path found | Missing resources/backend reported, real integrations may skip with explicit reason | Tool/version/resource observations are not experimental or public-database evidence. |

## Confirmed boundaries

Caller inspection finds no public database retrieval from the four current workflows. It cannot establish whether a researcher previously downloaded a supplied file. No source is invented from an accession or filename. Reference DNA is not an experimental-strain genotype.

Successful fetch receipts record database, requested ID, resolved accession/version, UTC retrieval time, returned decoded UTF-8 content hash and retrieval status. The saved record uses exactly those bytes. Search hashes canonical search/summary responses and records returned accession versions, without claiming each sequence was fetched. Unknown versions stay unknown. Failed attempts have time/status but no invented sequence or content hash.

Source recording reuses the existing source schema and active recorder. Off records nothing; normal/strict failure policies stay unchanged. Verified retrieval concerns parsed response/version only. There is no new node kind, relation kind or scientific inference.

The no-argument standalone source script and default environment probe previously initiated network access. Explicit flags close those default paths without changing dependency judgments. Sequence-like accession rejection closes a GET disclosure path. Legacy consent/URL helpers are not promoted to an upload workflow.

## Reproducible verification

`tests/test_public_source_trace.py`: real loopback HTTP server, constructed GenBank, independent hashlib, actual files, explicit-network refusal, malformed/unavailable/sequence-like boundaries and source nodes. External connections are refused; tests never query real NCBI.

`tests/test_kit_network_defaults.py`: actual public describe/workflow/verify commands with Python socket/DNS entries blocked and counted. Covers both Construct preparation branches, Identity comparison/supplied/designed assays, Evidence inline/CSV/genotype/missing observations, and CRISPR check/replacement. Scientific rejection is retained. This is Python connection-attempt evidence for reached operations, not packet capture of unrelated applications. C2 operations do not exist in this baseline and are not claimed.

Raw execution, individual skips, exact-commit CI, private English Wiki material and unresolved differences are indexed in the morning handoff. Test definitions are not successful execution evidence. 官方 GitLab CI 未执行。
