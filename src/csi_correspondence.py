"""Offline mathematical audit helpers, not a RuView adapter or transport.

ESP-IDF v5.4 ESP32-S3: interleaved imaginary, real int8 bytes.
The HT20 model is conditional on explicitly supplied metadata/configuration.
It does not certify a historical board's installed binary.
"""
from math import atan2, hypot

FFT64_ORDER = tuple(range(32)) + tuple(range(-32, 0))


def idf_complex(values, first_word_invalid=False):
    """Keep positions; invalid first four bytes become two unknown pairs, not zero."""
    if type(first_word_invalid) is not bool:
        raise ValueError('first_word_invalid must be boolean')
    if len(values) == 0 or len(values) % 2:
        raise ValueError('Complete nonempty byte pairs required')
    if any(type(v) is not int or not -128 <= v <= 127 for v in values):
        raise ValueError('Signed int8 scalars required')
    return tuple(None if first_word_invalid and k < 4 else complex(values[k+1], values[k])
                 for k in range(0, len(values), 2))


def amplitude_phase(z):
    """Zero/invalid pairs have no measurable phase; no normalization or scaling."""
    if z is None:
        return None, None
    return hypot(z.real, z.imag), None if z == 0 else atan2(z.imag, z.real)


def documented_ht20_layout(metadata, config):
    """Restricted IDF table model; never infer PHY, LTFs or antenna count from len."""
    expected = {'sig_mode': 1, 'bandwidth': 0, 'secondary_channel': 0, 'stbc': 0}
    if any(metadata.get(k) != v for k, v in expected.items()):
        raise ValueError('Only explicit HT20, no secondary, non-STBC is audited')
    for key in ('lltf_en','htltf_en','stbc_htltf2_en','ltf_merge_en','channel_filter_en','manu_scale'):
        if type(config.get(key)) is not bool:
            raise ValueError('Explicit CSI acquisition configuration required: '+key)
    if not config['lltf_en'] or not config['htltf_en']:
        raise ValueError('This model requires both LLTF and HT-LTF enabled')
    if metadata.get('len') != 256:
        raise ValueError('Length inconsistent with metadata and enabled LTFs')
    return (
        {'name':'LLTF','byte_start':0,'byte_stop':128,'indices':FFT64_ORDER},
        {'name':'HT-LTF','byte_start':128,'byte_stop':256,'indices':FFT64_ORDER},
    )


def carrier_role(block, index):
    """802.11a/g and HT20 nominal carrier roles, not an invalidity detector."""
    if block not in ('LLTF','HT-LTF') or index not in FFT64_ORDER:
        raise ValueError('Unknown block or index')
    if index == 0:
        return 'DC'
    edge = 26 if block == 'LLTF' else 28
    if abs(index) > edge:
        return 'guard'
    return 'pilot' if index in (-21, -7, 7, 21) else 'data'
