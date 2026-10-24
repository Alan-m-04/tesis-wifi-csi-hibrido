"""Audit capture files offline. Never discovers or opens serial devices.

New code for the hybrid base. The imported collector is kept byte-identical.
Its original quality result and additional integrity/profile checks stay separate.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

import capture_csi_multi as capture

ROLES = dict(capture.RECEIVERS)
NAMES = {"session.json"} | {
    rx.lower() + suffix for rx in ROLES
    for suffix in (".csv", ".serial.log", ".summary.json")
}


def regular_file(root, name):
    if name not in NAMES:
        raise ValueError("Unexpected capture filename")
    p = root / name
    if p.is_symlink() or not p.is_file():
        raise ValueError("A regular, non-symlink capture file is required: " + name)
    return p


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def scan_raw(path):
    raw = path.read_bytes()
    complete = raw.split(b"\n")
    rows, numeric, lines = [], [], []
    counts = dict(malformed_rows=0, unexpected_source_rows=0,
                  unexpected_metadata_rows=0, boot_error_count=0, oversized_lines=0)
    resets, ready = [], []
    for number, line in enumerate(complete[:-1], 1):
        text = capture.ANSI.sub("", line.decode("utf-8", errors="replace")).strip()
        if "rst:" in text or ("ESP-ROM:" in text and "rst:" not in text):
            resets.append(number)
        if " READY" in text:
            ready.append(number)
        if capture.ERROR.search(text):
            counts["boot_error_count"] += 1
        if len(line) > 65536:
            counts["oversized_lines"] += 1
            continue
        if not text.startswith("CSI_DATA,"):
            continue
        try:
            row, record, values = capture.validate_sample(text)
        except (ValueError, TypeError, csv.Error, StopIteration):
            counts["malformed_rows"] += 1
            continue
        if record["mac"].lower() != capture.SOURCE:
            counts["unexpected_source_rows"] += 1
            continue
        if (values["channel"], values["bandwidth"], values["rx_state"]) != (11, 0, 0):
            counts["unexpected_metadata_rows"] += 1
            continue
        rows.append(row)
        numeric.append(values)
        lines.append(number)
    gaps = nonincreasing = wraps = discontinuities = drops = decreases = 0
    for a, b in zip(numeric, numeric[1:]):
        if b["id"] <= a["id"]:
            nonincreasing += 1
        else:
            gaps += max(0, b["id"] - a["id"] - 1)
            delta = (b["local_timestamp"] - a["local_timestamp"]) % 2**32
            if delta == 0 or delta > 10_000_000:
                discontinuities += 1
            elif b["local_timestamp"] < a["local_timestamp"]:
                wraps += 1
        difference = b["queue_drops"] - a["queue_drops"]
        decreases += difference < 0
        drops += max(0, difference)
    counts.update(callback_id_gaps=gaps, nonincreasing_ids=nonincreasing,
                  device_clock_wraps=wraps, device_time_discontinuities=discontinuities,
                  queue_drop_increment=drops, queue_counter_decreases=decreases)
    # Reproduce the original collector's flags; gaps are an additional check below.
    original_flags = ("malformed_rows", "unexpected_source_rows", "unexpected_metadata_rows",
                      "boot_error_count", "oversized_lines", "queue_drop_increment",
                      "nonincreasing_ids", "device_time_discontinuities", "queue_counter_decreases")
    return dict(rows=rows, numeric=numeric, counts=counts,
                trailing_bytes=len(complete[-1]), ready_lines=ready,
                initial_boot_markers=sum(n < lines[0] for n in resets) if lines else len(resets),
                midstream_boot_markers=sum(n >= lines[0] for n in resets) if lines else 0,
                collector_quality_ok=bool(rows) and not any(counts[k] for k in original_flags))


def audit_capture(directory, manifest=None):
    root = Path(directory)
    if not root.is_dir():
        raise ValueError("Capture directory does not exist")
    session = json.loads(regular_file(root, "session.json").read_text())
    if set(session["results"]) != set(ROLES) or set(session["receivers"]) != set(ROLES):
        raise ValueError("Exactly RX-01 and RX-02 are required")
    if len(set(session["receivers"].values())) != 2:
        raise ValueError("Receiver ports must remain distinct")
    gate = int(session["capture_start_monotonic_ns"])
    deadline = int(session["capture_deadline_monotonic_ns"])
    expected_duration = int(float(session["requested_seconds"]) * 1e9)
    if gate < 0 or deadline <= gate or deadline - gate != expected_duration:
        raise ValueError("Invalid shared capture window")
    manifest_ok = True
    if manifest is not None:
        entries = manifest["files"]
        names = [x["name"] for x in entries]
        if len(names) != len(set(names)) or set(names) != NAMES:
            raise ValueError("Manifest must pin exactly the seven capture files")
        manifest_ok = all(sha(regular_file(root, x["name"])) == x["sha256"]
                          and regular_file(root, x["name"]).stat().st_size == x["bytes"]
                          for x in entries)
    profile = json.loads((Path(__file__).resolve().parents[1] / "config/csi_esp32s3.json").read_text())
    if profile["source_mac"] != capture.SOURCE or profile["receivers"] != ROLES:
        raise ValueError("Profile and imported collector identities differ")
    report = dict(schema="tesis-offline-capture-audit-v1", operation="offline_validation",
                  new_physical_capture=False, manifest_ok=manifest_ok,
                  source_evidence_type=manifest.get("evidence_type") if manifest else "unspecified",
                  session_status=session["status"], receivers={})
    for rx, serial in ROLES.items():
        stem = rx.lower()
        raw = regular_file(root, stem + ".serial.log")
        exported = regular_file(root, stem + ".csv")
        summary = json.loads(regular_file(root, stem + ".summary.json").read_text())
        parsed = scan_raw(raw)
        with exported.open(newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != capture.EXTRA_FIELDS + capture.FIELDS:
                raise ValueError("Unexpected CSV schema for " + rx)
            rows = list(reader)
        if any(None in r or any(v is None for v in r.values()) for r in rows):
            raise ValueError("Truncated or extra CSV columns")
        identities_ok = all(r["receiver_id"] == rx and r["usb_serial"] == serial
                            and r["session_id"] == session["session_id"] for r in rows)
        host = [int(r["host_monotonic_ns"]) for r in rows]
        wall = [datetime.fromisoformat(r["host_timestamp_utc"]) for r in rows]
        host_ok = all(t.utcoffset() is not None for t in wall) and all(b >= a for a, b in zip(wall, wall[1:]))
        host_ok = host_ok and all(b >= a for a, b in zip(host, host[1:]))
        frames_match = parsed["rows"] == [[r[k] for k in capture.FIELDS] for r in rows]
        hashes_ok = summary.get("csv_sha256") == sha(exported) and summary.get("serial_log_sha256") == sha(raw)
        summary_ok = summary == session["results"][rx] and summary.get("valid_rows") == len(rows)
        summary_ok = summary_ok and summary.get("usb_serial") == serial and summary.get("receiver_id") == rx
        for key, value in parsed["counts"].items():
            summary_ok = summary_ok and summary.get(key) == value
        original_ok = parsed["collector_quality_ok"]
        summary_ok = summary_ok and summary.get("format_reception_ok") == original_ok and not summary.get("error")
        matrix_ok = all(r["len"] == profile["matrix"]["observed_length_bytes"]
                        and r["first_word_invalid"] == 0 and r["sig_mode"] == 1
                        and r["mcs"] == 0 and r["stbc"] == 0 for r in parsed["numeric"])
        frames_in_gate = all(gate <= t < deadline for t in host)
        additional_ok = (parsed["counts"]["callback_id_gaps"] == 0
                         and parsed["midstream_boot_markers"] == 0 and frames_in_gate)
        integrity_ok = all((identities_ok, host_ok, frames_match, hashes_ok, summary_ok))
        report["receivers"][rx] = dict(valid_rows=len(rows), raw_sha256=sha(raw), csv_sha256=sha(exported),
            raw_frames_equal_csv=frames_match, integrity_ok=integrity_ok,
            collector_quality_recorded=summary["format_reception_ok"], collector_quality_recomputed=original_ok,
            representation_profile_ok=matrix_ok, additional_checks_ok=additional_ok,
            host_frames_inside_requested_gate=frames_in_gate,
            counts=parsed["counts"], trailing_bytes=parsed["trailing_bytes"],
            initial_boot_markers=parsed["initial_boot_markers"], midstream_boot_markers=parsed["midstream_boot_markers"],
            first_id=parsed["numeric"][0]["id"] if parsed["numeric"] else None,
            last_id=parsed["numeric"][-1]["id"] if parsed["numeric"] else None,
            quality_ok=original_ok and integrity_ok and matrix_ok and additional_ok)
    report["quality_ok"] = manifest_ok and session["status"] == "completed" and all(
        x["quality_ok"] for x in report["receivers"].values())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text()) if args.manifest else None
        report = audit_capture(args.capture_directory, manifest)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, "Offline validation input error: " + str(exc) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["quality_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
