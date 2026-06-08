#!/usr/bin/env python
import sys
sys.path.insert(0, '/home/gabriel/Documents/Projects/beancount')
from importers.b3 import B3Importer

def main():
    imp = B3Importer()
    files = [
        'export_samples/negociacao-sample.xlsx',
        'export_samples/movimentacao-sample.xlsx'
    ]
    for f in files:
        print(f"--- {f} ---", file=sys.stderr)
        try:
            entries = imp.extract(f, [])
            print(f"Extracted {len(entries)} entries", file=sys.stderr)
            for e in entries:
                print(e)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

if __name__ == '__main__':
    main()
