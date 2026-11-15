import random,numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
D='/usr/share/fonts/opentype/noto/';SB=D+'NotoSansCJK-Black.ttc';SO=D+'NotoSansCJK-Bold.ttc';RB=D+'NotoSerifCJK-Black.ttc';RO=D+'NotoSerifCJK-Bold.ttc'
def F(p,s):return ImageFont.truetype(p,s,index=1)
def H(c):c=c.lstrip('#');return tuple(int(c[i:i+2],16) for i in(0,2,4))
def fit(d,t,p,m,w):
    while m>20:
        f=F(p,m);b=d.textbbox((0,0),t,font=f)
        if b[2]-b[0]<=w:return f
        m-=4
    return F(p,m)
PAL=[("#221D16","#050505","#EADFCB","#A3161C","#FFFFFF","#E2BE6A",0),("#1B2440","#04060C","#E6E1D6","#B01E2A","#FFF8EC","#E9D3A3",0),
("#4A1219","#120305","#F3E2D0","#0E0E0E","#F2D58F","#E8C27C",0),("#123A2E","#020A07","#E3EDE6","#A3161C","#FFFFFF","#DDBA62",0),
("#24142E","#07030A","#EDE3F2","#B3122B","#FFFFFF","#E6C77A",0),("#1A2028","#030405","#DDE3EA","#C8102E","#FFFFFF","#D8DDE3",0),
("#2E2418","#0B0805","#F1E6D2","#7A1020","#FCE9C0","#F0C987",0),("#0F2A3A","#02080C","#DCEBF2","#D0342C","#FFFFFF","#9FD3E6",0),
("#F4EEE3","#E6DCCB","#1A1A1A","#9E1B22","#FFF6E0","#B08A3E",1),("#FBFAF7","#E7E3DA","#1C1C1C","#121212","#F0CF7A","#B88A2E",1),
("#F3ECEA","#E2D2CE","#2A1A1A","#8E1630","#FFFFFF","#B5795E",1),("#EEF1F4","#D5DCE3","#111827","#B91C1C","#FFFFFF","#7C8A99",1)]
METAL={"gold":("#FFF1C1","#E2BE6A","#A87A26"),"silver":("#FFFFFF","#C9D0D8","#7A8590"),"rose":("#FFE6DA","#E3A68B","#9A5B45"),"champ":("#FFF6E3","#E9D3A3","#B8925A")}
def bg(a,b,kind,rnd):
    yy,xx=np.mgrid[0:1080,0:1080]
    if kind==0:r=np.clip(np.hypot(xx-540,yy-410)/(1527*.62),0,1)**2
    elif kind==1:r=np.clip((xx+yy)/2160,0,1)
    else:r=np.clip(np.hypot(xx-rnd.choice([200,880]),yy-150)/1400,0,1)**1.4
    A,B=np.array(H(a)),np.array(H(b));im=Image.fromarray((A*(1-r[...,None])+B*r[...,None]).astype('uint8'))
    if kind==2:
        ov=Image.new('L',(1080,1080),0);od=ImageDraw.Draw(ov)
        for _ in range(14):
            x,y,s=rnd.randint(60,1020),rnd.randint(60,1020),rnd.randint(20,90);od.ellipse((x-s,y-s,x+s,y+s),fill=rnd.randint(18,45))
        ov=ov.filter(ImageFilter.GaussianBlur(14));im.paste(Image.new('RGB',(1080,1080),(255,255,255)),(0,0),ov)
    return im
def frame(d,k,G):
    if k==0:d.rectangle((36,36,1043,1043),outline=G,width=3);d.rectangle((50,50,1029,1029),outline=G,width=1)
    elif k==1:
        d.rectangle((40,40,1039,1039),outline=G,width=1)
        for cx,cy,sx,sy in((40,40,1,1),(1039,40,-1,1),(40,1039,1,-1),(1039,1039,-1,-1)):
            for i,L in enumerate((90,66,42)):
                o=12+i*10;d.line((cx+sx*o,cy+sy*o,cx+sx*(o+L),cy+sy*o),fill=G,width=2);d.line((cx+sx*o,cy+sy*o,cx+sx*o,cy+sy*(o+L)),fill=G,width=2)
    elif k==2:d.rectangle((44,44,1035,1035),outline=G,width=2);d.line((160,150,920,150),fill=G);d.line((160,940,920,940),fill=G)
    else:
        for cx,cy,sx,sy in((48,48,1,1),(1031,48,-1,1),(48,1031,1,-1),(1031,1031,-1,-1)):
            d.line((cx,cy,cx+sx*120,cy),fill=G,width=4);d.line((cx,cy,cx,cy+sy*120),fill=G,width=4)
def metal(im,t,f,y,st,edge,glow,x=540,an='mm'):
    m=Image.new('L',(1080,1080),0);ImageDraw.Draw(m).text((x,y),t,font=f,fill=255,anchor=an)
    if glow:im.paste(Image.new('RGB',(1080,1080),H(st[1])),(0,0),m.filter(ImageFilter.GaussianBlur(28)).point(lambda v:int(v*.35)))
    s=Image.new('L',(1080,1080),0);s.paste(m.filter(ImageFilter.GaussianBlur(20)).point(lambda v:int(v*.55)),(0,10));im.paste(Image.new('RGB',(1080,1080)),(0,0),s)
    ImageDraw.Draw(im).text((x,y),t,font=f,fill=H(edge),anchor=an,stroke_width=2,stroke_fill=H(edge))
    bb=m.getbbox() or(0,0,1080,1080);c=[np.array(H(x),'float') for x in st];tt=np.clip((np.arange(1080)-bb[1])/max(1,bb[3]-bb[1]),0,1)[:,None]
    col=np.where(tt<.45,c[0]+(c[1]-c[0])*(tt/.45),c[1]+(c[2]-c[1])*((tt-.45)/.55));im.paste(Image.fromarray(np.repeat(col[:,None,:],1080,1).astype('uint8')),(0,0),m)
def stripes(im,G,rnd):
    ov=Image.new('L',(1080,1080),0);od=ImageDraw.Draw(ov);g=rnd.choice([28,40,56])
    for x in range(-1080,1080,g):od.line((x,1080,x+1080,0),fill=14,width=2)
    im.paste(Image.new('RGB',(1080,1080),G),(0,0),ov)
def render(th,series,seed):
    b,q,n,p=th;r=random.Random(seed);a,o,qc,band,btx,acc,light=r.choice(PAL)
    mk=r.choice(["gold","rose"] if light else (["silver","champ"] if acc in("#D8DDE3","#9FD3E6") else ["gold","champ","rose"]));st=METAL[mk];G=H(st[1])
    L=r.choice(["center","top","left","split","ring","stripe"])
    im=bg(a,o,r.choice([0,0,1,2]) if not light else r.choice([1,1,0]),r)
    if L=="stripe":stripes(im,G,r)
    d=ImageDraw.Draw(im)
    if L=="split":d.rectangle((0,700,1080,1080),fill=H(band))
    fk=r.randint(0,3);frame(d,fk,G)
    sc=H('#8A6A2E') if light else G;bc=H('#F6E9CF');lx=96
    f=F(SO,26)
    if L=="left":d.text((lx,108),series,font=f,fill=sc,anchor='lm')
    else:
        ws=[d.textbbox((0,0),c,font=f)[2] for c in series];x=540-(sum(ws)+5*(len(series)-1))/2
        for c,w in zip(series,ws):d.text((x,108),c,font=f,fill=sc,anchor='lm');x+=w+5
    fb=F(SB,40);bw=d.textbbox((0,0),b,font=fb)[2];bs=r.choice(["rect","pill","seal"]);by=170
    bx=lx+bw/2+34 if L=="left" else 540
    bcol=H(band) if L!="split" else H('#1A1714')
    if bs=="seal" and L!="left":d.ellipse((bx-62,by-14,bx+62,by+110),fill=bcol,outline=G,width=3);d.text((bx,by+48),b,font=fb,fill=bc,anchor='mm')
    else:
        box=(bx-bw/2-34,by,bx+bw/2+34,by+74)
        (d.rounded_rectangle(box,radius=37,fill=bcol,outline=G) if bs=="pill" else d.rectangle(box,fill=bcol,outline=G));d.text((bx,by+37),b,font=fb,fill=bc,anchor='mm')
    nf=r.choice([RB,RB,SB]);plain=light and r.random()<.4;edge='#3A2A0C' if mk!="silver" else '#2A3038';glow=(not light) and r.random()<.5
    def NUM(y,x=540,an='mm',w=920,mx=280):
        fn=fit(d,n,nf,mx,w)
        if plain:ImageDraw.Draw(im).text((x,y),n,font=fn,fill=H('#14110D'),anchor=an)
        else:metal(im,n,fn,y,st,edge,glow,x,an)
    if L=="top":
        NUM(400);d=ImageDraw.Draw(im);d.line((340,540,740,540),fill=G,width=2);d.text((540,610),q,font=fit(d,q,RO,80,900),fill=H(qc),anchor='mm')
    elif L=="left":
        d.rectangle((lx-26,300,lx-20,640),fill=G);d.text((lx,350),q,font=fit(d,q,RO,80,880),fill=H(qc),anchor='lm');NUM(530,lx,'lm',880)
    elif L=="ring":
        d.text((540,320),q,font=fit(d,q,RO,76,880),fill=H(qc),anchor='mm')
        d.ellipse((540-360,560-160,540+360,560+160),outline=G,width=3);d.ellipse((540-346,560-146,540+346,560+146),outline=G,width=1);NUM(560,w=640,mx=210)
    else:
        d.text((540,348),q,font=fit(d,q,RO,80,900),fill=H(qc),anchor='mm');NUM(540 if L!="split" else 535)
    d=ImageDraw.Draw(im)
    if L=="split":
        d.line((52,700,1028,700),fill=G,width=3);d.text((540,815),p,font=fit(d,p,SB,110,900),fill=H(btx),anchor='mm')
        d.text((540,962),"모르면 나만 손해 · 이유는 본문에서 ›",font=F(SO,32),fill=G,anchor='mm')
    else:
        y0,y1=735,880;ps=r.choice(["band","ribbon","pill"])
        if ps=="band":d.rectangle((52,y0,1028,y1),fill=H(band));d.rectangle((52,y0,1028,y0+1),fill=G);d.rectangle((52,y1-1,1028,y1),fill=G)
        elif ps=="ribbon":d.polygon([(40,y0),(1040,y0),(1000,(y0+y1)//2),(1040,y1),(40,y1),(80,(y0+y1)//2)],fill=H(band),outline=G)
        else:d.rounded_rectangle((70,y0,1010,y1),radius=72,fill=H(band),outline=G,width=2)
        d.text((540,(y0+y1)//2),p,font=fit(d,p,SB,104,860),fill=H(btx),anchor='mm')
        d.text((540,962),"모르면 나만 손해 · 이유는 본문에서 ›",font=F(SO,32),fill=G if not light else H('#8A6A2E'),anchor='mm')
    return Image.blend(im,Image.effect_noise((1080,1080),64).convert('RGB'),.03)
