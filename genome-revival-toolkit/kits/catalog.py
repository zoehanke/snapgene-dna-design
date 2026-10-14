"""Project application descriptors from local Kit manifests, never a fixed list."""
from functools import lru_cache
import importlib
from pathlib import Path

from core.kits import KitCatalog

ROOT=Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def applications():
    catalog=KitCatalog([ROOT])
    # Invalid neighbors remain visible through Core catalog diagnostics; they
    # do not hide the other valid applications.
    result={}
    kits=sorted(catalog.kits.values(),key=lambda k:k.manifest.get('metadata',{}).get('order',999))
    for kit in kits:
        command=kit.manifest.get('metadata',{}).get('command')
        if not command:continue
        if command in result:raise ValueError('Duplicate Toolkit application command: '+command)
        result[command]={'directory':kit.directory,'manifest':kit.manifest}
    return result


def application(command):
    return applications()[command]


def request_fields(command):
    return set(application(command)['manifest']['input_schema']['definitions']['request']['properties'])


def application_function(command,field):
    app=application(command);metadata=app['manifest']['metadata']
    # Existing import aliases retain callable identity, shared globals and patches.
    if field=='workflow_entry' and metadata.get('legacy_module'):
        module=importlib.import_module(metadata['legacy_module'])
        return getattr(module,metadata[field].rsplit(':',1)[1])
    filename,symbol=metadata[field].rsplit(':',1)
    path=(app['directory']/filename).resolve()
    if not path.is_relative_to(app['directory']):raise ValueError('Application entry outside its Kit.')
    relative=path.relative_to(ROOT).with_suffix('').as_posix().replace('/','.')
    return getattr(importlib.import_module('kits.'+relative),symbol)


def stage_application(stage):
    for command,app in applications().items():
        if stage.startswith(command+'.') or stage=='toolkit.'+command:return app
    return None


def trace_labels():
    labels={'toolkit.context':'核对项目材料与当前文件版本','toolkit.export':'保存本次报告与技术记录','outcome':'记录本次实际结果'}
    for app in applications().values():labels.update(app['manifest']['metadata']['trace_labels'])
    return labels


def trace_skip():
    return {stage for app in applications().values() for stage in app['manifest']['metadata']['trace_skip']}


def strip_trace_prefix(stage):
    app=stage_application(stage)
    prefix=app['manifest']['metadata']['trace_strip_prefix'] if app else ''
    return stage.removeprefix(prefix) if prefix else stage


def cli_description():
    parts=[app['manifest']['metadata']['cli_description'] for app in applications().values()]
    return 'Genome Revival Toolkit: '+', '.join(parts[:-1])+' and '+parts[-1]+'.'
