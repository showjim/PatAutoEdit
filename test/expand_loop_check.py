"""Checks for Expand Loop, Expand Repeat, and the repeat-label fix.

    python test/expand_loop_check.py

Expected vector counts are derived by hand from the UltraPin1600 counter rules
(see doc/feat-expand-loop/plan.md): `set cX N` runs a loop or counter repeat N
times, `set_msb` supplies the upper 12 bits of (N-1), and a loop counter is
back at its set value once its loop ends.

Every check runs in a throwaway directory, because the engine writes Output/
relative to the current working directory and drops intermediate files next to
the source ATP.
"""
import os
import re
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from src.atp_handler import MODE_LIST, missing_requirements  # noqa: E402
from src.logger import Logger  # noqa: E402
from src.main import process_atp_simple  # noqa: E402

FIXTURES = os.path.join(REPO, 'Sample', 'expand_loop')
SAMPLE_ATP = os.path.join(REPO, 'Sample', 'Sample_ATP.atp')

_failures = []


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'{status}  {name}' + (f'  -- {detail}' if detail and not condition else ''))
    if not condition:
        _failures.append(name)


class Run:
    """The outcome of one chain of modes on one file."""

    def __init__(self, text, messages):
        self.text = text          # output file content, or None when nothing was produced
        self.messages = messages  # every log line

    @property
    def ok(self):
        return self.text is not None

    def errors(self):
        return ' | '.join(m for m in self.messages if m.startswith('Error'))

    def warnings(self):
        return ' | '.join(m for m in self.messages if m.startswith('Warning'))

    def vectors(self):
        return [l for l in self.text.splitlines() if '>' in l and not l.strip().startswith('//')]

    def count(self, pattern):
        return len(re.findall(pattern, self.text, flags=re.MULTILINE))


def run_chain(source, modes, time_mode='Single'):
    """Copy `source` into a fresh directory and run `modes` on it in order."""
    cwd = os.getcwd()
    work = tempfile.mkdtemp(prefix='pae_expand_')
    try:
        os.chdir(work)
        name = os.path.basename(source)
        shutil.copy2(source, name)
        messages = []
        ops = [{"ATPFile": name, "CycleRange": [], "Mode": m, "PinName": "", "UserString": "",
                "TimeMode": time_mode, "IndexMode": "Cycle"} for m in modes]
        results = process_atp_simple([name], logger=Logger(gui_callback=messages.append),
                                     config_list=ops)
        text = None
        if results:
            with open(results[0]) as f:
                text = f.read()
        return Run(text, messages)
    finally:
        os.chdir(cwd)
        shutil.rmtree(work, ignore_errors=True)


def run_text(atp_text, modes, time_mode='Single', name='synthetic.atp'):
    """Write `atp_text` to a scratch file and run `modes` on it."""
    scratch = tempfile.mkdtemp(prefix='pae_src_')
    try:
        path = os.path.join(scratch, name)
        with open(path, 'w') as f:
            f.write(atp_text)
        return run_chain(path, modes, time_mode)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def srm(body, header='import tset t;\n\n', kind='srm_vector'):
    return header + kind + ' ( $tset, a )\n{\n' + body + '}\n'


def source_text(path):
    with open(path) as f:
        return f.read()


# --- modes are registered ----------------------------------------------------

def check_modes():
    for mode in ('Expand Loop', 'Expand Repeat', 'Expand Pattern'):
        check(f'{mode} is a known mode', mode in MODE_LIST)
        check(f'{mode} needs no pin, cycle or user string',
              missing_requirements({"Mode": mode}) == [], missing_requirements({"Mode": mode}))


# --- march6n: one counter, two loops, two counter repeats --------------------

def check_march6n():
    src = os.path.join(FIXTURES, 'march6n.atp')

    el = run_chain(src, ['Expand Loop'])
    check('march6n Expand Loop succeeds', el.ok, el.errors())
    if el.ok:
        check('march6n Expand Loop: 131,077 vectors', len(el.vectors()) == 131077, len(el.vectors()))
        check('march6n Expand Loop: module becomes vm_vector',
              el.count(r'^\s*vm_vector\b') == 1 and el.count(r'srm_vector') == 0)
        check('march6n Expand Loop: no loop / end_loop left',
              el.count(r'\bloop\b') == 0 and el.count(r'\bend_loop\b') == 0)
        check('march6n Expand Loop: both repeat c0 stay', el.count(r'\brepeat c0\b') == 2)
        check('march6n Expand Loop: set_msb and set c0 stay because repeat c0 still needs c0',
              el.count(r'\bset_msb\b') == 1 and el.count(r'\bset c0\b') == 1)
        check('march6n Expand Loop: end_loop labels dropped',
              el.count(r'march6n_1:') == 0 and el.count(r'march6n_2:') == 0)

    er = run_chain(src, ['Expand Repeat'])
    check('march6n Expand Repeat succeeds', er.ok, er.errors())
    if er.ok:
        # 9 source vectors, two of them repeat c0: 7 + 2 x 32,768.
        check('march6n Expand Repeat: 65,543 vectors', len(er.vectors()) == 65543, len(er.vectors()))
        check('march6n Expand Repeat: module stays srm_vector', er.count(r'^\s*srm_vector\b') == 1)
        check('march6n Expand Repeat: no repeat c0 left', er.count(r'\brepeat\s+c\d') == 0)
        check('march6n Expand Repeat: loops stay', er.count(r'\bloop c0\b') == 2)
        check('march6n Expand Repeat: set_msb and set c0 stay because loop c0 still needs c0',
              er.count(r'\bset_msb\b') == 1 and er.count(r'\bset c0\b') == 1)
        check('march6n Expand Repeat: end_loop labels stay',
              er.count(r'^march6n_1:') == 1 and er.count(r'^march6n_2:') == 1)

    ep = run_chain(src, ['Expand Pattern'])
    check('march6n Expand Pattern is byte-identical to Expand Repeat',
          er.ok and ep.ok and ep.text == er.text)

    both = run_chain(src, ['Expand Loop', 'Expand Repeat'])
    rev = run_chain(src, ['Expand Repeat', 'Expand Loop'])
    check('march6n Expand Loop -> Expand Repeat succeeds', both.ok, both.errors())
    check('march6n Expand Repeat -> Expand Loop succeeds', rev.ok, rev.errors())
    if both.ok and rev.ok:
        check('march6n both modes: 196,611 vectors', len(both.vectors()) == 196611, len(both.vectors()))
        check('march6n both modes: either order is byte-identical', both.text == rev.text)
        check('march6n both modes: no loop, end_loop, repeat cX, set or set_msb left',
              both.count(r'\b(loop|end_loop|set_msb)\b') == 0
              and both.count(r'\brepeat\s+c\d') == 0 and both.count(r'\bset\s+c\d') == 0)
        # One mto line per executed vector that had one: five such vectors, each
        # run 32,768 times, plus the jam_reg line before the first set.
        check('march6n both modes: every expanded copy keeps its mto line',
              both.count(r'^\(mto') == 5 * 32768 + 1, both.count(r'^\(mto'))
        check('march6n both modes: the (mto = dset 1 ) line appears once per loop-1 iteration',
              both.count(r'^\(mto = dset 1 \)') == 32768, both.count(r'^\(mto = dset 1 \)'))


# --- mychecker: nested loops, two counters, opcodes combined with stv -------

def check_mychecker():
    src = os.path.join(FIXTURES, 'mychecker.atp')
    original = source_text(src)

    el = run_chain(src, ['Expand Loop'])
    check('mychecker Expand Loop succeeds', el.ok, el.errors())
    if el.ok:
        check('mychecker Expand Loop: 65,543 vectors', len(el.vectors()) == 65543, len(el.vectors()))
        check('mychecker Expand Loop: module becomes vm_vector',
              el.count(r'^\s*vm_vector\b') == 1 and el.count(r'srm_vector') == 0)
        check('mychecker Expand Loop: no loop, end_loop, set or set_msb left',
              el.count(r'\b(loop|end_loop|set_msb)\b') == 0 and el.count(r'\bset\s+c\d') == 0)
        # set c1 255, stv (1) + read_cols body: 32 x (2 + 255 x 4 + 2), all stv.
        stv = [v for v in el.vectors() if 'stv' in v.split('>')[0]]
        check('mychecker Expand Loop: stv kept on every vector that had it',
              len(stv) == 1 + 32 * 1024, len(stv))
        check('mychecker Expand Loop: "set c1 255, stv" becomes "stv"',
              any(v.split('>')[0].strip() == 'stv' and 'XXXXXXXX' in v for v in el.vectors()))
        check('mychecker Expand Loop: full-line comments in the body are dropped',
              '// Write Background data' not in el.text and '// Read Background data' not in el.text)
        check('mychecker Expand Loop: header comments kept', '// Checker_board Pattern' in el.text)
        check('mychecker Expand Loop: module name kept', 'checker_board_mod' in el.text)

    er = run_chain(src, ['Expand Repeat'])
    check('mychecker Expand Repeat succeeds', er.ok, er.errors())
    if er.ok:
        check('mychecker Expand Repeat: nothing to expand, vector count unchanged',
              len(er.vectors()) == len(Run(original, []).vectors()))
        check('mychecker Expand Repeat: stays srm_vector', er.count(r'^\s*srm_vector\b') == 1)

    both = run_chain(src, ['Expand Loop', 'Expand Repeat'])
    rev = run_chain(src, ['Expand Repeat', 'Expand Loop'])
    check('mychecker either order is byte-identical', both.ok and rev.ok and both.text == rev.text)


# --- synthetic cases ---------------------------------------------------------

def check_synthetic():
    # A set inside the outer body changes the inner count from the 2nd outer pass on.
    r = run_text(srm(
        'set_msb 2       > t 0 ;\n'
        'set c0 3        > t 0 ;\n'
        'set c1 2        > t 0 ;\n'
        'outer:\n'
        'loop c0         > t 1 ;\n'
        'inner:\n'
        'loop c1         > t H ;\n'
        'end_loop inner  > t L ;\n'
        'set c1 4        > t 0 ;\n'
        'end_loop outer  > t 1 ;\n'
        'halt            > t 0 ;\n'), ['Expand Loop'])
    check('set inside a loop body succeeds', r.ok, r.errors())
    if r.ok:
        h = [v for v in r.vectors() if v.rstrip(' ;').endswith('H')]
        check('set inside a loop body: inner runs 2, then 4, then 4', len(h) == 10, len(h))
        check('set inside a loop body: 33 vectors', len(r.vectors()) == 33, len(r.vectors()))

    # MSBs matter above 65536, and a set without a fresh set_msb reuses them.
    r = run_text(srm(
        'set_msb 70000   > t 0 ;\n'
        'set c0 70000    > t 0 ;\n'
        'repeat c0       > t 1 ;\n'
        'set c1 3        > t 0 ;\n'
        'repeat c1       > t H ;\n'
        'halt            > t 0 ;\n'), ['Expand Repeat'])
    check('set_msb above 65536 succeeds', r.ok, r.errors())
    if r.ok:
        ones = [v for v in r.vectors() if v.rstrip(' ;').endswith('1')]
        h = [v for v in r.vectors() if v.rstrip(' ;').endswith('H')]
        check('set_msb above 65536: repeat c0 runs 70,000 times', len(ones) == 70000, len(ones))
        check('stale MSBs: set c1 3 after set_msb 70000 loads 65,538, so 65,539 runs',
              len(h) == 65539, len(h))
        check('counter repeats only: set and set_msb removed',
              r.count(r'\bset_msb\b') == 0 and r.count(r'\bset\s+c\d') == 0)

    # A label that is not an end_loop target, and a comment, inside a loop body.
    r = run_text(srm(
        'set_msb 3       > t 0 ;\n'
        'set c0 3        > t 0 ;\n'
        'top:\n'
        'loop c0         > t 1 ;\n'
        '// inside the body\n'
        'mid:\n'
        '                > t 0 ;\n'
        'end_loop top    > t 1 ;\n'
        'halt            > t 0 ;\n'), ['Expand Loop'])
    check('label inside a loop body succeeds', r.ok, r.errors())
    if r.ok:
        check('label inside a loop body: kept on the first copy only', r.count(r'^mid:') == 1)
        check('label inside a loop body: end_loop target dropped', r.count(r'^top:') == 0)
        check('label inside a loop body: warning names the label', 'mid' in r.warnings(), r.warnings())
        check('label inside a loop body: full-line comment dropped', 'inside the body' not in r.text)
        check('label inside a loop body: 2 + 3 x 3 + 1 vectors', len(r.vectors()) == 12, len(r.vectors()))

    # A label directly above a repeated vector is written once.
    r = run_text(srm('lbl:\nrepeat 3        > t 1 ;\nhalt            > t 0 ;\n', kind='vector'),
                 ['Expand Pattern'])
    check('label above repeat N succeeds', r.ok, r.errors())
    if r.ok:
        check('label above repeat N: written once', r.count(r'^lbl:') == 1, r.count(r'^lbl:'))
        check('label above repeat N: 3 + 1 vectors', len(r.vectors()) == 4, len(r.vectors()))

    r = run_text(srm('set_msb 3       > t 0 ;\nset c0 3        > t 0 ;\nlbl:\n'
                     'repeat c0       > t 1 ;\nhalt            > t 0 ;\n', kind='vm_vector'),
                 ['Expand Repeat'])
    check('label above repeat cX succeeds', r.ok, r.errors())
    if r.ok:
        check('label above repeat cX: written once', r.count(r'^lbl:') == 1, r.count(r'^lbl:'))
        check('label above repeat cX: 2 + 3 + 1 vectors', len(r.vectors()) == 6, len(r.vectors()))


# --- nothing to expand -------------------------------------------------------

def check_pass_through():
    r = run_chain(SAMPLE_ATP, ['Expand Loop'])
    check('Expand Loop on a plain vector file succeeds', r.ok, r.errors())
    check('Expand Loop on a plain vector file: byte-identical',
          r.ok and r.text == source_text(SAMPLE_ATP))
    check('Expand Loop on a plain vector file: info says it was copied unchanged',
          any(m.startswith('Info') and 'unchanged' in m for m in r.messages), r.messages)

    keepalive = srm('set_msb 3       > t 0 ;\nset c0 3        > t 0 ;\nrepeat c0       > t 1 ;\n'
                    'halt            > t 0 ;\n')
    r = run_text(keepalive, ['Expand Loop'])
    check('srm_vector without loops: stays SRM and byte-identical',
          r.ok and r.text == keepalive, r.errors())

    ep = run_chain(SAMPLE_ATP, ['Expand Pattern'])
    er = run_chain(SAMPLE_ATP, ['Expand Repeat'])
    check('Sample_ATP.atp: Expand Pattern and Expand Repeat byte-identical',
          ep.ok and er.ok and ep.text == er.text)


# --- fail-the-file cases -----------------------------------------------------

_LOOP = ('set_msb 3       > t 0 ;\nset c0 3        > t 0 ;\ntop:\nloop c0         > t 1 ;\n'
         '{extra}'
         'end_loop top    > t 1 ;\nhalt            > t 0 ;\n')


def expect_failure(name, run, needle):
    check(f'{name}: no output', not run.ok)
    check(f'{name}: error mentions {needle!r}', needle in run.errors(), run.errors())


def check_failures():
    for opcode in ('push_loop c0', 'pop_loop', 'clr_loop', 'jump top', 'call sub', 'return',
                   'set_infinite c0', 'set_msb_infinite'):
        word = opcode.split()[0]
        expect_failure(f'Expand Loop with {word}',
                       run_text(srm(_LOOP.format(extra=f'{opcode:<15} > t 0 ;\n')), ['Expand Loop']),
                       word)

    expect_failure('Expand Loop with a counter that was never set',
                   run_text(srm('set_msb 3       > t 0 ;\ntop:\nloop c2         > t 1 ;\n'
                                'end_loop top    > t 1 ;\n'), ['Expand Loop']), 'c2')
    expect_failure('Expand Loop with set before set_msb',
                   run_text(srm('set c0 3        > t 0 ;\ntop:\nloop c0         > t 1 ;\n'
                                'end_loop top    > t 1 ;\n'), ['Expand Loop']), 'set_msb')
    expect_failure('Expand Loop with an undefined end_loop label',
                   run_text(srm(_LOOP.format(extra='').replace('end_loop top', 'end_loop nowhere')),
                            ['Expand Loop']), 'nowhere')
    expect_failure('Expand Loop with a relative end_loop address',
                   run_text(srm(_LOOP.format(extra='').replace('end_loop top', 'end_loop -1  ')),
                            ['Expand Loop']), 'relative')
    expect_failure('Expand Loop on an opcode_mode=dual file',
                   run_text(srm(_LOOP.format(extra=''), header='opcode_mode=dual;\nimport tset t;\n\n'),
                            ['Expand Loop']), 'Single')
    expect_failure('Expand Loop with Dual chosen in the GUI',
                   run_text(srm(_LOOP.format(extra='')), ['Expand Loop'], time_mode='Dual'), 'Single')
    expect_failure('Expand Repeat on repeat c0 inside a loop counting on c0',
                   run_text(srm(_LOOP.format(extra='repeat c0       > t 0 ;\n')), ['Expand Repeat']),
                   'c0')
    expect_failure('Expand Loop on repeat c0 inside a loop counting on c0',
                   run_text(srm(_LOOP.format(extra='repeat c0       > t 0 ;\n')), ['Expand Loop']),
                   'c0')
    expect_failure('Expand Repeat on repeat c0 with no set',
                   run_text(srm('set_msb 3       > t 0 ;\nrepeat c0       > t 1 ;\n'), ['Expand Repeat']),
                   'c0')


# --- set_msb inside a loop body ----------------------------------------------

def check_msb_in_loop():
    """set_msb is legal inside a loop body, but with a set cX in the same body
    it gives cX a different value on later passes. Expand Loop follows every
    pass; Expand Repeat reads the body once, so it must refuse and say why."""
    # Pass 1: c1 = 2 runs (MSB 0). set_msb 65537 makes the MSBs 1, so pass 2: c1 = 65,538.
    inside = srm('set_msb 2       > t 0 ;\nset c0 2        > t 0 ;\nouter:\nloop c0         > t 0 ;\n'
                 'set c1 2        > t 0 ;\nrepeat c1       > t H ;\nset_msb 65537   > t 0 ;\n'
                 'end_loop outer  > t 0 ;\nhalt            > t 0 ;\n')
    # After the loop, c1 holds the last pass's value: 65,538 runs.
    after = srm('set_msb 2       > t 0 ;\nset c0 2        > t 0 ;\nouter:\nloop c0         > t 0 ;\n'
                'set c1 2        > t 0 ;\nset_msb 65537   > t 0 ;\nend_loop outer  > t 0 ;\n'
                'repeat c1       > t H ;\nhalt            > t 0 ;\n')
    for name, text, expected in (('repeat c1 inside the loop', inside, 2 + 65538),
                                 ('repeat c1 after the loop', after, 65538)):
        r = run_text(text, ['Expand Loop', 'Expand Repeat'])
        h = sum(v.rstrip(' ;').endswith('H') for v in r.vectors()) if r.ok else None
        check(f'{name}: Expand Loop -> Expand Repeat gives {expected:,} runs', h == expected, (h, r.errors()))
        r = run_text(text, ['Expand Repeat'])
        check(f'{name}: Expand Repeat alone fails', not r.ok)
        check(f'{name}: the error says why and what to run first',
              'set_msb' in r.errors() and 'c1' in r.errors() and 'Expand Loop first' in r.errors(),
              r.errors())

    # set_msb in a body with no set c1 there cannot change c1, so this is fine.
    r = run_text(srm('set_msb 2       > t 0 ;\nset c0 2        > t 0 ;\nset c1 3        > t 0 ;\n'
                     'outer:\nloop c0         > t 0 ;\nset_msb 65537   > t 0 ;\nend_loop outer  > t 0 ;\n'
                     'repeat c1       > t H ;\nhalt            > t 0 ;\n'), ['Expand Repeat'])
    h = sum(v.rstrip(' ;').endswith('H') for v in r.vectors()) if r.ok else None
    check('set_msb in a body without set c1: Expand Repeat gives 3 runs', h == 3, (h, r.errors()))


# --- counters this mode does not read ----------------------------------------

def check_unread_counters():
    """A mode only needs the value of opcodes it expands; a counter loaded
    elsewhere (e.g. from VBT) on an opcode it leaves in place is fine."""
    r = run_text(srm('set_msb 2       > t 0 ;\nset c0 2        > t 0 ;\ntop:\nloop c0         > t H ;\n'
                     'end_loop top    > t L ;\nrepeat c1       > t 1 ;\nhalt            > t 0 ;\n'),
                 ['Expand Loop'])
    check('Expand Loop leaves an unset repeat c1 in place', r.ok and 'repeat c1' in r.text, r.errors())
    r = run_text(srm('set_msb 2       > t 0 ;\nset c1 2        > t 0 ;\ntop:\nloop c0         > t H ;\n'
                     'end_loop top    > t L ;\nrepeat c1       > t 1 ;\nhalt            > t 0 ;\n'),
                 ['Expand Repeat'])
    check('Expand Repeat leaves an unset loop c0 in place', r.ok and 'loop c0' in r.text, r.errors())


def main():
    for fn in (check_modes, check_march6n, check_mychecker, check_synthetic, check_pass_through,
               check_failures, check_msb_in_loop, check_unread_counters):
        print(f'\n--- {fn.__name__} ---')
        fn()

    print()
    if _failures:
        print(f'{len(_failures)} check(s) FAILED: ' + ', '.join(_failures))
        return 1
    print('All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
