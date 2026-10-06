import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  setTokens: (a: string, r: string) => Promise<void>;
  load: () => Promise<void>;
  clear: () => Promise<void>;
};

export const useAuth = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  setTokens: async (accessToken, refreshToken) => {
    await SecureStore.setItemAsync('access_token', accessToken);
    await SecureStore.setItemAsync('refresh_token', refreshToken);
    set({ accessToken, refreshToken });
  },
  load: async () => {
    const accessToken = await SecureStore.getItemAsync('access_token');
    const refreshToken = await SecureStore.getItemAsync('refresh_token');
    set({ accessToken, refreshToken });
  },
  clear: async () => {
    await SecureStore.deleteItemAsync('access_token');
    await SecureStore.deleteItemAsync('refresh_token');
    set({ accessToken: null, refreshToken: null });
  },
}));
