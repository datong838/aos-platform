"""Fixed growth 1.9 signed-root profile for the existing controlled Product API."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = ROOT.parent / '.aos-recovery-20260916/state/growth-1.9-current-package/registry/signed-bundles-growth-1.9-current'


def load_launcher():
    from a0v_product_controlled_api import load_launcher as original
    launcher = original()
    launcher.BUNDLE_ROOT = BUNDLE_ROOT
    return launcher


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    load_launcher().main()
