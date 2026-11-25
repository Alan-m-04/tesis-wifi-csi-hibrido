"""Strict offline decoder for experimental TCSI v1. No serial/network access.

This decoder verifies framing, not acquisition quality or model eligibility.
No resynchronization, trimming, padding or repair is performed.
"""
import struct
import zlib

HEADER = struct.Struct('<4sBBBBIHH')
META = struct.Struct('<19q')
META_NAMES = ('rssi', 'rate', 'sig_mode', 'mcs', 'bandwidth', 'smoothing',
              'not_sounding', 'aggregation', 'stbc', 'fec_coding', 'sgi',
              'noise_floor', 'ampdu_cnt', 'channel', 'secondary_channel',
              'local_timestamp', 'ant', 'sig_len', 'rx_state')
MAX_PAYLOAD = 186 + 1024


def decode_frame(frame):
    if not isinstance(frame, bytes) or len(frame) < 20:
        raise ValueError('truncated frame or invalid input type')
    magic, version, kind, node, flags, seq, length, reserved = HEADER.unpack_from(frame)
    if (magic != b'TCSI' or version != 1 or kind not in (1, 2)
            or node > 2 or flags or reserved):
        raise ValueError('unsupported header')
    if length > MAX_PAYLOAD or len(frame) != 20 + length:
        raise ValueError('frame length mismatch')
    if zlib.crc32(frame[:-4]) != struct.unpack_from('<I', frame, len(frame)-4)[0]:
        raise ValueError('CRC mismatch')
    payload = frame[16:-4]
    result = dict(protocol='TCSI-v1-experimental', node_id=node, frame_seq=seq,
                  kind='csi' if kind == 1 else 'event',
                  acquisition_quality='not_evaluated', model_use='not_authorized')
    if kind == 2:
        if not 1 <= length <= 256 or any(c < 32 or c > 126 for c in payload):
            raise ValueError('invalid event payload')
        return dict(result, event=payload.decode('ascii'))
    if length < 188:
        raise ValueError('truncated CSI payload')
    csi_len = struct.unpack_from('<H', payload, 183)[0]
    if (not 2 <= csi_len <= 1024 or csi_len % 2 or length != 186 + csi_len
            or payload[185] > 1):
        raise ValueError('invalid CSI size or flags')
    callback, drops, epoch = struct.unpack_from('<III', payload)
    result.update(callback_id=callback, queue_drops=drops, topology_epoch=epoch,
                  layer=payload[12], first_word_invalid=bool(payload[185]),
                  csi_bytes=payload[186:], len=csi_len)
    for name, offset in [('source_mac', 13), ('node_mac', 19), ('parent_mac', 25)]:
        result[name] = payload[offset:offset+6].hex(':')
    result.update(zip(META_NAMES, META.unpack_from(payload, 31)))
    return result


class Decoder:
    """Bounded incremental decoder. On any error the connection stays rejected."""
    def __init__(self):
        self._buffer = bytearray()
        self._failed = False

    def feed(self, chunk):
        if self._failed:
            raise ValueError('decoder already rejected this stream')
        if not isinstance(chunk, bytes):
            self._failed = True
            raise ValueError('bytes required')
        results = []
        try:
            # Process one byte at a time so even a huge chunk cannot grow the
            # internal retained buffer beyond one bounded protocol frame.
            for byte in chunk:
                self._buffer.append(byte)
                if len(self._buffer) < HEADER.size:
                    continue
                magic, version, kind, node, flags, _, length, reserved = HEADER.unpack_from(self._buffer)
                if (magic != b'TCSI' or version != 1 or kind not in (1, 2)
                        or node > 2 or flags or reserved or length > MAX_PAYLOAD):
                    raise ValueError('unsupported stream header; no resynchronization')
                total = 20 + length
                if len(self._buffer) == total:
                    results.append(decode_frame(bytes(self._buffer)))
                    self._buffer.clear()
        except ValueError:
            self._failed = True
            raise
        return results

    def finish(self):
        if self._failed or self._buffer:
            self._failed = True
            raise ValueError('rejected stream or truncated tail')
