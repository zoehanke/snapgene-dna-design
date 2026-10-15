"""Kit-owned source selection; never inferred from material names."""
def references(request,context):
    return request.get('references',list(context.references))
