import { get, post } from "./fetch";
import type { FileInfo, FileUploadParams } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export const getApiBaseUrl = (): string => API_BASE_URL;

export const getApiOrigin = (): string => API_BASE_URL.replace(/\/api\/?$/, "");

export const resolveStorageUrl = (pathOrUrl: string): string => {
  if (!pathOrUrl) return pathOrUrl;
  if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) return pathOrUrl;
  if (pathOrUrl.startsWith("/storage/")) return `${getApiOrigin()}${pathOrUrl}`;
  return pathOrUrl;
};

/**
 * 文件模块 API
 */
export const fileApi = {
  /**
   * 上传文件
   * @param params 上传参数，包含文件和可选的会话 ID
   * @returns 文件信息
   */
  uploadFile: async (params: FileUploadParams): Promise<FileInfo> => {
    const formData = new FormData();
    formData.append("file", params.file);
    
    if (params.session_id) {
      formData.append("session_id", params.session_id);
    }

    return post<FileInfo>("/files", formData);
  },

  /**
   * 获取文件信息
   * @param fileId 文件 ID
   * @returns 文件信息
   */
  getFileInfo: (fileId: string): Promise<FileInfo> => {
    return get<FileInfo>(`/files/${fileId}`);
  },

  /**
   * 下载文件
   * @param fileId 文件 ID
   * @returns Blob 对象
   */
  downloadFile: async (fileId: string): Promise<Blob> => {
    const response = await fetch(`${getApiBaseUrl()}/files/${fileId}/download`);

    if (!response.ok) {
      throw new Error(`下载失败: ${response.statusText}`);
    }

    return response.blob();
  },

  /**
   * 下载文件并获取 URL（用于直接下载或预览）
   * @param fileId 文件 ID
   * @returns 文件下载 URL
   */
  getFileDownloadUrl: (fileId: string): string => {
    return `${getApiBaseUrl()}/files/${fileId}/download`;
  },
};
