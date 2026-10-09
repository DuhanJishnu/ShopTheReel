import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Image, Linking, StyleSheet, Text, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Screen } from '../../src/components/Screen';
import { Button } from '../../src/components/Button';
import { SegmentedControl } from '../../src/components/SegmentedControl';
import { colors, radius } from '../../src/theme/tokens';
import { api } from '../../src/api/client';
import { useAuth } from '../../src/store/auth';

type OutfitItem = {
  item: { id: string; category: string; subcategory: string; colours: string[]; confidence: number; crop_url: string | null };
  match: {
    id: string;
    product: { sku: string; brand: string; title: string; price_display: string; image_url: string | null; buy_url: string | null };
    match_pct: number;
    reason: string | null;
  } | null;
  suggested: boolean;
};

// Outfit result with live tiers (Exact / Similar / Budget) and feedback actions.
export default function Outfit() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { accessToken } = useAuth();
  const [tier, setTier] = useState('Exact');
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [items, setItems] = useState<OutfitItem[]>([]);
  const [total, setTotal] = useState('');
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(
    async (name = 'exact') => {
      if (!accessToken || !id) {
        setState('error');
        return;
      }
      setState('loading');
      try {
        const res = await api.getOutfit(accessToken, id, name);
        setItems(res.items);
        setTotal(res.total_display);
        setState('ready');
      } catch {
        setState('error');
      }
    },
    [accessToken, id],
  );

  useEffect(() => {
    // Initial fetch on mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load('exact');
  }, [load]);

  const sendFeedback = async (matchId: string, signal: 'like' | 'dislike' | 'wrong_item') => {
    if (!accessToken) return;
    try {
      await api.feedback(accessToken, matchId, signal);
    } catch {
      setNote('Feedback failed — try again');
    }
  };

  if (state === 'loading') return <ActivityIndicator style={{ marginTop: 80 }} color={colors.amber} />;
  if (state === 'error')
    return (
      <Screen>
        <Text style={s.title}>Couldn’t load the outfit</Text>
        <Button title="Retry" onPress={() => load(tier.toLowerCase())} />
      </Screen>
    );

  return (
    <Screen>
      <SegmentedControl
        options={['Exact', 'Similar', 'Budget']}
        value={tier}
        onChange={(v) => {
          setTier(v);
          setNote(null);
          void load(v.toLowerCase());
        }}
      />
      {note ? <Text style={s.note}>{note}</Text> : null}
      {items.length === 0 ? <Text style={s.sub}>No matches yet — the reel is probably still processing.</Text> : null}
      {items.map(({ item, match }) =>
        match ? (
          <View key={item.id} style={s.card}>
            <View style={s.compare}>
              {item.crop_url ? (
                <Image source={{ uri: item.crop_url }} style={s.crop} accessibilityLabel={`${item.subcategory} crop`} />
              ) : (
                <View style={[s.crop, s.empty]} />
              )}
              <Text style={s.arrow}>→</Text>
              {match.product.image_url ? (
                <Image source={{ uri: match.product.image_url }} style={s.product} accessibilityLabel={match.product.title} />
              ) : (
                <View style={[s.product, s.empty]} />
              )}
              <Text style={s.badge}>{match.match_pct}%</Text>
            </View>
            <Text style={s.brand}>{match.product.brand}</Text>
            <Text style={s.name}>{match.product.title}</Text>
            <Text style={s.price}>{match.product.price_display}</Text>
            {match.reason ? <Text style={s.reason}>{match.reason}</Text> : null}
            <Text style={s.partner}>Demo partner — link opens the mock retailer</Text>
            <View style={s.actions}>
              <Button variant="text" title="♡" onPress={() => void sendFeedback(match.id, 'like')} />
              <Button variant="text" title="✕" onPress={() => void sendFeedback(match.id, 'dislike')} />
              <Button variant="text" title="Wrong item?" onPress={() => void sendFeedback(match.id, 'wrong_item')} />
            </View>
            <Button
              title="Buy"
              onPress={() => {
                if (match.product.buy_url) void Linking.openURL(match.product.buy_url);
              }}
            />
          </View>
        ) : null,
      )}
      <View style={s.total}>
        <Text style={s.totalText}>Total · {items.length} items{'\n'}{total}</Text>
        <Button title="Buy all" onPress={() => router.replace('/')} />
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  note: { color: colors.warning, fontSize: 12, marginVertical: 8 },
  sub: { color: colors.textSecondary, marginVertical: 12 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.card,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 12,
  },
  compare: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  crop: { width: 72, height: 96, borderRadius: 12 },
  product: { width: 96, height: 120, borderRadius: 16 },
  empty: { backgroundColor: colors.surfaceRaised },
  arrow: { color: colors.amber },
  badge: { color: colors.amber, fontSize: 12, fontWeight: '600' },
  brand: { color: colors.textSecondary, fontSize: 11, letterSpacing: 1 },
  name: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
  price: { color: colors.amber, fontSize: 16, fontWeight: '600', marginVertical: 4 },
  reason: { color: colors.textSecondary, fontSize: 12, fontStyle: 'italic', marginBottom: 4 },
  partner: { color: colors.textDisabled, fontSize: 11, fontStyle: 'italic', marginBottom: 8 },
  actions: { flexDirection: 'row', gap: 4, marginBottom: 4 },
  total: {
    backgroundColor: colors.surfaceRaised,
    borderTopWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.card,
    padding: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  totalText: { color: colors.textPrimary, fontSize: 16, fontWeight: '600' },
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '600' },
});
