"""Kit-owned source selection; never inferred from material names."""
def references(request,context):
    return list(dict.fromkeys(request[k] for k in ('vector_reference','target_reference') if request.get(k)))
