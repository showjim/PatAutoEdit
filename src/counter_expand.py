'''
Expansion of counter-driven flow in ATP pattern modules.

`expand_loops` flattens loop / end_loop in srm_vector modules (they do not run
in VM) and turns those modules into vm_vector. `expand_counter_repeats`
flattens `repeat cX` in any module. Literal `repeat N` is left to
`remove_repeat`.

Counter semantics follow UltraPin1600 (IG-XL 11.10.00, Vector Data Microcode):

    set_msb M     MSB register = upper 12 bits of (M - 1)
    set cX N      cX = (MSB << 16) | low16(N - 1)
    loop cX ... end_loop lbl, repeat cX
                  run cX + 1 times, i.e. N times for `set cX N`

A loop counter is back at its set value once its loop ends, so one counter can
drive several loops and repeats in turn. Single mode only.
'''
import re
from typing import Dict, List, Optional, Tuple

from src.file_ops import openfile
from src.logger import Logger
from src.utils import is_label_line

_MODULE = re.compile(r'^\s*(srm_vector|vm_vector|vector)\b')
_OPCODE_MODE = re.compile(r'^\s*opcode_mode\s*=\s*(\w+)', re.IGNORECASE)

# Matched against the opcode field (text before '>') with parenthesised
# instrument groups such as (mto = ...) blanked out.
_OP_PATTERNS = (
    ('unsupported', re.compile(r'\b(push_loop|pop_loop|clr_loop|set_infinite|set_msb_infinite|'
                               r'branch_expr|jump\w*|call\w*|return\w*|if)\b')),
    ('set_msb', re.compile(r'\bset_msb\s+([^\s,]+)')),
    ('set', re.compile(r'\bset\s+c(\d+)\s+([^\s,]+)')),
    ('loop', re.compile(r'\bloop\s+c(\d+)\b')),
    ('end_loop', re.compile(r'\bend_loop\s+([^\s,]+)')),
    ('repeat', re.compile(r'\brepeat\s+c(\d+)\b')),
)
_RELATIVE_ADDRESS = re.compile(r'[+-]?\d+')
_COUNTER_REPEAT_LINE = re.compile(r'\brepeat\s+c\d+\b')
_MAX_VALUE = 2 ** 28 - 1
_COUNTERS = 16


class ExpandError(Exception):
    """A construct that cannot be expanded statically; aborts the file."""

    def __init__(self, line_no: Optional[int], message: str):
        super().__init__(message)
        self.line_no = line_no


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _mask_parens(text: str) -> str:
    """Blank out everything inside parentheses, keeping positions."""
    out, depth = [], 0
    for ch in text:
        if ch == '(':
            depth += 1
        out.append(' ' if depth else ch)
        if ch == ')' and depth:
            depth -= 1
    return ''.join(out)


class _Op:
    __slots__ = ('kind', 'span', 'counter', 'value', 'arg')

    def __init__(self, kind, span, counter=None, value=None, arg=None):
        self.kind, self.span, self.counter, self.value, self.arg = kind, span, counter, value, arg


class _Record:
    """One vector line and the label / instrument / comment lines above it."""
    __slots__ = ('pre', 'labels', 'line_no', 'field', 'rest', 'ops', 'out')

    def __init__(self, pre, line_no, vector):
        self.pre = pre  # [(kind, text, label name)] with kind in 'label', 'comment', 'other'
        self.labels = [name for kind, _, name in pre if kind == 'label']
        self.line_no = line_no
        gt = _mask_parens(vector).index('>')
        self.field, self.rest = vector[:gt], vector[gt:]
        self.ops = _parse_ops(self.field, line_no)
        self.out = vector  # vector line as written, after stripping


def _parse_value(text: str, opcode: str, line_no: int) -> int:
    try:
        value = int(text)
    except ValueError:
        raise ExpandError(line_no, f'cannot read the value of {opcode} {text!r}')
    if not 1 <= value <= _MAX_VALUE:
        raise ExpandError(line_no, f'{opcode} {value} is outside 1..{_MAX_VALUE}')
    return value


def _parse_counter(text: str, line_no: int) -> int:
    counter = int(text)
    if counter >= _COUNTERS:
        raise ExpandError(line_no, f'c{counter} is not a user counter (c0..c{_COUNTERS - 1})')
    return counter


def _parse_ops(field: str, line_no: int) -> List[_Op]:
    masked = _mask_parens(field)
    ops = []
    for kind, pattern in _OP_PATTERNS:
        for m in pattern.finditer(masked):
            if kind == 'unsupported':
                ops.append(_Op(kind, m.span(), arg=m.group(1)))
            elif kind == 'set_msb':
                ops.append(_Op(kind, m.span(), value=_parse_value(m.group(1), 'set_msb', line_no)))
            elif kind == 'set':
                ops.append(_Op(kind, m.span(), counter=_parse_counter(m.group(1), line_no),
                               value=_parse_value(m.group(2), 'set', line_no)))
            elif kind == 'end_loop':
                ops.append(_Op(kind, m.span(), arg=m.group(1)))
            else:
                ops.append(_Op(kind, m.span(), counter=_parse_counter(m.group(1), line_no)))
    ops.sort(key=lambda op: op.span[0])
    return ops


def _strip_field(field: str, spans: List[Tuple[int, int]]) -> str:
    """Remove the given opcode spans, keep the other comma-separated opcodes.

    The result is padded to the original width so the '>' column stays put.
    """
    chars = list(field)
    for start, end in spans:
        chars[start:end] = ' ' * (end - start)
    blanked = ''.join(chars)
    items, start = [], 0
    for i, ch in enumerate(_mask_parens(blanked)):
        if ch == ',':
            items.append(blanked[start:i])
            start = i + 1
    items.append(blanked[start:])
    return ', '.join(s.strip() for s in items if s.strip()).ljust(len(field))


class _Module:
    def __init__(self, header, kind, body, close):
        self.header = header  # lines from the end of the previous module through '{'
        self.kind = kind      # 'srm_vector', 'vm_vector', 'vector' or None
        self.body = body      # [(line_no, text)]
        self.close = close    # closing '}' line, or None at end of file

    def records(self) -> Tuple[List[_Record], List[tuple]]:
        """Group the body into records; also return the lines after the last vector."""
        records, pending = [], []
        for line_no, text in self.body:
            if text.strip().startswith('//'):
                pending.append(('comment', text, None))
            elif '>' in _mask_parens(text):
                records.append(_Record(pending, line_no, text))
                pending = []
            else:
                label = is_label_line(text)
                pending.append(('label', text, label) if label else ('other', text, None))
        return records, pending

    def write_verbatim(self, out):
        out.writelines(self.header)
        out.writelines(text for _, text in self.body)
        if self.close is not None:
            out.write(self.close)


def _read(path: str):
    """Yield, in file order, ('text', line) outside modules and ('module', _Module)."""
    with openfile(path) as f:
        pending, body, header = [], None, None
        for line_no, line in enumerate(f, start=1):
            if body is None:
                pending.append(line)
                if line.strip().startswith('{'):
                    kind = None
                    for text in pending:
                        m = _MODULE.match(text)
                        if m:
                            kind = m.group(1)
                    header, body, pending = pending, [], []
            elif line.strip().startswith('}'):
                yield 'module', _Module(header, kind, body, line)
                body = None
            else:
                body.append((line_no, line))
        if body is not None:
            yield 'module', _Module(header, kind, body, None)
        for line in pending:
            yield 'text', line


def _opcode_mode(path: str) -> str:
    with openfile(path) as f:
        for line in f:
            m = _OPCODE_MODE.match(line)
            if m:
                return m.group(1).lower()
            if line.strip().startswith('{'):
                break
    return 'single'


def _require_single(path: str, timemode: str, mode: str) -> None:
    if timemode == '2':
        raise ExpandError(None, f'{mode} supports Single mode only; Dual was selected')
    opcode_mode = _opcode_mode(path)
    if opcode_mode != 'single':
        raise ExpandError(None, f'{mode} supports Single mode only; the file sets '
                                f'opcode_mode={opcode_mode}')


# ---------------------------------------------------------------------------
# Shared analysis
# ---------------------------------------------------------------------------

class _Counters:
    """MSB register and user counters, loaded the way set_msb / set load them."""

    def __init__(self):
        self.msb = None
        self.values: Dict[int, int] = {}

    def set_msb(self, value: int) -> None:
        self.msb = ((value - 1) >> 16) & 0xFFF

    def set(self, counter: int, value: int, line_no: int) -> None:
        if self.msb is None:
            raise ExpandError(line_no, f'set c{counter} {value} comes before any set_msb')
        self.values[counter] = (self.msb << 16) | ((value - 1) & 0xFFFF)

    def get(self, counter: int, user: str, line_no: int) -> int:
        if counter not in self.values:
            raise ExpandError(line_no, f'{user} c{counter} uses a counter that is never set '
                                       f'in this module')
        return self.values[counter]


def _reject_unsupported(records: List[_Record], mode: str) -> None:
    for rec in records:
        for op in rec.ops:
            if op.kind == 'unsupported':
                raise ExpandError(rec.line_no, f'{op.arg} is not supported by {mode}')


def _loop_structure(records: List[_Record]):
    """Pair each end_loop with its loop and label.

    Returns (label index, end_loop target labels, bodies) where each body is
    (first record, end_loop record, counter).
    """
    label_idx = {name: i for i, rec in enumerate(records) for name in rec.labels}
    targets, bodies, stack = set(), [], []
    for i, rec in enumerate(records):
        for op in rec.ops:
            if op.kind == 'loop':
                stack.append((op.counter, rec.line_no))
            elif op.kind == 'end_loop':
                target = op.arg
                if _RELATIVE_ADDRESS.fullmatch(target):
                    # TODO: support end_loop with a relative address
                    raise ExpandError(rec.line_no, f'end_loop with a relative address ({target}) '
                                                   f'is not supported yet; use a label')
                if target not in label_idx or label_idx[target] > i:
                    raise ExpandError(rec.line_no, f'end_loop {target}: no label {target} '
                                                   f'earlier in the module')
                if not stack:
                    raise ExpandError(rec.line_no, f'end_loop {target} has no matching loop')
                counter, _ = stack.pop()
                targets.add(target)
                bodies.append((label_idx[target], i, counter))
    if stack:
        counter, line_no = stack[-1]
        raise ExpandError(line_no, f'loop c{counter} has no end_loop')
    return label_idx, targets, bodies


def _prepare_strip(records: List[_Record], strip_kinds, remaining_counters) -> None:
    """Set each record's output vector line.

    Opcodes in `strip_kinds` are always removed. `set cX` is removed when cX
    is not in `remaining_counters` (no loop / repeat will still read it), and
    `set_msb` once every `set` in the module is removed.
    """
    sets = {op.counter for rec in records for op in rec.ops if op.kind == 'set'}
    strip_msb = not (sets & remaining_counters)
    for rec in records:
        spans = [op.span for op in rec.ops
                 if op.kind in strip_kinds
                 or (op.kind == 'set' and op.counter not in remaining_counters)
                 or (op.kind == 'set_msb' and strip_msb)]
        if spans:
            rec.out = _strip_field(rec.field, spans) + rec.rest


def _write_trailing(module: _Module, trailing, out) -> None:
    out.writelines(text for kind, text, _ in trailing if kind != 'comment')
    if module.close is not None:
        out.write(module.close)


def _log_error(logger: Logger, path: str, mode: str, e: ExpandError) -> None:
    where = f' line {e.line_no}' if e.line_no else ''
    logger.error(f'{mode} on {path}{where}: {e}')


# ---------------------------------------------------------------------------
# Expand Loop
# ---------------------------------------------------------------------------

def _expand_module_loops(module: _Module, records: List[_Record], trailing, out,
                         logger: Logger, path: str) -> None:
    _reject_unsupported(records, 'Expand Loop')
    label_idx, targets, _ = _loop_structure(records)
    repeat_counters = {op.counter for rec in records for op in rec.ops if op.kind == 'repeat'}
    _prepare_strip(records, ('loop', 'end_loop'), repeat_counters)

    header = list(module.header)
    for i in range(len(header) - 1, -1, -1):
        if _MODULE.match(header[i]):
            header[i] = header[i].replace('srm_vector', 'vm_vector', 1)
            break
    out.writelines(header)

    counters = _Counters()
    stack = []  # [counter, iterations left after this one, record that pushed it]
    written_labels, warned = set(), set()
    pc = 0
    while pc < len(records):
        rec = records[pc]
        next_pc = pc + 1
        active = {entry[0] for entry in stack}
        for op in rec.ops:
            if op.kind == 'set_msb':
                counters.set_msb(op.value)
            elif op.kind == 'set':
                if op.counter in active:
                    raise ExpandError(rec.line_no, f'set c{op.counter} inside a loop counting '
                                                   f'on c{op.counter}')
                counters.set(op.counter, op.value, rec.line_no)
            elif op.kind == 'loop':
                if stack and stack[-1][2] == pc:
                    continue  # a loop's own later iterations treat it as a NOP
                if op.counter in active:
                    raise ExpandError(rec.line_no, f'nested loops share counter c{op.counter}')
                stack.append([op.counter, counters.get(op.counter, 'loop', rec.line_no), pc])
                active.add(op.counter)
            elif op.kind == 'repeat':
                if op.counter in active:
                    raise ExpandError(rec.line_no, f'repeat c{op.counter} inside a loop counting '
                                                   f'on c{op.counter}')
            elif op.kind == 'end_loop':
                top = stack[-1]
                if top[1] == 0:
                    stack.pop()
                else:
                    top[1] -= 1
                    next_pc = label_idx[op.arg]

        for kind, text, name in rec.pre:
            if kind == 'comment':
                continue
            if kind == 'label':
                if name in targets:
                    continue
                if name in written_labels:
                    if name not in warned:
                        logger.warning(f'{path}: label {name} is inside an expanded loop body; '
                                       f'kept on the first copy only')
                        warned.add(name)
                    continue
                written_labels.add(name)
            out.write(text)
        out.write(rec.out)
        pc = next_pc

    _write_trailing(module, trailing, out)


def expand_loops(src: str, dst: str, timemode: str, logger: Logger) -> bool:
    """Write `src` to `dst` with every srm_vector loop flattened.

    An srm_vector module with loops becomes vm_vector; every other module is
    copied unchanged. Returns False, after logging why, when the file cannot
    be expanded.
    """
    mode = 'Expand Loop'
    try:
        _require_single(src, timemode, mode)
        expanded = 0
        with openfile(dst, mode='w') as out:
            for kind, item in _read(src):
                if kind == 'text':
                    out.write(item)
                    continue
                module = item
                if module.kind == 'srm_vector':
                    records, trailing = module.records()
                    if any(op.kind in ('loop', 'end_loop') for rec in records for op in rec.ops):
                        _expand_module_loops(module, records, trailing, out, logger, src)
                        expanded += 1
                        continue
                module.write_verbatim(out)
        if not expanded:
            logger.info(f'No srm_vector loops in {src}; copied unchanged')
        return True
    except ExpandError as e:
        _log_error(logger, src, mode, e)
        return False


# ---------------------------------------------------------------------------
# Expand Repeat (counter repeats)
# ---------------------------------------------------------------------------

def has_counter_repeat(path: str) -> bool:
    """True when some vector in the file uses `repeat cX`."""
    with openfile(path) as f:
        for line in f:
            if line.strip().startswith('//'):
                continue
            field = line.split('>', 1)[0] if '>' in line else ''
            if _COUNTER_REPEAT_LINE.search(_mask_parens(field)):
                return True
    return False


def _expand_module_repeats(module: _Module, records: List[_Record], trailing, out) -> None:
    _reject_unsupported(records, 'Expand Repeat')
    _, _, bodies = _loop_structure(records)
    loop_counters = {op.counter for rec in records for op in rec.ops if op.kind == 'loop'}
    _prepare_strip(records, ('repeat',), loop_counters)

    out.writelines(module.header)
    counters = _Counters()
    for i, rec in enumerate(records):
        enclosing = [body for body in bodies if body[0] <= i <= body[1]]
        copies = 1
        for op in rec.ops:
            if op.kind == 'set_msb':
                counters.set_msb(op.value)
            elif op.kind == 'set':
                if any(body[2] == op.counter for body in enclosing):
                    raise ExpandError(rec.line_no, f'set c{op.counter} inside a loop counting '
                                                   f'on c{op.counter}')
                counters.set(op.counter, op.value, rec.line_no)
            elif op.kind == 'repeat':
                c = op.counter
                if any(body[2] == c for body in enclosing):
                    raise ExpandError(rec.line_no, f'repeat c{c} inside a loop counting on c{c}')
                if enclosing:
                    last = max(body[1] for body in enclosing)
                    if any(later.kind == 'set' and later.counter == c
                           for r in records[i + 1:last + 1] for later in r.ops):
                        raise ExpandError(rec.line_no, f'repeat c{c} sits in a loop body that sets '
                                                       f'c{c} again later; run Expand Loop first')
                copies = counters.get(c, 'repeat', rec.line_no) + 1

        out.writelines(text for kind, text, _ in rec.pre if kind != 'comment')
        out.write(rec.out)
        if copies > 1:
            again = [text for kind, text, _ in rec.pre if kind == 'other'] + [rec.out]
            for _ in range(copies - 1):
                out.writelines(again)

    _write_trailing(module, trailing, out)


def expand_counter_repeats(src: str, dst: str, timemode: str, logger: Logger) -> bool:
    """Write `src` to `dst` with every `repeat cX` flattened.

    Labels above a repeated vector are written on the first copy only. Modules
    without `repeat cX` are copied unchanged. Returns False, after logging why,
    when the file cannot be expanded.
    """
    mode = 'Expand Repeat'
    try:
        _require_single(src, timemode, mode)
        with openfile(dst, mode='w') as out:
            for kind, item in _read(src):
                if kind == 'text':
                    out.write(item)
                    continue
                module = item
                records, trailing = module.records()
                if any(op.kind == 'repeat' for rec in records for op in rec.ops):
                    _expand_module_repeats(module, records, trailing, out)
                else:
                    module.write_verbatim(out)
        return True
    except ExpandError as e:
        _log_error(logger, src, mode, e)
        return False
