import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text } from 'react-native';
import { Screen } from '../src/components/Screen';
import { Button } from '../src/components/Button';
import { colors } from '../src/theme/tokens';
import { api } from '../src/api/client';
import { useAuth } from '../src/store/auth';

// Profile: view/edit sizes/budget (loading/empty/error states).
export default function Profile() {
  const { accessToken } = useAuth();
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [profile, setProfile] = useState<{ gender?: string | null; budget_max?: number | null } | null>(null);

  useEffect(() => {
    (async () => {
      if (!accessToken) {
        setState('error');
        return;
      }
      try {
        const p = await api.getProfile(accessToken);
        setProfile(p);
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
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '600' },
  sub: { color: colors.textSecondary, marginVertical: 8 },
});
