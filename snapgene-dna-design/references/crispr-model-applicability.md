# CRISPR model applicability

- A prediction model is not the same as the software that runs it.
- Always record software, model, training context, and applicability warnings
  separately.
- SpCas9: Doench 2016 / Azimuth V3 may be used with explicit
  "not specifically validated for yeast" warnings.  "Rule Set 3" has no
  independent authoritative citation and must not be presented as a
  separate model.
- AsCas12a: DeepCpf1 may be used for AsCas12a-related prediction. It must not
  be automatically applied to LbCas12a.
- LbCas12a: when no validated model is selected, return
  `status=unavailable`, `reason=no-validated-model-selected-for-lbcas12a`.
- Never apply a Cas9-derived off-target model to Cas12a without review.
