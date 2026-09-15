"""Controlled API profile for the verified core1.4/growth1.10 signed set."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
BUNDLE_ROOT=ROOT.parent/'.aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete'


def load_launcher():
    from a0v_product_controlled_api import load_launcher as original
    launcher=original();launcher.BUNDLE_ROOT=BUNDLE_ROOT
    return launcher


if __name__=='__main__':
    sys.dont_write_bytecode=True
    load_launcher().main()
