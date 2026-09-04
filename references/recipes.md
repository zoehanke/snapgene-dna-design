# Standard Laboratory SOP Recipes Reference (`core/recipes/`)

This reference document specifies the parameter schemas, biological mechanisms, quality checks, output contracts, and authoritative literature citations for all 7 standard laboratory recipes.

---

## 1. `recipe_gibson_assembly`

**Module:** `core.recipes.gibson`  
**Purpose:** Isothermal seamless assembly of DNA fragments via exonuclease-chewback, polymerase-fill, and ligase-seal.  
**Result Kind:** `construct` | **Completeness:** `complete_construct`  
**Citations:**
- Gibson, D.G. et al. (2009). *Enzymatic assembly of DNA molecules up to several hundred kilobases*. Nature Methods, 6(5), 343–345. doi:10.1038/nmeth.1318.
- NEB NEBuilder HiFi DNA Assembly Guidelines (2014).

### Parameters
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `vector_linear_seq` | `str` | *required* | Linearized vector nucleotide sequence string. |
| `insert_template_seq` | `str` | *required* | Insert donor template nucleotide sequence string. |
| `insert_start` | `int` | *required* | 0-based start coordinate of insert on template. |
| `insert_end` | `int` | *required* | 0-based end coordinate of insert on template. |
| `overlap_length` | `int` | `22` | Homology arm length in bp (gold standard 20–25 bp). |
| `circular_product` | `bool` | `True` | Whether assembled product should be circular plasmid. |

### CLI Example
```bash
python scripts/run_recipe.py --recipe recipe_gibson_assembly --params-json gibson_params.json --out-dir ./build --finalize --confirmed
```

---

## 2. `recipe_restriction_cloning`

**Module:** `core.recipes.restriction_cloning`  
**Purpose:** Directional or non-directional restriction digestion and T4 DNA ligation.  
**Result Kind:** `construct` | **Completeness:** `complete_construct`  
**Citations:**
- Green, M.R. and Sambrook, J. (2012). *Molecular Cloning: A Laboratory Manual* (4th ed.). Cold Spring Harbor Laboratory Press. Chapters 1 & 3.
- New England Biolabs (NEB). *Cleavage of Oligonucleotides with Restriction Endonucleases*.

### Parameters
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `vector_record_or_seq` | `str` or file | *required* | Vector plasmid sequence, file path, or SeqRecord. |
| `insert_template_or_seq` | `str` or file | *required* | Insert donor sequence, file path, or SeqRecord. |
| `insert_start` | `int` | *required* | 0-based start coordinate of insert on template. |
| `insert_end` | `int` | *required* | 0-based end coordinate of insert on template. |
| `enzyme5` | `str` | *required* | 5' restriction enzyme name (e.g. `EcoRI`, `NdeI`, `BamHI`). |
| `enzyme3` | `str` | *required* | 3' restriction enzyme name (e.g. `HindIII`, `XhoI`, `NotI`). |
| `vector_cut5_coord` | `int` | `None` | Optional explicit 0-based cut coordinate on vector. |
| `vector_cut3_coord` | `int` | `None` | Optional explicit 0-based cut coordinate on vector. |
| `protective_bases` | `str` | `None` | Flanking protective bases upstream of enzyme recognition site. |

---

## 3. `recipe_golden_gate`

**Module:** `core.recipes.golden_gate`  
**Purpose:** Type IIS restriction-ligation modular assembly (BsaI, BsmBI/Esp3I, BbsI, PaqCI).  
**Result Kind:** `construct` | **Completeness:** `complete_construct`  
**Citations:**
- Engler, C., Kandzia, R. and Marillonnet, S. (2008). *A one pot, one step, modular cloning method for DNA assembly*. PLoS ONE, 3(11), e3647.
- Potapov, V. et al. (2018). *Comprehensive profiling of four base overhang ligation fidelity by T4 DNA ligase*. ACS Synthetic Biology, 7(11), 2665–2674.

### Parameters
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `fragments` | `list[str]` | *required* | List of DNA fragment sequence strings carrying Type IIS recognition sites. |
| `enzyme_name` | `str` | `"BsaI"` | Type IIS enzyme name (`BsaI`, `BsmBI`, `Esp3I`, `BbsI`). |
| `circular_product` | `bool` | `True` | Whether assembled product is circular. |

---

## 4. `recipe_crispr_hdr_donor`

**Module:** `core.recipes.crispr_hdr`  
**Purpose:** Design high-efficiency ssODN or double-stranded HDR donor repair templates with synonymous PAM mutation.  
**Result Kind:** `component` | **Completeness:** `component_only`  
**Citations:**
- Ran, F.A. et al. (2013). *Genome engineering using the CRISPR-Cas9 system*. Nature Protocols, 8(11), 2281–2308.
- Paquet, D. et al. (2016). *Efficient introduction of specific homozygous and heterozygous mutations using CRISPR/Cas9*. Nature, 533(7601), 125–129.

### Parameters
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_seq_or_file` | `str` or file | *required* | Genomic target locus sequence or file. |
| `cut_position_0based` | `int` | *required* | 0-based DSB cleavage coordinate (3 bp upstream of NGG). |
| `edit_dna` | `str` | *required* | Payload sequence to insert or substitute at the cut site. |
| `donor_type` | `str` | `"ssODN"` | `"ssODN"` (single-stranded) or `"dsDNA"` / `"plasmid"`. |
| `homology_arm_len` | `int` | `50` | Length of left and right homology arms in bp. |
| `grna_seq` | `str` | `""` | 20 nt spacer sequence (used to identify PAM and introduce synonymous mutation). |
| `target_is_cds` | `bool` | `False` | Whether target locus is inside a coding CDS. |
| `cds_frame_offset` | `int` | `0` | Reading frame offset (0, 1, or 2) relative to cut site. |

---

## 5. `recipe_point_mutagenesis`

**Module:** `core.recipes.mutagenesis`  
**Purpose:** Site-directed mutagenesis primer design (QuikChange / Zheng 2004 protocol).  
**Result Kind:** `construct` | **Completeness:** `complete_construct`  
**Citations:**
- Zheng, L., Baumann, U. and Reymond, J.L. (2004). *An efficient one-step site-directed and site-saturation mutagenesis protocol*. Nucleic Acids Research, 32(14), e115.

### Parameters
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `template_record_or_seq` | `str` or file | *required* | Parental plasmid sequence or file. |
| `mutation_start_0based` | `int` | *required* | 0-based start coordinate of target codon/base to mutate. |
| `mutation_end_0based` | `int` | *required* | 0-based end coordinate of target codon/base to mutate. |
| `desired_seq` | `str` | *required* | Replacement nucleotide sequence. |
| `flanking_match_len` | `int` | `15` | Symmetrical matching flanking bases on each side (>= 10–15 bp). |

---

## 6. `recipe_protein_tagging`

**Module:** `core.recipes.protein_tagging`  
**Purpose:** In-frame fusion of affinity tags, epitopes, or fluorescent proteins with linker and protease cleavage sites.  
**Result Kind:** `component` | **Completeness:** `component_only`  
**Citations:**
- Terpe, K. (2003). *Overview of tag protein fusion: from molecular and biochemical fundamentals to commercial systems*. Appl Microbiol Biotechnol, 60(5), 523–533.
- Kozak, M. (1986). *Point mutations define a sequence flanking the AUG initiator codon that modulates translation by eukaryotic ribosomes*. Cell, 44(2), 283–292.
- Waugh, D.S. (2011). *An overview of enzymatic reagents for removal of affinity tags*. Protein Expr Purif, 80(2), 283–293.

### Parameters
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_cds_seq_or_file` | `str` or file | *required* | Target coding sequence or file. |
| `tag_name_or_seq` | `str` | `"6xHis"` | Standard tag name (`6xHis`, `FLAG`, `HA`, `Myc`, `V5`, `StrepII`, `GST`, `MBP`, `mCherry`, `EGFP`) or custom DNA sequence. |
| `tag_position` | `str` | `"C-terminal"` | `"C-terminal"` (strips CDS stop) or `"N-terminal"` (strips tag stop). |
| `linker_type` | `str` | `None` | Standard linker (`flexible_G4S_x1`, `flexible_G4S_x2`, `flexible_G4S_x3`, `rigid_EAAAK_x2`, `rigid_EAAAK_x3`) or custom sequence. |
| `protease_site` | `str` | `None` | Optional protease cleavage site (`TEV`, `PreScission`, `Thrombin`). |
| `include_kozak` | `bool` | `False` | Prepend Kozak consensus motif (`GCCACC`) for N-terminal mammalian expression. |

---

## 7. `recipe_cloning_verification`

**Module:** `core.recipes.verification`  
**Purpose:** Quality control design for recombinant clones: junction-crossing colony PCR screening primers, Sanger sequencing primer layout, and diagnostic restriction digest band prediction.  
**Result Kind:** `verification` | **Completeness:** `qc_only`  
**Citations:**
- Green, M.R. and Sambrook, J. (2012). *Molecular Cloning: A Laboratory Manual* (4th ed.). Chapters 1 & 8.
- Sanger, F. et al. (1977). *DNA sequencing with chain-terminating inhibitors*. PNAS, 74(12), 5463–5467.

### Parameters
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `recombinant_plasmid_or_seq` | `str` or file | *required* | Recombinant plasmid sequence or file. |
| `insert_junction_start_0based` | `int` | *required* | 0-based coordinate where insert begins. |
| `insert_junction_end_0based` | `int` | *required* | 0-based coordinate where insert ends. |
| `diagnostic_enzymes` | `list[str]` | `None` | Optional list of enzymes for analytical restriction digest gel electrophoresis. |
