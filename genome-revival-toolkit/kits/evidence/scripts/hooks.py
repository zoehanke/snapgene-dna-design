"""Kit-owned source selection; never inferred from material names."""
def references(request,context):
    if 'expected_results_file' in request:return list(context.references)
    return list(dict.fromkeys(row['reference_id'] for row in request.get('genotype_results',[]) if row.get('reference_id')))
