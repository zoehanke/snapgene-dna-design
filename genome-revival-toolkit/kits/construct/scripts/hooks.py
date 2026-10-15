"""Kit-owned source selection; never inferred from material names."""
def references(request,context):
    return list(dict.fromkeys(request[k] for k in ('target_reference','cargo_reference','donor_template_reference') if request.get(k)))
