# Baseline status

Imported baseline: `0.9.1-dev1`.

This is a development snapshot, not an RC or formal release. Independent
review found three P0 classes that must be fixed before release:

1. A zero-width linear interval can be interpreted as a whole record.
2. Required-component validation can use an unused input record instead of the
   final product sequence.
3. The authoritative gate can be fooled by changing mutable plan or validation
   dictionaries after planning.

The baseline test suite passing does not close these findings. New development
must add failing regression tests first, then fix the shared invariants. Do not
change truth data or acceptance criteria to obtain a green result.
