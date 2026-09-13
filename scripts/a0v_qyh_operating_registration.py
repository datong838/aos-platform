"""Fixed next registration after the retained pristine-withdrawal acceptance."""
import importlib.util
from pathlib import Path


def load_profile():
    path=Path(__file__).with_name('a0v_qyh_registration_cycle.py')
    spec=importlib.util.spec_from_file_location('qyh_operating_registration_profile',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PREDECESSOR_WITHDRAWAL_KEY=module.KEY+'-withdraw'
    module.KEY='a0v-qyh-reboot-operating-registration-v1'
    module.STATE=module.ROOT.parent/'.aos-recovery-20260913/state/qyh-operating-registration-v1'
    module.TASK_ID='A0V-QYH-OPERATING-REGISTRATION-20260913'
    return module


if __name__=='__main__':load_profile().main()
