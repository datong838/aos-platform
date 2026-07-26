#!/usr/bin/env bash
# 灌入测试组织数据（dev-org / dev-project / 默认人员 / 工单 / 订单 / 模块等）
# 用法：scripts/demo/seed-test-org.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "$SCRIPT_DIR/../../services/aos-api" && pwd)"

cd "$SERVICE_DIR"
.venv/bin/python -c "
from aos_api.demo import seed_test_org
result = seed_test_org()
print('seed_test_org_done:')
for k, v in result.items():
    print(f'  {k}: {v}')
"
