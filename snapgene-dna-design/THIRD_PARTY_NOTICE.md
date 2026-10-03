# Third-Party Notice

The software source code in this repository (including `scripts/`, `tests/`,
`SKILL.md`, `agents/openai.yaml`, and `references/`) is provided under the MIT
License in `LICENSE`.

The following files are **not covered by the MIT License**:

- `fixtures/pDONR201.dna`
- `fixtures/golden/pDEST40.dna`
- `fixtures/golden/pENTR-D-TOPO.dna`
- `fixtures/golden/pcDNA3.2-V5-GW-D-TOPO.dna`
- `fixtures/golden/pGEM-T-linearized.dna`

These files were copied from the SnapGene 6.x plasmid collection
(`the local SnapGene plasmid collection`, GraphPad Software / SnapGene). SnapGene states that
maps, notes, and annotations from its plasmid collection are copyrighted
material:

- Academic, non-profit, and government users may use them with attribution:
  **www.snapgene.com/resources**
- Commercial users must contact GraphPad for a separate license.

Derived golden fixtures (`fixtures/golden/attB-EmGFP.*`,
`fixtures/golden/pENTR-EmGFP.gb`, `fixtures/golden/pDEST-EmGFP.gb`,
`fixtures/golden/pGEM-T-insert.gb`) contain sequences/features derived from
those SnapGene files and are therefore subject to the same restrictions.

**Do not redistribute this package commercially, or claim these fixture files
under MIT, without written authorization from GraphPad/SnapGene.**

For a redistribution excluding the known restricted fixtures:

- Delete `fixtures/pDONR201.dna` **and** the entire `fixtures/golden/`
  directory (the derived `.gb`/`.fa` fixtures included), and
- replace them with independently constructed synthetic fixtures.

Recommended package variants:

- `academic-full`: keeps the real SnapGene-derived fixtures with the
  attribution above.
- `redistributable`: contains only independently constructed synthetic
  fixtures and no SnapGene-copied files.

Reference: SnapGene plasmid collection terms of use,
https://www.snapgene.com/resources.

## Bundled third-party model artifacts

Upstream identity, license text and per-file SHA-256 are in
`third_party/UPSTREAM-MANIFEST.json`.

- `third_party/azimuth/`: Azimuth 2.0 (BSD-3-Clause), Doench et al. 2016,
  DOI 10.1038/nbt.3437. License: `third_party/azimuth/LICENSE`.
- `third_party/deepcpf1/`: DeepCpf1 weights distributed by Bioconductor
  CRISPRseek 1.52.0 (Artistic-2.0), Kim et al. 2018, DOI 10.1038/nbt.4061.
  License: `third_party/deepcpf1/LICENSE`.

## Primer3 runtime

Primer3 and primer3-py are licensed under GPL-2.0-or-later. They are required for supported primer design and used as
external tools and are **not included** in either package produced by this
project. `scripts/primer3_core_backend.py` invokes a user-installed
`primer3_core` executable as a separate process. Installing primer3-py is one
way to obtain that executable, but its license and redistribution obligations
remain separate from this project's MIT license.

Upstream sources:

- https://github.com/primer3-org/primer3
- https://github.com/libnano/primer3-py

## Golden fixture provenance

The academic fixture set consists of:

- `fixtures/pDONR201.dna` — SnapGene `Gateway Donor Vectors/pDONR201.dna`
- `fixtures/golden/pDEST40.dna` — SnapGene `Gateway Destination Vectors/pcDNA-DEST40.dna`
- `fixtures/golden/pENTR-D-TOPO.dna` — SnapGene `TOPO Directional Vectors/pENTR D-TOPO.dna`
- `fixtures/golden/pcDNA3.2-V5-GW-D-TOPO.dna` — SnapGene `TOPO Directional Vectors/pcDNA3.2 V5 GW D-TOPO.dna`
- `fixtures/golden/pGEM-T-linearized.dna` — SnapGene `TA Cloning Vectors/pGEM-T (linearized).dna`

Derived golden fixtures (`attB-EmGFP.fa/.gb`, `pENTR-EmGFP.gb`,
`pDEST-EmGFP.gb`, `pGEM-T-insert.gb`) were generated once from feature
coordinates read from those SnapGene files; tests compare against the
committed files rather than against package constants.
