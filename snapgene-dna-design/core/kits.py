"""Local Kit metadata/loading over the existing tool and Trace interfaces."""
from __future__ import annotations

import ast
import copy
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
        self.core_version = core_version or (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self._schema = Draft7Validator(json.loads((ROOT / 'schemas/kit-v1.json').read_text(encoding='utf-8')))
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
        errors = sorted(self._schema.iter_errors(data), key=lambda e: str(list(e.path)))
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
        for contribution in data['contributions']:
            target = contribution['target']
            if EXTENSION_POINTS[target] != 'IMPLEMENTED':
                _fail('KIT_CONTRIBUTION_UNSUPPORTED', 'Contribution point is not implemented in this phase.', target=target)
            if contribution['name'] in names:
                _fail('KIT_TOOL_CONFLICT', 'Duplicate local tool contribution.', name=contribution['name'])
            names.add(contribution['name'])
            _entry(directory, contribution['content']['entrypoint'])
            try:
                Draft7Validator.check_schema(contribution['content']['parameters_schema'])
            except Exception as error:
                _fail('KIT_TOOL_SCHEMA_INVALID', 'Contributed tool schema is invalid.', reason=type(error).__name__)
        return Kit(directory, data, hashlib.sha256(raw).hexdigest(), origin)

    def describe(self, name=None):
        if name is None:
            return {'kits': [{'name': k.name, 'version': k.manifest['version'],
                             'tools': ['kit.'+k.name+'.'+c['name'] for c in k.manifest['contributions']],
                             **k.receipt()} for k in self.kits.values()],
                    'errors': self.errors, 'extension_points': dict(EXTENSION_POINTS)}
        kit = self._require(name)
        return {**kit.receipt(), 'manifest': copy.deepcopy(kit.manifest),
                'skill': str(kit.directory/'SKILL.md'), 'extension_points': dict(EXTENSION_POINTS)}

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
        if hashlib.sha256((kit.directory/'kit.json').read_bytes()).hexdigest() != kit.manifest_sha256:
            _fail('KIT_MANIFEST_CHANGED', 'Kit manifest changed after discovery; rediscover before loading.')
        if self._read(kit.directory, kit.origin).manifest != kit.manifest:
            _fail('KIT_MANIFEST_CHANGED', 'Kit descriptor changed after validation; rediscover before loading.')
        if kit.origin == 'external':
            print('External Kit '+kit.name+': loading Python code with host permissions from the supplied directory.', file=sys.stderr)
        from core.tools.registry import TOOL_REGISTRY, ToolSpec, register_tool
        specs = []
        registered = []
        try:
            function = self._function(kit, kit.manifest['entrypoint'])
            for row in kit.manifest['contributions']:
                content = row['content']
                tool_name = 'kit.'+kit.name+'.'+row['name']
                if tool_name in TOOL_REGISTRY:
                    _fail('KIT_TOOL_CONFLICT', 'Tool name already exists; no override.', name=tool_name)
                specs.append(ToolSpec(tool_name, self._function(kit, content['entrypoint']),
                    content['category'], row['description'], content['parameters_schema']))
            for spec in specs:
                register_tool(spec)
                registered.append(spec.name)
        except Exception as error:
            for tool_name in registered:
                TOOL_REGISTRY.pop(tool_name, None)
            if isinstance(error, KitError):
                raise
            _fail('KIT_LOAD_FAILED', 'Kit Python code or callable contract could not be loaded.', name=name, reason=type(error).__name__)
        self._registrations[name] = registered
        self._loaded[name] = function
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
        self._loaded.pop(name, None)

    def validate_inputs(self, name, inputs):
        kit = self._require(name)
        errors = list(Draft7Validator(kit.manifest['input_schema']).iter_errors(inputs))
        if errors:
            _fail('KIT_INPUT_INVALID', errors[0].message, field=list(errors[0].path))

    def run(self, name, inputs, out_dir):
        self.validate_inputs(name, inputs)
        result = self.load(name)(inputs, Path(out_dir))
        if not isinstance(result, dict):
            _fail('KIT_RESULT_INVALID', 'Kit entrypoint must return a JSON object.')
        return result
