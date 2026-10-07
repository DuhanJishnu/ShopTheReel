import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Screen } from '../../src/components/Screen';
import { Button } from '../../src/components/Button';
import { colors } from '../../src/theme/tokens';
import { api, eventsUrl } from '../../src/api/client';
import { useAuth } from '../../src/store/auth';

const STAGES = ['ingest', 'preprocess', 'extract', 'crop_merge'] as const;
const STAGE_LABEL: Record<string, string> = {
  ingest: 'Checking for duplicates…',
  preprocess: 'Sampling frames…',
  extract: 'Spotting garments…',
  crop_merge: 'Isolating crops…',
};

type StageState = { stage: string; status: string };

// Processing: live stage stepper via SSE, polling fallback every 2s.
export default function Processing() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { accessToken } = useAuth();
  const [status, setStatus] = useState('queued');
  const [stages, setStages] = useState<StageState[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!accessToken || !id) return;
    let polling = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const poll = async () => {
      try {
        const reel = await api.getReel(accessToken, id);
        setStatus(reel.status);
        setStages(reel.stages ?? []);
        if (reel.status === 'done' || reel.status === 'failed' || reel.status === 'partial') {
          if (timer) clearInterval(timer);
          if (reel.status === 'failed') setError(reel.error ?? 'Processing failed');
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load status');
        if (timer) clearInterval(timer);
      }
    };

    const stream = async () => {
      try {
        abort.current = new AbortController();
        const res = await fetch(eventsUrl(id), {
          headers: { Authorization: `Bearer ${accessToken}` },
          signal: abort.current.signal,
        });
        if (!res.ok || !res.body) throw new Error('sse unavailable');
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const parts = buf.split('\n\n');
          buf = parts.pop() ?? '';
          for (const p of parts) {
            const line = p.split('\n').find((l) => l.startsWith('data:'));
            if (!line) continue;
            try {
              const msg = JSON.parse(line.slice(5).trim());
              if (msg.type === 'status') setStatus(msg.status);
              if (msg.type === 'stage') {
                setStages((s) => {
                  const rest = s.filter((x) => x.stage !== msg.stage);
                  return [...rest, { stage: msg.stage, status: msg.status }];
                });
              }
              if (msg.type === 'done') {
                await poll();
                return;
              }
              if (msg.type === 'error') {
                setError(msg.error ?? 'Processing failed');
                return;
              }
            } catch {
              // ignore malformed chunks
            }
          }
        }
      } catch {
        if (!polling) {
          polling = true;
          await poll();
          timer = setInterval(poll, 2000);
        }
      }
    };

    stream();
    return () => {
      abort.current?.abort();
      if (timer) clearInterval(timer);
    };
  }, [accessToken, id]);

  const done = status === 'done';
  return (
    <Screen>
      <Text style={s.title}>Processing reel</Text>
      {error ? <Text style={s.error}>{error}</Text> : null}
      <View style={s.steps}>
        {STAGES.map((stage) => {
          const found = stages.find((x) => x.stage === stage);
          const st = found?.status ?? (done ? 'done' : 'pending');
          const mark = st === 'done' ? '✓' : st === 'failed' ? '✕' : st === 'running' ? '●' : '○';
          return (
            <View key={stage} style={s.row}>
              <Text style={[s.mark, st === 'done' && s.markDone, st === 'running' && s.markActive]}>{mark}</Text>
              <View>
                <Text style={s.stage}>{stage}</Text>
                <Text style={s.label}>{STAGE_LABEL[stage]}</Text>
              </View>
            </View>
          );
        })}
      </View>
      {!done && !error ? <ActivityIndicator color={colors.amber} /> : null}
      {done ? <Button title="View outfit" onPress={() => router.push(`/outfit/${id}`)} /> : null}
      {done ? <Button variant="secondary" title="Detected items" onPress={() => router.push(`/items/${id}`)} /> : null}
      {error ? <Button variant="secondary" title="Back home" onPress={() => router.replace('/')} /> : null}
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '600', marginBottom: 16 },
  error: { color: colors.error, marginBottom: 12 },
  steps: { gap: 14, marginBottom: 20 },
  row: { flexDirection: 'row', gap: 12, alignItems: 'center' },
  mark: { color: colors.textDisabled, fontSize: 18, width: 24 },
  markDone: { color: colors.amber },
  markActive: { color: colors.amber },
  stage: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
  label: { color: colors.textSecondary, fontSize: 12 },
});
