#!/usr/bin/env python
import sys
sys.path.insert(0, '/home/gabriel/Documents/Projects/beancount')

from importers.b3 import B3Importer
from beancount.core import data

def main():
    imp = B3Importer()
    
    # Test 1: Movimentacao
    print("--- Test 1: Movimentacao Sample ---")
    try:
        entries = imp.extract('export_samples/movimentacao-sample.xlsx', [])
        print(f"Success: Extracted {len(entries)} entries")
        for e in entries[:3]:
            print(e)
    except Exception as ex:
        print(f"Error in Movimentacao: {ex}")
        import traceback
        traceback.print_exc()

    # Test 2: Negociacao
    print("\n--- Test 2: Negociacao Sample ---")
    try:
        entries = imp.extract('export_samples/negociacao-sample.xlsx', [])
        print(f"Success: Extracted {len(entries)} entries")
        for e in entries:
            print(e)
    except Exception as ex:
        print(f"Error in Negociacao: {ex}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()