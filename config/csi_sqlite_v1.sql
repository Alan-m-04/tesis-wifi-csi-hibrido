-- Derivative index only. Raw bundles and their native validation stay authoritative.
CREATE TABLE devices (
    device_key TEXT PRIMARY KEY,
    identity_kind TEXT NOT NULL,
    identity_value TEXT NOT NULL,
    UNIQUE (identity_kind, identity_value)
);
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    protocol TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    partition_group TEXT NOT NULL,
    future_partition TEXT NOT NULL,
    bundle_path TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL
);
CREATE TABLE session_devices (
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    device_key TEXT NOT NULL REFERENCES devices(device_key),
    role TEXT NOT NULL CHECK (role IN ('receiver', 'transmitter')),
    label TEXT NOT NULL,
    identity_json TEXT NOT NULL,
    opened_ns INTEGER,
    closing_ns INTEGER,
    closed_ns INTEGER,
    PRIMARY KEY (session_id, device_key),
    UNIQUE (session_id, label),
    CHECK (role != 'receiver' OR (opened_ns IS NOT NULL AND closing_ns IS NOT NULL AND closed_ns IS NOT NULL AND
           closing_ns >= opened_ns AND closed_ns >= closing_ns))
);
CREATE TABLE source_files (
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    path TEXT NOT NULL,
    bytes INTEGER NOT NULL CHECK (bytes >= 0),
    sha256 TEXT NOT NULL,
    PRIMARY KEY (session_id, path)
);
CREATE TABLE csi_samples (
    session_id TEXT NOT NULL,
    device_key TEXT NOT NULL,
    line_1based INTEGER NOT NULL CHECK (line_1based > 0),
    callback_id INTEGER NOT NULL,
    local_timestamp_us INTEGER NOT NULL CHECK (local_timestamp_us BETWEEN 0 AND 4294967295),
    returned_ns INTEGER NOT NULL,
    first_read_started_ns INTEGER NOT NULL,
    rssi_dbm INTEGER NOT NULL,
    source_mac TEXT NOT NULL,
    queue_drops INTEGER NOT NULL,
    byte_offset INTEGER NOT NULL CHECK (byte_offset >= 0),
    byte_length INTEGER NOT NULL CHECK (byte_length > 0),
    line_sha256 TEXT NOT NULL,
    original_fields_json TEXT NOT NULL,
    reference_json TEXT NOT NULL,
    raw_line BLOB NOT NULL,
    PRIMARY KEY (session_id, device_key, line_1based),
    FOREIGN KEY (session_id, device_key) REFERENCES session_devices(session_id, device_key),
    CHECK (returned_ns >= first_read_started_ns),
    CHECK (length(raw_line) = byte_length)
);
CREATE INDEX samples_time ON csi_samples(session_id, device_key, returned_ns);
CREATE TABLE validation_results (
    session_id TEXT NOT NULL,
    device_key TEXT NOT NULL,
    check_name TEXT NOT NULL,
    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
    details_json TEXT NOT NULL,
    PRIMARY KEY (session_id, device_key, check_name),
    FOREIGN KEY (session_id, device_key) REFERENCES session_devices(session_id, device_key)
);
CREATE VIEW session_receiver_summary AS
WITH ordered AS (
    SELECT *,
        returned_ns - LAG(returned_ns) OVER w AS host_gap_ns,
        (local_timestamp_us - LAG(local_timestamp_us) OVER w + 4294967296) % 4294967296 AS local_gap_us
    FROM csi_samples
    WINDOW w AS (PARTITION BY session_id, device_key ORDER BY line_1based)
), aggregates AS (
    SELECT session_id, device_key, COUNT(*) AS rows,
        MAX(returned_ns) - MIN(returned_ns) AS sample_span_ns,
        MAX(host_gap_ns) AS max_host_gap_ns, MAX(local_gap_us) AS max_local_gap_us
    FROM ordered GROUP BY session_id, device_key
)
SELECT s.session_id, d.device_key, d.label AS receiver_id, s.future_partition,
    d.closed_ns - d.opened_ns AS duration_ns,
    (d.closed_ns - d.opened_ns) / 1e9 AS duration_s,
    d.closing_ns - d.opened_ns AS service_duration_ns,
    (d.closing_ns - d.opened_ns) / 1e9 AS service_duration_s,
    COALESCE(a.rows, 0) AS rows, a.sample_span_ns, a.sample_span_ns / 1e9 AS sample_span_s,
    CASE WHEN a.rows > 1 AND a.sample_span_ns > 0
         THEN (a.rows - 1) * 1e9 / a.sample_span_ns END AS capture_frequency_hz,
    COALESCE(a.rows, 0) * 1e9 / NULLIF(d.closed_ns - d.opened_ns, 0) AS rows_per_open_second,
    a.max_host_gap_ns, a.max_host_gap_ns / 1e6 AS max_host_gap_ms,
    a.max_local_gap_us, a.max_local_gap_us / 1e3 AS max_local_gap_ms,
    q.passed AS strict_quality_ok,
    CASE q.passed WHEN 1 THEN 'accepted' WHEN 0 THEN 'rejected' ELSE 'unknown' END AS quality_status,
    q.details_json AS quality_details_json,
    i.passed AS integrity_ok, r.passed AS replay_ok, c.passed AS close_ok,
    g.passed AS diagnostic_ok
FROM sessions s JOIN session_devices d USING (session_id)
LEFT JOIN aggregates a USING (session_id, device_key)
LEFT JOIN validation_results q ON q.session_id=s.session_id AND q.device_key=d.device_key AND q.check_name='strict_quality'
LEFT JOIN validation_results i ON i.session_id=s.session_id AND i.device_key=d.device_key AND i.check_name='integrity'
LEFT JOIN validation_results r ON r.session_id=s.session_id AND r.device_key=d.device_key AND r.check_name='replay'
LEFT JOIN validation_results c ON c.session_id=s.session_id AND c.device_key=d.device_key AND c.check_name='closure'
LEFT JOIN validation_results g ON g.session_id=s.session_id AND g.device_key=d.device_key AND g.check_name='diagnostic'
WHERE d.role='receiver';
