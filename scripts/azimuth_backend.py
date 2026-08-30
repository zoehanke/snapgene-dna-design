# -*- coding: utf-8 -*-
"""azimuth_backend.py - Real Doench-2016 / Azimuth SpCas9 scoring.

The official Azimuth 2.0 package is Python 2 code and its saved
scikit-learn pickle predates modern scikit-learn, so this backend:

1. imports the converted Azimuth featurization code from
   ``third_party/azimuth`` (BSD licensed),
2. loads ``saved_models/V3_model_nopos.pickle`` with a compatibility
   unpickler that captures the GradientBoostingRegressor tree state,
3. performs the exact gradient-boosting inference with numpy.

Scores are the model's raw predictions in [0, 1].
"""
import pathlib
import sys

import numpy as np
import pandas

THIRD_PARTY = pathlib.Path(__file__).resolve().parents[1] / "third_party" / "azimuth"
MODEL_PICKLE = THIRD_PARTY / "saved_models" / "V3_model_nopos.pickle"


class BackendUnavailable(RuntimeError):
    pass


class _CaptureTree:
    def __new__(cls, n_features, n_classes, n_outputs):
        obj = object.__new__(cls)
        obj.args = (n_features, n_classes, n_outputs)
        obj.state = None
        return obj

    def __setstate__(self, state):
        self.state = state


class _CaptureDecisionTree:
    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj.state = None
        return obj

    def __setstate__(self, state):
        self.state = state


class _CaptureGBR:
    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj.state = None
        return obj

    def __setstate__(self, state):
        self.state = state


class _CaptureMean:
    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj.state = None
        return obj

    def __setstate__(self, state):
        self.state = state


class _CompatibilityUnpickler(__import__("pickle").Unpickler):
    def find_class(self, module, name):
        if module == "sklearn.tree._tree" and name == "Tree":
            return _CaptureTree
        if module == "sklearn.tree.tree" and name == "DecisionTreeRegressor":
            return _CaptureDecisionTree
        if module == "sklearn.ensemble.gradient_boosting":
            return {
                "GradientBoostingRegressor": _CaptureGBR,
                "MeanEstimator": _CaptureMean,
            }.get(name, type(name, (), {}))
        return super().find_class(module, name)


class AzimuthPredictor:
    """Real Azimuth V3 model (Doench 2016) with its original 627 features."""

    def __init__(self, model_path=None, featurization_root=None):
        self.model_path = pathlib.Path(model_path or MODEL_PICKLE)
        self.featurization_root = pathlib.Path(
            featurization_root or THIRD_PARTY)
        if not self.model_path.exists():
            raise BackendUnavailable(
                "AZIMUTH_MODEL_NOT_FOUND: %s" % self.model_path)
        package_parent = str(pathlib.Path(self.featurization_root).parent)
        if package_parent not in sys.path:
            sys.path.insert(0, package_parent)
        try:
            import azimuth.features.featurization as feat
            import azimuth.util as az_util
        except Exception as error:  # noqa: BLE001
            raise BackendUnavailable(
                "AZIMUTH_FEATURIZATION_UNAVAILABLE: %s" % error)
        self._feat = feat
        self._az_util = az_util
        import pickle
        with open(self.model_path, "rb") as handle:
            self._model, self._learn_options = _CompatibilityUnpickler(
                handle, encoding="latin1").load()
        self._state = self._model.state

    @property
    def model_version(self):
        return "Azimuth-V3/Doench-2016"

    def predict(self, sequences):
        """Score one or more 30mer contexts.

        ``sequences`` must be 30 bp: 4 upstream + 20 protospacer + NGG +
        3 downstream.
        """
        if isinstance(sequences, str):
            sequences = [sequences]
        for index, seq in enumerate(sequences):
            seq = str(seq).upper()
            if len(seq) != 30:
                raise ValueError(
                    "AZIMUTH_CONTEXT_LENGTH: sequence %d has length %d, "
                    "expected 30" % (index, len(seq)))
            if not all(base in "ACGT" for base in seq):
                raise ValueError(
                    "AZIMUTH_CONTEXT_BASE: sequence %d contains non-ACGT "
                    "bases" % index)
        frame = pandas.DataFrame(
            columns=["30mer", "Strand"],
            data=list(zip([str(s).upper() for s in sequences],
                          ["NA"] * len(sequences))))
        gene_position = pandas.DataFrame(
            columns=["Percent Peptide", "Amino Acid Cut position"])
        feature_sets = self._feat.featurize_data(
            frame, self._learn_options, pandas.DataFrame(), gene_position,
            pam_audit=True, length_audit=False)
        inputs, _dim, _dimsum, _feature_names = \
            self._az_util.concatenate_feature_sets(feature_sets)
        return self._gbr_predict(inputs.astype(np.float64))

    def _gbr_predict(self, inputs):
        state = self._state
        init = float(np.asarray(state["init_"].state["mean"]))
        learning_rate = float(state["learning_rate"])
        predictions = np.full((inputs.shape[0], 1), init, dtype=np.float64)
        for stage in range(state["estimators_"].shape[0]):
            tree = state["estimators_"][stage, 0].state["tree_"].state
            predictions += learning_rate * self._tree_predict(
                tree, inputs)
        return predictions.ravel().tolist()

    @staticmethod
    def _tree_predict(tree_state, inputs):
        nodes = tree_state["nodes"]
        left = nodes["left_child"]
        right = nodes["right_child"]
        features = nodes["feature"]
        thresholds = nodes["threshold"]
        values = tree_state["values"]
        indices = np.zeros(inputs.shape[0], dtype=np.int64)
        # Trees in this model have max_depth == 3; four levels are enough.
        for _level in range(4):
            node = indices
            internal = left[node] != -1
            if not np.any(internal):
                break
            rows = np.nonzero(internal)[0]
            go_left = inputs[rows, features[node[rows]]] <= thresholds[node[rows]]
            indices[rows[go_left]] = left[node[rows[go_left]]]
            indices[rows[~go_left]] = right[node[rows[~go_left]]]
        return values[indices, 0, 0].reshape(-1, 1)


_PREDICTOR = None


def score_30mers(sequences):
    """Return list of Azimuth V3 scores for 30mer contexts."""
    global _PREDICTOR
    if _PREDICTOR is None:
        _PREDICTOR = AzimuthPredictor()
    return _PREDICTOR.predict(sequences)
