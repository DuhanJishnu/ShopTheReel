import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { Screen } from '../src/components/Screen';
import { Button } from '../src/components/Button';
import { Chip } from '../src/components/Chip';
import { colors } from '../src/theme/tokens';
import { api } from '../src/api/client';
import { useAuth } from '../src/store/auth';

// Profile: view/edit sizes/budget + Style DNA from liked feedback.
export default function Profile() {
  const { accessToken } = useAuth();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [profile, setProfile] = useState<{ gender?: string | null; budget_max?: number | null } | null>(null);
  const [dna, setDna] = useState<{ top_colours: string[]; top_brands: string[]; top_tags: string[]; taste_trained: boolean } | null>(null);

  useEffect(() => {
    (async () => {
      if (!accessToken) {
        setState('error');
        return;
      }
      try {
        const p = await api.getProfile(accessToken);
        setProfile(p);
        try {
          setDna(await api.getStyleDNA(accessToken));
        } catch {
          setDna(null);
        }
        setState('ready');
      } catch {
        setState('error');
      }
    })();
  }, [accessToken]);

  if (state === 'loading') return <ActivityIndicator style={{ marginTop: 80 }} color={colors.amber} />;
  if (state === 'error' || !profile)
    return (
      <Screen>
        <Text style={s.title}>Profile unavailable</Text>
        <Text style={s.sub}>Sign in to view your Style DNA.</Text>
      </Screen>
    );
  return (
    <Screen>
      <Text style={s.title}>Style DNA</Text>
      <Text style={s.sub}>Gender: {profile.gender ?? '—'} · Target: {profile.budget_max ?? '—'}</Text>
      <Button
        title="Save sample profile"
        onPress={async () => {
          if (!accessToken) return;
          await api.putProfile(accessToken, { gender: 'women', budget_min: 1000, budget_max: 7500 });
        }}
      />
      <Text style={s.title}>Style DNA</Text>
      {dna ? (
        <View style={s.chips}>
          {[...dna.top_colours, ...dna.top_tags, ...dna.top_brands].map((t) => (
            <Chip key={t} label={t} selected onPress={() => {}} />
          ))}
          {!dna.taste_trained ? <Text style={s.sub}>Like a few matches to train your taste.</Text> : null}
        </View>
      ) : (
        <Text style={s.sub}>No taste signals yet.</Text>
      )}
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '600' },
  sub: { color: colors.textSecondary, marginVertical: 8 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 },
});
