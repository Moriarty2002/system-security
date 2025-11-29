#!/usr/bin/env python3
"""Deprecated helper removed — shell-based installer is used instead.

This file remains as a no-op placeholder to avoid import-time errors
in environments that still reference it. The shell installer at
`/usr/local/bin/install_ca.sh` is now the canonical startup CA installer.
"""
import sys

def main():
    print('install_ca.py is deprecated; using shell installer instead')
    return 0

if __name__ == '__main__':
    sys.exit(main())
