"""Kit-owned source selection; never inferred from material names."""
def references(request,context):
    return list(dict.fromkeys(row['reference_id'] for row in request.get('genotype_results',[]) if row.get('reference_id')))
