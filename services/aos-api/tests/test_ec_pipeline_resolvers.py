"""G3: evidence resolver 注册测试。

dataset_resolver 查 engine._datasets 内存 store，验证 output_ref 指向的 dataset 真实存在。
scope 隔离靠写入侧（create_dataset 带 scope），resolver 只做 rid 全局存在性检查。
"""

from __future__ import annotations

import pytest

from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")


@pytest.fixture(autouse=True)
def reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield


def test_dataset_resolver_returns_true_for_existing_dataset():
    eng = get_engine()
    ds = eng.create_dataset(TEST_SCOPE, name="test-ds")

    from aos_api.ec_pipeline_resolvers import dataset_resolver

    ref = f"dataset://catalog/{ds.id}"
    assert dataset_resolver(ref) is True


def test_dataset_resolver_returns_false_for_missing_dataset():
    from aos_api.ec_pipeline_resolvers import dataset_resolver

    assert dataset_resolver("dataset://catalog/ds-nonexistent-999") is False


def test_dataset_resolver_returns_false_for_malformed_ref():
    from aos_api.ec_pipeline_resolvers import dataset_resolver

    assert dataset_resolver("not-a-uri") is False
    assert dataset_resolver("dataset://no-host") is False
    assert dataset_resolver("http://catalog/x") is False
    assert dataset_resolver("") is False


def test_dataset_resolver_is_callable_with_str_returns_bool():
    from aos_api.ec_pipeline_resolvers import dataset_resolver

    result = dataset_resolver("dataset://catalog/any")
    assert isinstance(result, bool)
