# EditPat
Tool to edit ATP pattern file for DSSC/CMEM/HRAM.

How to use：
1. Prepare the config CSV file — see [Config file format](#config-file-format) below;

	![Setup File](/img/config_csv.png "Setup File")
2. Choose the ATP file, config file, Pin Name(single pin support only), edit method and time mode;	
	![PAT_UI](/img/PAT_UI.png "PAT_UI")
3. Feature support:
	* DigCap/DigSrc;
	* HRAM/CMEM;
	* Expand Repeat(remove "repeat N" and "repeat cX"); "Expand Pattern" is the old name of the same mode and will be dropped in a future version;
	* Expand Loop(flatten "loop"/"end_loop" in srm_vector modules, which then become vm_vector);
	* Compress Pattern(add "repeat");

## Config file format

**One row is one operation.** Rows that share the same `Pattern` form a chain and
are applied top to bottom — each step reads the output of the step above it, so a
file can be edited as many times as you need.

```csv
Instance,Pattern,Status,Process Type,Pin or Method,Cycle,User String
,Sample_ATP.atp,Done,DSSC Capture,TDO,[7-7];[12-12],
,Sample_ATP.atp,Done,DSSC Capture,PORN,[13-14],
,Sample_ATP.atp,Done,DSSC Source,TDI,[9-9],
,Sample_ATP.atp,Done,WFLAG,,[8-8],
,Sample_ATP - 1.atp,Done,DSSC Source,TDI,[7-7];[9-9],
,Sample_ATP - 1.atp,Done,DSSC Capture,TDO,[7-7];[12-12],
```

`Sample_ATP.atp` above gets four chained operations; `Sample_ATP - 1.atp` gets two.

| Column | Notes |
| --- | --- |
| `Pattern` | ATP filename. Required. |
| `Process Type` | One of: DSSC Capture, DSSC Source, CMEM/HRAM Capture, Expand Pattern, Expand Repeat, Expand Loop, Compress Pattern, WFLAG, Add Opcode, Remove Opcode. Required. |
| `Pin or Method` | Blank for modes that take no pin (`WFLAG`, `Expand Repeat`, `Expand Loop`, `Compress Pattern`). |
| `Cycle` | `[a-b];[c-d]` form. Blank for `Expand Repeat`, `Expand Loop`, `Compress Pattern`, `Remove Opcode`. |
| `User String` | Only used by `Add Opcode` / `Remove Opcode`. |
| `Instance`, `Status` | Ignored. Kept for your own bookkeeping. |

Column names are matched case-insensitively and column order does not matter.
Your whole config is checked before anything runs, so a mistake is reported up
front rather than half-way through a batch.

Note: the older 9-column format, where one row held two operations, is no longer
supported. Such a file is rejected with a message showing the rows to use
instead. The screenshot above still shows the old layout and needs re-taking.

`Expand Repeat` and `Compress Pattern` always use single time mode; use the
Classical tab for dual-mode files. `Expand Loop` supports single mode only.
