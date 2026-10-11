"""Cache publicly displayed Tencent hero artwork for the portfolio; no runtime hotlinking."""
import base64,hashlib,io,json,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'site/src/content/assets/hero-art';OUT.mkdir(parents=True,exist_ok=True)
heroes=json.loads((ROOT/'data/raw/heroes.json').read_text(encoding='utf-8'))
manifest=[];portraits={}
def fetch(key,url):
 path=OUT/(key+'.webp')
 meta_path=OUT/(key+'.meta.json')
 if path.exists() and meta_path.exists():
  meta=json.loads(meta_path.read_text(encoding='utf-8'));assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['asset_sha256'];manifest.append(meta);return path.read_bytes()
 req=urllib.request.Request(url,headers={'User-Agent':'HoK-MetaLab/1.0 personal-portfolio','Referer':'https://pvp.qq.com/'})
 try:
  with urllib.request.urlopen(req,timeout=15) as r:body=r.read();status=r.status
  img=Image.open(io.BytesIO(body)).convert('RGB')
  if key=='splash-107':img.thumbnail((1440,900))
  else:img.thumbnail((160,160))
  buf=io.BytesIO();img.save(buf,format='WEBP',quality=85);data=buf.getvalue();path.write_bytes(data)
  meta={'key':key,'url':url,'source_page':'https://pvp.qq.com/web201605/herodetail/'+key.split('-')[-1]+'.shtml','provider':'Tencent / 王者荣耀官方美术','retrieved_at':datetime.now(timezone.utc).isoformat(),'http_status':status,'original_sha256':hashlib.sha256(body).hexdigest(),'asset_sha256':hashlib.sha256(data).hexdigest(),'dimensions':list(img.size),'bytes':len(data)}
  meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');manifest.append(meta);return data
 except Exception as e:print('Unavailable artwork',key,type(e).__name__,flush=True);return None
for i,h in enumerate(heroes):
 hid=h['ename'];data=fetch('portrait-'+str(hid),f'https://game.gtimg.cn/images/yxzj/img201606/heroimg/{hid}/{hid}.jpg')
 if data:portraits[str(hid)]='data:image/webp;base64,'+base64.b64encode(data).decode()
 if (i+1)%25==0:print('Portraits reviewed',i+1,'/',len(heroes),flush=True)
 time.sleep(.08)
splash=fetch('splash-107','https://game.gtimg.cn/images/yxzj/img201606/skin/hero-info/107/107-bigskin-1.jpg')
assert splash is not None,'Main artwork unavailable'
(OUT/'portraits.json').write_text(json.dumps(portraits,separators=(',',':')),encoding='utf-8')
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'cached_portraits':len(portraits),'catalog_heroes':len(heroes),'splash_bytes':len(splash),'total_asset_bytes':sum(x['bytes'] for x in manifest)},ensure_ascii=False),flush=True)
