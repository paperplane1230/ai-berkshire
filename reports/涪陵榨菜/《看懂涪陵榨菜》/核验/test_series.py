"""Independent checks of the figures, not a validation of future cash flows."""
import json,unittest
from pathlib import Path
from 事实反算 import independent_model, products_check, brokers_check
P=Path(__file__).resolve().parent
def read(name):return json.loads((P/name).read_text(encoding='utf8'))
class Series(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i=read('输入.json'); cls.model=read('复算输出.json'); cls.actual=independent_model()
    def near(self,a,b):self.assertLess(abs(float(a)-float(b)),.00501)
    def test_quotes(self):
        q=self.i['market'];self.assertEqual(float(q['price_sina']),float(q['price_qq'])); self.assertEqual(q['time_qq'][:8],'20261126'); self.assertEqual(q['time_sina'][:10],'2026-11-26')
    def test_filing_reconciles(self):
        rows=read('财务对照.json')['items'];self.assertEqual(len(rows),65);self.assertTrue(all(float(a)==float(b) for _,_,a,b,_ in rows))
    def test_products(self):
        for year,v in products_check().items():
            a=next(x for x in self.i['history_product'] if x['year']==year);self.near(a['implied_per_tonne'],v[2]);self.near(a['gross_profit_per_tonne'],v[5]);self.near(a['margin_product'],v[3])
    def test_brokers(self):self.near(brokers_check()['implied_q4_profit_yoy'],38.97)
    def test_market_cap(self):self.near(self.model['snapshot']['cap'],11.58*1153919028/1e8)
    def test_history(self):
        x=read('估值历史与横比.json');self.assertEqual(x['count'],1212);self.near(self.model['snapshot']['hist_pct'],x['le_current']*100/x['count']);self.near(self.model['snapshot']['PE'],x['sample_rows'][-1]['PE_TTM'])
    def test_at_disclosure(self):
        x=read('估值历史与横比.json')['sample_rows'];i=self.i
        for rec,y,z in zip(x,('h1_2026','ytd_2026q3'),('h1_2025','ytd_2025q3')):
            ni=float(i['annual']['2025']['profit'])+float(i[y]['profit'])-float(i[z]['profit']);self.assertLess(abs(float(rec['TOTAL_MARKET_CAP'])/ni-float(rec['PE_TTM'])),1e-6)
    def test_simple_fcf(self):
        i=self.i; tot=lambda k:float(i['annual']['2025'][k])+float(i['ytd_2026q3'][k])-float(i['ytd_2025q3'][k]);self.near(self.model['snapshot']['fcf'],(tot('ocf')-tot('capex'))/1e8)
    def test_models(self):
        for case,actual in self.actual['scenarios_PV3_IRR3_PV10_IRR10'].items():
            for col,num in zip(('pv3','irr3','pv10','irr10'),actual):self.near(self.model['cases'][case][col],num)
    def test_rate_sensitivity(self):
        for rate,(pv,irr,withpv,withirr,_,_) in self.actual['moderate_rate_PV_IRR_plus20cY1PV_IRR_immediatePV_shortfall'].items():
            row=self.model['sensitivity']['温和改善'][f'{rate:.2f}'];self.near(row['pv'],pv); self.near(row['irr'],irr);self.near(row['with_interim_irr'],withirr);self.near(row['with_interim_pv'],withpv)
    def test_asset_exclusion(self):
        for row in self.model['asset_bridge']:
            a,m,p=self.actual['asset_surplus_PV16_PEimplied'][float(row['phase2'])];self.near(row['rest'],a);self.near(row['price16'],m);self.near(row['implied_pe'],p)
    def test_terminal_timing(self):
        x=self.model['cases']['温和改善'];self.near(x['exit10'],(664722356.57/1153919028)*1.03**10*1.01*(1-.01/.15)/(.08-.01));self.assertAlmostEqual(float(x['pv10']),float(x['divPV10'])+float(x['termPV10']),delta=.011)
    def test_reverse(self):self.near(self.model['additional']['rev_g'],self.actual['reverse_growth_pct'])
    def test_annuity(self):
        af=sum(1/(1.08**j) for j in range(1,16));self.near(self.model['additional']['annuity15_wan'],50000/af);self.near(self.model['additional']['delay2_wan'],50000/af*1.08**2)
    def test_expired_right(self):
        self.near(self.model['snapshot']['hist_yield'],(.20+.22)/11.58*100);self.assertTrue(float(self.model['sensitivity']['温和改善']['0.06']['with_interim_pv'])<11.58)
if __name__=='__main__':unittest.main(verbosity=2)
