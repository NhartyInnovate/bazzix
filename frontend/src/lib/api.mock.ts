// Bazzix API Client — implements persistent data storage using localStorage
// and communicates with the backend for the AI response generator.

const TOKEN_KEY = "bazzix.token";
const USERS_KEY = "bazzix.users";
const CONVERSATIONS_KEY = "bazzix.conversations";
const MESSAGES_KEY = "bazzix.messages";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

// ---------- Helper Storage Functions ----------

function getStored<T>(key: string, defaultValue: T): T {
  if (typeof window === "undefined") return defaultValue;
  const val = window.localStorage.getItem(key);
  if (!val) return defaultValue;
  try {
    return JSON.parse(val) as T;
  } catch {
    return defaultValue;
  }
}

function setStored<T>(key: string, value: T) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

// ---------- Types (mirror backend schemas) ----------

export type User = {
  id: number | string;
  first_name: string;
  last_name: string;
  email: string;
  created_at?: string;
};

export type StoredUser = User & { password?: string };

export type Conversation = {
  id: number | string;
  title: string;
  created_at: string;
  updated_at?: string;
  user_id?: string | number;
};

export type MessageRole = "user" | "assistant";

export type Message = {
  id: number | string;
  role: MessageRole;
  content: string;
  created_at: string;
  conversation_id?: string | number;
};

export type ChatResponse = {
  response: string;
};

// ---------- Auth Helpers ----------

function getCurrentUser(): User {
  const token = getToken();
  if (!token) {
    throw new ApiError(401, "Not authenticated");
  }
  const email = token.replace("mock-token-for-", "");
  const users = getStored<StoredUser[]>(USERS_KEY, []);
  const user = users.find((u) => u.email === email);
  if (!user) {
    throw new ApiError(401, "User not found");
  }
  return {
    id: user.id,
    first_name: user.first_name,
    last_name: user.last_name,
    email: user.email,
    created_at: user.created_at,
  };
}

// ---------- API implementation ----------

export const api = {
  register(input: { first_name: string; last_name: string; email: string; password: string }) {
    return new Promise<User>((resolve, reject) => {
      setTimeout(() => {
        try {
          const users = getStored<StoredUser[]>(USERS_KEY, []);
          const exists = users.some((u) => u.email.toLowerCase() === input.email.toLowerCase());
          if (exists) {
            reject(new ApiError(400, "An account with this email already exists."));
            return;
          }

          const newUser = {
            id: `usr_${Date.now()}`,
            first_name: input.first_name,
            last_name: input.last_name,
            email: input.email,
            password: input.password,
            created_at: new Date().toISOString(),
          };

          users.push(newUser);
          setStored(USERS_KEY, users);

          resolve({
            id: newUser.id,
            first_name: newUser.first_name,
            last_name: newUser.last_name,
            email: newUser.email,
            created_at: newUser.created_at,
          });
        } catch (err) {
          reject(new ApiError(500, "Registration failed", err));
        }
      }, 500);
    });
  },

  async login(email: string, password: string) {
    return new Promise<{ access_token: string; token_type?: string }>((resolve, reject) => {
      setTimeout(() => {
        try {
          const users = getStored<StoredUser[]>(USERS_KEY, []);
          const user = users.find(
            (u) => u.email.toLowerCase() === email.toLowerCase() && u.password === password,
          );
          if (!user) {
            reject(new ApiError(401, "Invalid email or password."));
            return;
          }

          const token = `mock-token-for-${user.email}`;
          setToken(token);
          resolve({ access_token: token, token_type: "bearer" });
        } catch (err) {
          reject(new ApiError(500, "Login failed", err));
        }
      }, 500);
    });
  },

  me() {
    return new Promise<User>((resolve, reject) => {
      try {
        const user = getCurrentUser();
        resolve(user);
      } catch (err) {
        reject(err);
      }
    });
  },

  // ---------- Conversations ----------

  listConversations() {
    return new Promise<Conversation[]>((resolve, reject) => {
      try {
        const user = getCurrentUser();
        const convs = getStored<Conversation[]>(CONVERSATIONS_KEY, []);
        const userConvs = convs.filter((c) => c.user_id === user.id);
        userConvs.sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        );
        resolve(userConvs);
      } catch (err) {
        reject(err);
      }
    });
  },

  createConversation(title = "New Workspace") {
    return new Promise<Conversation>((resolve, reject) => {
      try {
        const user = getCurrentUser();
        const convs = getStored<Conversation[]>(CONVERSATIONS_KEY, []);
        const newConv: Conversation = {
          id: `conv_${Date.now()}`,
          title,
          created_at: new Date().toISOString(),
          user_id: user.id,
        };
        convs.push(newConv);
        setStored(CONVERSATIONS_KEY, convs);
        resolve(newConv);
      } catch (err) {
        reject(err);
      }
    });
  },

  getConversation(id: string | number) {
    return new Promise<Conversation>((resolve, reject) => {
      try {
        const user = getCurrentUser();
        const convs = getStored<Conversation[]>(CONVERSATIONS_KEY, []);
        const conv = convs.find((c) => String(c.id) === String(id) && c.user_id === user.id);
        if (!conv) {
          reject(new ApiError(404, "Workspace not found"));
          return;
        }
        resolve(conv);
      } catch (err) {
        reject(err);
      }
    });
  },

  renameConversation(id: string | number, title: string) {
    return new Promise<Conversation>((resolve, reject) => {
      try {
        const user = getCurrentUser();
        const convs = getStored<Conversation[]>(CONVERSATIONS_KEY, []);
        const index = convs.findIndex((c) => String(c.id) === String(id) && c.user_id === user.id);
        if (index === -1) {
          reject(new ApiError(404, "Workspace not found"));
          return;
        }
        convs[index]!.title = title;
        convs[index]!.updated_at = new Date().toISOString();
        setStored(CONVERSATIONS_KEY, convs);
        resolve(convs[index]!);
      } catch (err) {
        reject(err);
      }
    });
  },

  deleteConversation(id: string | number) {
    return new Promise<void>((resolve, reject) => {
      try {
        const user = getCurrentUser();
        const convs = getStored<Conversation[]>(CONVERSATIONS_KEY, []);
        const filteredConvs = convs.filter(
          (c) => !(String(c.id) === String(id) && c.user_id === user.id),
        );
        setStored(CONVERSATIONS_KEY, filteredConvs);

        const msgs = getStored<Message[]>(MESSAGES_KEY, []);
        const filteredMsgs = msgs.filter((m) => String(m.conversation_id) !== String(id));
        setStored(MESSAGES_KEY, filteredMsgs);

        resolve();
      } catch (err) {
        reject(err);
      }
    });
  },

  listMessages(id: string | number) {
    return new Promise<Message[]>((resolve, reject) => {
      try {
        const user = getCurrentUser();
        const convs = getStored<Conversation[]>(CONVERSATIONS_KEY, []);
        const conv = convs.find((c) => String(c.id) === String(id) && c.user_id === user.id);
        if (!conv) {
          reject(new ApiError(404, "Workspace not found"));
          return;
        }

        const msgs = getStored<Message[]>(MESSAGES_KEY, []);
        const convMsgs = msgs.filter((m) => String(m.conversation_id) === String(id));
        convMsgs.sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
        );
        resolve(convMsgs);
      } catch (err) {
        reject(err);
      }
    });
  },

  // ---------- Chat ----------

  async sendMessage(conversation_id: string | number, message: string) {
    try {
      const user = getCurrentUser();
      const convs = getStored<Conversation[]>(CONVERSATIONS_KEY, []);
      const conv = convs.find(
        (c) => String(c.id) === String(conversation_id) && c.user_id === user.id,
      );
      if (!conv) {
        throw new ApiError(404, "Workspace not found");
      }

      const msgs = getStored<Message[]>(MESSAGES_KEY, []);

      const userMsg: Message = {
        id: `msg_u_${Date.now()}`,
        role: "user",
        content: message,
        created_at: new Date().toISOString(),
        conversation_id,
      };
      msgs.push(userMsg);
      setStored(MESSAGES_KEY, msgs);

      const history = msgs
        .filter((m) => String(m.conversation_id) === String(conversation_id))
        .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

      let res: Response;
      try {
        res = await fetch("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            messages: history.map((h) => ({ role: h.role, content: h.content })),
          }),
        });
      } catch (err) {
        throw new ApiError(0, "We couldn't reach Bazzix. Please check your connection.", err);
      }

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new ApiError(res.status, errorData.error || "Failed to generate AI response.");
      }

      const data = (await res.json()) as ChatResponse;

      const assistantMsg: Message = {
        id: `msg_a_${Date.now()}`,
        role: "assistant",
        content: data.response,
        created_at: new Date().toISOString(),
        conversation_id,
      };

      const updatedMsgs = getStored<Message[]>(MESSAGES_KEY, []);
      updatedMsgs.push(assistantMsg);
      setStored(MESSAGES_KEY, updatedMsgs);

      return data;
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(500, "An error occurred while sending message.", err);
    }
  },
};
