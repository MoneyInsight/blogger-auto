import json,re,sys,os
sys.path.insert(0,'/home/claude/blogger-auto/naver-queue'); from thumb import render
R='/home/claude/blogger-auto'; Q=R+'/naver-queue/naver2'
cu=json.load(open(R+'/coupang/links.json'))['items']; B=['https://naver.me/FdqfXXDc','https://naver.me/GsBpaVui']
S='https://smartstore.naver.com/sonkb/products/13803027356'; E='<p><br></p>'
RR=(17-1)*24+12
T=lambda rows,head:'<table border="1" style="border-collapse:collapse;width:100%"><tr>'+''.join(f'<th>{h}</th>' for h in head)+'</tr>'+''.join('<tr>'+''.join(f'<td>{c}</td>' for c in r)+'</tr>' for r in rows)+'</table>'
SER={'경제':'오늘의 돈 브리핑 · 11.19','건강':'오늘의 건강 체크 · 11.19','IT':'오늘의 IT 트렌드 · 11.19'}
DIS={'경제':'※ 본 글은 투자 권유가 아니며, 투자 판단과 책임은 본인에게 있습니다.','건강':'※ 본 글은 일반 건강 정보이며, 개인 건강 상태에 따른 판단은 의사와 상담하세요.','IT':'※ 본 글은 공개된 보도·발표를 바탕으로 정리한 정보이며, 기기·앱 버전에 따라 내용이 다를 수 있습니다.'}
LOG=[]
DISC={'쿠팡': '이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.', '네이버': '네이버 브랜드 커넥트 링크를 통해 구매하면 판매 수익의 일부를 수수료로 받을 수 있습니다.'}
def build(i,kind,label,title,kw,thumb,intro2,box,secs,table,closing,src,tags,prod=None):
    # prod: 글 주제와 맞는 상품이 있을 때만 {'src':'쿠팡'|'네이버','url':...,'name':...}. 없으면 상품 카드 없음. 스마트스토어(S)는 항상 본문 중간.
    n=15*RR+i-1; c=cu[n%len(cu)]; bl=B[n%2]
    p=lambda t:f'<p>{t}</p>'+E
    it=kind=='IT'
    html=p(intro2[0]+' '+intro2[1]) if False else p(intro2[0])+p(intro2[1])
    if kind=='경제': html+=p('📌 [오늘의 돈 브리핑] — 지금 사람들이 가장 많이 찾는 돈 이야기를 정리해요.')
    html+=p('<br>'.join(f'<b>✔ {b}</b>' for b in box))
    for k,(h,paras) in enumerate(secs):
        html+=E+f'<h3>{h}</h3>'+E
        if k==1: html+=table+E
        html+=''.join(p(x) for x in paras)
        if k==1: html+=p(S)
    nxt='다음 편도 지금 사람들이 가장 많이 찾는 이야기로 곧 돌아온다.<br>도움이 됐다면 이웃추가 해두자!' if it else '다음 편도 지금 사람들이 가장 많이 찾는 이야기로 곧 돌아올게요.<br>도움이 됐다면 이웃추가 해두세요!'
    html+=p(closing)+p(nxt)
    if prod:
        pn=prod['name'][:40]
        html+=(E+'<p><b>🛒 이 글과 함께 보면 좋은 상품</b></p>'+f'<p>{prod["url"]}</p><p><a href="{prod["url"]}" target="_blank" rel="sponsored nofollow"><b>👉 {pn} — {prod["src"]}</b></a></p>'
          +f'<p style="font-size:13px;color:#888;">{DISC[prod["src"]]}</p>'+E)
    html+=f'<p style="font-size:13px;color:#888;">{DIS[kind]}<br>출처: {src}</p>'+E+'<p>'+' '.join('#'+t for t in tags)+'</p>'
    body=html.split('<p><b>🛒')[0].replace(S,'')
    txt=re.sub(r'<[^>]+>','',body).replace(' ','').replace('\n','')
    kwp=sum(kw in x for x in re.findall(r'<p>(.*?)</p>',body))+sum(kw in h for h,_ in secs)
    LOG.append(f'{i:02d} {kind} 본문{len(txt)} 제목{len(title)} 키워드문단{kwp} 15자:{kw[:3] in title[:15]} 첫문단:{kw in intro2[0]} 하루:{"하루" in html}')
    d=f'{Q}/20261119-{i:02d}'; os.makedirs(d,exist_ok=True)
    json.dump({"label":label,"title":title,"thumb":"thumb.png","images":[],"tags":[],"html":html,"product_urls":[S]+([prod["url"]] if prod else [])},open(d+'/post.json','w',encoding='utf8'),ensure_ascii=False,indent=1)
    render(thumb,SER[kind],n).save(d+'/thumb.png')
