"""
harness/port_runner.py - evaluate a port in a SEPARATE process.

The port never shares memory with the harness or the referee, so it cannot read
reference values or patch the exam at run time. Protocol: inputs as repr() floats,
one per line, on stdin; outputs one per line on stdout (repr float, or "nan" when
the call raised). Exit code 3 = the port could not be loaded (DISQUALIFIED).

Usage (by harness/trial.py): python -m harness.port_runner <path-to-port.py> <name>
"""

import sys


def main() -> int:
    path, name = sys.argv[1], sys.argv[2]
    from harness.port_guard import load_port

    try:
        fn = load_port(path, name)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    out = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        x = float(line)
        try:
            y = float(fn(x))
        except Exception:
            y = float("nan")
        out.append(repr(y))
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
