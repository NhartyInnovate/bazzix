// ========================================
// BAZZIX API CLIENT
// Central API Service
// ========================================
const TOKEN_KEY = "bazzix.token";

const API_BASE_URL = (import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export type ErrorCode =
  | "WORKSPACE_WAKING"
  | "SESSION_EXPIRED"
  | "NETWORK_UNAVAILABLE"
  | "SERVER_ERROR"
  | "REQUEST_TIMEOUT"
  | "UNKNOWN";

export class ApiError extends Error {
  status: number;
  detail?: any;
  code: ErrorCode;
  isRetryable: boolean;

  constructor(status: number, originalMessage: string, detail?: any) {
    super(originalMessage);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;

    // Map status to Product State and Human Copy
    if (status === 0 || status === null) {
      this.code = "NETWORK_UNAVAILABLE";
      this.message =
        "We couldn't reach your workspace. Check your internet connection and try again.";
      this.isRetryable = false;
    } else if (status === 401) {
      this.code = "SESSION_EXPIRED";
      this.message = "Your session has expired. Please sign in again.";
      this.isRetryable = false;
    } else if (status === 502 || status === 503 || status === 504) {
      this.code = "WORKSPACE_WAKING";
      this.message = "Your workspace is waking up. This usually takes less than a minute.";
      this.isRetryable = true; // Auto-retry allowed
    } else if (status === 408) {
      this.code = "REQUEST_TIMEOUT";
      this.message = "The request took longer than expected.";
      this.isRetryable = true; // Manual retry allowed
    } else if (status >= 500) {
      this.code = "SERVER_ERROR";
      this.message = "Something went wrong on our end. Please try again in a moment.";
      this.isRetryable = false;
    } else {
      this.code = "UNKNOWN";
      // Keep the original message for 400 validation errors, fallback if empty
      this.message = originalMessage || "Something unexpected happened.";
      this.isRetryable = false;
    }
  }
}

export type User = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
};

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export type Conversation = {
  id: number;
  title: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: number | string;
  role: string;
  content: string;
  created_at: string;
};

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);

  headers.set("Content-Type", "application/json");

  const token = getToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (err: any) {
    // Network error, DNS failure, etc.
    throw new ApiError(0, "Network error", err);
  }

  if (response.status === 401) {
    setToken(null);
  }

  if (!response.ok) {
    let detail: any = null;

    try {
      detail = await response.json();
    } catch {}

    throw new ApiError(
      response.status,
      detail?.detail || detail?.message || response.statusText,
      detail,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  async register(input: {
    first_name: string;
    last_name: string;
    email: string;
    password: string;
  }) {
    return request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async login(email: string, password: string) {
    const data = await request<{
      access_token: string;
      token_type: string;
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
      }),
    });

    setToken(data.access_token);

    return data;
  },

  async me() {
    return request<User>("/users/me");
  },
  async listConversations() {
    return request<Conversation[]>("/conversations");
  },

  async createConversation(title = "New Workspace") {
    return request<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({
        title,
      }),
    });
  },

  async renameConversation(id: number | string, title: string) {
    return request<Conversation>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        title,
      }),
    });
  },

  async togglePinConversation(id: number | string, isPinned: boolean) {
    return request<Conversation>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        is_pinned: isPinned,
      }),
    });
  },

  async deleteConversation(id: number | string) {
    return request<{ message: string }>(`/conversations/${id}`, {
      method: "DELETE",
    });
  },

  async getConversation(id: number | string) {
    return request<Conversation>(`/conversations/${id}`);
  },

  async listMessages(id: number | string) {
    return request<Message[]>(`/conversations/${id}/messages`);
  },

  async sendMessage(conversationId: number | string, message: string) {
    return request<{ response: string }>("/chat", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: Number(conversationId),
        message,
      }),
    });
  },

  async sendMessageStream(
    conversationId: number | string,
    message: string,
    onChunk: (text: string) => void,
    retryCount = 0,
  ): Promise<void> {
    const token = getToken();
    const headers = new Headers();
    headers.set("Content-Type", "application/json");
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          conversation_id: Number(conversationId),
          message,
        }),
      });
    } catch (err: any) {
      throw new ApiError(0, "Network error", err);
    }

    if (response.status === 401) {
      setToken(null);
    }

    if (!response.ok) {
      let detail: any = null;
      try {
        detail = await response.json();
      } catch {}

      const error = new ApiError(
        response.status,
        detail?.detail || detail?.message || response.statusText,
        detail,
      );

      // Smart Auto-Retry logic for Render Cold Starts (WORKSPACE_WAKING)
      if (error.code === "WORKSPACE_WAKING" && retryCount < 2) {
        // We throw the error so the UI can catch it and display the "Waking up" toast immediately,
        // but we don't handle the retry recursive call *here* because if we do, the UI promise doesn't reject
        // until all retries fail.
        // Actually, if we retry here, the UI awaits silently.
        // Let's retry here and the UI can show a loading state!
        // Wait, the user asked to show "Waking up your workspace..." and retry automatically.
        // It's cleaner to just reject, and let the UI handle the auto-retry so it can show the toast!
      }

      throw error;
    }

    if (!response.body) {
      throw new Error("No response body available for streaming");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            try {
              const dataStr = trimmed.slice(6);
              const dataObj = JSON.parse(dataStr);
              if (dataObj.content) {
                onChunk(dataObj.content);
              }
            } catch (e) {
              console.error("Error parsing stream JSON line:", trimmed, e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
};
