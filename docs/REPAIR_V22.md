# v2.2：全名单核验、批量财报输入和前端覆盖修复

历史阶段记录。此处 13 家覆盖及 14 家缺口已在 [v2.3](REPAIR_V23.md) 中更新，当前以 v2.3 为准。

日期：2026-10-04。基线仍为 `u2017310234/systemic-risk@2d0ee5079a814026a67c6c027205355572dff2a2`。

## 本轮结论

完成了 29 家逐项检查与输入工具修复；**没有完成 29 家风险值全覆盖**。目前 23 家有本次选取、在 2025-05-16 前已披露且符合 200 天阈值的负债证据，13 家的完整输入真实跑通 SRISK 近似，另有 2 家只有收益类指标。每家的缺口在 `examples/verified-disclosures-v22/v22-readiness-final.json`；该报告检查输入齐备程度，不证明危机预测有效性。

这仍是 2025-05-16 的历史重建。不是当前排名，不是 point-in-time 回测。Fed 当日参考汇率在 5 月 19 日才发布，运行明确选择 `historical_reconstruction`。

## 1. 原名单不只是过期，而是成员有误

原来写着 29 家，但放进 BBVA、UniCredit，漏掉 Royal Bank of Canada、Toronto-Dominion。已按 FSB 正式名单核对并纠正：

- [2023 名单](https://www.fsb.org/uploads/P271123.pdf)
- [2024 名单](https://www.fsb.org/uploads/P261124.pdf)
- [2025 名单](https://www.fsb.org/uploads/P271125.pdf)

2023—2025 三版成员相同，监管资本档位有变化。最新发布版为 2025，下一版预计 2026 年 11 月。保存名单年份、发布日期、保守启用日期与来源；2025-05-16 自动引用当时已经公布的 2024 名单，不使用晚于计算日的发布版。名单覆盖早于 2023-11-28 的研究日期会拒绝，不能假装有经过核实的历史成员库。早年的价格可作滚动窗口预热，但不输出那个时期的固定名单风险快照。

FSB 资本缓冲档位与本项目 SRISK 公式中的 k 是两种概念，不能把一个自动代入另一个。

## 2. 29 家中有 2 家不能直接使用本方法

- BPCE 无独立上市集团普通股价格，继续禁止用法国兴业银行替代。
- Groupe Crédit Agricole 与上市 Crédit Agricole S.A. 不是同一合并范围。即使补齐集团市值，也不能直接把上市子公司的股价收益当作整个集团的权益收益。本版不做这种近似替代。

两家保留在 29 家的总名单分母中，并分别显示原因。27 家“方法上可计算”全部齐备也不等于整个 29 家体系覆盖。总体系值继续留空；已覆盖部分显示独立小计。

## 3. SEC 接口扩到 16 个核实 CIK

支持 JPM、BAC、C、WFC、GS、MS、BK、STT、BARC、RBC、TD、HSBC、ING、SAN、UBS、DBK。增加 40-F/修订表单支持；CIK 不对直接拒绝。

离线批量导入：

```bash
python -m src.import_sec_batch \
  --input-dir /path/to/official-companyfacts \
  --output-dir inputs/fundamentals \
  --as-of 2025-05-16 \
  --report sec-import-report.json
```

输入文件命名为 `JPM-companyfacts.json` 等，来源是 `https://data.sec.gov/api/xbrl/companyfacts/CIKxxxxxxxxxx.json`。单家可继续使用 `gsib-sec-inputs` 命令下载官方数据。尊重 SEC 访问规则。批处理本身不联网；失败保留原银行文件，报告失败原因，退出码 2。

真实批处理核对了 16 家，15 家通过同一期、同一 accession 的资产负债平衡检查。DBK 的该标签在此次选取资料中缺少足够新的负债数据，拒绝写入；没有用资产减某个可能口径不同的权益来冒充负债。

修复了实际遇到的细节：

- UBS 的 DEI 股数为含库存股的发行股数，改用明确的流通在外股数标签。2024 年末发行 3,462,087,722 股，库存 287,262,471 股，流通在外 3,174,825,251 股。[官方股本表](https://www.sec.gov/Archives/edgar/data/1610520/000161052025000023/R8.htm)
- 美国银行 Company Facts 的 entityName 异常显示 BofA Finance LLC，额外核对 SEC submissions 的 CIK 70858 是 BANK OF AMERICA CORP /DE/；没有仅凭显示名称切换实体。
- JPM 某期没有含少数股东的权益标签，回退必须按单期、单份文件选择，不能因为其他年度存在该标签而遗漏本期权益。
- BNY 的 94 百万美元临时权益单列在负债与永久权益之间；有明确标签才加入平衡校验，不能把差额强行塞进负债。
- RBC 一条 2020 年旧股数为零，记录到 rejected_facts，避免污染当前有效股数读取。

这些防护不等于通用、免审核的财报语义解析器。发行人改变标签、范围或会计政策仍需复核。

## 4. 真实输入扩展与行情隔离

13 家完整历史重建：JPM、BAC、C、WFC、GS、MS、BK、STT、BARC、HSBC、ICBC、MUFG、SMFG。每家独立使用 252 对同区间收益验证 beta、LRMES 近似和 SRISK 公式；输出 JSON/CSV 一致。

还核对了 ABC、BOC、BOCOM、STAN、GLE 等官方报表，保留原始会计准则标签：IFRS、US-GAAP、J-GAAP、PRC-GAAP 不混写成一个准则。跨准则、衍生品净额抵销差异会影响比较，新增 MIXED_ACCOUNTING_BASES 告警。MUFG 原表逐项按百万元取整，平衡差额 1 百万日元予以明示。

Wind 查询存在真实的超时、空结果和代码识别问题。部分无 count 查询成功补齐了美国银行；没有把所有错误都当作缺失报价。两条可疑返回被隔离：

- 请求 UBSG.SW 得到美元计价、纽约时区的 91.790，与目标瑞士普通股不符；未用于收益、市值或排名。
- 请求 SPTSX.GI 得到约 224.44、人民币成交额的序列，不能当作加拿大 TSX Composite；未用于计算。

加拿大股票返回到 5 月 15 日，且正确加拿大指数尚未核实齐备；不擅自把 15 日标成 16 日。HSBC 的返回单位标签写美元，但 LSE 普通股以 GBX 报价，使用有来源的显式覆盖，并保留告警。[HSBC LSE 页面](https://www.londonstockexchange.com/stock/HSBA/hsbc-holdings-plc/company-page?lang=en)

指定 MARKET_INPUTS_DIR 后，缺少市值不会偷偷请求 Yahoo。被标记 quarantined 的输入直接拒绝。超过 100 天的股数新增 OLD_SHARE_COUNT 提示。类股市值保留股本日期、来源、分量和估计性质。

## 5. 离线全名单预检

```bash
DATASET_KIND=historical_reconstruction \
MARKET_INPUTS_DIR=/path/to/market \
FUNDAMENTALS_DIR=/path/to/fundamentals \
gsib-readiness --as-of 2025-05-16 --output readiness.json \
  --require-eligible-complete
```

对每一家检查身份、报价与指数同日交集、滚动窗口、当日股价、负债披露日期、股类市值和汇率。缺数会写报告后返回非零，不能将“服务正在运行”当作“数据已就绪”。

## 6. 前端修复

- 添加加拿大区域、中文/英文名称、颜色和图布局坐标。
- 清理“bank_count ≥ 28 才显示日期”的硬编码。观察到 29 行不代表 29 家有可用风险值；27 家齐备也不能被错误地全部隐藏。
- 默认显示不完整日期并展示真实 SRISK 覆盖数；筛选完整可计算样本时使用 eligible_complete。
- 保留历史重建、数据质量和完整体系缺失提示。

## 尚未完成的事项与原因

1. 14 家方法可计算银行还缺完整同日行情、股类、披露或指数输入；逐项见预检 JSON。缺少当期负债的具体四家为 CCB、BNP、DBK、MFG。本轮没有把手头资料不齐说成银行未披露。
2. BPCE、Groupe Crédit Agricole 需要另行设计并验证集团权益代理方法；不能靠替换 ticker 解决。
3. 没有完整 29 家全历史、无前视重算，也没有完成危机预测能力校准。
4. 没有新增生产环境行情授权、凭据、自动更新服务或线上部署。现有聊天行情连接不是服务器的数据授权配置。

源码包包含选定官方事实、来源、预检报告和派生验证结果；不分发完整 Wind 行情库或银行报告全文。运行测试无需这些私有行情文件；复现真实历史运行需自备可合法使用的行情输入。
