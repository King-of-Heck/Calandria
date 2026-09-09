"""Command line entry: python -m calandria dump <file.docx>"""
import json
import sys

from .docx.parser import parse_docx
from .harness.flatten import flatten

USAGE = "usage: python -m calandria dump <file.docx>"


def main(argv) -> int:
    if len(argv) == 2 and argv[0] == "dump":
        print(json.dumps(flatten(parse_docx(argv[1])), ensure_ascii=True, indent=1))
        return 0
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
