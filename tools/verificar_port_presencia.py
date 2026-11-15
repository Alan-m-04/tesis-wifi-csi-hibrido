#!/usr/bin/env python3
"""Execute original Rust head vs explicit Python port on synthetic vectors only."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ruview_presence_port import Anchor, LABELS, PresenceSpecialistPort, RUVIEW_COMMIT, bits, f32


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def ref(path): return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'bytes': path.stat().st_size}


def corpus():
    fixture = json.loads((ROOT / 'tests/fixtures/presence_head_synthetic.json').read_text())
    assert fixture['evidence_type'] == 'synthetic_fixture' and fixture['not_physical_measurements']
    cases = fixture['cases'][:]
    rng = random.Random(1729)
    for i in range(2000):
        anchors = []
        for _ in range(rng.randrange(6)):
            label = rng.choice(LABELS)
            anchors.append({'label': label, 'mean': f32(rng.uniform(0, 200)), 'variance': f32(rng.uniform(0, 2000))})
        cases.append({'id': 'synthetic_random_' + str(i), 'anchors': anchors,
                      'query': {'mean': f32(rng.uniform(0, 200)), 'variance': f32(rng.uniform(0, 2000))}})
    return fixture, cases


def verify(out):
    provenance = json.loads((ROOT / 'vendor/ruview/presence/PROVENANCE.json').read_text())
    assert provenance['commit'] == RUVIEW_COMMIT
    for e in provenance['excerpts']:
        assert sha(ROOT / e['path']) == e['sha256'], e['path']
    original = (ROOT / 'vendor/ruview/presence/presence_original.rs').read_text()
    assert original.count('#[derive(Debug, Clone, Serialize, Deserialize)]') == 1
    assert original.count('#[serde(default)]') == 2
    compiled = original.replace('#[derive(Debug, Clone, Serialize, Deserialize)]', '#[derive(Debug, Clone)]').replace('#[serde(default)]', '')
    support = (ROOT / 'tests/rust/presence_reference_support.rs').read_text()
    support = support.replace('// @@ORIGINAL_EXPECTS_PRESENCE@@', (ROOT / 'vendor/ruview/presence/expects_presence_original.rs').read_text())
    support = support.replace('// @@ORIGINAL_PRESENCE@@', compiled)
    source = out / 'reference.rs'; source.write_text(support)
    lock = json.loads((ROOT / 'config/presence_rust_reference.lock.json').read_text())
    runtime = ROOT / lock['destination']
    compiler = runtime / 'bin/rustc'
    linker = runtime / 'lib/rustlib' / lock['host'] / 'bin/rust-lld'
    version = subprocess.check_output([str(compiler), '-vV'], text=True)
    assert 'release: ' + lock['version'] in version
    command = [str(compiler), str(source), '--edition=2021', '--target=' + lock['target'],
               '-C', 'opt-level=0', '-C', 'linker=' + str(linker), '-C', 'link-self-contained=yes',
               '-o', str(out / 'reference')]
    with (out / 'compile.stdout.log').open('x') as stdout, (out / 'compile.stderr.log').open('x') as stderr:
        subprocess.run(command, check=True, stdout=stdout, stderr=stderr)
    fixture, cases = corpus()
    lines, expected = [], []
    for case in cases:
        anchors = [Anchor(a['label'], a['mean'], a['variance']) for a in case['anchors']]
        words = [case['id'], str(len(anchors))]
        for a in anchors:
            words += [str(LABELS.index(a.label)), bits(a.mean), bits(a.variance)]
        q = case['query']; words += [bits(q['mean']), bits(q['variance'])]
        lines.append(' '.join(words))
        model = PresenceSpecialistPort.train(anchors)
        if model is None:
            expected.append(case['id'] + ' NONE')
        else:
            reading = model.infer(q['mean'], q['variance'])
            expected.append(' '.join([case['id'], 'MODEL', bits(model.threshold), bits(model.occupied_var),
                bits(model.empty_mean), 'NONE' if model.mean_dist_threshold is None else bits(model.mean_dist_threshold),
                bits(reading['value']), bits(reading['confidence_margin']), reading['label']]))
    payload = '\n'.join(lines) + '\n'
    (out / 'synthetic-input.txt').write_text(payload)
    (out / 'python-output.txt').write_text('\n'.join(expected) + '\n')
    run = subprocess.run([str(out / 'reference')], input=payload, text=True, capture_output=True, check=True)
    (out / 'rust-output.txt').write_text(run.stdout)
    (out / 'run.stderr.log').write_text(run.stderr)
    actual = run.stdout.splitlines()
    assert len(actual) == len(expected)
    mismatches = [{'case': cases[i]['id'], 'Python': p, 'Rust': r} for i, (p, r) in enumerate(zip(expected, actual)) if p != r]
    report = {'schema': 'tesis-presence-port-equivalence-v1', 'evidence_type': 'synthetic_fixture',
        'physical_data_used': False, 'ruview_commit': RUVIEW_COMMIT, 'implementation': 'Explicit Python binary32 head port',
        'rust_executed': True, 'full_RuView_crate_compiled': False,
        'rust_scope': 'Unmodified original PresenceSpecialist train/infer and expects_presence bodies; serialization attributes removed; minimal test types supplied.',
        'named_cases': len(fixture['cases']), 'deterministic_random_cases': 2000, 'random_seed': 1729,
        'case_count': len(cases), 'bitwise_model_value_confidence_and_label_matches': len(cases) - len(mismatches),
        'model_and_inference_cases': sum(x.split()[1] == 'MODEL' for x in actual),
        'missing_anchor_None_cases': sum(x.split()[1] == 'NONE' for x in actual),
        'mismatches': mismatches, 'equivalence_verified_for_tested_cases': not mismatches,
        'limits': ['Tested finite nonnegative inputs, boundary neighbors and normal bounded random features; not a proof for every IEEE value or Rust build.',
                   'Extraction is binary64 and stricter about missing/nonfinite rows; Features::from_series and enrollment gates are not ported.',
                   'No accuracy, calibration validity on real rooms, or presence validation follows from formula equivalence.'],
        'compiler_version': version, 'target': lock['target'], 'command': [str(x).replace(str(ROOT) + '/', '') for x in command],
        'sources': [ref(ROOT / p) for p in ('src/ruview_presence_port.py', 'tools/verificar_port_presencia.py', 'tools/preparar_rust_presencia.py', 'tests/fixtures/presence_head_synthetic.json',
                    'tests/rust/presence_reference_support.rs', 'vendor/ruview/presence/presence_original.rs',
                    'vendor/ruview/presence/expects_presence_original.rs', 'vendor/ruview/presence/PROVENANCE.json',
                    'vendor/ruview/presence/LICENSE', 'config/presence_rust_reference.lock.json')],
        'compiler_sha256': sha(compiler), 'linker_sha256': sha(linker),
        'artifacts': [ref(out / p) for p in ('reference.rs', 'reference', 'synthetic-input.txt', 'python-output.txt', 'rust-output.txt', 'compile.stdout.log', 'compile.stderr.log', 'run.stderr.log')]}
    (out / 'equivalence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if mismatches:
        raise ValueError('Rust/Python mismatch; preserved artifacts, no equivalence claim')
    print('RUST_ORIGINAL_BODIES_EXECUTED; synthetic bitwise matches: ' + str(len(cases)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-new', type=Path, required=True)
    parser.add_argument('--inside-sandbox', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(); out = args.output_new.resolve()
    if not out.is_relative_to(ROOT / 'results/local'):
        raise ValueError('New internal results/local output required')
    if not args.inside_sandbox:
        out.mkdir(parents=True, exist_ok=False)
        cmd = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
            '--ro-bind', '/lib64', '/lib64', '--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache',
            '--ro-bind', '/etc/localtime', '/etc/localtime', '--ro-bind', str(ROOT), str(ROOT), '--bind', str(out), str(out),
            '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--chdir', str(ROOT), '--setenv', 'HOME', '/tmp',
            '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', str(ROOT / '.venv/bin/python'), '-B', str(Path(__file__).resolve()),
            '--inside-sandbox', '--output-new', str(out)]
        return subprocess.run(cmd).returncode
    verify(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
