import { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text } from 'react-native';
import { router } from 'expo-router';
import * as FileSystem from 'expo-file-system';
import { Screen } from '../src/components/Screen';
import { Button } from '../src/components/Button';
import { SegmentedControl } from '../src/components/SegmentedControl';
import { colors } from '../src/theme/tokens';
import { api, uploadFile } from '../src/api/client';
import { useAuth } from '../src/store/auth';

// NOTE on expo-share-intent v8 (types read from the installed package, not invented):
// `useShareIntent()` returns { isReady, hasShareIntent, shareIntent, resetShareIntent, error }.
// Normalised files look like { path, mimeType, size, fileName, ... }; native Android
// shapes use { filePath, contentUri, fileSize } — handled below as fallbacks.
// Unavailable (e.g. Expo Go, no native share extension) falls back to an empty state.
// Dev build required: `npx expo prebuild` / EAS dev client. Android-first per human decision.
type SharedFile = {
  path?: string;
  uri?: string;
  filePath?: string;
  contentUri?: string;
  mimeType?: string;
  size?: number | null;
  fileSize?: number | string | null;
};

function useShareFiles(): { kind: 'video' | 'image'; uri: string; mime: string; size: number | null } | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('expo-share-intent') as Record<string, () => unknown>;
    const hook = mod.useShareIntent as (() => unknown) | undefined;
    if (!hook) return null;
    const ctx = hook() as {
      hasShareIntent?: boolean;
      shareIntent?: { type?: string; files?: SharedFile[] | null; text?: string; value?: string };
    };
    const files = ctx?.shareIntent?.files;
    if (ctx?.hasShareIntent && files?.length) {
      const f = files[0];
      const uri = f.path ?? f.filePath ?? f.contentUri ?? f.uri ?? '';
      const mime = f.mimeType ?? 'video/mp4';
      const rawSize = f.size ?? f.fileSize ?? null;
      const size = typeof rawSize === 'string' ? parseInt(rawSize, 10) || null : rawSize;
      return { kind: mime.startsWith('image/') ? 'image' : 'video', uri, mime, size };
    }
    return null;
  } catch {
    return null;
  }
}

export default function ShareReceiver() {
  const { accessToken } = useAuth();
  const shared = useShareFiles();
  const [kind, setKind] = useState<'video' | 'image'>('video');
  const [status, setStatus] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  const active = shared ? { kind: shared.kind, uri: shared.uri, mime: shared.mime, size: shared.size } : null;

  const analyse = async () => {
    if (!accessToken) {
      setStatus('error');
      setMessage('Sign in first.');
      return;
    }
    if (!active) {
      setStatus('error');
      setMessage('No shared media found. Share a video/image from your gallery.');
      return;
    }
    setStatus('uploading');
    setMessage(null);
    try {
      // Prefer the size reported by the share intent; fall back to a filesystem stat
      // (getInfoAsync is legacy API in SDK 57 but still functional).
      let size = active.size ?? 5 * 1024 * 1024;
      if (active.size == null) {
        const info = await FileSystem.getInfoAsync(active.uri);
        if (info.exists && 'size' in info) size = info.size as number;
      }
      const presign = await api.presign(accessToken, { content_type: active.mime, size_bytes: size, kind });
      await uploadFile(presign.upload_url, active.uri, active.mime);
      const reelKind = kind === 'video' ? 'video' : 'images';
      const reel = await api.createReel(accessToken, { kind: reelKind, storage_keys: [presign.storage_key] });
      router.push(`/processing/${reel.id}`);
      setStatus('done');
      setMessage(`Uploaded to ${presign.storage_key}.`);
    } catch (e) {
      setStatus('error');
      setMessage(e instanceof Error ? e.message : 'Upload failed');
    }
  };

  return (
    <Screen>
      <Text style={s.title}>Share receiver</Text>
      {active ? (
        <Text style={s.sub}>Media: {active.uri.slice(0, 60)}…</Text>
      ) : (
        <Text style={s.sub}>No share intent — open via the OS share sheet in a dev build, or test with gallery share.</Text>
      )}
      <SegmentedControl options={['video', 'image']} value={kind} onChange={(v) => setKind(v as 'video' | 'image')} />
      {status === 'uploading' ? <ActivityIndicator color={colors.amber} /> : null}
      {message ? <Text style={s.msg}>{message}</Text> : null}
      <Button title="Analyse" onPress={analyse} loading={status === 'uploading'} />
      {status === 'error' ? <Button variant="secondary" title="Retry" onPress={analyse} /> : null}
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '600', marginBottom: 8 },
  sub: { color: colors.textSecondary, marginBottom: 12 },
  msg: { color: colors.textPrimary, marginVertical: 12 },
});
