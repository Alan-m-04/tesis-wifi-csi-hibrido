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
from controlled_protocol import V1, V2, V3, STOP_POLICY_V2
from audit_bounded_stop import audit_bounded_stop

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
    rows, numeric, lines, byte_ends = [], [], [], []
    offset = 0
    counts = dict(malformed_rows=0, unexpected_source_rows=0,
                  unexpected_metadata_rows=0, boot_error_count=0, oversized_lines=0)
    resets, ready, embedded_boot, orphan_fragments = [], [], [], []
    for number, line in enumerate(complete[:-1], 1):
        offset += len(line) + 1
        text = capture.ANSI.sub("", line.decode("utf-8", errors="replace")).strip()
        if 'ESP-ROM:' in text and not text.startswith('ESP-ROM:'):
            embedded_boot.append(number)
        if text.startswith(('"', ',')) and not text.startswith('CSI_DATA,'):
            orphan_fragments.append(number)
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
        byte_ends.append(offset)
    if len(complete[-1]) > 65536:
        counts['oversized_lines'] += 1
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
    return dict(rows=rows, numeric=numeric, counts=counts, row_byte_ends=byte_ends,
                trailing_bytes=len(complete[-1]), ready_lines=ready,
                embedded_boot_lines=embedded_boot, orphan_fragment_lines=orphan_fragments,
                initial_boot_markers=sum(n < lines[0] for n in resets) if lines else len(resets),
                midstream_boot_markers=sum(n >= lines[0] for n in resets) if lines else 0,
                collector_quality_ok=bool(rows) and not any(counts[k] for k in original_flags))


def audit_read_ledger(root,rx,manifest,parsed,rows,gate,deadline):
    expected={r.lower()+'.reads.jsonl' for r in ROLES}
    entries=manifest.get('read_ledgers',[])
    if len(entries)!=2 or {e['name'] for e in entries}!=expected:
        raise ValueError('Exactly two read ledgers required')
    item=next(e for e in entries if e['name']==rx.lower()+'.reads.jsonl')
    path=root/item['name']
    if path.is_symlink() or not path.is_file():raise ValueError('Regular read ledger required')
    if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:return False
    events=[json.loads(x) for x in path.read_text().splitlines()]
    raw_size=(root/(rx.lower()+'.serial.log')).stat().st_size
    offset=0;last=gate
    for event in events:
        start,end=int(event['started_ns']),int(event['returned_ns'])
        if event['offset']!=offset or type(event['size']) is not int or event['size']<=0 or not gate<=start<=end<deadline or start<last:return False
        offset+=event['size'];last=end
    if offset!=raw_size:return False
    event_index=0
    for row,byte_end in zip(rows,parsed['row_byte_ends']):
        while event_index<len(events) and events[event_index]['offset']+events[event_index]['size']<byte_end:event_index+=1
        if event_index>=len(events):return False
        event=events[event_index]
        if not event['offset']<byte_end<=event['offset']+event['size']:return False
        if int(row['host_monotonic_ns'])!=int(event['returned_ns']) or row['host_timestamp_utc']!=event['host_timestamp_utc']:return False
    return True


def audit_capture(directory, manifest=None):
    root = Path(directory)
    if not root.is_dir():
        raise ValueError("Capture directory does not exist")
    session = json.loads(regular_file(root, "session.json").read_text())
    if session.get('protocol') == V3:
        from audit_availability import audit_availability_capture
        return audit_availability_capture(root, manifest, session)
    if set(session["results"]) != set(ROLES) or set(session["receivers"]) != set(ROLES):
        raise ValueError("Exactly RX-01 and RX-02 are required")
    if len(set(session["receivers"].values())) != 2:
        raise ValueError("Receiver ports must remain distinct")
    gate = int(session["capture_start_monotonic_ns"])
    deadline = int(session["capture_deadline_monotonic_ns"])
    expected_duration = int(float(session["requested_seconds"]) * 1e9)
    v2 = session.get('protocol') == V2
    controlled = session.get('protocol') in (V1, V2)
    if controlled:
        common=session['controlled']
        common_start=int(common['common_start_ns']); common_deadline=int(common['common_deadline_ns'])
        common_fits = (gate <= common_start < common_deadline and common_start <= deadline
                       and (common_deadline <= deadline or (v2 and session['status'] != 'completed')))
        if (gate < 0 or not common_fits
                or common_deadline-common_start != expected_duration or common.get('stable_window') is not None):
            raise ValueError('Invalid controlled envelope/common window')
        if v2 and (common.get('stop_policy') != STOP_POLICY_V2 or manifest is None
                   or manifest.get('source_run_kind') != V2 or manifest.get('schema') != 'tesis-controlled-capture-v2'):
            raise ValueError('Invalid v2 manifest or fixed stop policy')
        if v2 and session.get('evidence_type') != 'synthetic_fixture' and expected_duration != 30_000_000_000:
            raise ValueError('Physical v2 requires 30 nominal seconds')
    elif gate < 0 or deadline <= gate or deadline - gate != expected_duration:
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
        original_ok = parsed["collector_quality_ok"] and (not v2 or not summary.get('error'))
        summary_ok = summary_ok and summary.get("format_reception_ok") == original_ok and (v2 or not summary.get("error"))
        matrix_ok = all(r["len"] == profile["matrix"]["observed_length_bytes"]
                        and r["first_word_invalid"] == 0 and r["sig_mode"] == 1
                        and r["mcs"] == 0 and r["stbc"] == 0 for r in parsed["numeric"])
        frames_in_gate = all(gate <= t < deadline for t in host)
        ledger_ok=True; common_rows=None
        if controlled:
            if manifest is None:raise ValueError('Controlled recording requires its manifest and read ledgers')
            ledger_ok = audit_read_ledger(root,rx,manifest,parsed,rows,gate,deadline)
            common_rows=sum(common_start <= t < common_deadline for t in host)
            ledger_ok = ledger_ok and summary.get('trailing_bytes') == parsed['trailing_bytes']

        additional_ok = (parsed["counts"]["callback_id_gaps"] == 0
                         and parsed["midstream_boot_markers"] == 0 and frames_in_gate
                         and (not controlled or (parsed['trailing_bytes'] == 0 and common_rows > 0
                                                and not parsed['embedded_boot_lines'] and not parsed['orphan_fragment_lines'])))
        if v2:
            stop_integrity, stop_quality = audit_bounded_stop(root, rx, summary, parsed, session)
            ledger_ok = ledger_ok and stop_integrity
            additional_ok = additional_ok and stop_quality
        integrity_ok = all((identities_ok, host_ok, frames_match, hashes_ok, summary_ok, ledger_ok))
        report["receivers"][rx] = dict(valid_rows=len(rows), raw_sha256=sha(raw), csv_sha256=sha(exported),
            raw_frames_equal_csv=frames_match, integrity_ok=integrity_ok,
            collector_quality_recorded=summary["format_reception_ok"], collector_quality_recomputed=original_ok,
            representation_profile_ok=matrix_ok, additional_checks_ok=additional_ok,
            host_frames_inside_requested_gate=frames_in_gate,
            read_ledger_ok=ledger_ok if controlled else None, common_window_rows=common_rows,
            counts=parsed["counts"], trailing_bytes=parsed["trailing_bytes"],
            embedded_boot_lines=parsed["embedded_boot_lines"], orphan_fragment_lines=parsed["orphan_fragment_lines"],
            initial_boot_markers=parsed["initial_boot_markers"], midstream_boot_markers=parsed["midstream_boot_markers"],
            first_id=parsed["numeric"][0]["id"] if parsed["numeric"] else None,
            last_id=parsed["numeric"][-1]["id"] if parsed["numeric"] else None,
            quality_ok=original_ok and integrity_ok and matrix_ok and additional_ok)
        if v2:
            report['receivers'][rx].update(
                complete_rows_quality_ok=parsed['collector_quality_ok'] and matrix_ok,
                preamble_rows=sum(t < common_start for t in host),
                post_deadline_rows=sum(t >= common_deadline for t in host),
                stop_metadata_ok=stop_integrity, stop_quality_ok=stop_quality, stop=summary.get('stop'))
    postflight_ok=(all(manifest.get('postflight',{}).get(rx,{}).get('identity_ok') is True for rx in ROLES) if controlled else None)
    report['postflight_identity_ok']=postflight_ok
    report["quality_ok"] = postflight_ok is not False and manifest_ok and session["status"] == "completed" and all(
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
