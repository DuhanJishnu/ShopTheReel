import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Image, StyleSheet, Text, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Screen } from '../../src/components/Screen';
import { Button } from '../../src/components/Button';
import { Chip } from '../../src/components/Chip';
import { colors, radius } from '../../src/theme/tokens';
import { api } from '../../src/api/client';
import { useAuth } from '../../src/store/auth';

type Item = {
  id: string;
  category: string;
  subcategory: string;
  colours: string[];
  confidence: number;
  crop_url: string | null;
};

// Detected items: crop strip + attributes (bbox overlay lands with real frames in Phase 3+).
export default function Items() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { accessToken } = useAuth();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [items, setItems] = useState<Item[]>([]);

  const load = useCallback(async () => {
    if (!accessToken || !id) {
      setState('error');
      return;
    }
    setState('loading');
    try {
      setItems(await api.getItems(accessToken, id));
      setState('ready');
    } catch {
      setState('error');
    }
  }, [accessToken, id]);

  useEffect(() => {
    // Initial data fetch on mount (canonical exception to set-state-in-effect).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  if (state === 'loading') return <ActivityIndicator style={{ marginTop: 80 }} color={colors.amber} />;
  if (state === 'error')
    return (
      <Screen>
        <Text style={s.title}>Couldn’t load items</Text>
        <Button title="Retry" onPress={load} />
      </Screen>
    );
  if (items.length === 0)
    return (
      <Screen>
        <Text style={s.title}>No garments detected</Text>
        <Text style={s.sub}>Try a clip with a clearer full-body shot.</Text>
        <Button variant="secondary" title="Back home" onPress={() => router.replace('/')} />
      </Screen>
    );
  return (
    <Screen>
      <Text style={s.title}>Detected garments</Text>
      <Text style={s.sub}>{items.length} items · tap a card for alternatives in Phase 3</Text>
      {items.map((item) => (
        <View key={item.id} style={s.card}>
          {item.crop_url ? (
            <Image source={{ uri: item.crop_url }} style={s.crop} accessibilityLabel={`${item.subcategory} crop`} />
          ) : (
            <View style={[s.crop, s.cropEmpty]} />
          )}
          <View style={s.meta}>
            <Chip label={item.category} selected onPress={() => {}} />
            <Text style={s.name}>{item.subcategory || item.category}</Text>
            <Text style={s.conf}>{Math.round(item.confidence * 100)}% confidence · {(item.colours ?? []).join(', ')}</Text>
          </View>
        </View>
      ))}
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '600' },
  sub: { color: colors.textSecondary, fontSize: 13, marginVertical: 8 },
  card: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.card,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 12,
    gap: 12,
  },
  crop: { width: 72, height: 96, borderRadius: 12 },
  cropEmpty: { backgroundColor: colors.surfaceRaised },
  meta: { flex: 1, gap: 6, justifyContent: 'center' },
  name: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
  conf: { color: colors.amber, fontSize: 12 },
});
