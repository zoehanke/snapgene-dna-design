"""Kit-owned source selection; never inferred from material names."""
def references(request,context):
    ids=[request[k] for k in ('target_reference','cargo_reference','donor_template_reference') if request.get(k)]
    options=request.get('identity_handoff')
    if isinstance(options,dict) and isinstance(options.get('references'),list):ids.extend(options['references'])
    return list(dict.fromkeys(ids))
