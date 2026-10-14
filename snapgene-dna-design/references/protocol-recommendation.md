# Protocol recommendation rules

- Never invent temperatures, times, buffers, enzyme systems, or reaction
  volumes from model memory.
- If recommending a specific product, conditions must come from that product's
  current official protocol.
- Do not mix conditions from different polymerases or kits.
- Record `retrieved_at` for web sources. When a page has no revision, write
  `document_revision: unknown`.
- When no network or no authoritative source is available, mark the
  recommendation `unavailable` and still emit the objective reaction profile.
