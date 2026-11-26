"""Targeted checks of prose not covered by the random numeric-table sample."""
from datetime import date
from decimal import Decimal as D
from pathlib import Path
import json,sys
from 事实反算 import products_check,independent_model
P=Path(__file__).resolve().parent
def read(name):return json.loads((P/name).read_text(encoding='utf8'))
i=read('输入.json'); his=products_check();m=independent_model();a,b=his['2021'],his['2025'];m22=his['2022'];sh=D(i['market']['shares']); d=i['ytd_2026q3']; last=i['ytd_2025q3']; h=i['h1_2026'];h0=i['h1_2025']; reports={f.name[:2]:f.read_text(encoding='utf8').replace(',','') for f in P.parent.glob('0?-*.md')}
records=[]
def check(n,label,token,actual,unit,places,source):
    assert token in reports[n],(n,label,token)
    v=D(str(actual)); target=D(token.replace('−','-').replace('+','')); assert abs(v-target)<=D('.5')*(D(10)**-places),(label,token,v)
    records.append(dict(article=n,label=label,value=token,unit=unit,unrounded=str(v),proof=source))
check('01','恢复2021名义毛利所需2025口径销量','11.87',a[4]*10**4/b[5],'万吨',2,'2021全年品类毛利额除以2025毛利每吨')
check('01','固定2025吨数所需毛利每吨','10912',a[4]*10000/b[1],'元/吨',0,'2021毛利额除以2025榨菜销量')
for yy,row,quote in [('2021',a,'7465.50'),('2022',m22,'7948.40')]:check('01',yy+'年结转吨成本',quote,row[2]-row[5],'元/吨',2,'同年分品类营业成本／出货吨数，非鲜菜采购价')
check('02','累计募资投入进度','34.13',100*D('9.475026')/D('27.762643'),'%',2,'半年专项募集资金累计已用／调整后一期募集资金计划')
check('02','整体工程进度口径','28.34',100*D('9.9447532346')/D('35.089268'),'%',2,'半年报整体累计实际投入／整体预算')
check('02','永续静态门槛','4000',50000*D('.08'),'万元/年',0,'全部预算起初投入，次年末起无限期、零增长净增现金')
check('03','单季经营现金同比','0.70',100*((D(d['ocf'])-D(h['ocf']))/(D(last['ocf'])-D(h0['ocf']))-1),'%',2,'2026与2025各自9M减H1再做同比')
check('03','历史股息率','3.63',D('.42')/D('11.58')*100,'%',2,'两笔2025所属年度实施公告／11月26日收盘')
check('03','10年门槛反解','8.09',m['reverse_growth_pct'],'%',2,'独立割线求根，固定65%派息、1%永续增长、8%门槛')
check('03','历史估值经验百分位','34.49',D(418)/1212*100,'%',2,'五年日度归母PE_TTM中不高于当日的日数／有效样本数')
delta=(date(2027,12,31)-date(2026,11,26)).days-365;check('03','时点示例实际多天数','35',delta,'日',0,'11/26至次年12/31按实际日期天数减365')
check('03','6%档日历近似缺口','0.08',11.58-.2-m['moderate_rate_PV_IRR_plus20cY1PV_IRR_immediatePV_shortfall'][.06][0]/1.06**(delta/365),'元',2,'整条现金流同时后移35天、0.20元现在取得，非付款安排')
(P/'重点勾稽结果.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(len(records),'targeted checks passed')
