"""Independent formula checks; no network, no user account or position data."""
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
I=json.loads((HERE/'财务与模型输入.json').read_text(encoding='utf8'))
O=json.loads((HERE/'估值结果.json').read_text(encoding='utf8'))
P=float(I['quotes']['qq']['price']); N=int(I['shares_filing']); E=(11565166497.81+8803770151.52-10426102617.04)/N
def cashes(case,rate=.08,starting=E,permanent=False):
    a,b,d,g,pe=map(float,case); eps=starting; c=[]; three=[]
    for t in range(1,11):
        eps*=1+(a if t<=3 else b);c.append(max(d*eps,.75*eps,1.22) if t==1 else d*eps)
        if t==3:three=c.copy();three[-1]+=pe*eps
    c[-1]+=eps*(1+g)*(d if permanent else 1-g/.14)/(rate-g)
    return three,c
def pv(c,r):return sum(f/(1+r)**n for n,f in enumerate(c,1))
class Report(unittest.TestCase):
    def check2(self,x,y):self.assertLess(abs(float(x)-y),.00501)
    def test_snapshot(self):
        s=O['snapshot']; self.assertEqual(I['quotes']['sina']['date'],'2026-11-24');self.assertEqual(P,float(I['quotes']['sina']['price']));self.check2(s['cap_yi'],P*N/1e8);self.check2(s['pe'],P/E);self.check2(s['divyield'],1.38/P*100)
    def test_cross_vendor(self):
        rows=json.loads((HERE/'财务双渠道对照.json').read_text(encoding='utf8'));self.assertEqual(len(rows),109);self.assertTrue(all(float(x['filing_yuan'])==float(x['vendor_yuan']) for x in rows))
    def test_cashflow(self):
        i=I['interims'];cf=lambda name:float(i[name]['ocf'])-float(i[name]['capex']);self.check2(O['snapshot']['ttmFCF'],(14343920490.32-3036644156.68+cf('2026ytd')-cf('2025ytd'))/1e8)
    def test_policy_expiry(self):
        for tag,v in I['cases'].items():
            c,_=cashes(v);self.check2(O['scenarios'][tag]['dps1'],c[0]); self.check2(c[1],E*(1+float(v[0]))**2*float(v[2]))
    def test_prices_and_return(self):
        for name,case in I['cases'].items():
            result=O['scenarios'][name]; short,long=cashes(case)
            for term,cash in [('3',short),('10',long)]:
                self.check2(result['pv'+term],pv(cash,.08)); self.assertLess(abs(pv(cash,float(result['irr'+term])/100)-P),.022)
    def test_sensitivity(self):
        for name,case in I['cases'].items():
            for rate,res in O['sensitivity'][name].items():
                r=float(rate)/100; _,cash=cashes(case,r);self.check2(res['pv'],pv(cash,r)); self.assertEqual(res['meets_r'],pv(cash,r)>=P);self.assertEqual(res['spread_ok'],r-float(case[3])>=.05-1e-10)
    def test_reverse(self):
        a=O['reverse_and_alternatives']; case=I['cases']['经营改善']; c=[float(a['implied_growth_first3'])/100,*case[1:]];self.assertLess(abs(pv(cashes(c)[1],.08)-P),.006);self.assertLess(abs(pv(cashes(case,starting=float(a['implied_normal_profit'])*1e8/N)[1],.08)-P),.003)
    def test_terminal_cash(self):self.check2(O['reverse_and_alternatives']['base_fixed_payout_pv'],pv(cashes(I['cases']['经营改善'],permanent=True)[1],.08))
    def test_coincident_market_multiples(self):
        q=I['quotes']['qq']; s=O['snapshot']; self.check2(q['pe'],P/E);self.check2(q['cap_yi'],P*N/1e8);self.check2(s['deductPE'],P*N/(11068321695.12+8532200099.99-10102781490.65))
    def test_restored_EPS(self):
        x=O['reverse_and_alternatives']; self.check2(x['FY25StartingPV'],pv(cashes(I['cases']['经营改善'],starting=11565166497.81/N)[1],.08))
    def test_price_bridge(self):
        x=O['reverse_and_alternatives'];s=O['scenarios']['经营改善'];self.assertAlmostEqual(float(x['baseAt8DividendPV'])+float(x['baseAt8TerminalPV']),float(s['pv10']),delta=.011);self.assertAlmostEqual(float(x['baseExit3PV'])+float(x['baseDPS3PV']),float(s['pv3']),delta=.011)
    def test_required_exit(self):
        x=O['reverse_and_alternatives'];c,_=cashes([.06,.03,.75,.01,float(x['required_pe3'])]);self.assertLess(abs(pv(c,.08)-P),.009)
    def test_no_guaranteed_loss_bound(self):self.assertLess(float(O['scenarios']['压力']['pv10']),float(O['scenarios']['经营改善']['pv10']));self.assertGreater(P,float(O['scenarios']['顺利修复']['pv10']));self.assertGreater(float(O['scenarios']['顺利修复']['pv3']),P)
if __name__=='__main__':unittest.main(verbosity=2)
