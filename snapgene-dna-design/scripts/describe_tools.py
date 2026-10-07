#!/usr/bin/env python3
"""List executable tools, or show one tool's current parameters without reading source."""
from __future__ import annotations

import argparse
import inspect
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def describe(name: str | None = None) -> dict:
    from core.tools import TOOL_REGISTRY
    import core.recipes as recipes
    if name == 'workflow_requirements':
        from core.requirements import requirements_definition
        return {'name': name, 'kind': 'goal_contract', 'parameters': requirements_definition(),
                'entrypoint': 'validate_candidate / deliver_result / scripts/finalize_workflow.py',
                'coverage': 'Declared computable constraints; free-text original_request is retained, not automatically verified.'}
    recipe_names = sorted(n for n in dir(recipes) if n.startswith('recipe_') and callable(getattr(recipes,n)))
    if name is None:
        return {'contracts': ['workflow_requirements'], 'recipes': recipe_names,
                'tools': [{'name': key, 'category': spec.category} for key,spec in sorted(TOOL_REGISTRY.items())]}
    if name in recipe_names:
        from core.workflow import get_method
        spec=get_method(name)
        return {**spec.to_definition(),'kind':'recipe','signature':str(spec._signature),
                'reference':'references/recipes.md','entrypoint':'scripts/run_step.py or scripts/run_recipe.py'}
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        raise ValueError(f'Unknown tool or recipe: {name}')
    entrypoint = ('scripts/run_step.py or scripts/run_pipeline.py' if spec.category in {'compute','inspect'}
                  else 'direct callable; use the corresponding file/external CLI, not a Pipeline step')
    return {**spec.to_definition(), 'signature': str(inspect.signature(spec.callable)),
            'parameter_aliases': spec.param_aliases,
            'entrypoint': entrypoint}


def main():
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name', nargs='?', help='Tool/recipe name; omit to list available names')
    args = parser.parse_args()
    try:
        result = describe(args.name)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
