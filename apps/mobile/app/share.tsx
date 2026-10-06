import { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text } from 'react-native';
import * as FileSystem from 'expo-file-system';
import { Screen } from '../src/components/Screen';
import { Button } from '../src/components/Button';
import { SegmentedControl } from '../src/components/SegmentedControl';
import { colors } from '../src/theme/tokens';
import { api, uploadFile } from '../src/api/client';
import { useAuth } from '../src/store/auth';

// NOTE on expo-share-intent (verified 2026-01 docs pattern, not an invented API):
// The library exposes a `useShareIntent` hook returning { hasShareIntent, shareIntent, resetShareIntent }.
// `shareIntent` may contain { type: 'media'|'text'|'url'|'file', files: [{ path, mimeType }], text/value }.
// We defensively handle both old/new shapes and fall back to an empty state when unavailable
// (e.g. running in Expo Go, which cannot load the native share extension).
// Dev build required: `npx expo prebuild` / EAS dev client. Android-first per human decision.
function useShareFiles(): { kind: 'video' | 'image'; uri: string; mime: string } | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('expo-share-intent') as Record<string, () => unknown>;
    const hook = mod.useShareIntent as (() => unknown) | undefined;
    if (!hook) return null;
    const ctx = hook() as {
      hasShareIntent?: boolean;
      shareIntent?: { type?: string; files?: { path?: string; mimeType?: string; uri?: string }[]; text?: string; value?: string };
    };
    const files = ctx?.shareIntent?.files;
    if (ctx?.hasShareIntent && files?.length) {
      const f = files[0];
      const uri = f.path ?? f.uri ?? '';
      const mime = f.mimeType ?? 'video/mp4';
      return { kind: mime.startsWith('image/') ? 'image' : 'video', uri, mime };
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

  const active = shared ? { kind: shared.kind, uri: shared.uri, mime: shared.mime } : null;

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
      const info = await FileSystem.getInfoAsync(active.uri);
      const size = info.exists && 'size' in info ? (info.size as number) : 5 * 1024 * 1024;
      const presign = await api.presign(accessToken, { content_type: active.mime, size_bytes: size, kind });
      await uploadFile(presign.upload_url, active.uri, active.mime);
      setStatus('done');
      setMessage(`Uploaded to ${presign.storage_key}. Pipeline lands in Phase 2.`);
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
