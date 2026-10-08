"""Actual step execution, Recipe adaptation and locally replayable facts.

No planner, task-kind choice or global state: hosts remain free to choose each step.
"""
from __future__ import annotations
import copy
from contextvars import ContextVar
from dataclasses import dataclass, field, fields
import functools
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import sys
from typing import get_type_hints, get_args
from Bio.SeqRecord import SeqRecord
from core.errors import CoreError, PlanningError
from core.models.molecule import Molecule, as_molecule
from core.tools.result import ToolResult, to_wire

_operation_sink=ContextVar('workflow_operations',default=None)


def record_operation(method,params,result):
    sink=_operation_sink.get()
    if sink is not None:
        sink.append({'method':method,'params':to_wire(params),'result':result.to_dict()})


def _digest(value):
    return hashlib.sha256(json.dumps(to_wire(value),sort_keys=True,ensure_ascii=False,
                                    separators=(',',':')).encode('utf-8')).hexdigest()


def runtime_conditions():
    """Bind implementation and relevant computation environment, not a sample name."""
    from importlib.metadata import version
    root=Path(__file__).resolve().parents[1]
    code=hashlib.sha256()
    for file in sorted(p for folder in ('core','scripts') for p in (root/folder).rglob('*.py')):
        code.update(file.relative_to(root).as_posix().encode('utf-8'))
        code.update(file.read_bytes().replace(b'\r\n',b'\n'))
    from core.tools.primer3_backend import discover_primer3_core
    executable=discover_primer3_core()
    primer3={'path':str(executable),'sha256':hashlib.sha256(Path(executable).read_bytes()).hexdigest()} if executable else None
    return {'implementation_sha256':code.hexdigest(),'python':platform.python_version(),
            'biopython':version('biopython'),'primer3_py':version('primer3-py'),'primer3_core':primer3,
            'backend_configuration':{key:os.environ.get(key) for key in ('PRIMER3_CORE','CAS_OFFINDER_EXE','CAS_OFFINDER_EXE_V3')}}


@functools.lru_cache(maxsize=16)
def _recipe_spec(name):
    import core.recipes as recipes
    from core.recipes.contract import RecipeResult
    from core.tools.registry import ToolSpec
    fn=getattr(recipes,name,None)
    if name not in recipes.__all__ or not name.startswith('recipe_') or not callable(fn):
        return None
    declaration=next((d for d in recipes.GET_RECIPE_DEFINITIONS() if d['name']==name),{})
    @functools.wraps(fn)
    def adapted(*args,**params):
        result=fn(*args,**params)
        if not isinstance(result,RecipeResult):
            raise TypeError('Recipe does not implement RecipeResult')
        metadata={f.name:getattr(result,f.name) for f in fields(result)
                  if f.name not in ('products','analysis','checks','details')}
        analysis={**result.analysis,**metadata,'details':result.details,'method_analysis':result.analysis,
                  'preparation':result.details.get('preparation',[])}
        return ToolResult(products=result.products,analysis=analysis,checks=result.checks)
    from Bio.Seq import Seq
    adapted.__annotations__=get_type_hints(fn,globalns={**fn.__globals__,'SeqRecord':SeqRecord,'Seq':Seq})
    # ToolSpec derives shape/defaults from this real wrapped signature.
    return ToolSpec(name,adapted,'compute',inspect.getdoc(fn) or name,
                    declaration.get('parameters',{'type':'object','properties':{}}))


def get_method(name):
    from core.tools import get_tool
    return get_tool(name) or _recipe_spec(name if name.startswith('recipe_') else 'recipe_'+name)


def method_definitions():
    import core.recipes as recipes
    from core.tools import TOOL_REGISTRY
    names=list(TOOL_REGISTRY)+[n for n in recipes.__all__ if n.startswith('recipe_')]
    return [get_method(name).to_definition() for name in names]


def _materials(value):
    if isinstance(value,Molecule):
        return [value]
    if isinstance(value,SeqRecord) or (isinstance(value,dict) and 'sequence' in value):
        return [as_molecule(value)]
    if isinstance(value,(str,Path)):
        from core.models.molecule import ProteinSequence
        from core.tools.sequence_ops import DNA_IUPAC_ALPHABET
        if isinstance(value,str) and not isinstance(value,ProteinSequence):
            text=''.join(value.split()).upper()
            if text and set(text)<=DNA_IUPAC_ALPHABET:
                return [as_molecule(value)]
        try:
            if len(str(value))<1024 and Path(value).is_file():
                return [as_molecule(value)]
        except OSError:
            pass
    if isinstance(value,dict):
        return [m for item in value.values() for m in _materials(item)]
    if isinstance(value,(tuple,list)):
        return [m for item in value for m in _materials(item)]
    return []


@dataclass
class StepExecution:
    step_id: str
    method: str
    params: dict
    result: ToolResult | None = None
    error: dict | None = None
    input_versions: list[str] = field(default_factory=list)
    source_versions: dict = field(default_factory=dict)
    conditions: dict = field(default_factory=dict)
    operations: list = field(default_factory=list)
    requirements: dict = field(default_factory=dict)
    goal_coverage: dict = field(default_factory=dict)

    @property
    def status(self):
        return 'failed' if self.error else 'completed'

    def to_dict(self):
        return {'step_id':self.step_id,'method':self.method,'status':self.status,
                'params':to_wire(self.params),'result':to_wire(self.result),'error':self.error,
                'input_versions':self.input_versions,'source_versions':self.source_versions,
                'conditions':self.conditions,'operations':self.operations,
                'requirements':to_wire(self.requirements),'goal_coverage':to_wire(self.goal_coverage),
                'task_completion':self.task_completion}

    @property
    def task_completion(self):
        from core.requirements import completion_report
        return completion_report(self.goal_coverage,local_success=not self.error,final=False)


def run_step(method, params, *, step_id='step', sources=None, previous=(), requirements=None, _history_checked=False):
    """Run one discoverable method; return real results or a concrete retained failure."""
    record=StepExecution(step_id,method,copy.deepcopy(params))
    try:
        from core.requirements import inherit_requirements, goal_coverage, check_goal_constraints
        record.requirements=inherit_requirements(previous,requirements)
        record.goal_coverage=goal_coverage(record.requirements,[])
        from core.handlers.composite_pipeline import _resolve_param_val, _resolve_source_records
        sources=_resolve_source_records(sources or {})
        if previous and not _history_checked:
            from core.workflow_validation import replay_steps
            previous=replay_steps(previous,sources)
        completed={row.step_id:row.result for row in previous if row.status=='completed'}
        if not step_id or step_id in completed or step_id in sources:
            raise PlanningError('INVALID_STEP_ID','Step id must be unique and distinct from sources')
        spec=get_method(method)
        if spec is None:
            raise PlanningError('UNKNOWN_METHOD',f'Unknown tool or Recipe: {method}')
        if spec.category not in ('compute','inspect'):
            raise PlanningError('PIPELINE_SIDE_EFFECT','Write/network/external methods use their explicit file boundary')
        resolved=_resolve_param_val(params,completed,sources)
        bound=spec.bind_arguments(resolved)
        hints=get_type_hints(spec._function)
        for name,value in list(bound.arguments.items()):
            annotation=hints.get(name)
            if SeqRecord in get_args(annotation) or annotation is SeqRecord or isinstance(value,SeqRecord):
                if value is not None:
                    bound.arguments[name]=as_molecule(sources.get(value,value) if isinstance(value,str) else value)
        def nested_materials(value):
            if isinstance(value,dict):
                if 'sequence' in value:return as_molecule(value)
                return {k:as_molecule(sources.get(v,v) if isinstance(v,str) else v) if k in ('template','source','vector') and isinstance(v,(str,Path,SeqRecord,dict))
                        else nested_materials(v) for k,v in value.items()}
            if isinstance(value,list):return [nested_materials(v) for v in value]
            return value
        record.params={name:nested_materials(value) if name=='fragments' else value for name,value in bound.arguments.items()}
        # list[MoleculeInput] must have the same semantics as a top-level material.
        for name,value in list(record.params.items()):
            hint=hints.get(name)
            args=get_args(hint)
            if isinstance(value,list) and args and SeqRecord in get_args(args[0]):
                record.params[name]=[as_molecule(sources.get(v,v) if isinstance(v,str) else v) for v in value]
        record.input_versions=[m.record_version for m in _materials(record.params)]
        record.source_versions={name:m.record_version for name,m in sources.items()}
        record.conditions=runtime_conditions()
        token=_operation_sink.set(record.operations)
        try:
            record.result=spec.execute(**record.params)
            if len(record.result.products)==1 and record.requirements:
                product=record.result.only_product()
                traces,_,checks=check_goal_constraints(record.requirements,product,sources)
                record.goal_coverage=goal_coverage(record.requirements,traces,checks=checks,subject_version=product.record_version)
        finally:
            _operation_sink.reset(token)
    except Exception as exc:
        record.error=exc.to_dict() if isinstance(exc,CoreError) else {
            'status':'failed','error_code':'STEP_EXECUTION_FAILED','message':str(exc),
            'details':{'exception':type(exc).__name__},'write_authoritative_artifact':False}
    return record


def product_summaries(result):
    """Summarize real products without silently selecting one or turning QC into DNA."""
    return [{'product_index':index,'length':len(m),'topology':m.topology,
             'strandedness':m.strandedness,'ends':m.to_dict()['ends'],
             'record_version':m.record_version,'source_versions':[r['record_version'] for r in m.source_refs],
             'features':[f.qualifiers.get('label',f.qualifiers.get('gene',[f.type])) for f in m.features]}
            for index,m in enumerate(result.products)]


def recipe_result(result):
    """Reconstitute the existing report object without recomputing or copying DNA."""
    from core.recipes.contract import RecipeResult
    values={f.name:result.analysis[f.name] for f in fields(RecipeResult)
            if f.name not in ('products','analysis','checks','details') and f.name in result.analysis}
    return RecipeResult(**values,products=result.products,checks=result.checks,
                        analysis=result.analysis.get('method_analysis',{}),details=result.analysis.get('details',{}))
