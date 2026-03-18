const HOT_TOPIC_TEMPLATES = [
  '截至 {dateLabel}，请围绕{topic}写一份深度研判：背景演化、核心矛盾、利益相关方、未来 6 个月情景推演。',
  '基于{topic}，做一份“政策—产业—资本市场”三层联动分析，并给出可执行的跟踪清单。',
  '请对{topic}进行正反双方论证：各列 5 条最强论据，最后给出你的中立裁决与依据。',
  '围绕{topic}输出一份可直接用于汇报的结构化简报：关键数据、时间线、风险矩阵、结论建议。',
  '从全球竞争视角分析{topic}：中国、美国、欧盟的策略差异与潜在连锁反应。',
  '请把{topic}拆成“短期信号、中期趋势、长期拐点”三层，并给出每层可量化指标。',
  '围绕{topic}做一次事实核查：争议观点、证据强弱、可信来源、可证伪点。',
  '针对{topic}给出 10 个值得持续追踪的问题，并说明每个问题的决策价值。',
] as const

const HOT_TOPIC_POOL = [
  'AI 智能体与多模态应用落地',
  'AIGC 视频生成与短剧工业化',
  '开源大模型与闭源模型竞争',
  '先进制程芯片与算力基础设施',
  '机器人与具身智能',
  '自动驾驶商业化进展',
  '跨境电商与全球供应链重构',
  '新能源车价格战与盈利能力',
  '储能与新型电力系统调度',
  '低空经济与无人机应用',
  '数字医疗与 AI 辅助诊疗',
  '银发经济与医疗健康消费',
  '消费复苏与即时零售',
  '文旅新消费与城市营销',
  '体育赛事经济与品牌投放',
  '网络安全与数据合规',
  'Web3 合规化与现实场景应用',
  '云计算成本优化与 FinOps',
  '开发者生态与开源治理',
  '教育科技与个性化学习',
  '地缘冲突对大宗商品与航运价格影响',
  '全球利率周期与人民币资产定价',
  '平台经济监管与中小商家生态',
  '能源转型中的光伏与储能出海',
  '生成式 AI 对就业结构的再分配',
] as const

function hashString(input: string): number {
  let hash = 0
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0
  }
  return hash
}

function sanitizeQuestion(text: string): string {
  return text.replace(/[「」]/g, '').replace(/\s+/g, ' ').trim()
}

export function getSuggestedQuestions(count = 4): string[] {
  const now = new Date()
  const dateLabel = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}-${String(now.getUTCDate()).padStart(2, '0')}`
  const seedKey = `${now.getUTCFullYear()}-${now.getUTCMonth() + 1}-${now.getUTCDate()}-${now.getUTCHours()}`
  let seed = hashString(seedKey)
  const topics = [...HOT_TOPIC_POOL]
  const templates = [...HOT_TOPIC_TEMPLATES]
  const result: string[] = []
  const target = Math.max(1, Math.min(count, 8))

  while (result.length < target && topics.length > 0) {
    seed = (seed * 1664525 + 1013904223) >>> 0
    const topicIndex = seed % topics.length
    const topic = topics.splice(topicIndex, 1)[0]
    seed = (seed * 1664525 + 1013904223) >>> 0
    const template = templates[seed % templates.length]
    result.push(sanitizeQuestion(template.replace('{topic}', topic).replace('{dateLabel}', dateLabel)))
  }

  return result
}
