"""Private organization uploads and validated LINE message builders."""
import base64
import binascii
from io import BytesIO
import os
import re
import sqlite3
from urllib.parse import urlsplit
from uuid import uuid4
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
import app
import channels
import reports

MAX_UPLOAD = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000


MAX_BYTES = 1_000_000  # 單張圖片轉成 PNG 後的上限


def png_bytes(image):
    out=BytesIO();image.save(out,format='PNG',optimize=True)
    return out.getvalue()


def compact(image):
    data=png_bytes(image)
    if len(data)>MAX_BYTES:
        data=png_bytes(image.quantize(colors=128))
    if len(data)>MAX_BYTES:
        data=png_bytes(image.quantize(colors=32))
    if len(data)>MAX_BYTES:
        raise ValueError('圖片內容過大，請裁切後再選擇。')
    return data


def upload(payload,user):
    encoded=payload.get('data','');name=payload.get('name','圖片')
    if not isinstance(encoded,str) or len(encoded)>((MAX_UPLOAD+2)//3)*4 or not isinstance(name,str) or len(name)>240:
        raise ValueError('請選擇 8 MB 以內的 JPG 或 PNG。')
    organization_id=payload.get('organization_id','') if user['role']=='platform_admin' else user['organization_id']
    channels.enforce_organization(organization_id)
    if not isinstance(organization_id,str) or (organization_id and not any(o['org_id']==organization_id and o['active'] for o in reports.organizations())):
        raise ValueError('請選擇有效組織。')
    try:
        raw=base64.b64decode(encoded,validate=True)
        if not raw or len(raw)>MAX_UPLOAD:
            raise ValueError()
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as original:
                if original.format not in {'PNG','JPEG'} or getattr(original,'n_frames',1)!=1:
                    raise ValueError()
                original.load()
                image=ImageOps.exif_transpose(original).convert('RGBA')
                image.thumbnail((2048,2048),Image.Resampling.LANCZOS)
                # Remove source metadata and always store a normalized PNG.
                clean=Image.new('RGBA',image.size);clean.paste(image)
                data=compact(clean)
    except (ValueError,OSError,binascii.Error,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise ValueError('無法讀取圖片，請選擇 8 MB、2000 萬畫素以內的單張 JPG／PNG。') from None
    asset_id=uuid4().hex
    folder=app.BASE_DIR/'data'/'uploads';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(asset_id+'.png');path.write_bytes(data)
    safe_name=name.replace('\\','/').rsplit('/',1)[-1] or '圖片'
    try:
        with app.database_connection() as conn:
            conn.execute('INSERT INTO upload_assets(channel_id,asset_id,name,organization_id,owner) VALUES (current_channel(),?,?,?,?)',(asset_id,safe_name,organization_id,user['email']))
    except Exception:
        path.unlink(missing_ok=True);raise
    return {'asset_id':asset_id,'name':safe_name,'organization_id':organization_id,'size':len(data),'width':clean.width,'height':clean.height,
            'preview':'data:image/png;base64,'+base64.b64encode(data).decode('ascii')}


def asset(asset_id,user):
    if not isinstance(asset_id,str) or not re.fullmatch('[0-9a-f]{32}',asset_id):
        raise ValueError('圖片識別資料不正確。')
    with app.database_connection() as conn:
        conn.row_factory=sqlite3.Row
        row=conn.execute('SELECT * FROM upload_assets WHERE upload_assets.channel_id=current_channel() AND asset_id=?',(asset_id,)).fetchone()
    if not row or not reports.same_organization(user,row['organization_id']) or (user['role']=='operator' and row['owner']!=user['email']):
        raise ValueError('找不到可使用的圖片。')
    path=app.BASE_DIR/'data'/'uploads'/(asset_id+'.png')
    if not path.is_file():
        raise ValueError('圖片已不存在，請重新選擇。')
    return {**dict(row),'path':path}


def text(value,maximum,required=False):
    if not isinstance(value,str) or len(value.encode('utf-16-le'))//2>maximum or (required and not value.strip()):
        raise ValueError(f'請填寫 {maximum} 字以內的內容。')
    return value.strip()


def action(item):
    url=text(item.get('url',''),1000,True)
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or any(ord(c)<32 for c in url):
        raise ValueError('按鈕連結請使用完整 HTTPS 網址。')
    return {'type':'uri','label':text(item.get('label','開啟連結'),20,True),'uri':url}


def prepare(draft,user,selected):
    if not isinstance(draft,dict) or draft.get('format') not in {'images','card','carousel','imagemap'}:
        raise ValueError('請選擇訊息格式。')
    kind=draft['format'];items=draft.get('items');limit={'images':5,'card':1,'carousel':12,'imagemap':1}[kind]
    if not isinstance(items,list) or not 1<=len(items)<=limit or (kind in {'card','imagemap'} and len(items)!=1):
        raise ValueError(f'這個格式支援 1 至 {limit} 張圖片。')
    alt=text(draft.get('alt_text','圖片訊息'),400,True)
    clean=[]
    for item in items:
        if not isinstance(item,dict):
            raise ValueError('卡片格式不正確。')
        picture=asset(item.get('asset_id'),user)
        if picture['organization_id'] and any(r['organization_id']!=picture['organization_id'] for r in selected):
            raise ValueError('圖片與發送對象必須屬於同一組織。')
        card={'asset':picture}
        if kind in {'card','carousel'}:
            card.update(title=text(item.get('title',''),80,True),description=text(item.get('text',''),500),action=action(item))
        clean.append(card)
    areas=[]
    if kind=='imagemap':
        layout=draft.get('layout','one')
        grids={'one':(1,1),'two':(2,1),'four':(2,2),'six':(3,2)}
        if layout not in grids:
            raise ValueError('請選擇點擊區域版型。')
        cols,rows=grids[layout]
        values=draft.get('areas',[])
        if not isinstance(values,list) or len(values)!=cols*rows or any(not isinstance(v,dict) for v in values):
            raise ValueError('請填寫每個區塊的連結。')
        areas=[action(v) for v in values]
        with Image.open(clean[0]['asset']['path']) as image:
            ratio=image.height/image.width
            if not .5<=ratio<=2:
                raise ValueError('圖文訊息的圖片高寬比請介於 1:2 至 2:1。')
    return {'format':kind,'alt_text':alt,'items':clean,'areas':areas,'layout':draft.get('layout','one')}


def build(prepared,publish,verify):
    """Publish only after every card, action and recipient scope has validated."""
    base=app.public_base_url()
    parsed=urlsplit(base)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise ValueError('PUBLIC_BASE_URL 必須是 HTTPS 網站根網址。')
    kind=prepared['format'];urls=[]
    for item in prepared['items'] if kind != 'imagemap' else []:
        url,data=publish(item['asset']['path'],base);verify(url,data);urls.append(url)
    if kind=='images':
        return [{'type':'image','originalContentUrl':url,'previewImageUrl':url} for url in urls]
    if kind=='imagemap':
        with Image.open(prepared['items'][0]['asset']['path']) as image:
            height=round(1040*image.height/image.width)
            map_id=uuid4().hex
            folder=app.BASE_DIR/'published-images';folder.mkdir(exist_ok=True)
            for width in (240,300,460,700,1040):
                resized=image.convert('RGBA').resize((width,round(height*width/1040)),Image.Resampling.LANCZOS)
                data=compact(resized);(folder/f'{map_id}-{width}.png').write_bytes(data)
                verify(base.rstrip('/')+f'/imagemaps/{map_id}/{width}',data)
        cols,rows={'one':(1,1),'two':(2,1),'four':(2,2),'six':(3,2)}[prepared['layout']]
        areas=[]
        for i,item in enumerate(prepared['areas']):
            col,row=i%cols,i//cols;x=1040*col//cols;y=height*row//rows
            areas.append({'type':'uri','linkUri':item['uri'],'area':{'x':x,'y':y,'width':1040*(col+1)//cols-x,'height':height*(row+1)//rows-y}})
        return [{'type':'imagemap','baseUrl':base.rstrip('/')+'/imagemaps/'+map_id,'altText':prepared['alt_text'],
                 'baseSize':{'width':1040,'height':height},'actions':areas}]
    bubbles=[]
    for card,url in zip(prepared['items'],urls):
        contents=[{'type':'text','text':card['title'],'weight':'bold','size':'lg','wrap':True}]
        if card['description']:
            contents.append({'type':'text','text':card['description'],'size':'sm','wrap':True,'margin':'md'})
        bubbles.append({'type':'bubble','hero':{'type':'image','url':url,'size':'full','aspectRatio':'4:3','aspectMode':'cover'},
                        'body':{'type':'box','layout':'vertical','contents':contents},
                        'footer':{'type':'box','layout':'vertical','contents':[{'type':'button','style':'primary','action':card['action']}]}})
    contents=bubbles[0] if kind=='card' else {'type':'carousel','contents':bubbles}
    return [{'type':'flex','altText':prepared['alt_text'],'contents':contents}]
