# Systemic Risk — 核心修复版 v2.3

以版本化的 29 家银行研究样本为基础，计算 MES、CoVaR/ΔCoVaR，以及 OLS-beta 累积下行情景下的资本缺口近似。

基线仓库：<https://github.com/u2017310234/systemic-risk>，commit `2d0ee5079a814026a67c6c027205355572dff2a2`。

## 先读这些

- [第四轮：27 家可计算样本补齐、拆股处理和 CoVaR 数值核验](docs/REPAIR_V23.md)

- [第三轮：29 家名单核验、数据预检与剩余缺口](docs/REPAIR_V22.md)

- [第二轮真实数据核账](docs/REAL_DATA_RECONCILIATION.md)
- [新增数据接口与告警](docs/DATA_PIPELINE_V21.md)
- [修复清单、输入格式、运行和方法边界](docs/REPAIR.md)
- [实际验证结果](docs/VALIDATION.md)
- [基本面文件格式示例](inputs/fundamentals.example.json)，纯合成示例，不是银行真实数据

本包是本地修复结果，未改远端仓库或线上部署。没有携带旧版风险数值；旧结果须重新计算。附带 27 家银行的选定披露资料历史重建结果及 29 家适用性检查，并明确标记其范围。缺少真实披露日期、集团市值等输入时，SRISK 返回空值，不能当作零风险。

## 核心变化

- 报价币、报表币和汇率方向明确；失败不冒充美元
- 不再把 BPCE 当成 GLE；多股类或上市子公司与集团口径不符时要求核实数据
- 日期匹配、数据覆盖范围、零值和空值明确
- JSON/CSV 同批计算并校验，原子提交，失败不损坏上一批
- 前端相关性按相同日期区间计算，系统历史百分位与横截面相对分数分开
- MCP SDK 不再被本地同名模块遮蔽，入口为 `gsib-mcp` 或 `risk_mcp.server:app`

## 快速测试

```bash
python -m venv .venv
. .venv/bin/activate
pip install '.[test]'
pytest tests loc/test_branch_locator.py -q
cd frontend
npm ci
npm test
npm run typecheck
```

生产运行及前端构建需要先准备数据，详见修复说明。离线测试不请求市场数据。

## 不应声称的能力

它不是已校准的危机预测模型，名单已核对 2023、2024、2025 三版，按计算日选择当时已发布版；已完成 27 家银行在 2025-05-16 的选定披露资料历史重建，27 家方法可计算、2 家集团不具备直接上市权益输入；未完成全样本、全历史重算。供应商历史股数仍不等于经验证的 point-in-time 数据。部署前应补齐来源、重新计算并与独立基准对照。

## 不下载原始行情的 UI 演示

```bash
python -m src.demo --snapshot examples/verified-disclosures-v23/reconstructed-snapshot.json --output demo-data
cd frontend
DATA_SOURCE_DIR=../demo-data npm run build
```

这是标明日期的单日历史重建，目标目录必须为空。它不提供虚构的历史走势或当前风险判断。
