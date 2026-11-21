"""Capture and compare ATP outputs across the config-format rewrite.

The four-op capability already works on master; only the CSV parser changes.
These helpers exist so the parser rewrite can be proven behaviour-preserving
against outputs captured from unmodified code.

    python test/regression_baseline.py run-sample <outdir>   # the simple CSV sample
    python test/regression_baseline.py run-chain4 <outdir>   # hand-built 4-op chain
    python test/regression_baseline.py diff <dirA> <dirB> [name ...]

`run-sample` reads Sample/Sample_ATP - simple.csv, so it captures the baseline
when run before the rewrite and verifies it afterwards. `run-chain4` builds its
config list in memory, bypassing the parser entirely, so it works on either side
of the change and is what Sample_ATP.atp's output is compared against — the
rewritten sample gives that file four ops instead of two.

Every run happens in a throwaway directory with a copy of Sample/, because the
engine writes relative to the current working directory and drops temp files
next to the source ATP.
"""
import hashlib
import os
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from patautoedit.atp_handler import analyse_merge_config, build_config_from_classical  # noqa: E402
from patautoedit.logger import Logger  # noqa: E402
from patautoedit.main import process_atp_simple  # noqa: E402

SAMPLE_DIR = os.path.join(REPO, 'Sample')
CONFIG = os.path.join(SAMPLE_DIR, 'Sample_ATP - simple.csv')


def _atp_files():
    return [os.path.join('Sample', f)
            for f in sorted(os.listdir('Sample'))
            if f.lower().endswith('.atp')]


def _chain4_config():
    """The four ops the rewritten sample lists for Sample_ATP.atp.

    Built in memory so it exercises the chain engine without the parser, which
    makes it usable as a baseline on both sides of the rewrite.
    """
    def op(cycles, mode, pin):
        return {"ATPFile": "Sample_ATP.atp", "CycleRange": cycles, "Mode": mode,
                "PinName": pin, "TimeMode": "Single", "IndexMode": "Cycle"}
    return [
        op([7, 7, 12, 12], 'DSSC Capture', 'TDO'),
        op([13, 14], 'DSSC Source', 'PORN'),
        op([9, 9], 'DSSC Source', 'TDI'),
        op([8, 8], 'WFLAG', ''),
    ]


def _run(config_list, outdir, tag):
    work = tempfile.mkdtemp(prefix='pae_regress_')
    cwd = os.getcwd()
    try:
        os.chdir(work)
        shutil.copytree(SAMPLE_DIR, 'Sample')
        logger = Logger()
        results = process_atp_simple(_atp_files(), logger=logger, config_list=config_list)

        os.makedirs(outdir, exist_ok=True)
        for path in results:
            if os.path.exists(path):
                shutil.copy2(path, os.path.join(outdir, os.path.basename(path)))
        print(f'[{tag}] {len(results)} result(s) -> {outdir}')
        for name in sorted(os.listdir(outdir)):
            print(f'[{tag}]   {name}  {_digest(os.path.join(outdir, name))}')
    finally:
        os.chdir(cwd)
        shutil.rmtree(work, ignore_errors=True)


def _digest(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def run_sample(outdir):
    logger = Logger()
    config = analyse_merge_config(CONFIG, logger)
    print(f'[sample] parsed {len(config)} op(s)')
    _run(config, outdir, 'sample')


def run_chain4(outdir):
    _run(_chain4_config(), outdir, 'chain4')


def run_classical(outdir):
    """The Classical tab's path: 2-column CSV plus GUI settings."""
    config = build_config_from_classical(os.path.join(SAMPLE_DIR, 'Sample_ATP.csv'),
                                         'DSSC Capture', 'TDO', 'Single', 'Cycle')
    print(f'[classical] built {len(config)} op(s)')
    _run(config, outdir, 'classical')


def diff(dir_a, dir_b, names=None):
    names = names or sorted(set(os.listdir(dir_a)) | set(os.listdir(dir_b)))
    status = 0
    for name in names:
        pa, pb = os.path.join(dir_a, name), os.path.join(dir_b, name)
        if not os.path.exists(pa):
            print(f'MISSING in {dir_a}: {name}')
            status = 1
        elif not os.path.exists(pb):
            print(f'MISSING in {dir_b}: {name}')
            status = 1
        elif _digest(pa) == _digest(pb):
            print(f'SAME     {name}  {_digest(pa)}')
        else:
            print(f'DIFFERS  {name}  {_digest(pa)} != {_digest(pb)}')
            status = 1
    return status


if __name__ == '__main__':
    usage = ('usage: regression_baseline.py '
             '{run-sample|run-chain4|run-classical} <outdir> | diff <dirA> <dirB> [name ...]')
    if len(sys.argv) < 3:
        print(usage)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == 'run-sample':
        run_sample(sys.argv[2])
    elif cmd == 'run-chain4':
        run_chain4(sys.argv[2])
    elif cmd == 'run-classical':
        run_classical(sys.argv[2])
    elif cmd == 'diff':
        sys.exit(diff(sys.argv[2], sys.argv[3], sys.argv[4:]))
    else:
        print(usage)
        sys.exit(2)
