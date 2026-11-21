"""Command-line interface for PatAutoEdit.

    patautoedit run CONFIG.csv [--atp-dir DIR | --atp FILE ...] [--pinmap FILE]
    patautoedit check CONFIG.csv [--atp-dir DIR | --atp FILE ...] [--pinmap FILE]
    patautoedit modes

`run` applies the config and writes edited ATPs to --output-dir (default
Output/ under the current directory). `check` validates and prints the plan
without writing. `modes` lists the Process Types and the fields each needs.
"""
import argparse
import json
import os
import sys
from typing import Dict, List

from patautoedit import version
from patautoedit.atp_handler import (ConfigError, MODE_LIST, analyse_merge_config,
                                     missing_requirements)
from patautoedit.logger import Logger
from patautoedit.main import check_config, run_config


class _CliLogger(Logger):
    """Logger that keeps warnings for the JSON result."""

    def __init__(self, stream):
        super().__init__(stream=stream)
        self.warnings: List[str] = []

    def warning(self, msg):
        self.warnings.append(msg)
        super().warning(msg)


def _logger(use_json: bool) -> _CliLogger:
    return _CliLogger(sys.stderr if use_json else sys.stdout)


def _candidate_atps(parser: argparse.ArgumentParser, args) -> List[str]:
    if args.atp:
        paths = []
        for path in args.atp:
            if not os.path.isfile(path):
                parser.error(f"ATP file not found: {path}")
            paths.append(os.path.abspath(path))
        return paths

    atp_dir = args.atp_dir or os.path.dirname(os.path.abspath(args.config))
    if not os.path.isdir(atp_dir):
        parser.error(f"ATP directory not found: {atp_dir}")
    names = sorted(
        entry.name for entry in os.scandir(atp_dir)
        if entry.is_file() and entry.name.lower().endswith((".atp", ".atp.gz"))
    )
    return [os.path.abspath(os.path.join(atp_dir, name)) for name in names]


def _check_paths(parser: argparse.ArgumentParser, args) -> None:
    if not os.path.isfile(args.config):
        parser.error(f"config file not found: {args.config}")
    if args.pinmap and not os.path.isfile(args.pinmap):
        parser.error(f"pinmap file not found: {args.pinmap}")


def _parse_config(parser: argparse.ArgumentParser, args, logger: Logger):
    try:
        return analyse_merge_config(args.config, logger)
    except ConfigError as e:
        return e
    except OSError as e:
        return e


def _failed_run(args, problems: List[str], warnings: List[str]) -> Dict:
    return {
        "version": version,
        "ok": False,
        "config": os.path.abspath(args.config),
        "output_dir": os.path.abspath(args.output_dir),
        "outputs": [],
        "failed": [],
        "skipped": [],
        "warnings": warnings,
        "problems": problems,
        "counts": {"matched": 0, "succeeded": 0, "failed": 0},
    }


def _emit_run(result: Dict, use_json: bool) -> None:
    if use_json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    counts = result["counts"]
    if result["problems"]:
        print("Configuration rejected; nothing was processed.")
    elif counts["matched"] == 0:
        print("No ATP files matched the config; nothing was processed.")
    elif counts["failed"]:
        print(f"{counts['failed']} of {counts['matched']} file(s) failed.")
    else:
        print(f"{counts['succeeded']} file(s) processed. Output: {result['output_dir']}")


def _run(args, parser: argparse.ArgumentParser) -> int:
    _check_paths(parser, args)
    atp_files = _candidate_atps(parser, args)
    logger = _logger(args.json)

    config_list = _parse_config(parser, args, logger)
    if isinstance(config_list, Exception):
        result = _failed_run(args, [str(config_list)], logger.warnings)
        _emit_run(result, args.json)
        return 1

    run = run_config(atp_files, config_list, logger, pin_map=args.pinmap or "",
                     output_dir=args.output_dir)
    result = {
        "version": version,
        "ok": run["ok"],
        "config": os.path.abspath(args.config),
        "output_dir": run["output_dir"],
        "outputs": run["outputs"],
        "failed": run["failed"],
        "skipped": run["skipped"],
        "warnings": logger.warnings,
        "problems": run["problems"],
        "counts": {
            "matched": len(run["outputs"]) + len(run["failed"]),
            "succeeded": len(run["outputs"]),
            "failed": len(run["failed"]),
        },
    }
    _emit_run(result, args.json)
    return 0 if result["ok"] else 1


def _failed_check(args, problems: List[str], warnings: List[str]) -> Dict:
    return {
        "version": version,
        "ok": False,
        "config": os.path.abspath(args.config),
        "plan": [],
        "skipped": [],
        "warnings": warnings,
        "problems": problems,
        "counts": {"matched": 0},
    }


def _emit_check(result: Dict, use_json: bool) -> None:
    if use_json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    for item in result["plan"]:
        print(f"{os.path.basename(item['source'])}: {' -> '.join(item['operations'])}")
    if result["skipped"]:
        print("Skipped: " + ", ".join(result["skipped"]))
    if result["problems"]:
        print("Configuration rejected; nothing would be processed.")
    elif result["plan"]:
        print(f"{len(result['plan'])} file(s) would be processed.")
    else:
        print("No ATP files matched the config; nothing would be processed.")


def _check(args, parser: argparse.ArgumentParser) -> int:
    _check_paths(parser, args)
    atp_files = _candidate_atps(parser, args)
    logger = _logger(args.json)

    config_list = _parse_config(parser, args, logger)
    if isinstance(config_list, Exception):
        result = _failed_check(args, [str(config_list)], logger.warnings)
        _emit_check(result, args.json)
        return 1

    checked = check_config(atp_files, config_list, logger, pin_map=args.pinmap or "")
    result = {
        "version": version,
        "ok": checked["ok"],
        "config": os.path.abspath(args.config),
        "plan": checked["plan"],
        "skipped": checked["skipped"],
        "warnings": logger.warnings,
        "problems": checked["problems"],
        "counts": {"matched": len(checked["plan"])},
    }
    _emit_check(result, args.json)
    return 0 if result["ok"] else 1


def _modes(args, parser: argparse.ArgumentParser) -> int:
    rows = [{"process_type": mode, "requires": missing_requirements({"Mode": mode})}
            for mode in MODE_LIST]
    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    for row in rows:
        print(f"{row['process_type']}: {', '.join(row['requires']) or '-'}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patautoedit",
        description="Edit ATP pattern files for DSSC/CMEM/HRAM.",
    )
    parser.add_argument("--version", action="version", version=version)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("config", help="row-per-op config CSV")
        p.add_argument("--atp-dir",
                       help="folder holding *.atp / *.atp.gz; default: the config's folder")
        p.add_argument("--atp", action="append", metavar="FILE",
                       help="candidate ATP file; repeatable; overrides --atp-dir")
        p.add_argument("--pinmap", help="optional pinmap file")
        p.add_argument("--json", action="store_true",
                       help="print one JSON object on stdout; logs go to stderr")

    run = sub.add_parser("run", help="apply a config CSV")
    add_common(run)
    run.add_argument("--output-dir", default="Output",
                     help="folder for edited files (default: ./Output)")
    run.set_defaults(func=_run)

    check = sub.add_parser("check", help="validate a config CSV without writing files")
    add_common(check)
    check.set_defaults(func=_check)

    modes = sub.add_parser("modes", help="list Process Types and required fields")
    modes.add_argument("--json", action="store_true",
                       help="print the list as JSON")
    modes.set_defaults(func=_modes)
    return parser


def main(argv=None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    return args.func(args, parser)


if __name__ == "__main__":
    sys.exit(main())
