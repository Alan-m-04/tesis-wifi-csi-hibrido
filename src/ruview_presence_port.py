"""Explicit Python port of RuView PresenceSpecialist (MIT), pinned fefb0f9.

Only train/infer are ported. Each scalar operation is rounded to IEEE binary32;
the physical extractor never calls these functions. This is not the Rust crate,
Features::from_series, a pretrained model or a calibrated presence probability.
Attribution/source hashes: vendor/ruview/presence/PROVENANCE.json and its LICENSE.
"""
from dataclasses import dataclass
import math
import struct

RUVIEW_COMMIT = 'fefb0f918eefa7db6daef8cc83787fc7d6f74187'
LABELS = ('Empty', 'StandStill', 'Sit', 'LieDown', 'BreatheSlow', 'BreatheNormal', 'SmallMove', 'SleepPosture')
CONTRACT = 'presence-offline-v1/LLTF52/row-mean/session-population'


def f32(value):
    try:
        return struct.unpack('!f', struct.pack('!f', value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


def bits(value):
    return struct.pack('!f', f32(value)).hex()


def add(a, b): return f32(a + b)
def sub(a, b): return f32(a - b)
def mul(a, b): return f32(a * b)
def div(a, b): return f32(a / b)


def finite_features(mean, variance):
    if type(mean) not in (int, float) or type(variance) not in (int, float):
        raise ValueError('Numeric amplitude mean/variance required')
    mean, variance = f32(mean), f32(variance)
    if not math.isfinite(mean) or not math.isfinite(variance) or mean < 0 or variance < 0:
        raise ValueError('Finite nonnegative amplitude mean/variance required')
    return mean, variance


@dataclass(frozen=True)
class Anchor:
    label: str
    mean: float
    variance: float


@dataclass(frozen=True)
class PresenceSpecialistPort:
    threshold: float
    occupied_var: float
    empty_mean: float
    mean_dist_threshold: float | None

    @classmethod
    def train(cls, anchors):
        """Literal head algorithm; callers must separately establish eligibility."""
        anchors = tuple(anchors)
        for a in anchors:
            if a.label not in LABELS:
                raise ValueError('Unknown RuView anchor label')
            finite_features(a.mean, a.variance)
        empty = next((a for a in anchors if a.label == 'Empty'), None)
        occupied = [a for a in anchors if a.label != 'Empty']
        if empty is None or not occupied:
            return None
        def average(values):
            total = f32(-0.0)
            for value in values:
                total = add(total, f32(value))
            return div(total, f32(len(values)))
        occ_var = average([a.variance for a in occupied])
        occ_mean = average([a.mean for a in occupied])
        empty_var, empty_mean = f32(empty.variance), f32(empty.mean)
        mean_dist = abs(sub(occ_mean, empty_mean))
        mean_threshold = mul(f32(.5), mean_dist) if mean_dist > f32(1e-4) else None
        variance_separates = occ_var > mul(empty_var, add(f32(1), f32(.05)))
        threshold = mul(f32(.5), add(empty_var, occ_var)) if variance_separates else math.inf
        return cls(threshold, max(occ_var, add(empty_var, f32(1e-3))), empty_mean, mean_threshold)

    def infer(self, mean, variance):
        """Port output for equivalence tests; confidence is a margin, not probability."""
        mean, variance = finite_features(mean, variance)
        mean_dist = abs(sub(mean, self.empty_mean))
        present = variance > self.threshold or (self.mean_dist_threshold is not None and mean_dist > self.mean_dist_threshold)
        var_conf = 0.0
        if math.isfinite(self.threshold):
            span = max(sub(self.occupied_var, self.threshold), f32(1e-3))
            var_conf = min(f32(1), max(f32(0), div(abs(sub(variance, self.threshold)), span)))
        mean_conf = 0.0
        if self.mean_dist_threshold is not None:
            thr = self.mean_dist_threshold
            mean_conf = min(f32(1), max(f32(0), div(abs(sub(mean_dist, thr)), max(thr, f32(1e-3)))))
        return {'value': f32(1 if present else 0), 'confidence_margin': max(var_conf, mean_conf),
                'label': 'present' if present else 'absent'}


def calibrate_synthetic(anchors, *, receiver, scope):
    """Test-only calibration. Physical calibration is deliberately not exposed by CLI.

    Each input must explicitly declare synthetic evidence, RX and a common
    scope. No model is valid when both channels are disabled or math overflows.
    """
    if receiver not in ('RX-01', 'RX-02') or not isinstance(scope, str) or not scope:
        raise ValueError('Synthetic RX/scope required')
    for a in anchors:
        if a.get('evidence_type') != 'synthetic_fixture' or a.get('receiver') != receiver or a.get('scope') != scope:
            raise ValueError('Only explicitly synthetic anchors from one RX/scope allowed')
    model = PresenceSpecialistPort.train([Anchor(a['label'], a['mean'], a['variance']) for a in anchors])
    result = {'status': 'sin calibración', 'receiver': receiver, 'scope': scope, 'contract': CONTRACT,
              'evidence_type': 'synthetic_fixture', 'model': None, 'reason': 'missing_empty_or_occupied_anchor'}
    if model is None:
        return result
    finite = math.isfinite(model.occupied_var) and math.isfinite(model.empty_mean)
    finite = finite and (model.mean_dist_threshold is None or math.isfinite(model.mean_dist_threshold))
    if not finite:
        result['reason'] = 'numerical_overflow'; return result
    if not math.isfinite(model.threshold) and model.mean_dist_threshold is None:
        result.update(status='sin separabilidad', reason='both_channels_disabled'); return result
    result.update(status='calibración sintética', model=model, reason=None)
    return result


def infer_synthetic(mean, variance, *, receiver, scope, calibration=None, evidence_type='synthetic_fixture'):
    """Safe synthetic test wrapper; never transfers a test model to physical data."""
    if evidence_type != 'synthetic_fixture':
        raise ValueError('Synthetic models cannot classify physical data')
    result = {'status': 'sin calibración', 'presence': None, 'confidence_margin': None,
              'inference_executed': False, 'evidence_type': 'synthetic_fixture'}
    try:
        finite_features(mean, variance)
    except ValueError:
        return dict(result, status='no evaluable', reason='required_features_incomplete')
    if calibration is None:
        return result
    if (calibration.get('receiver') != receiver or calibration.get('scope') != scope or
            calibration.get('contract') != CONTRACT or calibration.get('evidence_type') != 'synthetic_fixture'):
        result['reason'] = 'calibration_scope_mismatch'; return result
    if calibration['status'] != 'calibración sintética' or calibration.get('model') is None:
        result['status'] = calibration['status']; return result
    reading = calibration['model'].infer(mean, variance)
    return dict(result, status='resultado sintético', presence=bool(reading['value']),
                confidence_margin=reading['confidence_margin'], inference_executed=True)
