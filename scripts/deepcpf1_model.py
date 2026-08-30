# -*- coding: utf-8 -*-
"""deepcpf1_model.py - Real DeepCpf1 (Kim et al. 2018) AsCas12a scoring.

Loads the published DeepCpf1 Keras weights (shipped by Bioconductor
CRISPRseek, Artistic License 2.0) and evaluates the exact network
architecture with PyTorch.  Input semantics:

    34 bp = 4 bp upstream flank + 4 bp PAM (TTTV) + 20 bp gRNA
            + 6 bp downstream flank

The sequence-only model output is divided by 100 (matching CRISPRseek's
``deepCpf1``), yielding a score in [0, 1].  The chromatin-accessibility
variant is available through ``predict_with_chromatin`` and its output is
multiplied by 3 before the /100 scaling, exactly as in CRISPRseek.
"""
import pathlib

import numpy as np

THIRD_PARTY = pathlib.Path(__file__).resolve().parents[1] / "third_party" / "deepcpf1"
SEQ_WEIGHTS = THIRD_PARTY / "Seq_deepCpf1_weights.h5"
CA_WEIGHTS = THIRD_PARTY / "DeepCpf1_weights.h5"


class BackendUnavailable(RuntimeError):
    pass


def _torch():
    try:
        import torch
        return torch
    except Exception as error:  # noqa: BLE001
        raise BackendUnavailable("DEEPCPF1_TORCH_UNAVAILABLE: %s" % error)


def _h5py():
    try:
        import h5py
        return h5py
    except Exception as error:  # noqa: BLE001
        raise BackendUnavailable("DEEPCPF1_H5PY_UNAVAILABLE: %s" % error)


def _onehot(sequences):
    lookup = {"A": 0, "C": 1, "G": 2, "T": 3}
    matrix = np.zeros((len(sequences), 34, 4), dtype=np.float32)
    for i, seq in enumerate(sequences):
        seq = str(seq).upper()
        if len(seq) != 34:
            raise ValueError("DEEPCPF1_CONTEXT_LENGTH: expected 34 bp, got %d"
                             % len(seq))
        for pos, base in enumerate(seq):
            if base not in lookup:
                raise ValueError(
                    "DEEPCPF1_CONTEXT_BASE: non-ACGT base %r at %d" % (base, pos))
            matrix[i, pos, lookup[base]] = 1.0
    return matrix


class _SeqOnlyNet:
    """Exact Keras architecture of DeepCpf1 sequence-only branch."""

    def __init__(self, torch, weights_path):
        torch.manual_seed(0)
        conv = torch.nn.Conv1d(4, 80, 5)
        dense1 = torch.nn.Linear(1200, 80)
        dense2 = torch.nn.Linear(80, 40)
        dense3 = torch.nn.Linear(40, 40)
        dense4 = torch.nn.Linear(40, 1)
        self._layers = [conv, dense1, dense2, dense3, dense4]
        self._load_h5(weights_path)

    def _load_h5(self, weights_path):
        import h5py
        torch = _torch()
        with h5py.File(str(weights_path), "r") as handle:
            kernel = handle["conv1d_1/conv1d_1/kernel:0"][:]
            bias = handle["conv1d_1/conv1d_1/bias:0"][:]
            dense = [(handle["dense_%d/dense_%d/kernel:0" % (i, i)][:],
                      handle["dense_%d/dense_%d/bias:0" % (i, i)][:])
                     for i in range(1, 5)]
        # Keras Conv1D kernel (kernel_size, in_channels, filters) ->
        # PyTorch Conv1d weight (filters, in_channels, kernel_size).
        self._layers[0].weight.data = torch.tensor(
            np.ascontiguousarray(np.transpose(kernel, (2, 1, 0))))
        self._layers[0].bias.data = torch.tensor(np.ascontiguousarray(bias))
        for index, (weight, bias_value) in enumerate(dense, start=1):
            self._layers[index].weight.data = torch.tensor(
                np.ascontiguousarray(weight.T))
            self._layers[index].bias.data = torch.tensor(
                np.ascontiguousarray(bias_value))

    def forward(self, batch):
        torch = _torch()
        conv, dense1, dense2, dense3, dense4 = self._layers
        x = torch.relu(conv(batch))
        x = torch.nn.functional.avg_pool1d(x, 2)
        # Keras Flatten is position-major; PyTorch Conv1d output is
        # channel-major, so permute before flattening.
        x = x.permute(0, 2, 1).flatten(1)
        x = torch.relu(dense1(x))
        x = torch.relu(dense2(x))
        x = torch.relu(dense3(x))
        return dense4(x)


class _SeqCANet:
    """DeepCpf1 model including the chromatin-accessibility branch."""

    def __init__(self, torch, weights_path):
        torch.manual_seed(0)
        conv = torch.nn.Conv1d(4, 80, 5)
        dense1 = torch.nn.Linear(1200, 80)
        dense2 = torch.nn.Linear(80, 40)
        dense3_seq = torch.nn.Linear(40, 40)
        dense3_ca = torch.nn.Linear(1, 40)
        dense_out = torch.nn.Linear(40, 1)
        self._layers = [conv, dense1, dense2, dense3_seq, dense3_ca, dense_out]
        self._load_h5(weights_path)

    def _load_h5(self, weights_path):
        import h5py
        torch = _torch()
        with h5py.File(str(weights_path), "r") as handle:
            kernel = handle["conv1d_1/conv1d_1/kernel:0"][:]
            bias = handle["conv1d_1/conv1d_1/bias:0"][:]
            dense_weights = []
            for i in range(1, 6):
                dense_weights.append((
                    handle["dense_%d/dense_%d/kernel:0" % (i, i)][:],
                    handle["dense_%d/dense_%d/bias:0" % (i, i)][:]))
        self._layers[0].weight.data = torch.tensor(
            np.ascontiguousarray(np.transpose(kernel, (2, 1, 0))))
        self._layers[0].bias.data = torch.tensor(np.ascontiguousarray(bias))
        # dense_1..dense_3 feed the sequence branch, dense_4 feeds the
        # chromatin branch, dense_5 is the final output layer.
        branch_indices = [1, 2, 3, 4, 5]
        for layer_index, weight_index in zip(range(1, 6), branch_indices):
            weight, bias_value = dense_weights[weight_index - 1]
            self._layers[layer_index].weight.data = torch.tensor(
                np.ascontiguousarray(weight.T))
            self._layers[layer_index].bias.data = torch.tensor(
                np.ascontiguousarray(bias_value))

    def forward(self, batch, chromatin):
        torch = _torch()
        conv, dense1, dense2, dense3_seq, dense3_ca, dense_out = self._layers
        x = torch.relu(conv(batch))
        x = torch.nn.functional.avg_pool1d(x, 2)
        x = x.permute(0, 2, 1).flatten(1)
        x = torch.relu(dense1(x))
        x = torch.relu(dense2(x))
        seq_branch = torch.relu(dense3_seq(x))
        ca_branch = torch.relu(dense3_ca(chromatin))
        return dense_out(seq_branch * ca_branch)


_SEQ_NET = None
_CA_NET = None


def _load_seq_net():
    global _SEQ_NET
    if _SEQ_NET is None:
        if not SEQ_WEIGHTS.exists():
            raise BackendUnavailable("DEEPCPF1_WEIGHTS_NOT_FOUND: %s" % SEQ_WEIGHTS)
        _SEQ_NET = _SeqOnlyNet(_torch(), SEQ_WEIGHTS)
    return _SEQ_NET


def _load_ca_net():
    global _CA_NET
    if _CA_NET is None:
        if not CA_WEIGHTS.exists():
            raise BackendUnavailable("DEEPCPF1_CA_WEIGHTS_NOT_FOUND: %s" % CA_WEIGHTS)
        _CA_NET = _SeqCANet(_torch(), CA_WEIGHTS)
    return _CA_NET


def predict_sequence_only(sequences):
    """Score 34bp contexts; returns scores in [0, 1] (raw output / 100)."""
    if isinstance(sequences, str):
        sequences = [sequences]
    matrix = _onehot(sequences)
    torch = _torch()
    net = _load_seq_net()
    with torch.no_grad():
        raw = net.forward(torch.tensor(matrix).permute(0, 2, 1)).numpy().ravel()
    return (raw / 100.0).tolist()


def predict_with_chromatin(sequences, chromatin_accessible):
    """Score with binary chromatin accessibility; output is raw*3/100."""
    if isinstance(sequences, str):
        sequences = [sequences]
    matrix = _onehot(sequences)
    ca = np.asarray(chromatin_accessible, dtype=np.float32).reshape(-1, 1) * 100.0
    if ca.shape[0] != matrix.shape[0]:
        raise ValueError("DEEPCPF1_CA_LENGTH_MISMATCH")
    torch = _torch()
    net = _load_ca_net()
    with torch.no_grad():
        raw = net.forward(torch.tensor(matrix).permute(0, 2, 1),
                          torch.tensor(ca)).numpy().ravel()
    return (raw * 3.0 / 100.0).tolist()
