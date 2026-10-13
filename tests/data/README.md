# Template regression inputs

The former external donor record has been moved out of the current source tree. The [Addgene EcoFlex kit](https://www.addgene.org/kits/freemont-ecoflex-moclo/) provides GenBank resources, but [its terms](https://www.addgene.org/terms-of-use/) do not establish unrestricted redistribution permission for that record. Article licensing does not automatically apply to the depositor ZIP. The original is retained privately for known-case integration.

Default regressions now use the standalone fixed-seed generator `scripts/synthetic_trace_template.py`: complete 3100/4200 bp circular inputs, independent annotations, unchanged outside DNA, actual successive PCR intermediates and exported file readback. Expected values come from construction and direct slicing, not the implementation under test. Repeated binding sites and independently confirmed excessive hairpin structure remain rejection cases; thresholds are unchanged.

Set `SNAPGENE_EXTERNAL_REGRESSION_TEMPLATE` only when a legally obtained complete original is available. Those optional known-input integrations are reported separately; absence is a skip, not a passed default regression. Private originals are not copied into source, release packages or official candidates. A private archive is not a redistribution license.
