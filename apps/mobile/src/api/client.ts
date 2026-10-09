// Minimal fetch-based API client. Base URL from EXPO_PUBLIC_API_URL.
const BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://10.0.2.2:8000';

export type TokenPair = { access_token: string; refresh_token: string };

async function req(path: string, init: RequestInit, requestId?: string) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as object) };
  if (requestId) headers['X-Request-ID'] = requestId;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  register: (email: string, password: string) =>
    req('/v1/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    req('/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  google: (idToken: string) =>
    req('/v1/auth/google', { method: 'POST', body: JSON.stringify({ id_token: idToken }) }),
  getProfile: (token: string) => req('/v1/me/profile', { method: 'GET', headers: { Authorization: `Bearer ${token}` } }),
  putProfile: (token: string, body: object) =>
    req('/v1/me/profile', { method: 'PUT', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(body) }),
  presign: (token: string, body: { content_type: string; size_bytes: number; kind: 'video' | 'image' }) =>
    req('/v1/uploads/presign', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    }),
  createReel: (token: string, body: { kind: 'video' | 'images' | 'link'; storage_keys?: string[]; source_url?: string }) =>
    req('/v1/reels', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    }),
  getReel: (token: string, id: string) =>
    req(`/v1/reels/${id}`, { method: 'GET', headers: { Authorization: `Bearer ${token}` } }),
  getItems: (token: string, id: string) =>
    req(`/v1/reels/${id}/items`, { method: 'GET', headers: { Authorization: `Bearer ${token}` } }),
  getOutfit: (token: string, id: string, tier = 'exact') =>
    req(`/v1/reels/${id}/outfit?tier=${tier}`, { method: 'GET', headers: { Authorization: `Bearer ${token}` } }),
  feedback: (token: string, matchId: string, signal: 'like' | 'dislike' | 'wrong_item' | 'bought') =>
    req(`/v1/matches/${matchId}/feedback`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ signal }),
    }),
  listLooks: (token: string) =>
    req('/v1/looks', { method: 'GET', headers: { Authorization: `Bearer ${token}` } }),
  createLook: (token: string, body: { title: string; reel_id?: string; match_ids: string[] }) =>
    req('/v1/looks', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(body) }),
  shareLook: (token: string, id: string) =>
    req(`/v1/looks/${id}/share`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } }),
  listBoards: (token: string) =>
    req('/v1/boards', { method: 'GET', headers: { Authorization: `Bearer ${token}` } }),
  createBoard: (token: string, name: string) =>
    req('/v1/boards', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ name }) }),
  addBoardLook: (token: string, boardId: string, lookId: string) =>
    req(`/v1/boards/${boardId}/looks`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ look_id: lookId }),
    }),
  getStyleDNA: (token: string) =>
    req('/v1/me/style-dna', { method: 'GET', headers: { Authorization: `Bearer ${token}` } }),
};

export const eventsUrl = (id: string) => `${BASE}/v1/reels/${id}/events`;

export async function uploadFile(uploadUrl: string, uri: string, contentType: string): Promise<void> {
  // RN fetch can PUT a blob from a file URI via { uri, type } workaround; keep simple XHR-free approach.
  const blob = await (await fetch(uri)).blob();
  const res = await fetch(uploadUrl, { method: 'PUT', headers: { 'Content-Type': contentType }, body: blob });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
}
