---
name: genome-construct
description: Prepare a specified linear integration donor from actual templates when target/cargo boundaries and arm length are supplied. Use Identity for regional assay comparison, Evidence for submitted observations, and CRISPR for guide plasmids. This Kit does not select a genomic locus or certify integration.
---

# Prepare a source-bound donor

Preserve the original request, actual template versions and explicitly selected intervals. Read kit.json for input fields and the example; ProjectContext is shared on the Toolkit side.

Run the declared entry with request_file/context_file. The retained CLI is `run_toolkit.py construct --request request.json --context context.json --out-dir output`. Supply a complete donor template for PCR, or explicit target/cargo templates for the existing Gibson route.

Inspect the actual preparation, complete-oligo quality, both donor interfaces, original goals and saved-file readback. A failed preparation or gate retains its original error; it does not authorize a method change or a candidate delivery.

Present returned DNA/order/verification files and verify TOOLKIT-RECEIPT.json through `run_toolkit.py verify`. Read README.md for generated examples and the unchanged scientific limits. Local donor checks do not establish whole-genome specificity, strain identity, wet preparation, genomic integration or revival.
