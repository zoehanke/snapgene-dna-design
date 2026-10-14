"""Local Kit metadata/loading over the existing tool and Trace interfaces."""
from __future__ import annotations

import ast
import copy
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
from types import ModuleType

from jsonschema import Draft7Validator
from core.errors import CoreError

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_POINTS = {
    'tools': 'IMPLEMENTED', 'pipeline': 'NOT_IMPLEMENTED',
    'gates': 'NOT_IMPLEMENTED', 'rules': 'NOT_IMPLEMENTED',
    'handlers': 'NOT_IMPLEMENTED', 'recipes': 'NOT_IMPLEMENTED',
    'contracts': 'NOT_IMPLEMENTED', 'references': 'NOT_IMPLEMENTED',
}
V2_EXTENSION_POINTS = {**EXTENSION_POINTS, 'pipeline':'IMPLEMENTED', 'gates':'IMPLEMENTED', 'rules':'IMPLEMENTED'}


class KitError(CoreError):
    """A metadata/loading failure, not a biological validation result."""


def _fail(code, message, **details):
    raise KitError(code, message, details=details)


def _version(text):
    if not isinstance(text, str) or not re.fullmatch(r'\d+\.\d+\.\d+', text):
        _fail('KIT_VERSION_INVALID', 'Use a stable numeric major.minor.patch version.')
    return tuple(int(n) for n in text.split('.'))


def _entry(root, text):
    filename, symbol = text.rsplit(':', 1)
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        _fail('KIT_ENTRY_MISSING', 'Kit entrypoint file is missing or outside its directory.', entrypoint=text)
    try:
        tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=filename)
    except (OSError, UnicodeError, SyntaxError) as error:
        _fail('KIT_ENTRY_INVALID', 'Kit entrypoint is not readable Python.', entrypoint=text, reason=type(error).__name__)
    if not any(isinstance(node, ast.FunctionDef) and node.name == symbol for node in tree.body):
        _fail('KIT_ENTRY_MISSING', 'Kit entrypoint must name a module-level synchronous function.', entrypoint=text)
    return path, symbol


@dataclass(frozen=True)
class Kit:
    directory: Path
    manifest: dict
    manifest_sha256: str
    origin: str

    @property
    def name(self):
        return self.manifest['name']

    def receipt(self):
        return {'name': self.name, 'version': self.manifest['version'],
                'manifest_sha256': self.manifest_sha256,
                'source': self.directory.as_uri(), 'origin': self.origin}


class KitCatalog:
    """Metadata discovery never imports code; loading requires explicit use."""

    def __init__(self, directories=(), *, bundled_directory=None, core_version=None):
        self.kits = {}
        self.errors = []
        self._loaded = {}
        self._registrations = {}
        self._bindings = {}
        self._gates = {}
        self._rules = {}
        self.core_version = core_version or (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self._schemas = {version:Draft7Validator(json.loads((ROOT / ('schemas/'+version+'.json')).read_text(encoding='utf-8')))
                         for version in ('kit-v1','kit-v2')}
        bundled = Path(bundled_directory) if bundled_directory is not None else ROOT / 'kits'
        roots = [(bundled, 'bundled')] if bundled.exists() else []
        roots += [(Path(path), 'external') for path in directories]
        seen = set()
        for directory, origin in roots:
            directory = directory.resolve()
            candidates = [directory] if (directory / 'kit.json').is_file() or (directory / 'SKILL.md').is_file() else (
                sorted(p for p in directory.iterdir() if p.is_dir() and ((p/'kit.json').exists() or (p/'SKILL.md').exists()))
                if directory.is_dir() else [directory])
            for candidate in candidates:
                candidate = candidate.resolve()
                if candidate in seen:
                    continue
                seen.add(candidate)
                try:
                    kit = self._read(candidate, origin)
                    if kit.name in self.kits:
                        _fail('KIT_NAME_CONFLICT', 'Kit name is already discovered; it is not overridden.', name=kit.name)
                    self.kits[kit.name] = kit
                except KitError as error:
                    self.errors.append({'directory': str(candidate), **error.to_dict()})

    def _read(self, directory, origin):
        path = directory / 'kit.json'
        try:
            raw = path.read_bytes()
            data = json.loads(raw.decode('utf-8-sig'))
        except (OSError, UnicodeError, ValueError) as error:
            _fail('KIT_MANIFEST_INVALID', 'Kit manifest is missing or unreadable JSON.', reason=type(error).__name__)
        schema=self._schemas.get(data.get('schema_version')) if isinstance(data,dict) else None
        if schema is None:
            _fail('KIT_MANIFEST_INVALID','Kit manifest needs a supported schema_version (kit-v1 or kit-v2).')
        errors = sorted(schema.iter_errors(data), key=lambda e: str(list(e.path)))
        if errors:
            first = errors[0]
            _fail('KIT_MANIFEST_INVALID', first.message, field=list(first.path))
        minimum, maximum, current = (_version(data['core_version']['minimum']),
                                     _version(data['core_version']['maximum_exclusive']),
                                     _version(self.core_version))
        if minimum >= maximum:
            _fail('KIT_VERSION_INVALID', 'Core version range must have minimum below maximum_exclusive.')
        if not minimum <= current < maximum:
            _fail('KIT_CORE_INCOMPATIBLE', 'Kit requires a different Core version range.',
                  required=data['core_version'], actual=self.core_version)
        if not (directory / 'SKILL.md').is_file():
            _fail('KIT_SKILL_MISSING', 'Kit needs its own SKILL.md.')
        try:
            Draft7Validator.check_schema(data['input_schema'])
            if data['input_schema'].get('type') != 'object':
                _fail('KIT_INPUT_SCHEMA_INVALID', 'Kit input_schema must describe an object.')
            Draft7Validator(data['input_schema']).validate(data['input_example'])
        except KitError:
            raise
        except Exception as error:
            _fail('KIT_INPUT_SCHEMA_INVALID', 'Kit input schema/example is invalid.', reason=type(error).__name__)
        _entry(directory, data['entrypoint'])
        names = set()
        points=V2_EXTENSION_POINTS if data['schema_version']=='kit-v2' else EXTENSION_POINTS
        for contribution in data['contributions']:
            target = contribution['target']
            if points[target] != 'IMPLEMENTED':
                _fail('KIT_CONTRIBUTION_UNSUPPORTED', 'Contribution point is not implemented in this phase.', target=target)
            if contribution['name'] in names:
                _fail('KIT_TOOL_CONFLICT', 'Duplicate local tool contribution.', name=contribution['name'])
            names.add(contribution['name'])
            content=contribution['content']
            if not contribution['source'].strip():
                _fail('KIT_CONTRIBUTION_SOURCE_MISSING','Every contribution needs a nonblank source.')
            if target in ('tools','gates'):_entry(directory, content['entrypoint'])
            try:
                if target=='tools':Draft7Validator.check_schema(content['parameters_schema'])
                if target=='pipeline':Draft7Validator.check_schema(content['inputs_schema'])
            except Exception as error:
                _fail('KIT_TOOL_SCHEMA_INVALID', 'Contributed tool schema is invalid.', reason=type(error).__name__)
            if target=='gates':
                scopes=[row['scope'] for row in content['required_scopes']]
                if len(scopes)!=len(set(scopes)):_fail('KIT_GATE_CONFLICT','Gate scopes must be unique.')
                accepted=set()
                for row in content.get('acceptances',[]):
                    if row['scope'] not in scopes or row['scope'] in accepted or not row['source'].strip() or not row['reason'].strip():
                        _fail('KIT_ACCEPTANCE_INVALID','Acceptance needs one declared scope, source and reason.')
                    accepted.add(row['scope'])
            if target=='rules':
                from core.kit_contributions import rule_rows
                path=(directory/content['path']).resolve()
                if not path.is_relative_to(directory) or not path.is_file():_fail('KIT_RULE_MISSING','Rule file is missing or outside its Kit.')
                try:rule_rows(path,content['fields'])
                except CoreError as error:_fail(error.error_code,error.message,**error.details)
        return Kit(directory, data, hashlib.sha256(raw).hexdigest(), origin)

    def describe(self, name=None):
        if name is None:
            return {'kits': [{'name': k.name, 'version': k.manifest['version'],
                             'tools': [self.contribution_name(k,c) for c in k.manifest['contributions'] if c['target'] in ('tools','pipeline')],
                             **k.receipt()} for k in self.kits.values()],
                    'errors': self.errors, 'extension_points': dict(V2_EXTENSION_POINTS)}
        kit = self._require(name)
        return {**kit.receipt(), 'manifest': copy.deepcopy(kit.manifest),
                'skill': str(kit.directory/'SKILL.md'), 'extension_points': dict(V2_EXTENSION_POINTS if kit.manifest['schema_version']=='kit-v2' else EXTENSION_POINTS)}

    @staticmethod
    def contribution_name(kit,row):
        return 'kit.'+kit.name+'.'+('' if row['target']=='tools' else row['target']+'.')+row['name']

    def _require(self, name):
        if name not in self.kits:
            _fail('KIT_NOT_FOUND', 'Kit is not available; inspect catalog diagnostics.', name=name, errors=self.errors)
        return self.kits[name]

    def _function(self, kit, entrypoint):
        path, symbol = _entry(kit.directory, entrypoint)
        namespace = '_dna_kit_' + hashlib.sha256((str(kit.directory)+kit.manifest_sha256).encode('utf-8')).hexdigest()[:24]
        if namespace not in sys.modules:
            package = ModuleType(namespace)
            package.__path__ = [str(kit.directory)]
            package.__package__ = namespace
            sys.modules[namespace] = package
        relative = path.relative_to(kit.directory).with_suffix('').as_posix().replace('/', '.')
        module = importlib.import_module(namespace+'.'+relative)
        function = getattr(module, symbol, None)
        if not callable(function):
            _fail('KIT_ENTRY_INVALID', 'Kit entrypoint did not expose its declared callable.', entrypoint=entrypoint)
        return function

    def load(self, name):
        if name in self._loaded:
            return self._loaded[name]
        kit = self._require(name)
        try:
            raw = (kit.directory/'kit.json').read_bytes()
        except OSError as error:
            _fail('KIT_MANIFEST_INVALID', 'Kit manifest became unreadable after discovery.', reason=type(error).__name__)
        if hashlib.sha256(raw).hexdigest() != kit.manifest_sha256:
            _fail('KIT_MANIFEST_CHANGED', 'Kit manifest changed after discovery; rediscover before loading.')
        if self._read(kit.directory, kit.origin).manifest != kit.manifest:
            _fail('KIT_MANIFEST_CHANGED', 'Kit descriptor changed after validation; rediscover before loading.')
        if kit.origin == 'external':
            print('External Kit '+kit.name+': loading Python code with host permissions from the supplied directory.', file=sys.stderr)
        from core.tools.registry import TOOL_REGISTRY, ToolSpec, register_tool
        specs = []
        registered = []
        bindings = []
        gates=[];rules=[]
        try:
            function = self._function(kit, kit.manifest['entrypoint'])
            for row in kit.manifest['contributions']:
                content = row['content']
                tool_name = self.contribution_name(kit,row)
                if row['target']=='gates':
                    gates.append({'name':tool_name,'content':copy.deepcopy(content),'source':row['source'],
                                  'callable':self._function(kit,content['entrypoint'])})
                    continue
                if row['target']=='rules':
                    from core.kit_contributions import rule_rows
                    rules.append({'name':tool_name,'fields':content['fields'],'rows':rule_rows(kit.directory/content['path'],content['fields'])})
                    continue
                if tool_name in TOOL_REGISTRY:
                    _fail('KIT_TOOL_CONFLICT', 'Tool name already exists; no override.', name=tool_name)
                if row['target']=='pipeline':
                    from core.kit_contributions import pipeline_callable
                    specs.append(ToolSpec(tool_name,pipeline_callable(content,lambda inputs:self.execution_scope(name,inputs)),'compute',row['description'],
                        {'type':'object','properties':{'inputs':content['inputs_schema']}}))
                else:
                    specs.append(ToolSpec(tool_name, self._function(kit, content['entrypoint']),
                        content['category'], row['description'], content['parameters_schema']))
            for spec in specs:
                original = spec._function
                module = sys.modules.get(original.__module__)
                aliases = [key for key, value in vars(module).items() if value is original] if module else []
                register_tool(spec)
                registered.append(spec.name)
                bindings.extend((module, key, original, spec.callable) for key in aliases)
        except (Exception, SystemExit) as error:
            for tool_name in registered:
                TOOL_REGISTRY.pop(tool_name, None)
            self._restore_bindings(bindings)
            if isinstance(error, KitError):
                raise
            _fail('KIT_LOAD_FAILED', 'Kit Python code or callable contract could not be loaded.', name=name, reason=type(error).__name__)
        self._registrations[name] = registered
        self._bindings[name] = bindings
        self._loaded[name] = function
        self._gates[name]=gates
        self._rules[name]=rules
        from evidence_trace.runtime import observe_value
        observe_value('kit.load', kit.receipt())
        return function

    def load_tools(self):
        for name in list(self.kits):
            try:
                self.load(name)
            except KitError as error:
                self.errors.append({'name': name, **error.to_dict()})
        return self.describe()

    def unload(self, name):
        """Remove only this catalog's tool registrations; imported Python is not sandboxed."""
        from core.tools.registry import TOOL_REGISTRY
        for tool_name in self._registrations.pop(name, []):
            TOOL_REGISTRY.pop(tool_name, None)
        self._restore_bindings(self._bindings.pop(name, []))
        self._loaded.pop(name, None)
        self._gates.pop(name,None)
        self._rules.pop(name,None)

    @staticmethod
    def _restore_bindings(bindings):
        for module, key, original, wrapper in reversed(bindings):
            if getattr(module, key, None) is wrapper:
                setattr(module, key, original)

    def validate_inputs(self, name, inputs):
        kit = self._require(name)
        errors = list(Draft7Validator(kit.manifest['input_schema']).iter_errors(inputs))
        if errors:
            _fail('KIT_INPUT_INVALID', errors[0].message, field=list(errors[0].path))

    def run(self, name, inputs, out_dir):
        self.validate_inputs(name, inputs)
        function=self.load(name)
        with self.execution_scope(name,inputs):
            result = function(inputs, Path(out_dir))
            from core.kit_contributions import active_validation
            context=active_validation()
            context['terminal_status']=result.get('status') if isinstance(result,dict) else None
            if isinstance(result,dict) and self._gates[name]:
                result['kit_gate_results']=list(context['results'].values())
        if not isinstance(result, dict):
            _fail('KIT_RESULT_INVALID', 'Kit entrypoint must return a JSON object.')
        try:
            encoded = json.dumps(result, allow_nan=False)
            if json.loads(encoded) != result:
                raise ValueError('Result changes under JSON serialization.')
        except (TypeError, ValueError, OverflowError, RecursionError) as error:
            _fail('KIT_RESULT_INVALID', 'Kit entrypoint must return a JSON object with finite JSON values.', reason=type(error).__name__)
        return result

    @contextmanager
    def execution_scope(self,name,inputs):
        from core.kit_contributions import validation_scope,active_validation
        if name not in self._loaded:self.load(name)
        active=active_validation()
        receipt=self._require(name).receipt()
        parent=active if active and active['kit']==receipt else None
        with validation_scope(receipt,inputs,self._gates[name]) as context:
            try:yield
            finally:
                if parent:
                    parent['evaluated'].update(context['evaluated'])
                    parent['results'].update(context['results'])
            missing=[gate['name'] for gate in context['gates'] if gate['name'] not in context['evaluated']]
            if missing:_fail('KIT_GATE_NOT_EXECUTED','A declared mandatory gate was not executed.',gates=missing)
            if context.get('terminal_status') not in ('failed','incomplete','blocked'):
                from core.kit_contributions import require_gate_results
                require_gate_results(context['results'].values())

    def gate(self,name,gate_name,*,candidate,sources,requirements=None,steps=(),inputs=None):
        from core.kit_contributions import evaluate_gate
        self.load(name)
        target=next((gate for gate in self._gates[name] if gate['name'].endswith('.'+gate_name)),None)
        if target is None:_fail('KIT_GATE_NOT_FOUND','Declared gate is not available.',name=gate_name)
        return evaluate_gate(target,candidate=candidate,sources=sources,requirements=requirements,steps=steps,inputs=inputs)

    def rules(self,name,rule_name=None):
        kit=self._require(name)
        from core.kit_contributions import rule_rows
        result=[]
        for row in kit.manifest['contributions']:
            if row['target']=='rules' and (rule_name is None or row['name']==rule_name):
                result.append({'name':self.contribution_name(kit,row),'fields':row['content']['fields'],
                              'rows':rule_rows(kit.directory/row['content']['path'],row['content']['fields'])})
        return result

    def evaluate_rules(self,name,rule_name,trigger,context):
        from core.kit_contributions import evaluate_rule_rows
        entries=self.rules(name,rule_name)
        if not entries:_fail('KIT_RULE_NOT_FOUND','Declared rule contribution is not available.',name=rule_name)
        return evaluate_rule_rows(entries[0]['rows'],entries[0]['fields'],trigger,context,name)
