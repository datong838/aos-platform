"""No-effect source inventory: local launchers and templates are not fleet authority."""

from pathlib import Path

from a0v_w5c6j_host_topology_discovery import classify


ROOT = Path(__file__).resolve().parents[4]


def test_launchd_plist_only_names_one_local_runtime_launcher():
    plist = (ROOT / 'deploy/dev/com.aos.a0v-w5c3-runtime-host.plist').read_text()
    assert 'scripts/a0v_ecommerce_runtime_host.py' in plist
    assert '<key>KeepAlive</key><false/>' in plist
    assert 'fleet' not in plist.lower()
    assert 'cluster' not in plist.lower()


def test_spoke_deployment_template_is_not_aos_runtime_host_universe():
    deployment = (ROOT / 'deploy/spoke-full/chart/templates/deployment.yaml').read_text()
    values = (ROOT / 'deploy/spoke-full/chart/values.yaml').read_text()
    assert 'replicas: {{ .Values.replicaCount }}' in deployment
    assert 'replicaCount: 1' in values
    assert 'a0v_ecommerce_runtime_host.py' not in deployment
    assert 'a0v_ecommerce_runtime_host.py' not in values


def test_local_and_managed_zero_counts_remain_non_authoritative():
    result = classify({
        'knownLauncherPids': [],
        'managedDirectory': {'outcome': 'MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY'},
        'databaseSessions': {'knownLoginSessions': 0, 'remoteClientSessions': 0,
                             'unknownClientSessions': 0},
    })
    assert result['topologyComplete'] is False
    assert result['closureAuthorized'] is False
    assert result['reason'] == 'UNMANAGED_OR_OTHER_MACHINE_HOSTS_NOT_EXCLUDED'
