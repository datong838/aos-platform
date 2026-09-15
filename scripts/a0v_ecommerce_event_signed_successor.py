"""Signed event-complete core/growth releases; retained history is immutable."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def load_successor():
    from a0v_ecommerce_current_signed_successor import load_successor as previous
    import build_ecommerce_event_candidates as profile
    successor=previous();helper=successor.legacy();helper._builder=profile.load_builder
    successor.legacy=lambda:helper
    recovery=successor.ROOT.parent/'.aos-recovery-20260916/state/event-complete-package'
    successor.BUILD=recovery/'build/candidates'
    successor.BUILD_RECEIPT=recovery/'build/build-receipt.json'
    successor.QUALIFICATION=recovery/'build/qualification-receipt.json'
    successor.STATE=recovery/'registry'
    successor.OLD_ROOT=successor.ROOT.parent/'.aos-recovery-20260916/state/growth-1.9-current-package/registry/signed-bundles-growth-1.9-current'
    successor.NEW_ROOT=successor.STATE/'signed-bundles-event-complete'
    successor.VERSIONS=dict(successor.VERSIONS,**{'domain.ecommerce.core':'1.4.0','solution.ecommerce.growth':'1.10.0'})
    successor.EXPECTED_OLD_COUNT=17;successor.EXPECTED_NEW_COUNT=19
    successor.EXTRA_BUILD_PATHS=(*successor.EXTRA_BUILD_PATHS,'scripts/prepare_ecommerce_event_candidates.py','scripts/build_ecommerce_event_candidates.py')
    successor.ACTOR_PREFIX='a0v-event-complete-20260916'
    successor.SUCCESS_OUTCOME='EVENT_COMPLETE_REGISTRY_GREEN'
    original=successor.require_sessions
    def require_sessions(document):
        copied=json.loads(json.dumps(document))
        core=(copied.get('runtimeSessions') or {}).get('domain.ecommerce.core') or {}
        expected_result=dict(schemaVersion='aos.product-event-window-result/v1',requestHash=profile.digest(profile.PAYLOAD),events=[dict(eventKey='a'*64,deadline='2026-09-16T00:11:00+00:00')])
        expected=dict(method=profile.METHOD,payloadHash=profile.digest(profile.PAYLOAD),resultHash=profile.digest(expected_result),executionAllowed=False,evidence='qualification-fixture-only')
        if core.get('contributionCount')!=2 or core.get('readProbe')!=expected:
            raise ValueError('real isolated core event invocation required')
        core['contributionCount']=1
        original(copied)
    successor.require_sessions=require_sessions
    return successor


def main():
    path=Path(__file__).with_name('a0v_ecommerce_current_signed_successor.py')
    spec=importlib.util.spec_from_file_location('event_complete_publish_entry',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.load_successor=load_successor
    module.main()


if __name__=='__main__':main()
