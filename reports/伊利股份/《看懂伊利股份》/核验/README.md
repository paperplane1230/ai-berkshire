# 伊利股份系列：数字从哪里来

财务截止2026年9月30日，市场与公告截止2026年11月24日晚。单位默认为人民币。核验包只包含选用的事实、参数、程序与检查结果，不转载研报全文；它不是一次新的独立审计。

## 一、先按口径选来源

| 要回答的问题 | 来源与核对位置 | 可核实的边界 |
|---|---|---|
| 五年收入、成本、现金和品类 | 伊利[2021](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=8109959)、[2022](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=9144519)、[2023](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=10160415)、[2024](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=11071730)、[2025年报](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12279896)。对照五份原件，品类表物理页分别为19、19、18、19—20、22；有些PDF物理页和印刷页码不同 | 年报各报当年值；现金资本开支只含购建长期资产，不含收购。品类毛利额=收入减成本，不是营业利润。管理层的价量拆解是公司解释，不是独立零售调查。 |
| 累计与单季、澳优减值、渠道 | [半年报](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12547482)、[三季报](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12679906)、[三季经营公告](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12679909)；经营公告分产品、销售模式两表 | 资产、负债是时点；现金流、利润是期间。取合并报表；Q3现金流用同年的前三季减半年。含财务公司利息的营业总收入与营业收入分别呈现。 |
| 经营解释和独立对照 | [半年业绩会](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12576411)、[三季度业绩会](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12689823)、[澳优中报](https://doc.irasia.com/listco/hk/ausnutria/interim/2026/intrepc.pdf)、[澳优11月换帅公告](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1109/2026110900857.pdf)、[农业农村部周度奶价](https://xmsyj.moa.gov.cn/jcyj/202611/t20261118_6489557.htm)、[蒙牛中期说明](https://www.mengniu.com.cn/news/group_news/detail/29126.html) | 分清集团和子公司，以及行业原奶监测、企业采购、消费者成交价。公司披露渠道新鲜度不是观察到了每家门店的库存。 |
| 分红和两种购股 | [中期分红预案](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12679907)、[股东会决议](https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-11-21/600887_20261121_CPPL.pdf)、[注销型回购报告书](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12606948)、[10月底进度](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12687849)、[员工长期服务计划购股](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600887&id=12705082) | 方案通过、确定登记日、支付、注销分开；截至检索时未见中期权益分派实施公告，不作已到账处理。 |
| 盈利与现金预测 | [东吴10月30日](https://pdf.dfcfw.com/pdf/H3_AP202610311831255059_1.pdf)页3、[西南10月31日](https://pdf.dfcfw.com/pdf/H3_AP202611031831368880_1.pdf)页2、[山西11月17日](https://pdf.dfcfw.com/pdf/H3_AP202611171831777655_1.pdf)页3、[中邮11月23日](https://pdf.dfcfw.com/pdf/H3_AP202611231831952527_1.pdf)页3 | 仅四家机构各版本的预测，并非市场总体。隐含Q4=全年预测−已发生的前三季，不是卖方逐季指引。 |
| 行情、主要财务双路径核对 | [腾讯](https://qt.gtimg.cn/q=sh600887)、[新浪](https://hq.sinajs.cn/list=sh600887)、[东方财富三表](https://data.eastmoney.com/bbsj/600887.html)；检索时点、接口及SHA-256见[来源记录](行情财务来源.json) | 两路11月24日价格与报价日期均一致；总股本按注册口径，不扣尚未注销的回购。东方财富与发行人是不同取数渠道，底层是同一会计事实。 |

## 二、离线复算

- [财务与模型输入](财务与模型输入.json)保留元、股等原始单位。模型条目依次为：前三年每股收益增速、第4—10年增速、预测分红率、永续增速、三年退出市盈率。三年定价条件不能移作十年终值。
- [财务双渠道对照](财务双渠道对照.json)有69条近季及近年记录、40条年度复核，全部按原始精度一致，前后有重叠，不代表109个独立事实。营业收入在东财用营业总收入减利息还原。品类和个别附注缺少独立统计，不混入这组计数。
- 运行本目录的 Python 脚本 [估值复算.py](估值复算.py) 可重新生成[估值结果](估值结果.json)、[双源与估值工具日志](严谨性工具输出.txt)和[终值检查](终值口径检查.txt)。仅需标准库和仓库内的 tools；不联网。
- 运行 [test_valuation.py](test_valuation.py) 可用独立的逐年现金流、浮点折现与残差检查交叉验证 Decimal 模型。每期末股息和最终转售价是不同现金流；统一从报价日近似按完整年度间隔折现，不是具体交易日的实际税后结算回报。模型排除2026所属年度全部剩余分配，包括已通过、未查到实施日的中期及金额未定的末期。这两笔现金若买入者符合资格，应按实施日另计，不与退出价和其他股息重算。
- 首个完整预测财年2027假定现有回报规划兑现，股本恒定、不逐笔模拟回购专户；2028起派息取情景假设。十年基准假设人民币门槛8%、稳态新增资本回报14%，不是公司的实测资本成本或实测ROIC。终值使用第十一年利润，分母过窄的敏感性不用于定价。工具中的1.7%仅为历史规则基准，不作为当日国债行情。食品安全尾部事件不量化，亦不人为赋概率。

## 三、正式稿核查结果

四篇已独立交叉阅读，复核了出厂销量与终端消费、每吨金额变动与百分比变动、集团与子公司，以及估值中排除的2026所属年度过渡期股息。见[正文篇幅与文件校验值](篇幅与版本.json)。

四篇数据表中分别识别出33、44、42、48个数值，共167个；以固定种子20261124逐篇抽取15%（向上取整），分别为5、7、7、8项。27项全部通过，无跳过样本；这些检查不覆盖全部叙述性数字。产品表等单源数据按原件复核，模型检查算术，不是预测兑现证明。[抽检样本](正文抽检样本.json)｜[逐项依据](正文抽检依据.json)｜[判决](正文抽检结果.json)。13项独立估值复算测试通过；相对链接与隐私模式检查通过。
