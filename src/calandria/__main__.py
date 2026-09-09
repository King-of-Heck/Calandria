"""Command line entry:
    python -m calandria dump <file.docx>
    python -m calandria compare <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]
    python -m calandria layout <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]
                               [--hide-unchanged] [--hide-insertions] [--hide-deletions]
                               [--hide-formatting] [--pages]
    python -m calandria pdf <a.docx> <b.docx> <out.pdf> [--ignore-case] [--no-count-numbering]
                            [--hide-unchanged] [--hide-insertions] [--hide-deletions]
                            [--hide-formatting] [--no-change-bars] [--render-set=NAME]
                            [--report=first|last|none]
    python -m calandria serve [--port=N] [--idle=SECONDS] [--no-browser] [--verbose]
"""
import json
import os
import sys
from datetime import datetime

from .diff.compare import compare
from .docx.parser import parse_docx
from .harness.flatten import flatten
from .layout.engine import layout
from .layout.pieces import LayoutOptions
from .pdf.draw import PdfOptions
from .pdf.rendersets import RENDER_SETS
from .pdf.report import report_info
from .pdf.writer import REPORTS, render
from .server.app import DEFAULT_IDLE, serve

USAGE = ("usage: python -m calandria dump <file.docx>\n"
         "       python -m calandria compare <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]\n"
         "       python -m calandria layout <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]\n"
         "                                  [--hide-unchanged] [--hide-insertions] [--hide-deletions]\n"
         "                                  [--hide-formatting] [--pages]\n"
         "       python -m calandria pdf <a.docx> <b.docx> <out.pdf> [--ignore-case] [--no-count-numbering]\n"
         "                               [--hide-unchanged] [--hide-insertions] [--hide-deletions]\n"
         "                               [--hide-formatting] [--no-change-bars] [--render-set=NAME]\n"
         "                               [--report=first|last|none]\n"
         "       python -m calandria serve [--port=N] [--idle=SECONDS] [--no-browser] [--verbose]")
_COMPARE_FLAGS = {"--ignore-case", "--no-count-numbering"}
_HIDE_FLAGS = {"--hide-unchanged", "--hide-insertions", "--hide-deletions", "--hide-formatting"}
_LAYOUT_FLAGS = _COMPARE_FLAGS | _HIDE_FLAGS | {"--pages"}
_PDF_FLAGS = _COMPARE_FLAGS | _HIDE_FLAGS | {"--no-change-bars"}
_PDF_VALUED = {"--render-set", "--report"}
_SERVE_FLAGS = {"--no-browser", "--verbose"}
_SERVE_VALUED = {"--port", "--idle"}


def _parse(rest, allowed, valued=frozenset(), n=2):
    """Flags (`--x`), valued flags (`--x=y`) and exactly n positionals, in any order."""
    flags, values, positionals = set(), {}, []
    for a in rest:
        if a.startswith("--"):
            k, eq, v = a.partition("=")
            if eq and k in valued:
                values[k] = v
            elif not eq and a in allowed:
                flags.add(a)
            else:
                return None
        else:
            positionals.append(a)
    if len(positionals) != n:
        return None
    return flags, values, positionals


def _layout_options(flags) -> LayoutOptions:
    return LayoutOptions(show_equal="--hide-unchanged" not in flags,
                         show_insertions="--hide-insertions" not in flags,
                         show_deletions="--hide-deletions" not in flags,
                         show_formatting="--hide-formatting" not in flags)


def _compare(flags, pa, pb):
    return compare(parse_docx(pa), parse_docx(pb), ignore_case="--ignore-case" in flags,
                   count_numbering="--no-count-numbering" not in flags)


def main(argv) -> int:
    if len(argv) == 2 and argv[0] == "dump":
        print(json.dumps(flatten(parse_docx(argv[1])), ensure_ascii=True, indent=1))
        return 0
    if argv and argv[0] in ("compare", "layout"):
        parsed = _parse(argv[1:], _COMPARE_FLAGS if argv[0] == "compare" else _LAYOUT_FLAGS)
        if parsed is None:
            print(USAGE)
            return 2
        flags, _, (pa, pb) = parsed
        cmp = _compare(flags, pa, pb)
        if argv[0] == "compare":
            print(json.dumps(cmp.to_dict(), ensure_ascii=True, indent=1))
            return 0
        result = layout(cmp, _layout_options(flags))
        out = {"pages": result.page_count} if "--pages" in flags else result.to_dict()
        print(json.dumps(out, ensure_ascii=True, indent=1))
        return 0
    if argv and argv[0] == "pdf":
        parsed = _parse(argv[1:], _PDF_FLAGS, _PDF_VALUED, n=3)
        if parsed is None or parsed[1].get("--report", "last") not in REPORTS:
            print(USAGE)
            return 2
        flags, values, (pa, pb, out_path) = parsed
        rs_name = values.get("--render-set", "Standard")
        if rs_name not in RENDER_SETS:
            print(f"unknown rendering set: {rs_name} (available: {', '.join(RENDER_SETS)})")
            return 2
        cmp = _compare(flags, pa, pb)
        result = layout(cmp, _layout_options(flags))
        now = datetime.now()          # one clock: the report's time stamp and the PDF creation date
        opts = PdfOptions(render_set=rs_name, change_bars="--no-change-bars" not in flags,
                          report=values.get("--report", "last"), now=now)
        info = report_info(cmp, os.path.basename(pa), os.path.basename(pb), rs_name, now)
        data, drawn = render(result, info, opts)
        with open(out_path, "wb") as f:
            f.write(data)
        print(json.dumps({"pages": drawn.pages, "out": out_path}, ensure_ascii=True))
        return 0
    if argv and argv[0] == "serve":
        parsed = _parse(argv[1:], _SERVE_FLAGS, _SERVE_VALUED, n=0)
        if parsed is None:
            print(USAGE)
            return 2
        flags, values, _ = parsed
        try:
            port = int(values.get("--port", "0"))
            idle = float(values.get("--idle", str(DEFAULT_IDLE)))
        except ValueError:
            print(USAGE)
            return 2
        if not 0 <= port <= 65535 or idle < 0:
            print(USAGE)
            return 2
        serve(port=port, open_browser="--no-browser" not in flags, idle=idle, verbose="--verbose" in flags,
              ready=lambda url: print(json.dumps({"url": url}), flush=True))
        return 0
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
