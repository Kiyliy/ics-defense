// @ts-check

import OpenAI from 'openai';
import dotenv from 'dotenv';
dotenv.config();

/** @typedef {import('openai/resources/chat/completions').ChatCompletionMessageParam} ChatCompletionMessageParam */

/**
 * @typedef {{
 *   analysis: string
 *   mitre_tactic: string
 *   mitre_technique: string
 *   risk_level: 'low' | 'medium' | 'high' | 'critical' | 'unknown'
 *   confidence: number
 *   recommendation: string
 *   action_type: 'block' | 'isolate' | 'monitor' | 'investigate' | 'manual_review'
 *   rationale: string
 * }} LLMAnalysis
 */

const client = new OpenAI({
  apiKey: process.env.XAI_API_KEY,
  baseURL: process.env.XAI_BASE_URL || 'https://api.x.ai/v1',
});

const MODEL = process.env.XAI_MODEL || 'grok-3-mini-fast';
// 注: XAI_API_KEY 和 XAI_BASE_URL 统一通过 .env 配置

const SYSTEM_PROMPT = `你是一个工控安全分析专家 AI 助手，负责分析安全告警、推断攻击链并生成处置建议。

你的能力：
1. 告警语义分析：理解多源告警的上下文含义
2. 攻击链推断：基于 MITRE ATT&CK for ICS 映射攻击阶段
3. 风险分级：综合告警严重度、资产重要度、漏洞评分进行风险评估
4. 策略建议：生成可执行的处置建议（阻断、隔离、监控、调查）

输出要求：始终返回 JSON 格式，包含以下字段：
- analysis: 分析摘要
- mitre_tactic: MITRE ATT&CK 战术名称
- mitre_technique: MITRE ATT&CK 技术 ID（如 T0800）
- risk_level: low / medium / high / critical
- confidence: 0-1 置信度
- recommendation: 处置建议
- action_type: block / isolate / monitor / investigate
- rationale: 推理依据

禁止输出 Markdown、代码块或额外解释。`;

const ANALYSIS_RESPONSE_SCHEMA = /** @type {const} */ ({
  type: 'json_schema',
  json_schema: {
    name: 'ics_alert_analysis',
    strict: true,
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        analysis: { type: 'string' },
        mitre_tactic: { type: 'string' },
        mitre_technique: { type: 'string' },
        risk_level: { type: 'string', enum: ['low', 'medium', 'high', 'critical', 'unknown'] },
        confidence: { type: 'number' },
        recommendation: { type: 'string' },
        action_type: { type: 'string', enum: ['block', 'isolate', 'monitor', 'investigate', 'manual_review'] },
        rationale: { type: 'string' },
      },
      required: [
        'analysis',
        'mitre_tactic',
        'mitre_technique',
        'risk_level',
        'confidence',
        'recommendation',
        'action_type',
        'rationale',
      ],
    },
  },
});

/**
 * 分析单条或多条告警，返回 LLM 的结构化分析结果
 */
/**
 * @param {unknown[]} alerts
 * @returns {Promise<LLMAnalysis>}
 */
export async function analyzeAlerts(alerts) {
  return createLLMService().analyzeAlerts(alerts);
}

/**
 * @param {ChatCompletionMessageParam[]} messages
 * @returns {Promise<string>}
 */
export async function chat(messages) {
  return createLLMService().chat(messages);
}

/**
 * @param {{ client?: Pick<OpenAI, 'chat'>, model?: string }} [options]
 */
export function createLLMService({ client: injectedClient = client, model = MODEL } = {}) {
  return {
    /** @param {unknown[]} alerts */
    async analyzeAlerts(alerts) {
  const userMessage = `请分析以下安全告警并给出攻击链推断和处置建议：


${JSON.stringify(alerts, null, 2)}`;

      const response = await injectedClient.chat.completions.create({
    model,
    messages: [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'user', content: userMessage },
    ],
    temperature: 0.2,
    response_format: ANALYSIS_RESPONSE_SCHEMA,
  });

      const content = response.choices[0]?.message?.content;
      if (typeof content !== 'string') {
        return {
          analysis: '',
          mitre_tactic: 'Unknown',
          mitre_technique: 'Unknown',
          risk_level: 'unknown',
          confidence: 0,
          recommendation: '',
          action_type: 'manual_review',
          rationale: 'LLM returned empty content',
        };
      }

      try {
        return /** @type {LLMAnalysis} */ (JSON.parse(content));
      } catch {
        return {
          analysis: content,
          mitre_tactic: 'Unknown',
          mitre_technique: 'Unknown',
          risk_level: 'unknown',
          confidence: 0,
          recommendation: '',
          action_type: 'manual_review',
          rationale: 'Failed to parse JSON response',
        };
      }
    },
    /** @param {ChatCompletionMessageParam[]} messages */
    async chat(messages) {
      const response = await injectedClient.chat.completions.create({
        model,
        messages: [
          /** @type {ChatCompletionMessageParam} */ ({ role: 'system', content: SYSTEM_PROMPT }),
          ...messages,
        ],
        temperature: 0.5,
      });
      return response.choices[0]?.message?.content ?? '';
    },
  };
}
