/**
 * 将 SSE 事件列表转换为时间线展示项与计划步骤
 * 与 chat 流式 / 任务详情接口的响应格式一致
 *
 * 后端事件格式为 { event: "message"|"title"|..., data: {...} }，
 * 前端统一使用 { type, data }，需先归一化。
 */

import type {
  SSEEventData,
  SSEEventType,
  ChatMessage,
  PlanStep,
  PlanEvent,
  StepEvent,
  ToolEvent,
  SessionFile,
} from "@/lib/api/types";

/** 后端返回的原始事件（可能用 event 或 type 表示类型） */
type RawEvent = { event?: string; type?: string; data?: unknown };

/**
 * 将后端单条事件转为前端 SSEEventData（统一 type + data）
 */
export function normalizeEvent(raw: RawEvent): SSEEventData | null {
  const type = (raw.type ?? raw.event) as SSEEventType | undefined;
  const data = raw.data;
  if (!type || data === undefined) return null;
  return { type, data } as SSEEventData;
}

/**
 * 将后端事件列表转为前端 SSEEventData[]
 */
export function normalizeEvents(rawList: unknown): SSEEventData[] {
  if (!Array.isArray(rawList)) return [];
  const out: SSEEventData[] = [];
  for (const raw of rawList) {
    const normalized = normalizeEvent(raw as RawEvent);
    if (normalized) out.push(normalized);
  }
  return out;
}

/** 时间线单项：用于渲染对话区的一条记录 */
export type TimelineItem =
  | { kind: "user"; id: string; data: ChatMessage }
  | { kind: "attachments"; id: string; role: "user" | "assistant"; files: AttachmentFile[] }
  | { kind: "assistant"; id: string; data: ChatMessage }
  | { kind: "tool"; id: string; data: ToolEvent; timeLabel?: string }
  | { kind: "step"; id: string; data: StepEvent; tools: ToolEvent[] }
  | { kind: "error"; id: string; error: string; timestamp?: number };

/** 附件展示用（文件名、类型、大小等） */
export type AttachmentFile = {
  id: string;
  filename: string;
  extension: string;
  size: number;
  sizeLabel?: string;
};

function inferExtension(filename: string, extension?: string): string {
  const normalized = (extension || "").trim();
  if (normalized) return normalized;
  const ext = (filename || "").split(".").pop() || "";
  return ext;
}

/** 从 SessionFile 转为 AttachmentFile */
export function sessionFileToAttachment(f: SessionFile): AttachmentFile {
  return {
    id: f.id,
    filename: f.filename,
    extension: inferExtension(f.filename, f.extension),
    size: f.size,
  };
}

/** 从 ChatMessage.attachments 项转为 AttachmentFile（无 size 时用 0） */
export function chatAttachmentToDisplay(
  a: { file_id?: string; id?: string; filename: string; size?: number; [key: string]: unknown }
): AttachmentFile {
  const ext = (a.filename || "").split(".").pop() || "";
  return {
    id: a.file_id || a.id || "",
    filename: a.filename || "",
    extension: inferExtension(a.filename || "", ext),
    size: typeof a.size === "number" ? a.size : 0,
  };
}

function stableId(prefix: string, index: number, suffix: string): string {
  return `${prefix}-${index}-${suffix}`;
}

/** 将时间戳格式化为相对时间，如 2天前、刚刚 */
function formatTimeLabel(ts: number | string | undefined): string | undefined {
  if (ts === undefined || ts === null) return undefined;
  let t = typeof ts === "string" ? parseInt(ts, 10) : ts;
  if (Number.isNaN(t)) return undefined;
  
  // 后端返回的是秒级时间戳（10位数），需要转为毫秒级（13位数）
  if (t < 10000000000) {
    t = t * 1000;
  }
  
  const now = Date.now();
  const diff = now - t;
  if (diff < 0) return "刚刚";
  if (diff < 60 * 1000) return "刚刚";
  if (diff < 60 * 60 * 1000) return `${Math.floor(diff / (60 * 1000))}分钟前`;
  if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / (60 * 60 * 1000))}小时前`;
  if (diff < 2 * 24 * 60 * 60 * 1000) return "昨天";
  if (diff < 7 * 24 * 60 * 60 * 1000) return `${Math.floor(diff / (24 * 60 * 60 * 1000))}天前`;
  if (diff < 30 * 24 * 60 * 60 * 1000) return `${Math.floor(diff / (7 * 24 * 60 * 60 * 1000))}周前`;
  return undefined;
}

export function getToolTimeLabel(tool: ToolEvent): string | undefined {
  const ts = (tool as { timestamp?: number; created_at?: number; ts?: number }).timestamp
    ?? (tool as { created_at?: number }).created_at
    ?? (tool as { ts?: number }).ts;
  return formatTimeLabel(ts);
}

/**
 * 将 SSE 事件列表归并为时间线展示项（顺序与设计一致）
 */
export function eventsToTimeline(events: SSEEventData[]): TimelineItem[] {
  const list: TimelineItem[] = [];
  let lastStepId: string | null = null;
  let messageIndex = 0;
  let toolIndex = 0;
  let stepIndex = 0;
  let errorIndex = 0;

  for (const ev of events) {
    switch (ev.type) {
      case "message": {
        const msg = ev.data as ChatMessage;
        if (msg.role === "user") {
          // 用户消息标志着新的对话轮次，清除 step 上下文
          lastStepId = null;
          
          list.push({
            kind: "user",
            id: stableId("user", messageIndex++, String(list.length)),
            data: msg,
          });
          if (msg.attachments && msg.attachments.length > 0) {
            list.push({
              kind: "attachments",
              id: stableId("att", messageIndex, "user"),
              role: "user",
              files: msg.attachments.map(chatAttachmentToDisplay),
            });
          }
        } else if (msg.role === "assistant") {
          // 所有 assistant 消息都直接添加，不去重
          list.push({
            kind: "assistant",
            id: stableId("assistant", messageIndex++, String(list.length)),
            data: msg,
          });
          if (msg.attachments && msg.attachments.length > 0) {
            list.push({
              kind: "attachments",
              id: stableId("att", messageIndex, "assistant"),
              role: "assistant",
              files: msg.attachments.map(chatAttachmentToDisplay),
            });
          }
        }
        break;
      }
      case "step": {
        const step = ev.data as StepEvent;
        
        // 判断是更新现有 step 还是创建新 step
        // 关键：只有当 lastStepId === step.id 时才是同一个 step 的状态更新
        if (lastStepId !== null && lastStepId === step.id) {
          // 这是同一个 step 的状态更新（running -> completed）
          // 从后往前查找，确保找到最新的（最后一个）匹配的 step
          let existingIdx = -1;
          for (let i = list.length - 1; i >= 0; i--) {
            const item = list[i];
            if (item.kind === "step" && item.data.id === step.id) {
              existingIdx = i;
              break;
            }
          }
          
          if (existingIdx >= 0) {
            const existing = list[existingIdx];
            if (existing.kind === "step") {
              list[existingIdx] = { 
                kind: "step", 
                id: existing.id, 
                data: step, 
                tools: existing.tools // 保留已有的 tools
              };
            }
          }
        } else {
          // 新的 step (第一次出现或新对话轮次的 step)
          list.push({
            kind: "step",
            id: stableId("step", stepIndex++, step.id + "_" + String(list.length)),
            data: step,
            tools: [], // 初始为空，tools 会在后续添加
          });
        }
        
        // 更新 lastStepId 跟踪
        // 只要 step 不是 completed/failed 状态，就保持跟踪
        if (step.status === 'completed' || step.status === 'failed') {
          lastStepId = null;
        } else {
          // running, pending 等其他状态都设置 lastStepId
          lastStepId = step.id;
        }
        
        break;
      }
      case "tool": {
        const tool = ev.data as ToolEvent;
        const toolCallId = (tool as { tool_call_id?: string }).tool_call_id;

        if (lastStepId !== null) {
          // 工具属于当前 step，添加到 step 的 tools 中
          // 重要：从后往前查找，确保找到最新的（最后一个）匹配的 step
          let stepIdx = -1;
          for (let i = list.length - 1; i >= 0; i--) {
            const item = list[i];
            if (item.kind === "step" && item.data.id === lastStepId) {
              stepIdx = i;
              break;
            }
          }
          
          if (stepIdx >= 0) {
            const step = list[stepIdx];
            if (step.kind === "step") {
              if (toolCallId != null) {
                // 检查是否已存在相同 tool_call_id 的工具（更新场景）
                const existingToolIdx = step.tools.findIndex(
                  (t) => (t as { tool_call_id?: string }).tool_call_id === toolCallId
                );
                if (existingToolIdx >= 0) {
                  // 更新现有工具
                  const newTools = [...step.tools];
                  newTools[existingToolIdx] = tool;
                  list[stepIdx] = { ...step, tools: newTools };
                  break;
                }
              }
              // 添加新工具
              list[stepIdx] = { ...step, tools: [...step.tools, tool] };
            }
          }
        } else {
          // 工具不属于任何 step，作为独立工具添加
          if (toolCallId != null) {
            const last = list[list.length - 1];
            if (
              last?.kind === "tool" &&
              (last.data as { tool_call_id?: string }).tool_call_id === toolCallId
            ) {
              // 更新最后一个独立工具
              list[list.length - 1] = { ...last, data: tool };
              break;
            }
          }
          // 添加新的独立工具
          list.push({
            kind: "tool",
            id: stableId("tool", toolIndex++, (tool.name || "") + (tool.function || "")),
            data: tool,
            timeLabel: getToolTimeLabel(tool),
          });
        }
        break;
      }
      case "title":
      case "plan":
      case "wait":
      case "done":
        break;
      case "error": {
        // 处理错误事件
        const errorData = ev.data as { error?: string; created_at?: number; event_id?: string; [key: string]: unknown };
        if (errorData.error) {
          list.push({
            kind: "error",
            id: stableId("error", errorIndex++, String(list.length)),
            error: errorData.error,
            timestamp: errorData.created_at,
          });
        }
        break;
      }
      default:
        break;
    }
  }

  return list;
}

/**
 * 从事件列表中取最新的 plan 步骤（用于底部任务进度面板）
 */
export function getLatestPlanFromEvents(events: SSEEventData[]): PlanStep[] {
  let steps: PlanStep[] = [];
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev.type === "plan") {
      const plan = ev.data as PlanEvent;
      if (plan.steps && Array.isArray(plan.steps)) {
        steps = plan.steps;
      }
      break;
    }
  }
  return steps;
}
