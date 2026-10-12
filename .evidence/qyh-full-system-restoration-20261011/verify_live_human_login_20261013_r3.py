"""One known live login attempt and read-only tenant checks; no secret outputs."""
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:18080'

def request(path, method='GET', body=None, headers=None, target=URL):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(target+path,data=data,method=method,headers={'Content-Type':'application/json',**(headers or {})})
    try:
        with urllib.request.urlopen(req,timeout=20) as response: return response.status,json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {}

if __name__ == '__main__':
    intent = BASE / 'live-human-login-verification-intent-20261013-r3.json'
    assert not intent.exists(), 'Known attempt exists: reconcile, no automatic credential replay'
    config_status,config = request('/v1/auth/oidc')
    assert config_status == 200 and config['allowDevToken'] is False and config['tokenUrlConfigured'] is True
    secret = json.loads(Path('/Users/ddt/.aos-local-identities/qyh-20261013/user-password-input.json').read_text())
    intent.write_text(json.dumps({'user':'datong838','target':'original live API18080','singleAttempt':True,'businessWrites':False},indent=2))
    status,tokens = request('/v1/auth/token','POST',{'grantType':'password','username':secret['username'],'password':secret['password']})
    assert status == 200 and tokens.get('accessToken'), 'Credential attempt terminal failure; inspect sanitized source, no replay'
    headers = {'Authorization':'Bearer '+tokens['accessToken'],'X-Org-Id':'org-org','X-Project-Id':'dev-project'}
    try:
        status,me = request('/v1/me',headers=headers)
        assert status == 200, 'Token accepted but canonical me failed; inspect exact current state'
        assert me['subject']=='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' and me['orgId']=='org-org' and me['projectId']=='dev-project'
        assert me['tokenKind']=='oidc' and 'admin' in me['roles']
        org_status,orgs = request('/v1/orgs',headers=headers)
        negatives={}
        for name,changed in [('crossOrg',{'X-Org-Id':'dev-org'}),('crossProject',{'X-Project-Id':'unknown-workspace'}),('devToken',{'Authorization':'Bearer dev'})]:
            code,_=request('/v1/me',headers={**headers,**changed});assert code in {401,403};negatives[name]=code
        code,_=request('/v1/auth/token','POST',{'grantType':'dev'});assert code==403;negatives['devGrant']=code
        code,_=request('/v1/installations','POST',{},headers);assert code==405;negatives['businessWrite']=code
        result={'outcome':'LIVE_ORIGINAL_PASSWORD_AND_CANONICAL_QYH_ME_GREEN','credentialsAccepted':True,
            'me':{k:me[k] for k in ['subject','orgId','orgName','projectId','workspaceName','roles','tokenKind','displayName']},
            'orgListStatus':org_status,'negativeStatuses':negatives,'passwordOrTokensStored':False,
            'profileCacheReady':me['displayName']=='datong838','interactiveHumanLoginObserved':False,'eightWorkbenchesAccepted':False,'businessExecutionAuthorized':False}
        (BASE/'live-human-login-verification-20261013-r3.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
        print('Live original password login and canonical Qyh admin verified; all5 negative gates refused.')
    finally:
        if tokens.get('refreshToken'):
            body=urllib.parse.urlencode({'client_id':'aos-api','refresh_token':tokens['refreshToken']}).encode()
            req=urllib.request.Request('http://127.0.0.1:18448/realms/qyh-local/protocol/openid-connect/logout',data=body,method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req,timeout=20) as response:
                assert response.status==204
            (BASE/'live-human-login-selftest-session-logout-20261013-r3.json').write_text('{"status":204,"onlyNewSelftestSession":true}\n')
