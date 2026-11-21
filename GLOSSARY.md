# EditPat

EditPat edits ATP pattern files for Teradyne IG-XL testers. Each edit is one row of a config CSV, and rows for the same ATP are applied in order.

## Language

**Operation**:
One row of a config CSV: one edit applied to one ATP. Rows sharing a `Pattern` form a chain and run top to bottom.
_Avoid_: step, task

**Process Type**:
The field on an operation that selects what the edit does, for example `DSSC Capture` or `Expand Loop`, written in the config column `Process Type`.
_Avoid_: mode (that is the internal code name)

**Candidate ATP**:
An ATP file offered to a run, either found in the `--atp-dir` folder or named with `--atp`. A config `Pattern` that matches no candidate ATP is skipped.
_Avoid_: target file, input file

**Expand**:
Writing each pass of a loop, or each run of a repeated vector, out as its own vectors. MTO commands stay on every copy.
_Avoid_: flatten, unroll

**Run count**:
The number of times a loop or counter repeat runs: the N in `set cX N`. The counter register holds N − 1, and `Patgen.Counter` in a VBT writes that register value directly.
_Avoid_: counter value (it can mean either number)

**Preloaded counter**:
A pattern counter (`c0`–`c15`) whose value the test program loads before the pattern starts, rather than the ATP setting it with `set cX`.
_Avoid_: preset (MTO uses it for X/Y/Z address presets), VBT counter

**Variant**:
An expanded ATP built from one set of counter values. One source ATP can have several, one for each set of counter values it runs with.
_Avoid_: version
