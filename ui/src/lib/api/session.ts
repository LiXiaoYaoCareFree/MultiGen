import { get, post, createSSEStream, parseSSEStream } from "./fetch";
import type {
  Session,
  SessionDetail,
  SessionsData,
  CreateSessionParams,
  ChatParams,
  SessionFile,
  ViewFileParams,
  ViewShellParams,
  SSEEventData,
  SSEEventHandler,
} from "./types";

/**
 * 会话列表流式更新回调
 */
type SessionsStreamCallback = (sessions: Session[]) => void;

/**
 * 会话模块 API
 */
export const sessionApi = {
  /**
   * 获取会话列表
   */
  getSessions: (): Promise<SessionsData> => {
    return get<SessionsData>("/sessions");
  },

  /**
   * 创建新会话
   */
  createSession: (params?: CreateSessionParams): Promise<Session> => {
    return post<Session>("/sessions", params || {});
  },

  /**
   * 流式订阅会话列表更新（SSE）
   *
   * 通过 /sessions/stream 端点建立 SSE 长连接，
   * 服务端定期推送完整的会话列表数据。
   *
   * 使用 AbortController 管理连接生命周期，调用返回的清理函数
   * 可以彻底中止底层 fetch 连接，避免连接泄漏。
   *
   * @param onSessions 每次收到新会话列表时的回调
   * @param onError    连接异常或流结束时的回调（可用于触发重连）
   * @returns 清理函数，调用后会彻底关闭连接
   */
  streamSessions: (
    onSessions: SessionsStreamCallback,
    onError?: (error: Error) => void
  ): (() => void) => {
    const controller = new AbortController();

    const startStream = async () => {
      try {
        const stream = await createSSEStream("/sessions/stream", {}, {
          signal: controller.signal,
        });

        await parseSSEStream(
          stream,
          (messageEvent) => {
            if (controller.signal.aborted) return;

            const data =
              typeof messageEvent.data === "string"
                ? JSON.parse(messageEvent.data)
                : messageEvent.data;

            // 服务端事件格式: event: sessions  data: { sessions: [...] }
            // 注意：部分事件可能没有 event: 行，此时 type 默认为 "message"
            // 因此只校验数据结构，不强制要求 type === "sessions"
            if (data?.sessions && Array.isArray(data.sessions)) {
              onSessions(data.sessions as Session[]);
            }
          },
          (error) => {
            if (!controller.signal.aborted && onError) {
              onError(error);
            }
          }
        );

        // 流正常结束（服务端关闭连接），通知上层以便重连
        if (!controller.signal.aborted && onError) {
          onError(new Error("SSE 流已结束"));
        }
      } catch (error) {
        if (!controller.signal.aborted && onError) {
          onError(
            error instanceof Error ? error : new Error("SSE 连接失败")
          );
        }
      }
    };

    startStream();

    // 返回清理函数：通过 abort 彻底中止底层 fetch 连接
    return () => {
      controller.abort();
    };
  },

  /**
   * 获取会话详情
   */
  getSession: (sessionId: string): Promise<Session> => {
    return get<Session>(`/sessions/${sessionId}`);
  },

  /**
   * 获取会话详情（含事件列表，与 chat 流式响应格式一致）
   * 若后端在 GET /sessions/:id 中返回 events 字段则一并返回
   */
  getSessionDetail: (sessionId: string): Promise<SessionDetail> => {
    return get<SessionDetail>(`/sessions/${sessionId}`);
  },

  /**
   * 发起聊天请求（SSE 流式）
   * @param sessionId 会话 ID
   * @param params 聊天参数
   * @param onEvent 事件处理器
   * @param onError 错误处理器
   * @returns 清理函数
   */
  chat: (
    sessionId: string,
    params: ChatParams,
    onEvent: SSEEventHandler,
    onError?: (error: Error) => void
  ): (() => void) => {
    const controller = new AbortController();

    const startStream = async () => {
      try {
        const stream = await createSSEStream(
          `/sessions/${sessionId}/chat`,
          params,
          { 
            signal: controller.signal,
            // 流式连接需要很长时间，设置为 5 分钟超时
            timeout: 5 * 60 * 1000
          }
        );
        
        await parseSSEStream(
          stream,
          (messageEvent) => {
            if (controller.signal.aborted) return;
            
            // messageEvent.data 已经在 parseSSEStream 中解析为对象
            const data =
              typeof messageEvent.data === "string"
                ? JSON.parse(messageEvent.data)
                : messageEvent.data;
            
            onEvent({
              type: messageEvent.type as SSEEventData["type"],
              data,
            } as SSEEventData);
          },
          (error) => {
            if (!controller.signal.aborted && onError) {
              onError(error);
            }
          }
        );

        // 流正常结束（服务端关闭连接），通知上层以便重连或状态恢复
        if (!controller.signal.aborted && onError) {
          onError(new Error("SSE_STREAM_END"));
        }
      } catch (error) {
        // 忽略 AbortError，这是正常的连接中止
        if (error instanceof Error && error.name === 'AbortError') {
          return;
        }
        if (!controller.signal.aborted && onError) {
          onError(
            error instanceof Error ? error : new Error("启动聊天流失败")
          );
        }
      }
    };

    startStream();

    // 返回清理函数：通过 AbortController 中止连接
    return () => {
      controller.abort();
    };
  },

  /**
   * 停止会话
   */
  stopSession: (sessionId: string): Promise<void> => {
    return post<void>(`/sessions/${sessionId}/stop`, {});
  },

  /**
   * 删除会话
   */
  deleteSession: (sessionId: string, adminApiKey?: string): Promise<void> => {
    return post<void>(`/sessions/${sessionId}/delete`, { admin_api_key: adminApiKey });
  },

  /**
   * 清除未读消息数
   */
  clearUnreadMessageCount: (sessionId: string): Promise<void> => {
    return post<void>(
      `/sessions/${sessionId}/clear-unread-message-count`,
      {}
    );
  },

  /**
   * 获取会话文件列表
   */
  getSessionFiles: (sessionId: string): Promise<SessionFile[]> => {
    return get<SessionFile[]>(`/sessions/${sessionId}/files`);
  },

  /**
   * 查看沙箱文件内容
   */
  viewFile: (
    sessionId: string,
    params: ViewFileParams
  ): Promise<{ content: string; [key: string]: unknown }> => {
    return post<{ content: string; [key: string]: unknown }>(
      `/sessions/${sessionId}/file`,
      params
    );
  },

  /**
   * 查看 Shell 输出
   */
  viewShell: (
    sessionId: string,
    params: ViewShellParams
  ): Promise<{ output: string; [key: string]: unknown }> => {
    return post<{ output: string; [key: string]: unknown }>(
      `/sessions/${sessionId}/shell`,
      params
    );
  },
};

