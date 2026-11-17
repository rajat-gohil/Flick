/**
 * Authentication and Guest Identity Management for Flick
 * Stores tokens and session state in localStorage.
 * Recovery codes are NEVER stored in persistent storage.
 */

export interface AuthUser {
  id?: number;
  username?: string;
  display_name?: string;
  email?: string;
  is_guest: boolean;
  guest_uuid?: string;
}

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(localStorage.getItem("auth_token"));
}

export function isGuest(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("is_guest") === "true";
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

export function getCurrentUser(): AuthUser | null {
  if (!isLoggedIn()) return null;
  const idStr = localStorage.getItem("user_id");
  return {
    id: idStr ? Number(idStr) : undefined,
    username: localStorage.getItem("username") || undefined,
    display_name: localStorage.getItem("display_name") || undefined,
    email: localStorage.getItem("email") || undefined,
    is_guest: isGuest(),
    guest_uuid: localStorage.getItem("guest_uuid") || undefined,
  };
}

export function saveAuthState(data: {
  token: string;
  user: {
    id: number | string;
    username: string;
    display_name?: string;
    email?: string;
    is_guest?: boolean;
    guest_uuid?: string;
  };
}) {
  if (typeof window === "undefined") return;
  localStorage.setItem("auth_token", data.token);
  localStorage.setItem("user_id", String(data.user.id));
  localStorage.setItem("username", data.user.username);
  if (data.user.display_name) {
    localStorage.setItem("display_name", data.user.display_name);
  }
  if (data.user.email) {
    localStorage.setItem("email", data.user.email);
  } else {
    localStorage.removeItem("email");
  }
  if (data.user.is_guest) {
    localStorage.setItem("is_guest", "true");
  } else {
    localStorage.setItem("is_guest", "false");
  }
  if (data.user.guest_uuid) {
    localStorage.setItem("guest_uuid", data.user.guest_uuid);
  }
}

export function updateAuthState(partial: {
  display_name?: string;
  username?: string;
  email?: string;
  is_guest?: boolean;
}) {
  if (typeof window === "undefined") return;
  if (partial.display_name !== undefined) {
    localStorage.setItem("display_name", partial.display_name);
  }
  if (partial.username !== undefined) {
    localStorage.setItem("username", partial.username);
  }
  if (partial.email !== undefined) {
    localStorage.setItem("email", partial.email);
  }
  if (partial.is_guest !== undefined) {
    localStorage.setItem("is_guest", partial.is_guest ? "true" : "false");
  }
}

export function logout() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("auth_token");
  localStorage.removeItem("user_id");
  localStorage.removeItem("username");
  localStorage.removeItem("display_name");
  localStorage.removeItem("email");
  localStorage.removeItem("is_guest");
  localStorage.removeItem("guest_uuid");
}

export const clearAuthState = logout;
