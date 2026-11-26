"""Independent, offline arithmetic for the source register. Amounts in CNY unless stated."""
from decimal import Decimal as D
from math import isclose

H=D(10)**8
# year, product revenue/cost in yuan, product and all-food sales (10,000 tonnes).
products=[('2021','2226315299.91','1006349316.96','13.48','15.32'),('2022','2174807004.71','936321727.41','11.78','14.03'),('2023','2075636010.98','938595422.51','11.33','13.45'),('2024','2044418784.36','929197436.92','11.14','13.26'),('2025','2059471664.42','910468972.04','11.18','13.40')]
def products_check():
    out={}
    for yr,rs,cs,qs,alls in products:
        r,c,q,a=map(D,(rs,cs,qs,alls));assert 0<q<a
        out[yr]=(r/H,q,r/q/D(10000),(r-c)/r*100,(r-c)/H,(r-c)/q/D(10000),a)
    assert abs(out['2025'][3]-D('55.79'))<D('.005');return out

# FY forecast inputs are millions, as printed in the individual analyst tables.
def brokers_check():
    f={'国信4月':('2583','831'),'开源4月':('2562','817'),'西南4月':('2549.88','826.18'),'国信11月':('2516','746')}
    nine_rev,nine_ni=map(D,['2067509518.74','613891650.82']); prior_q4_rev=D('2431922780.17')-D('1998577368.74');prior_q4_ni=D('768034038.98')-D('672969983.10')
    new_rev,new_ni=map(D,f['国信11月']);old_rev,old_ni=map(D,f['国信4月']);r=new_rev*10**6-nine_rev;p=new_ni*10**6-nine_ni
    o=dict(revision_revenue_pct=(new_rev/old_rev-1)*100,revision_profit_pct=(new_ni/old_ni-1)*100,implied_q4_revenue_yi=r/H,implied_q4_profit_yi=p/H,implied_q4_revenue_yoy=(r/prior_q4_rev-1)*100,implied_q4_profit_yoy=(p/prior_q4_ni-1)*100)
    assert abs(o['implied_q4_profit_yoy']-D('38.97'))<D('.005');return o

def independent_model():
    # Separate implementation: recurrent cash flows; Newton IRR, not the primary
    # model's bisection. This checks conditional arithmetic, not economic assumptions.
    price=11.58; sh=1153919028; ep=(697935713.13+581904031.35-615117387.91)/sh
    def npv(cf,r):return sum(x/(1+r)**n for n,x in enumerate(cf,1))
    def irr(cf):
        x=.04
        for _ in range(30):x-=(npv(cf,x)-price)/sum(-n*v/(1+x)**(n+1) for n,v in enumerate(cf,1))
        assert abs(npv(cf,x)-price)<1e-8;return x*100
    def flows(horizon,growth,terminal_mult,terminal_growth):
        eps=ep; ds=[]
        for _ in range(horizon):eps*=1+growth;ds.append(eps*.65)
        ds[-1]+=eps*(1+terminal_growth)*terminal_mult;return ds
    paths={}
    for name,g3,p3,g10,g in [('压力',-.03,14,-.02,0),('温和改善',.03,18,.03,.01),('顺利',.07,22,.06,.02)]:
        c3=flows(3,g3,p3,0);k=(1-g/.15)/(.08-g);c10=flows(10,g10,k,g);paths[name]=[npv(c3,.08),irr(c3),npv(c10,.08),irr(c10)]
    # Yield of a November buyer who might receive an extra FY2026 interim payout.
    # Whether entitled and when it arrives are not determined by the forecast.
    s={}
    for r in (.06,.07,.08,.09,.10):
        cf=flows(10,.03,(1-.01/.15)/(r-.01),.01);c=cf.copy();c[0]+=.2
        s[r]=[npv(cf,r),irr(cf),npv(c,r),irr(c),npv(cf,r)+.2,price-npv(cf,r)]
    # Reverse growth via secant iterations.
    def residual(growth):return npv(flows(10,growth,(1-.01/.15)/(.08-.01),.01),.08)-price
    a,b=.06,.10
    for _ in range(20):
        if abs(residual(b))<1e-10:break
        a,b=b,b-residual(b)*(b-a)/(residual(b)-residual(a))
    assert abs(residual(b))<1e-8
    # The asset method is an alternative to, not a supplement to, whole-equity DCF.
    pool=(2900736352.79+3491711152.72-79089.88)/1e8; div=.2*sh/1e8; core=(ep*sh-(90305534.79+54404339.53-66647594.29)*.85)/1e8; bridge={}
    for reserve in (0,2.5,5):
        surplus=pool-24-7-1.5-div-reserve;released=surplus/1.08**3
        bridge[reserve]=[surplus,(16*core+div+released)/(sh/1e8),(price*sh/1e8-div-released)/core]
    assert isclose(bridge[0][1]-bridge[5][1],5/(sh/1e8)/1.08**3,abs_tol=1e-8)
    assert 5.95<s[.06][3]<5.97 and 2.91<s[.08][1]<2.93;assert round(b*100,2)==8.09
    return {'scenarios_PV3_IRR3_PV10_IRR10':paths,'moderate_rate_PV_IRR_plus20cY1PV_IRR_immediatePV_shortfall':s,'asset_surplus_PV16_PEimplied':bridge,'reverse_growth_pct':b*100}

if __name__=='__main__':
    for y,c in products_check().items():print(y,*[str(x.quantize(D('.01'))) for x in c]);
    print({k:str(v.quantize(D('.0001'))) for k,v in brokers_check().items()});print(independent_model())
