# 验证记录 · v2.3 · 2026-10-04

## 已执行

- 140 项 Python 测试通过。
- 15 项前端测试通过；TypeScript 类型检查通过。
- 使用真实派生输出的 Next.js 生产构建通过。
- Python wheel 2.3.0 构建；安装到独立目录后从源码目录外核对 import、名单和 MCP 服务对象。
- MCP 实际 ASGI tools/list、tools/call 查询回归通过。
- 29 家成员逐项预检：27 家方法可计算、2 家集团缺少直接上市权益；完整风险输入 27 家。
- 16 个 SEC 注册实体批量导入，15 家通过同一报表期、同一 accession 的资产负债平衡检查；1 家缺乏当期标签数据，保留失败而非补造。
- 真实管线遍历 29 家；27 家的 MES、LRMES、CoVaR/ΔCoVaR、SRISK 近似均有值。包含全部 8 家美国 G-SIB。
- 27 家分别用 252 对收益观测、独立中心化乘积计算 beta，再核对 LRMES、SRISK；最大 SRISK 计算差为 0.000000572 USD 十亿以内，来自输出小数位舍入。
- 27 家分位数回归通过独立二点顶点枚举验证，pinball loss 最大差小于 0.000000369；失败 IRLS 的同目标 LP 后备通过原始/对偶与约束残差检查。
- 输出 JSON/CSV 同批校验通过。完整体系 SRISK 保持 null，缺失没有计为零。
- 精确基线补丁可应用性及逐文件字节对照结果见随包 verification/。

真实来源、边界与缺口：REPAIR_V23.md。机器可读结果：examples/verified-disclosures-v23/。前三轮记录保留作为历史核账，不代表新增覆盖。

## 边界

计算日 2025-05-16；选定披露资料与最近公开股数并非每天精确股本。Fed 参考汇率于 5 月 19 日发布，因此输出标记 historical_reconstruction，不是无前视回测或当前排名。已公布的会计准则差异、旧财报、旧股数和单位覆盖均有提示。

没有完整 29 家全历史重算、危机预测校准、真实浏览器视觉验收或线上部署。原始 Wind 批量行情不在公开源码包中；生产运行仍需合法行情输入。数据读取工具的成功响应不自动等于证券身份正确，错误候选已隔离。

两条上游警告仍存在：MCP/Pydantic lifespan 类型提示、Starlette/httpx TestClient 弃用提示；实际请求回归通过。

## 验证环境

Python3.12 / Node24.19.0；numpy2.3.5、pandas2.2.3、statsmodels0.15.0、yfinance1.7.0、mcp1.29.0、fastapi0.141.1、pytest9.1.1、pyarrow25.0.1、httpx0.28.1；Next15.5.15。
