#!/usr/bin/env bash
# 清空测试组织数据（dev-org / dev-project 下所有数据）
# 用法：scripts/demo/clear-test-org.sh
# 注意：此脚本会删除数据，仅在回归清理或重置测试环境时调用。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "$SCRIPT_DIR/../../services/aos-api" && pwd)"

cd "$SERVICE_DIR"
.venv/bin/python -c "
from aos_api.demo import clear_test_org
result = clear_test_org()
print('clear_test_org_done:')
for k, v in result.items():
    print(f'  {k}: {v}')
"
