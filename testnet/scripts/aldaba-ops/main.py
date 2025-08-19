#!/usr/bin/env python3
# coding=utf-8
from aldaba_ops.test_runner import run

import sys


def main(args=None):
    # exec('aldaba-ops --version')
    run.test('flow.json')
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
