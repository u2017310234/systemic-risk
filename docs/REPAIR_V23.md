# v2.3：27 家可计算样本补齐与数值核验

2026-10-04。本轮接续 v2.2，解决该轮未齐备的 14 家输入。计算日期仍为 **2025-05-16**，输出模式仍为 **historical_reconstruction**。

## 已完成的结果

- 29 家正式名单：27 家可用上市集团权益方法计算，ACA/BPCE 两家不适用，原因及总名单分母保留。
- 27/27 家输入预检通过；27 家都有 MES、LRMES 近似、CoVaR、ΔCoVaR 和 SRISK 近似结果。
- JSON/CSV 一致性通过。27 家独立计算 beta 与 SRISK，最大输出舍入差小于 0.000000572 USD 十亿。
- 27 家分位数回归另用独立的二点顶点枚举核对 pinball loss，最大目标函数差小于 0.000000369。
- 27 家已覆盖小计为 2746.9793 USD 十亿；**完整 29 家体系总量仍为 null**。小计不是今天的排名，也不是已校准的危机预测。

机器可读证据在 `examples/verified-disclosures-v23/`：逐家选定事实、股类估值、行情身份控制、快照、输入预检、独立公式与分位数目标核验。

## 1. 行情恢复后，核实证券身份

在前次限流后重新检查 Yahoo 官方公开接口，接口恢复；遇到 403/429 的读取仍立即停止，不绕过限制。取得的数据分别核对 symbol、instrumentType、currency、exchangeName 和交易所当地日期。

- 加拿大：RY.TO、TD.TO，CAD，Toronto；指数 ^GSPTSE。
- 欧洲：各银行原上市普通股及 ^STOXX50E；瑞银为 UBSG.SW、CHF、EBS。
- 中国：H 股收益序列；A 股及 H 股分别估值，不能拿一种价格乘总股数。
- BNY 的 Yahoo BK 查询返回 404，保留前一轮已经核实的 Wind BK.N 输入，明确是多来源历史重建，不做静默证券替换。

v2.2 两条可疑 Wind 返回仍保留隔离记录。新的、身份相符的 Yahoo 来源替代其用途，不把原错误数据重新放行。

`src/yahoo_inputs.py` 是离线解析器，也可从命令行使用：

```bash
python -m src.yahoo_inputs --input chart.json --symbol 8316.T \
  --currency JPY --exchange JPX --as-of 2025-05-16 \
  --retrieved-on 2026-10-04 --complete-split-window --output normalized.json
```

只有确实请求了截至取得日期的完整拆股事件窗口，才能指定 complete-split-window；否则只输出收益价格，不输出可乘股数的估值价格。解析器不下载资料、不猜代码、不读当前总市值填历史。

## 2. 未来拆股会改变今天下载的历史 Close

SMFG 在 2026 年发生 1 拆 2；Yahoo 的历史 Close 已反映这次后来的拆股。2025-05-16 的提供方 split-adjusted close 为 1730.5，恢复到当时股数单位后为 **3461**，与前一轮 Wind 的当日基准价一致。

- 收益使用 adjusted close，保持收益序列的一致口径。
- 市值使用 Close，按照估值日之后的拆股事件恢复当时单位，不用分红调整价格。
- 不重复乘估值日之前的拆股因子。
- 原始 Close、恢复倍数和事件保存在 market_cap_evidence；输出 LATER_SPLIT_RESTORED 提示。

发行人核实：[SMFG 2026 拆股公告](https://www.smbc.co.jp/news_e/pdf/e20260513_03.pdf)。法定生效日为 2026-10-01，行情中的交易除权记录日期与法定日期不同，不能混称。这里的估值日在两者之前，恢复因子均为 2。这仍不证明拥有完整 point-in-time 行情快照。

## 3. 补齐四家负债与各类股本

- CCB：改从 HKEX 获取官方 IFRS 一季报，避免官网 502；A 股 9,593,657,606，H 股 240,417,319,880。股份变动表里的部分“Others”也是发起人持有的 H 股，不能漏算。
- BNP：2024 官方注册文件，集团资产、负债、权益核平；发行股数减集团持有的自身股份。
- DBK：直接核对 2025-04-29 SEC 6-K 附件，未拿后来重列的比较数字回填。2025Q1 负债为 EUR 1,337,306 百万。股本计算排除尚未发行的 vested share awards。
- MFG：发行人 FY2024 日本准则报表，报告期末 2025-03-31；发行股数减库存股。未用之后发布的 US-GAAP 年报替换。
- ABC、BOC、BOCOM：分别核对官方年报 A/H 股数和一季报负债。后来的增发不提前套入 5 月估值。

主要新来源：

- [CCB 2025Q1](https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0429/2025042901137.pdf)
- [CCB 2024](https://www.hkexnews.hk/listedco/listconews/sehk/2025/0328/2025032800700.pdf)
- [ABC 2024](https://www.abchina.com.cn/cn/AboutABC/investor_relations/announcements/h-announcement/202503/P020250328727621058319.pdf)
- [BOC 2024](https://www.boc.cn/investor/ir3/202503/P020250326687482371928.pdf)
- [BOCOM 2024](https://www.hkexnews.hk/listedco/listconews/sehk/2025/0321/2025032101699_c.pdf)
- [BNP 2024 报表](https://reports.invest.bnpparibas/esef/2024/bnpp-2024-12-31-en.html) / [2025-03-20 发布证明](https://invest.bnpparibas/en/document/release-of-the-english-version-of-the-universal-registration-document-and-annual-financial-report-2024)
- [DBK 2025Q1 原始附件](https://www.sec.gov/Archives/edgar/data/1159508/000115950825000028/db20250429991.htm)
- [MFG 官方金融资料入口](https://www.mizuhogroup.com/investors/financial-information?tab=financial-statements) / [FY2024 原表](https://cdn.prod.website-files.com/67cb23eaf0c6c4d4080e059a/685028cbfb401efcae3bdea2_data24_fy.pdf)

注意股数口径仍是选定公开资料的估计。GLE 使用发行人期末 NAPS 分母，非 EPS 加权平均股数；该口径包括集团交易持股，已明确写入 SHARE_BASIS_VARIANT，不能声称股本口径完全统一。DBK、STAN 等原表有股数取整，保留精度提示。年报股数较旧时仍提示 OLD_SHARE_COUNT。

## 4. CoVaR 真正解决收敛问题

完整运行最初出现 1 家 CoVaR 缺失，原 IRLS 在 1000 次迭代内没有收敛。本版增加同一分位数损失函数的线性规划求解后备：

- 非负正、负残差，截距与斜率不设符号限制。
- 标准化改善数值条件后还原原单位。
- 只有求解成功、约束残差合格、直接 pinball loss 与原始/对偶目标一致时接受。
- 两种求解都失败时仍为空，不填零，也不换成普通最小二乘。

参考 [SciPy HiGHS 文档](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs.html)。27 家最终 CoVaR 全部有值；独立顶点枚举核对记录一并提供。数据政策版本升到 2.3，禁止与先前批次混接。

## 5. 附带可启动的单日演示

无需下载原始行情即可把已核验快照装入一个新的空目录：

```bash
python -m src.demo \
  --snapshot examples/verified-disclosures-v23/reconstructed-snapshot.json \
  --output demo-data
cd frontend
DATA_SOURCE_DIR=../demo-data npm run build
```

只生成真实的一天及 27 家对应 CSV，不捏造历史趋势；非空目标拒绝覆盖。演示始终标记历史重建。要重新计算、回测或日更，仍需合法的行情、财报和及时更新的股本输入。

## 本轮未声称完成的事项

- ACA/BPCE 不具备本方法要求的直接上市集团权益，仍不适用。
- 未统一 IFRS、US-GAAP、J-GAAP、PRC-GAAP 的抵销和资产负债计量差异。
- 股数并非每天精确值；部分选定负债仍来自当时已公开年报，不声称搜集了所有最新季度披露。
- Fed 2025-05-16 汇率于 5 月 19 日发布，故仍不是无前视回测。
- 没有全历史回算、危机预测校准、真实浏览器视觉验收、GitHub 上传或线上部署。
