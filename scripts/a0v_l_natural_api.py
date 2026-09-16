"""Keep the independent snapshot worker and add only the QYH natural Cron."""
from datetime import datetime, timezone
import json
import subprocess

import a0v_snapshot_product_api as snapshot_api

ORIGINAL_LAUNCHER = snapshot_api.load_launcher
TASK = 'SC4-5L6Y5F4-REFRESH-DEPLOY-20260916'


def load_launcher():
    launcher = ORIGINAL_LAUNCHER()
    launcher.API_FLAGS = dict(launcher.API_FLAGS, AOS_QYH_CRON_ENABLED='true')
    return launcher


def main():
    leases = json.loads((snapshot_api.ROOT.parent /
        'docs/palantier/AOS项目开发上下文/memory/leases.json').read_text())['leases']
    current = [row for row in leases if row['task_id'] == TASK]
    if (len(current) != 1 or current[0]['owner'] != 'm1' or current[0]['status'] != 'ACTIVE'
        or datetime.fromisoformat(current[0]['lease_expires_at']) <= datetime.now(timezone.utc)
        or subprocess.check_output(['git','branch','--show-current'],
                                   cwd=snapshot_api.ROOT, text=True).strip() != 'm1'):
        raise ValueError('current m1 natural-event lease required')
    with snapshot_api.api_lock(snapshot_api.STATE / 'api.lock'):
        load_launcher().main()


if __name__ == '__main__':
    main()
