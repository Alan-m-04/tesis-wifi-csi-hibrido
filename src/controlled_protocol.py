"""Versioned capture contract, shared by acquisition and offline audit."""
V1 = 'controlled_dual_v1'
V2 = 'controlled_dual_v2'
STOP_POLICY_V2 = {'grace_ns': 250_000_000, 'max_completion_bytes': 65536}
