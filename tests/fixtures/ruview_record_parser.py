# Reviewed pure-function excerpt of ruvnet/RuView/scripts/record-csi-udp.py
# Commit fefb0f918eefa7db6daef8cc83787fc7d6f74187; Copyright (c) 2024 rUv; MIT, see LICENSE.RuView.MIT.
# No socket imports, CLI or acquisition. Functions below copied verbatim.
import struct
import time
from datetime import datetime, timezone
CSI_MAGIC = 0xC5110001
CSI_HDR_FMT = "<IBBHIIbbBB"
CSI_HDR_SIZE = struct.calcsize(CSI_HDR_FMT)

def freq_to_channel(freq_mhz):
    """802.11 channel number for a 2.4/5 GHz centre frequency (0 if unknown)."""
    if freq_mhz == 2484:
        return 14
    if 2412 <= freq_mhz <= 2472:
        return (freq_mhz - 2407) // 5
    if 5000 <= freq_mhz <= 5900:
        return (freq_mhz - 5000) // 5
    return 0

def parse_csi_packet(data):
    """Parse ADR-018 binary CSI packet into dict, or None if it is not one."""
    if len(data) < CSI_HDR_SIZE:
        return None

    (magic, node_id, n_antennas, n_sub, freq_mhz, seq,
     rssi, noise_floor, ppdu_type, flags) = struct.unpack_from(CSI_HDR_FMT, data)
    # Same antenna/subcarrier limits as esp32_parser.rs
    if magic != CSI_MAGIC or not 1 <= n_antennas <= 4 or n_sub > 256:
        return None

    n_pairs = n_antennas * n_sub
    iq_data = data[CSI_HDR_SIZE:CSI_HDR_SIZE + n_pairs * 2]
    if len(iq_data) < n_pairs * 2:
        return None

    # Compute amplitudes
    amplitudes = []
    for i in range(0, len(iq_data), 2):
        I = struct.unpack('b', bytes([iq_data[i]]))[0]
        Q = struct.unpack('b', bytes([iq_data[i + 1]]))[0]
        amplitudes.append(round((I * I + Q * Q) ** 0.5, 2))

    return {
        "type": "raw_csi",
        # true UTC, not local-time-labeled-Z (#1007 Bug 1) — e.g. "2026-06-17T01:23:45.678Z"
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "ts_ns": time.time_ns(),
        "node_id": node_id,
        "seq": seq,
        "rssi": rssi,
        "noise_floor": noise_floor,
        "freq_mhz": freq_mhz,
        "channel": freq_to_channel(freq_mhz),
        "ppdu_type": ppdu_type,
        "flags": flags,
        "n_antennas": n_antennas,
        "n_subcarriers": n_sub,
        "subcarriers": n_pairs,  # I/Q pairs in iq_hex (n_antennas * n_subcarriers)
        "amplitudes": amplitudes,
        "iq_hex": iq_data.hex(),
    }
