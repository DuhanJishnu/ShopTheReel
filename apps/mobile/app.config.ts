import type { ExpoConfig } from 'expo/config';

// Android-first (human decision). expo-share-intent needs a dev build (native code).
const config: ExpoConfig = {
  name: 'ShopTheReel',
  slug: 'shopthereel',
  scheme: 'shopthereel',
  version: '0.1.0',
  orientation: 'portrait',
  newArchEnabled: true,
  android: {
    package: 'com.shopthereel.app',
    intentFilters: [
      { action: 'VIEW', data: { mimeType: 'text/plain' }, category: ['DEFAULT'] },
      { action: 'SEND', data: { mimeType: 'text/plain' }, category: ['DEFAULT'] },
      { action: 'SEND', data: { mimeType: 'video/*' }, category: ['DEFAULT'] },
      { action: 'SEND', data: { mimeType: 'image/*' }, category: ['DEFAULT'] },
      { action: 'SEND_MULTIPLE', data: { mimeType: 'image/*' }, category: ['DEFAULT'] },
    ],
  },
  plugins: ['expo-router', 'expo-secure-store', 'expo-share-intent'],
};

export default config;
