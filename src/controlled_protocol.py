"""Versioned capture contract, shared by acquisition and offline audit."""
V1 = 'controlled_dual_v1'
V2 = 'controlled_dual_v2'
V3 = 'controlled_dual_v3'
STOP_POLICY_V2 = {'grace_ns': 250_000_000, 'max_completion_bytes': 65536}
AVAILABILITY_V3 = {
    'ready_required': True, 'consecutive_rows': 3, 'freshness_ns': 1_000_000_000,
    'max_wait_ns': 10_000_000_000, 'window_ns': 30_000_000_000,
    'minimum_included_rows_per_receiver': 1,
    'max_gap_ns': None, 'flow_drop': 'reader_termination_before_T1',
    'inclusion': 'first_read_started_ns>=T0 and LF_returned_ns<T1',
    'campaign_model_suitability': 'not_evaluated',
}
