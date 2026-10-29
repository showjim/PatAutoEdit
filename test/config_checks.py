"""Checks for the row-per-op config format and its failure paths.

    python test/config_checks.py

Every check runs in a throwaway directory, because the engine writes Output/
relative to the current working directory and drops intermediate files next to
the source ATP.
"""
import os
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from src.atp_handler import ConfigError, analyse_merge_config  # noqa: E402
from src.logger import Logger  # noqa: E402
from src.main import process_atp_simple  # noqa: E402

SAMPLE_DIR = os.path.join(REPO, 'Sample')
ATP = 'Sample_ATP.atp'

HEADER = 'Pattern,Process Type,Pin or Method,Cycle,User String'

_failures = []


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'{status}  {name}' + (f'  -- {detail}' if detail and not condition else ''))
    if not condition:
        _failures.append(name)


def _workdir():
    """Fresh directory holding a copy of Sample/, with cwd already moved into it."""
    work = tempfile.mkdtemp(prefix='pae_checks_')
    shutil.copytree(SAMPLE_DIR, os.path.join(work, 'Sample'))
    os.chdir(work)
    return work


def _atp_files():
    return [os.path.join('Sample', f) for f in sorted(os.listdir('Sample'))
            if f.lower().endswith('.atp')]


def _config_file(text, name='config.csv'):
    with open(name, 'w', newline='', encoding='utf-8') as f:
        f.write(text)
    return name


def _op(cycles, mode, pin, user_string=''):
    return {"ATPFile": ATP, "CycleRange": cycles, "Mode": mode, "PinName": pin,
            "UserString": user_string, "TimeMode": "Single", "IndexMode": "Cycle"}


def _parse(text, logger=None):
    return analyse_merge_config(_config_file(text), logger or Logger())


def _parse_error(text):
    try:
        _parse(text)
        return None
    except ConfigError as e:
        return str(e)


# --- parsing ---------------------------------------------------------------

def check_parser(work):
    os.chdir(work)

    msg = _parse_error('Instance(Optional),Pattern,Status,Process Type,Pin or Method,Cycle,Pin or Method,PIN,Cycle\n'
                       ',a.atp,Done,DSSC Capture,TDO,[7-7],DSSC Capture,PORN,[13-14]\n')
    check('legacy 9-column file is rejected', msg is not None and 'one row per operation' in msg, msg)

    msg = _parse_error('Pattern,Process Type\n' + f'{ATP},DSSC Capture\n')
    check('missing required columns are named',
          msg is not None and 'pin or method' in msg and 'cycle' in msg, msg)

    msg = _parse_error('Pattern,Process Type,Pin or Method,Cycle\n')
    check('header with no data rows is rejected',
          msg is not None and 'no operations' in msg, msg)

    msg = _parse_error(HEADER + f'\n{ATP},DSSC Capture,TDO,not-a-cycle\n')
    check('malformed Cycle is rejected with the line number',
          msg is not None and 'line 2' in msg, msg)

    ops = _parse(HEADER + f'\n{ATP},DSSC Capture,TDO,[7-7]\n\n\n{ATP},WFLAG,,[8-8]\n')
    check('blank rows mid-file are skipped, not treated as end-of-file',
          len(ops) == 2, f'parsed {len(ops)}')

    ops = _parse('Pattern,Process Type,Pin or Method,Cycle,NotAColumn\n'
                 f'{ATP},DSSC Capture,TDO,[7-7],junk\n')
    check('unknown column does not stop parsing', len(ops) == 1)

    ops = _parse('pattern,PROCESS type,pin or Method,cycle\n' + f'{ATP},DSSC Capture,TDO,[7-7]\n')
    check('column names are matched case-insensitively', len(ops) == 1)

    ops = _parse(f'Cycle,Pin or Method,Process Type,Pattern\n[7-7],TDO,DSSC Capture,{ATP}\n')
    check('column order does not matter',
          len(ops) == 1 and ops[0]['Mode'] == 'DSSC Capture' and ops[0]['PinName'] == 'TDO')

    ops = _parse(HEADER + f'\n{ATP},DSSC Capture,TDO,[7-7]\n{ATP},WFLAG,,[8-8]\n{ATP},DSSC Source,TDI,[9-9]\n')
    check('N operations on one file all parse', len(ops) == 3, f'parsed {len(ops)}')


# --- validation ------------------------------------------------------------

def check_validation(work):
    os.chdir(work)
    logger = Logger()

    cases = [
        ('unknown Process Type is rejected', [_op([7], 'Not A Mode', 'TDO')]),
        ('Capture without a pin is rejected', [_op([7], 'DSSC Capture', '')]),
        ('Capture without a cycle is rejected', [_op([], 'DSSC Capture', 'TDO')]),
        ('Add Opcode without a User String is rejected', [_op([7], 'Add Opcode', '', '')]),
    ]
    for name, config in cases:
        result = process_atp_simple(_atp_files(), logger=logger, config_list=config)
        check(name, result == [], f'returned {result}')

    result = process_atp_simple(_atp_files(), logger=logger,
                                config_list=[_op([7], 'Add Opcode', '', 'set_msb_infinite')])
    check('Add Opcode with a User String is accepted', result != [])

    result = process_atp_simple(_atp_files(), logger=logger,
                                config_list=[{"ATPFile": 'no-such-file.atp', "CycleRange": [7],
                                              "Mode": 'DSSC Capture', "PinName": 'TDO',
                                              "UserString": '', "TimeMode": "Single",
                                              "IndexMode": "Cycle"}])
    check('unmatched Pattern warns and is skipped, without failing the run', result == [])


# --- failure propagation ---------------------------------------------------

def check_failures(work):
    os.chdir(work)
    logger = Logger()

    result = process_atp_simple(_atp_files(), logger=logger,
                                config_list=[_op([99999], 'DSSC Capture', 'TDO')])
    check('a failed op yields no result (not the input path)', result == [], f'returned {result}')

    result = process_atp_simple(_atp_files(), logger=logger,
                                config_list=[_op([7, 7], 'DSSC Capture', 'TDO'),
                                             _op([99999], 'DSSC Capture', 'PORN'),
                                             _op([9, 9], 'DSSC Source', 'TDI')])
    check('a failure aborts the chain and drops the whole file', result == [], f'returned {result}')


# --- capability ------------------------------------------------------------

def check_user_string(work):
    os.chdir(work)
    logger = Logger()
    original = open(os.path.join('Sample', ATP), 'rb').read()

    result = process_atp_simple(_atp_files(), logger=logger,
                                config_list=[_op([7], 'Remove Opcode', '', 'repeat')])
    changed = bool(result) and open(result[0], 'rb').read() != original
    check('Remove Opcode with a User String actually edits the file', changed)

    shutil.rmtree('Output', ignore_errors=True)
    result = process_atp_simple(_atp_files(), logger=logger,
                                config_list=[_op([7], 'Add Opcode', '', 'set_msb_infinite')])
    edited = bool(result) and open(result[0], 'rb').read() != original
    check('Add Opcode with a User String actually edits the file', edited)


def check_source_dir(work):
    os.chdir(work)
    logger = Logger()
    before = set(os.listdir('Sample'))

    process_atp_simple(_atp_files(), logger=logger,
                       config_list=[_op([7, 7], 'DSSC Capture', 'TDO'),
                                    _op([13, 14], 'DSSC Capture', 'PORN'),
                                    _op([9, 9], 'DSSC Source', 'TDI')])
    check('a successful chain leaves the source directory untouched',
          set(os.listdir('Sample')) == before, str(set(os.listdir('Sample')) - before))

    process_atp_simple(_atp_files(), logger=logger,
                       config_list=[_op([99999], 'DSSC Capture', 'TDO')])
    leftover = set(os.listdir('Sample')) - before
    check('a failing op leaves no intermediate in the source directory',
          leftover == set(), str(leftover))


def check_scratch_files(work):
    """Scratch files sit next to the source and are named after it. An
    upper-case extension must not make the scratch path equal the source, and
    a user's file that happens to carry the scratch name must survive."""
    os.chdir(work)
    with open(os.path.join('Sample', ATP)) as f:
        original = f.read()
    counter_atp = ('import tset t;\n\nvector ( $tset, a )\n{\nset_msb 3  > t 0 ;\nset c0 3   > t 0 ;\n'
                   'repeat c0  > t 1 ;\nhalt       > t 0 ;\n}\n')

    def run(name, text, mode, cycles=(), pin='', user_string=''):
        path = os.path.join('Sample', name)
        with open(path, 'w') as f:
            f.write(text)
        messages = []
        op = dict(_op(list(cycles), mode, pin, user_string), ATPFile=name)
        results = process_atp_simple([path], logger=Logger(gui_callback=messages.append),
                                     config_list=[op])
        return path, results, ' | '.join(m for m in messages if m.startswith('Error'))

    for mode, cycles, pin, user_string in (('Expand Pattern', (), '', ''),
                                           ('Expand Repeat', (), '', ''),
                                           ('Expand Loop', (), '', ''),
                                           ('Compress Pattern', (), '', ''),
                                           ('Remove Opcode', (), '', 'repeat'),
                                           ('DSSC Capture', (7, 7), 'TDO', '')):
        path, results, errors = run('Upper.ATP', original, mode, cycles, pin, user_string)
        kept = None
        if os.path.exists(path):
            with open(path) as f:
                kept = f.read()
        size = os.path.getsize(results[0]) if results and os.path.exists(results[0]) else 0
        check(f'{mode} on an upper-case .ATP keeps the source', kept == original, errors)
        check(f'{mode} on an upper-case .ATP writes a non-empty output', size > 0, errors)

    for mode, tag, text, user_string in (('Expand Pattern', 'RemoveRepeat', original, ''),
                                         ('Expand Repeat', 'ExpandCounterRepeat', counter_atp, ''),
                                         ('Expand Loop', 'ExpandLoop', original, ''),
                                         ('Compress Pattern', 'AddRepeat', original, ''),
                                         ('Remove Opcode', 'RemoveOpcode', original, 'repeat')):
        sibling = os.path.join('Sample', f'Mine_{tag}.atp')
        with open(sibling, 'w') as f:
            f.write('my own file\n')
        _, results, errors = run('Mine.atp', text, mode, user_string=user_string)
        survived = False
        if os.path.exists(sibling):
            with open(sibling) as f:
                survived = f.read() == 'my own file\n'
            os.remove(sibling)
        check(f'{mode} leaves an existing Mine_{tag}.atp untouched', survived)
        check(f'{mode} fails and names the clashing Mine_{tag}.atp',
              not results and f'Mine_{tag}.atp' in errors, errors)


# --- parallel dispatch -----------------------------------------------------

def check_parallel(work):
    """The GUI runs this path. A task that dies must still be reported as
    finished, or the completion counter never reaches the total and the
    Generate button stays disabled forever."""
    os.chdir(work)
    from multiprocessing import Manager, Pool
    from src.main import dispatch_config_parallel

    manager = Manager()
    results = manager.list()
    logger = Logger()

    ok = dict(_op([7, 7], 'DSSC Capture', 'TDO'))
    bad = dict(_op([99999], 'DSSC Capture', 'TDO'))
    bad['ATPFile'] = 'Sample_ATP - 1.atp'

    with Pool(processes=2) as pool:
        total = dispatch_config_parallel(pool, _atp_files(), [ok, bad], logger, '',
                                         results.append)
        pool.close()
        pool.join()

    check('every dispatched task reports completion',
          total == 2 and len(results) == 2, f'total={total} callbacks={len(results)}')
    check('a failing task reports None rather than a path',
          sum(1 for r in results if r is None) == 1, f'results={list(results)}')
    check('a succeeding task reports its output path',
          sum(1 for r in results if r) == 1, f'results={list(results)}')

    with Pool(processes=2) as pool:
        total = dispatch_config_parallel(pool, _atp_files(),
                                         [_op([7], 'Not A Mode', 'TDO')], logger, '',
                                         results.append)
        pool.close()
        pool.join()
    check('a rejected config dispatches nothing', total == 0, f'total={total}')


def main():
    for fn in (check_parser, check_validation, check_failures, check_user_string,
               check_source_dir, check_scratch_files, check_parallel):
        cwd = os.getcwd()
        work = _workdir()
        print(f'\n--- {fn.__name__} ---')
        try:
            fn(work)
        finally:
            os.chdir(cwd)
            shutil.rmtree(work, ignore_errors=True)

    print()
    if _failures:
        print(f'{len(_failures)} check(s) FAILED: ' + ', '.join(_failures))
        return 1
    print('All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
