"""Deterministic account-race checks against actual desktop/mobile browser pages.

Only authentication/API responses are synthetic. Static product assets are served
unchanged from the checkout or the supplied website. APK checks reuse these fixture
definitions through verify_workshop_android.cjs and Playwright's Android transport.
No production accounts, credentials, or data are used.
"""
from __future__ import annotations

import argparse
import functools
import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SEED = """if(location.pathname==='/app/workshop.html'){
  localStorage.setItem('ai_xingyue_logged_in','1');
  localStorage.setItem('ai_xingyue_user',JSON.stringify({id:'account-a',name:'Old account'}));
  for(const key of Object.keys(localStorage))if(key.startsWith('homer.page-cache.'))localStorage.removeItem(key);
  const put=(scope,owner,id)=>localStorage.setItem('homer.page-cache.v1.'+scope+'.'+owner,
    JSON.stringify({savedAt:Date.now(),value:{list:[{id,name:id,is_public:false}],total:1}}));
  put('workshop','account-a','polluted-private-b');
  put('workshop','account-z','polluted-private-z');
  put('workshop-v2','account-a','cached-a');
  put('workshop-v2','account-b','cached-b');
  put('histories','account-a','unrelated-history');
}"""
STATE = """() => {
 const root=document.querySelector('[x-data="workshopPage()"]');
 const d=root&&window.Alpine?.$data(root);
 return d?{ready:d.ready,refreshing:d.refreshing,appsLoaded:d.appsLoaded,
  ids:d.myApps.map(x=>x.id),error:d.refreshError,user:d.user?.id||null,
  cache:Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.startsWith('homer.page-cache.'))),
  cachedUser:JSON.parse(localStorage.getItem('ai_xingyue_user')||'null')}:null;
}"""


class Static(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def wait(page, condition, seconds=12):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if condition(): return
        page.wait_for_timeout(25)
    raise AssertionError('Condition not satisfied before deadline')


def run_case(page, base, name, out):
    state={'account':'account-b','profiles':0,'works':0,'hold_profile':False,
           'hold_works':False,'fail_profile':False,'fail_works':False}
    held_profiles=[]; held_works=[]; errors=[]; resources=[]
    page.on('pageerror', lambda e:errors.append(str(e)))
    def fulfill(route, data, status=200):
        route.fulfill(status=status,content_type='application/json',body=json.dumps(data))
    def profile(account): return {'id':account,'name':'验收账号 '+account,'is_admin':False}
    def works(account): return {'data':{'list':[{'id':'private-'+account,'name':'私有作品 '+account,'is_public':False}],'total':1}}
    def route_api(route):
        path=urlsplit(route.request.url).path
        account=state['account']
        if path=='/console/api/account/profile':
            state['profiles']+=1
            if state['hold_profile']: held_profiles.append((route,account));return
            fulfill(route,profile(account) if not state['fail_profile'] else {'message':'fixture unavailable'},503 if state['fail_profile'] else 200);return
        if path=='/console/api/web/my-apps':
            state['works']+=1
            if state['hold_works']: held_works.append((route,account));return
            fulfill(route,works(account) if not state['fail_works'] else {'message':'fixture unavailable'},503 if state['fail_works'] else 200);return
        if path=='/admin/api/me': fulfill(route,{'message':'admin required'},403);return
        if path.endswith('/home-stats'): fulfill(route,{'data':{'apps':{'total':2}}});return
        if path.endswith('/site-settings'): fulfill(route,{'data':{}});return
        fulfill(route,{'data':{'list':[],'total':0},'points':100})
    for pattern in ('**/console/**','**/go/**','**/admin/api/**','**/api/homer/**'):
        page.route(pattern,route_api)
    def observe(response):
        if any(x in response.url for x in ('hub-pages.js','page-cache.js')):
            resources.append({'path':urlsplit(response.url).path,'apk':response.headers.get('x-homer-client-asset',''),'status':response.status})
    page.on('response',observe)
    def release_profiles():
        state['hold_profile']=False
        while held_profiles:
            route,account=held_profiles.pop(0);fulfill(route,profile(account))
    def release_works():
        state['hold_works']=False
        while held_works:
            route,account=held_works.pop(0);fulfill(route,works(account))
    def snapshot(): return page.evaluate(STATE)
    def complete(account='account-b'):
        wait(page,lambda: bool((s:=snapshot()) and not s['refreshing'] and s['ids']==['private-'+account]))
    def visible(): page.evaluate("window.dispatchEvent(new Event('homer:page-visible'))")
    try:
        if name in ('slow-profile','visible-during-init','logout-pending'):state['hold_profile']=True
        if name in ('account-changes-in-flight','destroy-pending'):state['hold_works']=True
        if name=='profile-failure':state['fail_profile']=True
        if name=='verified-cache-on-list-failure':state['fail_works']=True
        page.goto(base+'/app/workshop.html',wait_until='domcontentloaded')
        wait(page,lambda:state['profiles']>0 and bool(snapshot()))
        if name=='slow-profile':
            s=snapshot();assert s['ready'] and not s['ids'] and state['works']==0,s
            assert not any(k.startswith('homer.page-cache.v1.workshop.') for k in s['cache']),s
            assert 'homer.page-cache.v1.histories.account-a' in s['cache']
            assert page.locator('a[href="/app/create.html"]').first.count()>0
            release_profiles();complete()
        elif name=='visible-during-init':
            for _ in range(4):visible()
            assert state['works']==0
            release_profiles();complete();assert state['works']==1,state
        elif name=='visible-switch-account':
            complete();count=state['works'];state['account']='account-c';state['hold_profile']=True
            visible();wait(page,lambda:bool(held_profiles));assert not snapshot()['ids'] and state['works']==count
            release_profiles();complete('account-c')
        elif name=='account-changes-in-flight':
            wait(page,lambda:bool(held_works))
            state['account']='account-c'
            page.evaluate("localStorage.setItem('ai_xingyue_user',JSON.stringify({id:'account-c'}))")
            visible();release_works();complete('account-c')
            assert 'private-account-b' not in snapshot()['cache'].get('homer.page-cache.v1.workshop-v2.account-b','')
        elif name=='logout-pending':
            page.evaluate("async()=>{const m=await import('/assets/js/api.js?v=20260917-r8');m.clearAuth();}")
            # Native account teardown can announce page visibility after clearing auth.
            visible()
            release_profiles();wait(page,lambda:not snapshot()['refreshing'])
            s=snapshot();assert s['cachedUser'] is None and not s['ids'] and state['works']==0,s
        elif name=='profile-failure':
            wait(page,lambda:not snapshot()['refreshing'])
            s=snapshot();assert not s['ids'] and s['error'] and state['works']==0,s
            state['fail_profile']=False
            page.get_by_role('button',name='重试',exact=True).click();complete()
        elif name=='verified-cache-on-list-failure':
            wait(page,lambda:not snapshot()['refreshing'])
            s=snapshot();assert s['ids']==['cached-b'] and s['error'],s
        elif name=='destroy-pending':
            wait(page,lambda:bool(held_works))
            before=snapshot()['cache']
            page.evaluate("Alpine.$data(document.querySelector('[x-data=\"workshopPage()\"]')).destroy()")
            release_works();wait(page,lambda:not snapshot()['refreshing'])
            assert snapshot()['cache']==before
        else:raise ValueError(name)
        s=snapshot()
        assert 'private-account-b' not in s['cache'].get('homer.page-cache.v1.workshop-v2.account-a','')
        assert 'private-account-c' not in s['cache'].get('homer.page-cache.v1.workshop-v2.account-b','')
        assert not errors,errors
        overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
        assert not overflow
        if name in ('slow-profile','visible-switch-account'):
            page.screenshot(path=str(out/(name+'.png')),full_page=True)
        return {'name':name,'passed':True,'profile_requests':state['profiles'],'private_requests':state['works'],
                'visible_ids':s['ids'],'cache_keys':list(s['cache']),'page_errors':errors,'overflow':overflow,'resources':resources}
    finally:
        for route,_ in held_profiles+held_works:
            try:route.abort()
            except Exception:pass
        page.unroute_all(behavior='ignoreErrors')
        page.remove_listener('response',observe)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url')
    parser.add_argument('--output',type=Path,default=ROOT/'output/workshop-cache-fix-20261001/browser')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    server=None
    if not args.base_url:
        server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Static,directory=str(ROOT/'frontend')))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        args.base_url=f'http://127.0.0.1:{server.server_port}'
    cases=['slow-profile','visible-during-init','visible-switch-account','account-changes-in-flight',
           'logout-pending','profile-failure','verified-cache-on-list-failure','destroy-pending']
    results=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,channel='chrome')
            sizes=[(1440,900),(390,844)]
            for size in sizes:
                for name in cases:
                    ctx=browser.new_context(viewport={'width':size[0],'height':size[1]})
                    page=ctx.new_page()
                    page.set_default_timeout(12000)
                    page.add_init_script(SEED)
                    folder=args.output/str(size[0]);folder.mkdir(exist_ok=True)
                    try:result=run_case(page,args.base_url,name,folder)
                    except Exception as e:
                        result={'name':name,'passed':False,'error':str(e)[:1600]}
                        try:page.screenshot(path=str(folder/(name+'-failure.png')),full_page=True)
                        except Exception:pass
                    result['surface']=f'chromium-{size[0]}'
                    results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
                    (args.output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
                    ctx.close()
            browser.close()
    finally:
        if server:server.shutdown();server.server_close()
    return 0 if all(x['passed'] for x in results) else 1


if __name__=='__main__':raise SystemExit(main())
