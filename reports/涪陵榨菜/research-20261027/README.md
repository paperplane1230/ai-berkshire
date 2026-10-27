# 涪陵榨菜报告计算与检查

对应[研究报告](../涪陵榨菜研究报告-20261027.md)，财务截止2026年9月30日，研究与行情截止2026年10月27日晚。

- inputs.json：人民币元级原始数据、来源口径说明与显式估值假设。
- calculate.py / results.json：使用仓库financial_rigor和Decimal复算；无需联网或额外依赖。
- financial-rigor.txt：市值、关键财务双源、估值和三年情景记录。
- terminal-audit.txt / terminal-flip-*.txt：永续参数与折现率翻转检查。
- audit.py / audit-results.json / audit-verdict.txt：固定种子20261027、15%抽样；197项中随机选30项，排除3个时间/年份误识别，补充12项重点核验，共39项通过。保留完整排除理由。
- test_calculation.py：8项测试，覆盖市值、累计/单季、现金桥、金融资产去重、季节性授信、IRR求根、终值时点、分红跨期。

在仓库根目录，使用已验证可用的Python 3解释器运行以下命令；Windows默认python.exe若是Store别名，请使用既有uv解释器绝对路径，不需要再安装Python。

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python3 'reports/涪陵榨菜/research-20261027/calculate.py'
python3 'reports/涪陵榨菜/research-20261027/audit.py'
python3 -m unittest discover -s 'reports/涪陵榨菜/research-20261027' -p 'test_*.py' -v
```

## 必须保留的估值边界

三年情景派息率65%，十年压力模型70%，均非管理层承诺。合并盈利模型不另加现金；SOTP剔除假设税后存款利息后才加部分超额现金，两者不能叠加。

十年压力模型未单列期末剩余金融资产和累积留存现金，不是完整清算或资产估值。SOTP未独立估值建设中项目的未来增量利润，延迟现金兑现方案也未计等待期利息。这些是偏保守的不同交叉视角，不能把任一数值当唯一内在价值。

终值倍数是前瞻倍数，严格现金流模型使用第十一年利润。仓库terminal_value的近似IRR另使用第十年利润和固定初始股息率，两列有意不混同。6%敏感性档的乐观情景分母不足5个百分点，只供参考；10%超出仓库人民币区间。

现金及多数细项附注只有一个底层公司来源；媒体独立刊发不等于独立财务审计。假设一致性与公式通过不表示未来预测被验证。不得删除这些限制后引用工具的“准出”字样。
