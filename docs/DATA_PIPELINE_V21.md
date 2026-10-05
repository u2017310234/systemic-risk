# v2.1 数据接口与质量告警

历史阶段说明。v2.2 已扩展 SEC 注册实体、修正名单和覆盖显示，当前状态以 [REPAIR_V22.md](REPAIR_V22.md) 为准。

## 1. SEC 自动输入

支持已核实实体 JPM（CIK19617）与 Barclays PLC（CIK312069）。不会把 Barclays Bank PLC 子公司混入母公司。

```bash
python -m src.sec_inputs --bank JPM --as-of 2025-05-16 --output inputs/fundamentals/JPM.json
# 使用已下载的官方 Company Facts，完全离线：
python -m src.sec_inputs --bank BARC --as-of 2025-05-16 --input companyfacts.json --output inputs/fundamentals/BARC.json
```

导入带 accession、原始币种、报表期、filed 日期、来源 URL 和原文件 SHA256。只取实体级即时负债和股数；不把加权平均 EPS 股数当期末股数。不会自动运行定时任务。

仅凭 filed 日期无法知道最早一次新闻稿披露时间，因此这里使用“所选 SEC 文件披露日加一个日历日”的保守日频约定，并明确注明不是最早公开时刻。股数、负债按当时可得的最新报表期选择；同一期更正按实际公布后启用。冲突数据拒绝处理。

ICBC 和 SMFG 本次已人工核对官方报告并制作结构化示例；没有声称任意 PDF 都能自动可靠抽取。日本准则必须区分 J-GAAP 与 IFRS。

## 2. 市值组成

基本面 JSON 可提供 expected_share_classes 与 equity_valuations。每次估值包括日期、各股类组件及 FX 来源。

组件要求：

- share_class_id 与发行人登记一致。ICBC 必須包含 A 和 H；不允许漏掉一类后宣称完整。
- instrument_type=ordinary；不允许把 ADR 再当一类普通股相加。
- price_basis=unadjusted；price_date 必须等于 valuation_date。
- issued_shares 与 treasury_shares，或直接 outstanding_shares，两种方式二选一，禁止重复扣除库存股。
- shares_effective_date、shares_available_date、share_source 明确；未知时点不向历史倒灌。
- split_basis 与 price_split_basis 一致，避免拆股前后数量错配。
- 每种外币需同日、带来源的 USD_PER_UNIT 汇率。GBp/GBX 先乘 0.01 转 GBP。
- 来源晚于估值日发布时，只允许显式 historical_reconstruction 模式；默认拒绝其作为当时已知输入。

最近披露股数与日内实际股数可能不同，结果明确标注估计性质。

## 3. 本地行情输入

MARKET_INPUTS_DIR 指向一个独立目录，内含 manifest.json 和 date,value 两列的 CSV。这是正式输入通道，不是 monkeypatch。已用它实际跑通四家银行。

manifest.series 以 adjusted_close:<标准代码> 或 fx_usd_per_unit:<币种> 为键。每项包含 identifier、kind、path、sha256、source，可附 currency、provider_currency_label、available_date。

- CSV 文件路径不能逃出输入目录；必须通过 SHA256，日期唯一，数值有限且大于零。
- 已指定外部行情源时缺失仍为空，不会偷偷切换证券或换供应商。
- 如供应商币种标签与登记币种冲突，须提供 currency_override.source 和 reason；覆盖仍出现在告警中。
- 严格模式不使用 available_date 之后才发布的数据；历史重建可明确选择 DATASET_KIND=historical_reconstruction。
- 复权序列用于收益，市值的估值日价格必须单独核实。不能对历史复权 close 直接乘股数。

本次 Wind 数据通过用户已连接的行情工具取得。服务端仍需有授权的数据提供方式，或由已有工具生成上述 CSV。源码包不包含 Wind 原始批量行情。

## 4. 质量状态

/health 返回 service_status 与 data_status。quality.alerts 同时出现在快照、独立 quality-report.json 和前端面板：

- NO_SRISK / LOW_COVERAGE / INCOMPLETE_UNIVERSE
- COVERAGE_LOSS
- STALE_SNAPSHOT / FUTURE_DATA_DATE
- OLD_FUNDAMENTALS / UNSPECIFIED_ACCOUNTING
- ACCOUNTING_BASIS_CHANGED / LARGE_INPUT_CHANGE
- INPUT_WARNING，包括显式币种覆盖和未经 vintage 验证的行情

当前阈值是解释性启发规则，不是经过校准的预测阈值。快照 7 天、报表 100 天触发告警；报表硬有效期默认 200 天，且从报告期末起计算。

数据政策版本为 2.1，写入 calibration_id，防止旧的报表选择政策与新结果混接。升级请使用新 DATA_DIR 全量重算，保留原数据回滚。
