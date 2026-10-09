import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { Screen } from '../src/components/Screen';
import { Button } from '../src/components/Button';
import { Input } from '../src/components/Input';
import { Chip } from '../src/components/Chip';
import { colors, radius } from '../src/theme/tokens';
import { api } from '../src/api/client';
import { useAuth } from '../src/store/auth';

type Look = { id: string; title: string; is_public: boolean; share_slug: string | null; share_url: string | null };
type Board = { id: string; name: string; look_ids: string[] };

// Saved: looks with share links, boards with create + attach.
export default function Saved() {
  const { accessToken } = useAuth();
  const [looks, setLooks] = useState<Look[]>([]);
  const [boards, setBoards] = useState<Board[]>([]);
  const [boardName, setBoardName] = useState('');
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) {
      setState('error');
      return;
    }
    setState('loading');
    try {
      setLooks((await api.listLooks(accessToken)).items);
      setBoards((await api.listBoards(accessToken)).items);
      setState('ready');
    } catch {
      setState('error');
    }
  }, [accessToken]);

  useEffect(() => {
    // Initial fetch on mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const share = async (lookId: string) => {
    if (!accessToken) return;
    try {
      const res = await api.shareLook(accessToken, lookId);
      setMsg(`Shared: ${res.share_url}`);
      await load();
    } catch {
      setMsg('Share failed');
    }
  };

  const createBoard = async () => {
    if (!accessToken || !boardName.trim()) return;
    try {
      await api.createBoard(accessToken, boardName.trim());
      setBoardName('');
      await load();
    } catch {
      setMsg('Could not create board');
    }
  };

  if (state === 'loading') return <ActivityIndicator style={{ marginTop: 80 }} color={colors.amber} />;
  if (state === 'error')
    return (
      <Screen>
        <Text style={s.title}>Saved unavailable</Text>
        <Text style={s.sub}>Sign in to see your looks and boards.</Text>
      </Screen>
    );
  return (
    <Screen>
      <Text style={s.title}>Saved looks</Text>
      {looks.length === 0 ? <Text style={s.sub}>No saved looks yet — save one from an outfit.</Text> : null}
      {looks.map((look) => (
        <View key={look.id} style={s.card}>
          <Text style={s.name}>{look.title}</Text>
          {look.is_public ? <Text style={s.pub}>shared{look.share_slug ? ` · ${look.share_slug}` : ''}</Text> : null}
          <Button variant="secondary" title="Share link" onPress={() => void share(look.id)} />
        </View>
      ))}
      <Text style={s.title}>Boards</Text>
      <Input label="New board" value={boardName} onChangeText={setBoardName} placeholder="e.g. Festive" />
      <Button title="Create board" onPress={() => void createBoard()} />
      <View style={s.chips}>
        {boards.map((b) => (
          <Chip key={b.id} label={`${b.name} (${b.look_ids.length})`} selected={false} onPress={() => {}} />
        ))}
      </View>
      {msg ? <Text style={s.sub}>{msg}</Text> : null}
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '600', marginVertical: 8 },
  sub: { color: colors.textSecondary, fontSize: 13, marginBottom: 8 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.card,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 12,
    gap: 8,
  },
  name: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
  pub: { color: colors.success, fontSize: 12 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 },
});
