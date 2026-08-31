# fixtures/golden — academic-only sequence fixtures

These files are local test fixtures derived from public vector systems. They are
**academic-only** (packaged in the academic-full ZIP, excluded from the
redistributable ZIP by restricted-hash checks). They are snapshots used to test
Gateway / TA / TOPO workflows; they are not authoritative distributor copies.

| File | Source | Catalog / reference |
|---|---|---|
| `pDONR201.dna` | Invitrogen Gateway donor vector pDONR201 | Thermo Fisher Cat 11798-014; Hartley et al. 2000, Genome Res 10:1788-1795, DOI 10.1101/gr.143000 |
| `pDEST40.dna` | Invitrogen Gateway destination vector pDEST40 | Thermo Fisher Cat 12274015 |
| `pENTR-D-TOPO.dna` | Invitrogen pENTR/D-TOPO entry vector | Thermo Fisher K240020 |
| `pcDNA3.2-V5-GW-D-TOPO.dna` | Invitrogen pcDNA3.2/V5-GW/D-TOPO | Thermo Fisher pcDNA3.2/V5-GW/D-TOPO expression system (product documentation) |
| `pGEM-T-linearized.dna` | Promega pGEM-T Easy linearized vector | Promega Cat A1360 |
| `ta-insert.fa` | synthetic A-tailed PCR insert fixture | TA cloning, Marchuk et al. 1991, Nucleic Acids Res 19:1154, DOI 10.1093/nar/19.5.1154 |
| `attB-EmGFP.gb` / `pENTR-EmGFP.gb` | local Gateway attB/attL + EmGFP expected constructs | derived from standard attB1/attB2/attL1/attL2 sequences, Hartley et al. 2000 |
| `pDEST-EmGFP.gb` | local Gateway LR expected product | derived from pDEST40 + EmGFP, Hartley et al. 2000 |
| `pGEM-T-insert.gb` | local TA expected product | derived from pGEM-T Easy + ta-insert |

Use the files only for internal validation. For biological claims, re-download the
authoritative sequence from the cited distributor/NCBI record.
