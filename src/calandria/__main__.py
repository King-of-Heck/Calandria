"""Command line entry:
    python -m calandria dump <file.docx>
    python -m calandria compare <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]
"""
import json
import sys

from .diff.compare import compare
from .docx.parser import parse_docx
from .harness.flatten import flatten

USAGE = ("usage: python -m calandria dump <file.docx>\n"
         "       python -m calandria compare <a.docx> <b.docx> [--ignore-case] [--no-count-numbering]")
_FLAGS = {"--ignore-case", "--no-count-numbering"}


def main(argv) -> int:
    if len(argv) == 2 and argv[0] == "dump":
        print(json.dumps(flatten(parse_docx(argv[1])), ensure_ascii=True, indent=1))
        return 0
    if len(argv) >= 3 and argv[0] == "compare":
        flags = set(argv[3:])
        if flags - _FLAGS:
            print(USAGE)
            return 2
        cmp = compare(parse_docx(argv[1]), parse_docx(argv[2]),
                      ignore_case="--ignore-case" in flags,
                      count_numbering="--no-count-numbering" not in flags)
        print(json.dumps(cmp.to_dict(), ensure_ascii=True, indent=1))
        return 0
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
