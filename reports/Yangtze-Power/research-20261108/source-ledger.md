# 来源、口径与证据缺口

所有源值为公司披露的人民币元；主文亿元均除以100,000,000。行情是2026-11-06，资料读取2026-11-08。URL与原始内容哈希见source-manifest.json和本地meta。

| 编号 | 公开来源 | 本地位置 | 使用范围 |
|---|---|---|---|
| S1 | [2026Q3公告12684388](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600900&id=12684388) | local/三季报-20261108/yangtze/q3.txt、q3-pdf.pdf、q3-pdf-extracted.txt | 单季／累计收入利润、9月资产负债、9M现金流、母公司现金流、重述说明 |
| S2 | [2026H1公告12574728](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600900&id=12574728) | 同目录h1.txt、h1-pdf.pdf、h1-pdf-extracted.txt | 季度相减、税率、关联资金、短期融资券、建设支出与分红执行 |
| S3 | [2025年报12283277](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600900&id=12283277) | 同目录annual.txt、annual-tavily.md | 三年／分季度表、2025收入构成、电价、分红政策、GDR基础A股 |
| S4 | [发电公告12636814](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600900&id=12636814) | 同目录generation.txt | 六站Q3／9M电量及累计来水，不推断Q3来水 |
| S5 | [关联投资12684386](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600900&id=12684386) | 同目录related-investment.txt | 若羌既有股权作价、33%权益及项目零收入利润 |
| S6 | 东方财富RPT_F10_FINANCE_MAINFINADATA | 同目录eastmoney.json与meta | 2023-2026财务独立数据平台交叉核对，非另一次审计 |
| S7 | 腾讯qt.gtimg.cn及新浪hq.sinajs.cn | 同目录qq.txt、sina.txt与meta | 11月6日收盘29.91、总股本及市值 |
| S8 | [分红规划11301071](http://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600900&id=11301071) | 同目录dividend-policy-tavily.md；2025年报交叉 | 2026-2030现金分配不少于归母利润70%的政策；不作每股保底 |
| S9 | [业绩会通知12684387](https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?stockid=600900&id=12684387) | 同目录ir-meeting-tavily.md | 仅确认11月4日安排，未取得完整答问，不编造语气 |

## 精确关键值与核对

| 项目 | 源值 | 交叉核对或推导 |
|---|---:|---|
| 9M2026收入 | 63,056,214,868.25 | 东方财富TOTALOPERATEREVE同值，误差0% |
| 9M2026归母 | 26,343,828,523.43 | 东方财富PARENTNETPROFIT同值，误差0% |
| 9M2025可比归母 | 28,192,874,494.95 | 东方财富更新后历史期同值 |
| 2025全年归母 | 34,502,809,176.39 | 年报、中报未分配利润注及东方财富同值 |
| 9M2026CFO | 40,343,091,061.95 | 东方财富MGJYXJJE×总股本，舍入误差远低于1% |
| 9M2026capex现金 | 6,028,110,661.49 | Q3 PDF第12页；公开镜像同一公司披露，不算独立二源 |
| 2026H1归母 | 14,755,694,774.53 | 中报／东方财富同值；用于相减Q2、Q3 |
| 2026Q1归母 | 6,761,006,898.48 | 东方财富；本次使用旧文的一季度原件数值位置作线索，未新增下载Q1PDF，Q2作为派生值标识 |
| 期末归母权益 | 228,392,672,302.87 | 东方财富BPS×股本，低于显示精度误差 |
| 股本 | 24,468,217,716 | Q3股本与腾讯同值；不另加GDR |
| 11月6日股价 | 29.91 | 腾讯／新浪同值；日期亦逐项核对 |

季度现金流、单站发电量、债务构成等尚未取得第二家独立原始经营数据来源，主要依赖公司原件；不以公告镜像和PDF凑“两源”。跨源一致性测试不是独立审计财报真实性。

## 阅读与视觉证据

Q3 PDF第1页为主要指标；第7页为短期／到期债务；第9页为成本、费用与投资收益；第12页为资本开支及借还债、分红利息现金流。五项债务中的长期项还结合第8页文本。H1第99页图像确认税收优惠；短融明细、关联资金与抽蓄建设通过全文检索相应附注核对。所有图像仅在local中。

## 需继续承认的缺口

- 没有2026Q3同口径六站平均售电价：集团收入／六站发电量比值不得作为电价。
- 没有Q3现金资本开支的维护／扩张拆分，不能构造看似精确的归母FCFE。
- 没有9月“其他流动负债”的完整短融附注，故债务使用有说明的分类范围；这不是利率、到期日完整清单。
- 没有业绩会完整问答、电话会逐字稿或未公开管理层指引。
- 没有重新抓取完整复权价格史或当前同行财报行情，不沿用旧估值分位与六月同行表。
- 预测期EPS、电价／水文背景、末期PE及超过2030年分红率是研究假设，不是已发生事实，不以抽样PASS替代其风险披露。
