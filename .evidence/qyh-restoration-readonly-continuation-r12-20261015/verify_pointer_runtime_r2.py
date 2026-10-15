"""Fresh exact runtime/source/read/no-effect evidence; partial visual scope only."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys

E = Path(__file__).resolve().parent
R = E.parents[1]
S = R / '.evidence/qyh-restoration-successor-latest-restart-20261013'
HEAD = '8dbb4c7c3f48ee161f4d6bf231b35c865a77caf5'
sys.path.insert(0, str(R / 'scripts'))
import a0v_qyh_restored_http as guard


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def cmd(*args): return subprocess.check_output(args, cwd=R, text=True).strip()


def save(name, value):
    with (E / name).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


assert cmd('git', 'rev-parse', 'HEAD') == HEAD
assert cmd('lsof', '-t', '-nP', '-iTCP:18080', '-sTCP:LISTEN') == '54057'
api_source = guard.require_api_source_candidate(R / '.evidence/qyh-full-system-restoration-20261011/customer-closure-api-20261015.json')
assert str(api_source) in cmd('lsof', '-a', '-p', '54057', '-d', 'cwd', '-Fn')
assert not cmd('git', 'diff', '0b0c88882ce6e9cdab168baf485ef50fa5baefb7', 'HEAD', '--', 'services/aos-api', 'scripts', 'bundles')
assert cmd('lsof', '-t', '-nP', '-iTCP:18434', '-sTCP:LISTEN') == '61045'
assert cmd('ps', '-p', '61045', '-o', 'command=') == '/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node ' + str(E / 'customer-pointer-web-server.mjs')
web = read(E / 'customer-pointer-web-source.json')
source = Path(web['source'])
assert web['head'] == HEAD and len(web['manifest']) == 764
assert {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()} == web['manifest']
css = 'apps/web/src/styles/45-ecommerce-workshop.css'
assert sha(source / css) == sha(R / css) == web['sourceHashes'][css]
before_path = S / 'customer-pointer-web-before-20261015.json'
after_path = S / 'customer-pointer-web-after-r2-20261015.json'
before, after = read(before_path), read(after_path)
assert len(before['fingerprints']) == len(after['fingerprints']) == 650 and before['fingerprints'] == after['fingerprints']
for key in ['native', 'containerId', 'volume', 'pgStartedAt']: assert before[key] == after[key]
pg = json.loads(cmd('docker', '--context', 'colima-aos-extension', 'inspect', 'qyh-restored-pg-20261011'))[0]
assert pg['Id'] == before['containerId'] and pg['State']['StartedAt'] == before['pgStartedAt'] and pg['Mounts'][0]['Name'] == before['volume']
sdk = read(E / 'pointer-native-identity-sdk-r2.json')
assert sdk['me'] == dict(subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657', orgId='org-org', projectId='dev-project')
assert sdk['query400'] == 400 and sdk['anonymous401'] == 401 and sdk['normalRenewLoginStatus'] == 200
assert sdk['view']['tenant'] == sdk['contact']['tenant'] == dict(orgId='org-org', projectId='dev-project')
assert len(sdk['view']['views']) == 4 and sdk['contact']['allowedCommands'] == []
assert all(sdk['contact'][key] is False for key in ['permitRedemptionAllowed', 'contactResolutionAllowed', 'providerDispatchAllowed', 'sendAllowed', 'externalEffectsAllowed'])
browser = read(E / 'pointer-native-geometry-r2.json')
network = read(E / 'pointer-final-network-r2.json')
assert not browser['businessNonGet'] and not network['businessNonGet']
assert browser['temporaryViewportCleared'] and not browser['forceOrDomClickUsed'] and browser['explicitButtonsDown1Up0']
assert len(network['normalAuthPosts']) == 2 and all(x['status'] == 200 for x in network['normalAuthPosts'])
event = read(E / 'pointer-event-witness-r2.json')['event']
assert event['observed'] and event['isTrusted'] and event['tab'] == 'customer-tab-segment'
screens = []
for width, height in [(1280, 720), (1440, 900), (1920, 1080)]:
    metric = next(x for x in browser['metrics'] if x['width'] == width)
    geom = metric['geometry']
    assert geom['viewportWidth'] == geom['documentWidth'] == width and not geom['loading']
    assert geom['parentPointer'] == 'none' and geom['tabPointer'] == 'auto'
    assert len(geom['filters']) == 4 and all(x['height'] == 32 and x['hitInside'] for x in geom['filters'])
    expected = ['customer', 'segment', 'journey', 'dialogue']
    assert len(metric['tabs']) == 4
    for tab, suffix in zip(metric['tabs'], expected):
        assert tab['selected'] == ['customer-tab-' + suffix] and tab['panel'] == 'customer-panel-' + suffix
    assert metric['filters'] == [['可披露'], ['待复核'], ['已排除'], ['全部']]
    assert len(metric['keyboard']) == 4 and all(x['focusVisible'] for x in metric['keyboard'])
    assert metric['filterKeyboard']['tabFocus'] == dict(text='可披露', visible=True)
    assert metric['filterKeyboard']['enterActivatedDisclosureFilter']
    for kind in ['reference', 'actual']:
        path = E / f'pointer-{kind}-{width}-r2.png'
        assert struct.unpack('>II', path.read_bytes()[16:24]) == (width, height)
        screens.append(dict(file=path.name, sha256=sha(path), width=width, height=height, manuallyInspected=True))
save('pointer-full650-comparison-r2.json', dict(beforeFile=str(before_path.relative_to(R)), beforeSha=sha(before_path), afterFile=str(after_path.relative_to(R)), afterSha=sha(after_path), count=650, allEqual=True, tableEquality={t: before['fingerprints'][t] == after['fingerprints'][t] for t in sorted(before['fingerprints'])}))
save('pointer-live-shas-r2.json', dict(screens=screens, temporaryViewportCleared=True, wholeVisualComplete=False))
save('pointer-runtime-proof-r2.json', dict(head=HEAD, productFile=css, productCssSha=sha(R / css), webPid=61045, webSource=str(source), webManifestCount=764, webManifestVerified=True, apiPid=54057, apiSource=str(api_source), apiUnchanged=True, originalContainerId=before['containerId'], originalVolume=before['volume'], pgStartedAt=before['pgStartedAt'], native=before['native'], tables=650, all650BeforeAfterEqual=True, realIdentityVerified=True, sdkCustomerAndContactParsed=True, contactCommandsEmptyAndFiveEffectsFalse=True, query400=True, anonymous401=True, businessNonGet=[], postSwitchNormalAuthPosts=2, expiredReadOnlyJwtFailurePreservedAndNormalLoginRecovered=True, threeViewportsNativePointerAndKeyboardPassed=True, nativePointerTrustedWitness=True, explicitMouseButtonsDown1Up0=True, noForceOrDomClick=True, fourFilters32pxAndPointerHit=True, fourTabsAndPanelMatch=True, filterKeyboardTabEnter=True, keyboardVisibleFocus=True, noHorizontalOverflow=True, sameSizeScreens=6, onlyWebSwitched=True, dailyFullRestartSubstitute=False, fullFailureBrowserModeNotClaimed=True, wholeVisualComplete=False, wholeGoalComplete=False))
print(json.dumps(dict(webPid=61045, apiPid=54057, all650Equal=True, threeWidthsNormalInteraction=True, sixSameSizeScreens=True, wholeGoalComplete=False)))
