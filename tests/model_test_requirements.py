"""Development-test resource checks; scoring/loading errors remain failures."""
import importlib.util
import os
import unittest
from repository_paths import SKILL_ROOT

MODEL_RESOURCES = {
    'azimuth': (('numpy', 'pandas', 'sklearn', 'scipy', 'matplotlib', 'Bio'),
                ('third_party/azimuth/saved_models/V3_model_nopos.pickle',)),
    'deepcpf1': (('numpy', 'torch', 'h5py'),
                ('third_party/deepcpf1/Seq_deepCpf1_weights.h5',
                 'third_party/deepcpf1/DeepCpf1_weights.h5')),
}


def requires_real_models(*models):
    missing = []
    for model in models:
        dependencies, weights = MODEL_RESOURCES[model]
        missing.extend('module '+name for name in dependencies if importlib.util.find_spec(name) is None)
        missing.extend('weight '+name for name in weights if not (SKILL_ROOT/name).is_file())
    # Explicit opt-in forces execution, including failure if resources are absent.
    # Installed resources run automatically without the historical opt-in flag.
    available = not missing or os.environ.get('SNAPGENE_RUN_REAL_MODELS') == '1'
    return unittest.skipUnless(available, 'Optional model resources unavailable: ' + ', '.join(sorted(set(missing))))
