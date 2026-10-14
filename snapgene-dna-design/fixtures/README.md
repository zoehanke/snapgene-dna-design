# Fixtures

`fixtures/rich/` contains small synthetic GenBank records used for parser and
round-trip tests. They are not distributor records and must not be presented as
biological truth.

Real SnapGene-derived vectors and any user DNA remain outside this repository in
the private fixtures directory. Academic-only tests must be enabled explicitly
against a separately obtained fixture set.

Default primer-editing and targeted-correctness regressions create their own
deterministic Native/GenBank inputs in temporary directories. These exercise
annotation preservation, negative-strand joins, forbidden components, complete
PCR/assembly and delivery without private files. Synthetic marker/GFP labels are
test stand-ins, not claims of resistance or fluorescence; their sequence is not
copied from the SnapGene collection.

To repeat the original private pDONR201/EmGFP targeted case, explicitly set
`SNAPGENE_RUN_ACADEMIC_FIXTURES=1` and run
`python -X utf8 -B -m unittest discover -s tests -p test_targeted_correctness.py`.
This requires separately supplied `fixtures/pDONR201.dna`,
`fixtures/golden/attB-EmGFP.gb` and `fixtures/golden/pDEST-EmGFP.gb`.
The default tests still execute when these files are absent; they are not skipped.
