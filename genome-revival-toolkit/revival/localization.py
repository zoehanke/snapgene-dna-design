"""Project-owned titles; generic Trace remains unaware of this project."""
from contextlib import contextmanager
from evidence_trace.localization import language_scope as core_language_scope, translation_scope

TRANSLATIONS = {
    'Genome Revival：任务过程与证据': 'Genome Revival: workflow and evidence',
    'Genome Revival Toolkit 结果': 'Genome Revival Toolkit result',
}


@contextmanager
def language_scope(language=None):
    with core_language_scope(language), translation_scope(TRANSLATIONS):
        yield
