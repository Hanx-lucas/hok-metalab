"""Preserve the limited public-source pilot and optionally refresh its 9 requests.

Default: replay existing evidence, without network. --refresh: 2s request spacing,
one attempt per request, fail closed on authentication or schema rejection.
This is not an unattended whole-site crawler; wider API use should follow the
provider's published contact instructions and preserve attribution.
"""
import argparse, hashlib, json, shutil, sys, time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if (ROOT/'.deps').exists():sys.path.insert(0,str(ROOT/'.deps'))
from hoklab.daily import build_daily_queries, SEGMENTS, HEROES

def preserve(key, body, url, captured_at):
    obj=json.loads(body)
    if obj.get('status',{}).get('code')!=200:
        raise PermissionError('Provider rejected anonymous request; do not retry with bypasses')
    raw=ROOT/'data/raw/alternative';raw.mkdir(parents=True,exist_ok=True)
    meta={'key':key,'url':url,'method':'POST','http_status':200,'retrieved_at':captured_at,
          'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),
          'classification':'third_party_public_aggregate','credentials_used':False}
    dest=raw/(key+'.json')
    if dest.exists() and dest.read_bytes()!=body:
        archive=raw/'archive'/key;archive.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(dest,archive/(stamp+'.json'))
        shutil.copy2(dest.with_suffix('.meta.json'),archive/(stamp+'.meta.json'))
    dest.write_bytes(body);dest.with_suffix('.meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
    targets={'susu_app_info':'https://api.91m.top/hero/app?type=getAppInfo&gameType=wzry'}
    targets.update({f'susu_rank_{did}':f'https://api.91m.top/hero/app?type=getRanking&aid=0&bid=0&cid=0&did={did}&gameType=wzry' for did in SEGMENTS})
    targets.update({f'susu_history_{hid}':f'https://api.91m.top/hero/app?type=getHeroChartsLog&aid=0&bid=0&cid=0&did=0&id={hid}&gameType=wzry' for hid in HEROES})
    research=ROOT/'research/alternative_sources'
    if args.refresh:
        for key,url in targets.items():
            request=urllib.request.Request(url,data=b'',headers={'User-Agent':'HoK-MetaLab/1.0 academic portfolio research','Content-Type':'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(request,timeout=25) as response:body=response.read()
            preserve(key,body,url,datetime.now(timezone.utc).isoformat());time.sleep(2)
    else:
        # Published cache replay must not depend on private browser research artifacts.
        cache_complete=all((ROOT/'data/raw/alternative'/(key+'.json')).exists() for key in targets)
        requests=[] if cache_complete else json.loads((research/'susu-ui-requests.json').read_text(encoding='utf-8'))
        for key,url in targets.items():
            if (ROOT/'data/raw/alternative'/(key+'.json')).exists():continue
            if key=='susu_app_info':
                # The UI response binds announcement date and ranking snapshots.
                i=next(i for i,r in enumerate(requests) if 'type=getAppInfo&' in r['url']);path=research/f'ui-response-{i}.json';url=requests[i]['url']
            elif key.startswith('susu_rank_'):
                did=key.rsplit('_',1)[1];i=next(i for i,r in enumerate(requests) if 'type=getRanking&aid=0&' in r['url'] and f'&did={did}&' in r['url']);path=research/f'ui-response-{i}.json';url=requests[i]['url']
            elif key=='susu_history_527':
                i=next(i for i,r in enumerate(requests) if 'type=getHeroChartsLog&aid=0&bid=0&' in r['url'] and '&id=527&' in r['url']);path=research/f'ui-response-{i}.json';url=requests[i]['url']
            else:path=research/('susu_history_hero'+key.rsplit('_',1)[1]+'.json')
            captured=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()
            preserve(key,path.read_bytes(),url,captured)
    dest=ROOT/'data/reviewed_snapshot.json';snapshot=json.loads(dest.read_text(encoding='utf-8'))
    summary=build_daily_queries(snapshot)
    from hoklab.strength import build_strength_queries
    build_strength_queries(snapshot)
    dest.write_text(json.dumps(snapshot,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
