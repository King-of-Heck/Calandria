"""Command line entry:
    python -m calandria dump <file.docx>
    python -m calandria compare <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]
    python -m calandria layout <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]
                               [--hide-unchanged] [--hide-insertions] [--hide-deletions]
                               [--hide-formatting] [--pages]
"""
import json
import sys

from .diff.compare import compare
from .docx.parser import parse_docx
from .harness.flatten import flatten
from .layout.engine import layout
from .layout.pieces import LayoutOptions

USAGE = ("usage: python -m calandria dump <file.docx>\n"
         "       python -m calandria compare <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]\n"
         "       python -m calandria layout <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]\n"
         "                                  [--hide-unchanged] [--hide-insertions] [--hide-deletions]\n"
         "                                  [--hide-formatting] [--pages]")
_COMPARE_FLAGS = {"--ignore-case", "--no-count-numbering"}
_LAYOUT_FLAGS = _COMPARE_FLAGS | {"--hide-unchanged", "--hide-insertions", "--hide-deletions",
                                  "--hide-formatting", "--pages"}


def _parse_pair(rest, allowed):
    flags = {a for a in rest if a.startswith("--")}
    positionals = [a for a in rest if not a.startswith("--")]
    if flags - allowed or len(positionals) != 2:
        return None
    return flags, positionals


def main(argv) -> int:
    if len(argv) == 2 and argv[0] == "dump":
        print(json.dumps(flatten(parse_docx(argv[1])), ensure_ascii=True, indent=1))
        return 0
    if argv and argv[0] in ("compare", "layout"):
        parsed = _parse_pair(argv[1:], _COMPARE_FLAGS if argv[0] == "compare" else _LAYOUT_FLAGS)
        if parsed is None:
            print(USAGE)
            return 2
        flags, (pa, pb) = parsed
        cmp = compare(parse_docx(pa), parse_docx(pb), ignore_case="--ignore-case" in flags,
                      count_numbering="--no-count-numbering" not in flags)
        if argv[0] == "compare":
            print(json.dumps(cmp.to_dict(), ensure_ascii=True, indent=1))
            return 0
        opts = LayoutOptions(show_equal="--hide-unchanged" not in flags,
                             show_insertions="--hide-insertions" not in flags,
                             show_deletions="--hide-deletions" not in flags,
                             show_formatting="--hide-formatting" not in flags)
        result = layout(cmp, opts)
        out = {"pages": result.page_count} if "--pages" in flags else result.to_dict()
        print(json.dumps(out, ensure_ascii=True, indent=1))
        return 0
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
