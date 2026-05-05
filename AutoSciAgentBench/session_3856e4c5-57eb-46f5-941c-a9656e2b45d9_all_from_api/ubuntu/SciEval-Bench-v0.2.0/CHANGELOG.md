# Changelog

## [0.2.0] - 2026-04-28

### Added
- 完整的三级质量控制引擎 (scieval_qc.py)
- 编造检测清单生成与验证
- Code-Aware任务子类型支持
- 人工校验模块与Kappa计算
- LLM辅助+人工校验标注管线 (scieval_annotator.py)
- 多源数据采集工具 (scieval_collector.py)
- 六大学科全覆盖的关键词体系（167个关键词）
- 人文学科和工程学科数据覆盖

### Changed
- 评估维度从六维扩展为九维（新增可复现性、参考文献完整性、结果完整性）
- 评审体系从单层升级为Text-Only + Code-Aware双层

### Fixed
- 去污染验证的LLM截止日期比对逻辑

## [0.1.0] - 2026-04-27

### Added
- 初始原型数据集（13条实例，4学科大类，5任务类型）
- 基础评估器系统 (evaluator_system.py)
- 三种工具横向对比基准 (tool_benchmark.py)
- 统一方案架构设计文档
