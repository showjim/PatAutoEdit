"""Checks for the patautoedit command line.

    python test/cli_checks.py

Each check runs in a throwaway directory holding a copy of Sample/, because
the engine writes Output/ relative to the current working directory.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from patautoedit import version as PACKAGE_VERSION  # noqa: E402

SAMPLE_DIR = os.path.join(REPO, 'Sample')
HEADER = 'Pattern,Process Type,Pin or Method,Cycle\n'

_failures = []


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'{status}  {name}' + (f'  -- {detail}' if detail and not condition else ''))
    if not condition:
        _failures.append(name)


def _workdir():
    """Fresh directory holding a copy of Sample/, used as the process cwd."""
    work = tempfile.mkdtemp(prefix='pae_cli_')
    shutil.copytree(SAMPLE_DIR, os.path.join(work, 'Sample'))
    return work


def _write(work, name, text):
    with open(os.path.join(work, name), 'w', newline='', encoding='utf-8') as f:
        f.write(text)
    return name


def _cli(work, *args):
    env = dict(os.environ)
    env['PYTHONPATH'] = REPO + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    return subprocess.run([sys.executable, '-m', 'patautoedit', *args],
                          cwd=work, capture_output=True, text=True, env=env)


def _json(proc):
    return json.loads(proc.stdout)


# --- run -------------------------------------------------------------------

def check_run(work):
    _write(work, 'config.csv', HEADER + 'Sample_ATP.atp,DSSC Capture,TDO,[7-7]\n')
    proc = _cli(work, 'run', 'config.csv', '--atp-dir', 'Sample', '--json')
    data = _json(proc)

    check('run exits 0', proc.returncode == 0, proc.stderr)
    check('run reports ok', data['ok'] is True)
    check('run reports one output', len(data['outputs']) == 1)
    output = data['outputs'][0]['output'] if data['outputs'] else ''
    check('run wrote the output file', bool(output) and os.path.isfile(output))
    check('run defaults to <cwd>/Output',
          os.path.dirname(os.path.realpath(output))
          == os.path.join(os.path.realpath(work), 'Output'))
    check('JSON mode keeps logs off stdout', 'Info:' in proc.stderr)


def check_chain(work):
    _write(work, 'chain.csv', HEADER +
           'Sample_ATP.atp,DSSC Capture,TDO,[7-7]\n'
           'Sample_ATP.atp,WFLAG,,[8-8]\n')
    proc = _cli(work, 'run', 'chain.csv', '--atp-dir', 'Sample', '--json')
    data = _json(proc)

    check('chained rows exit 0', proc.returncode == 0, proc.stderr)
    check('chained rows are one output', len(data['outputs']) == 1)
    check('chained rows report two operations',
          bool(data['outputs']) and data['outputs'][0]['operations'] == 2)


def check_output_dir(work):
    _write(work, 'config.csv', HEADER + 'Sample_ATP.atp,DSSC Capture,TDO,[7-7]\n')
    proc = _cli(work, 'run', 'config.csv', '--atp-dir', 'Sample',
                '--output-dir', 'custom', '--json')
    data = _json(proc)
    output = data['outputs'][0]['output'] if data['outputs'] else ''

    check('--output-dir exits 0', proc.returncode == 0, proc.stderr)
    check('--output-dir is used',
          os.path.dirname(os.path.realpath(output))
          == os.path.join(os.path.realpath(work), 'custom'))
    check('--output-dir file exists', bool(output) and os.path.isfile(output))


def check_missing_pattern(work):
    _write(work, 'config.csv', HEADER +
           'Sample_ATP.atp,DSSC Capture,TDO,[7-7]\n'
           'nope.atp,WFLAG,,[8-8]\n')
    proc = _cli(work, 'run', 'config.csv', '--atp-dir', 'Sample', '--json')
    data = _json(proc)

    check('a missing Pattern warns but exits 0', proc.returncode == 0, proc.stderr)
    check('a missing Pattern is listed in skipped', data['skipped'] == ['nope.atp'],
          repr(data.get('skipped')))
    check('a missing Pattern is in warnings',
          any('nope.atp' in warning for warning in data['warnings']))
    check('a missing Pattern warning reaches stderr',
          'Cannot find atp file: nope.atp' in proc.stderr)


def check_zero_matched(work):
    _write(work, 'config.csv', HEADER + 'nope.atp,WFLAG,,[8-8]\n')
    proc = _cli(work, 'run', 'config.csv', '--atp-dir', 'Sample', '--json')
    data = _json(proc)

    check('zero matched exits 1', proc.returncode == 1, proc.stderr)
    check('zero matched is not ok', data['ok'] is False)
    check('zero matched reports zero counts', data['counts']['matched'] == 0)


def check_invalid_config(work):
    _write(work, 'bad.csv', 'Pattern,Process Type,Pin or Method\n'
                            'Sample_ATP.atp,DSSC Capture,TDO\n')
    proc = _cli(work, 'run', 'bad.csv', '--atp-dir', 'Sample', '--json')
    data = _json(proc)

    check('an invalid config exits 1', proc.returncode == 1, proc.stderr)
    check('an invalid config explains the problem', bool(data['problems']))
    check('an invalid config writes nothing',
          not os.path.exists(os.path.join(work, 'Output')))


def check_human_output(work):
    _write(work, 'config.csv', HEADER + 'Sample_ATP.atp,DSSC Capture,TDO,[7-7]\n')
    proc = _cli(work, 'run', 'config.csv', '--atp-dir', 'Sample')

    check('human mode exits 0', proc.returncode == 0, proc.stderr)
    check('human mode prints a summary', 'file(s) processed' in proc.stdout)


# --- check / modes ---------------------------------------------------------

def check_plan(work):
    _write(work, 'config.csv', HEADER + 'Sample_ATP.atp,DSSC Capture,TDO,[7-7]\n')
    proc = _cli(work, 'check', 'config.csv', '--atp-dir', 'Sample', '--json')
    data = _json(proc)

    check('check exits 0', proc.returncode == 0, proc.stderr)
    check('check returns a plan', len(data['plan']) == 1)
    check('plan names the operations',
          bool(data['plan']) and data['plan'][0]['operations'] == ['DSSC Capture'])
    check('check writes nothing',
          not os.path.exists(os.path.join(work, 'Output')))


def check_modes(work):
    proc = _cli(work, 'modes', '--json')
    rows = _json(proc)
    by_name = {row['process_type']: row['requires'] for row in rows}

    check('modes exits 0', proc.returncode == 0, proc.stderr)
    check('modes lists Expand Loop', 'Expand Loop' in by_name)
    check('modes names required fields',
          by_name.get('DSSC Capture') == ['Pin or Method', 'Cycle']
          and by_name.get('Expand Repeat') == [],
          repr(by_name))


# --- usage -----------------------------------------------------------------

def check_usage(work):
    _write(work, 'config.csv', HEADER + 'Sample_ATP.atp,DSSC Capture,TDO,[7-7]\n')
    proc = _cli(work, 'run', 'config.csv', '--atp', 'missing.atp', '--json')

    check('a missing --atp file exits 2', proc.returncode == 2, proc.stderr)


def check_version(work):
    proc = _cli(work, '--version')

    check('--version exits 0', proc.returncode == 0, proc.stderr)
    check('--version prints the package version', PACKAGE_VERSION in proc.stdout,
          proc.stdout)


def main():
    checks = [check_run, check_chain, check_output_dir, check_missing_pattern,
              check_zero_matched, check_invalid_config, check_human_output,
              check_plan, check_modes, check_usage, check_version]
    for fn in checks:
        work = _workdir()
        try:
            fn(work)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    if _failures:
        print(f"\n{len(_failures)} check(s) failed: " + ", ".join(_failures))
        return 1
    print("\nAll CLI checks passed.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
