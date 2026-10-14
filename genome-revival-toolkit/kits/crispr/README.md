# CRISPR plasmid Kit

Use this Kit for a supplied guide cassette and target: check existing DNA or replace a requested 20 nt spacer. Its thin workflow calls same-version Core rather than implementing another DNA algorithm. Construct prepares integration donors, Identity compares regional assays and Evidence evaluates submitted observation records.

## Inputs and run

kit.json owns wrapper/request fields. Supply vector_reference, target_reference and a uniquely directed promoter-to-scaffold cassette. Replacement requires spacer_seq. Explicit selectors resolve ambiguity. Declare actual strain_genotype for conditional selection; missing information remains unknown.

```text
python kits/crispr/examples/generate_inputs.py --out-dir example-inputs
python scripts/run_toolkit.py crispr --context example-inputs/context.json --request example-inputs/request.json --out-dir example-output --language en
python scripts/run_toolkit.py verify --out-dir example-output
```

The example uses fixed-seed synthetic input constructors. Its random scaffold is a locator, synthetic complete ORF/replication annotation only test structure, and conditional medium is not a measured phenotype. No laboratory or project-material claim is made.

## Checks, files and limits

Inspect sequence-derived direction, actual PAM and loci, orientation ambiguity, vector matches, complete primers, independently simulated preparation and declared selection. Failed checks block complete handoff. selection.tsv keeps row sources. Successful replacement returns Core-owned DNA/oligo/preparation files with Toolkit result/context/summary/receipt; rejected candidates remain explicitly labelled.

Scientific boundaries are retained in scripts/workflow.py and source-labelled rules. Inherited template findings keep their original severity; this Kit enables no acceptance exemption. Plans/simulations do not certify physical PCR/DpnI/KLD, gRNA function, editing efficiency, whole-genome specificity or experimental resistance. Official GitLab CI was not executed.
