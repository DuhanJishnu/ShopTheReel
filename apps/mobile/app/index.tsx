import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { Link } from 'expo-router';
import { Screen } from '../src/components/Screen';
import { Button } from '../src/components/Button';
import { colors } from '../src/theme/tokens';
import { useAuth } from '../src/store/auth';

// Home: empty state per DESIGN.md ("Share a reel to get started").
export default function Home() {
  const { load, accessToken } = useAuth();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    load().finally(() => setReady(true));
  }, [load]);
  if (!ready) return <ActivityIndicator style={{ marginTop: 80 }} color={colors.amber} />;
  return (
    <Screen>
      <Text style={styles.title}>Good evening</Text>
      <Text style={styles.sub}>Share a reel to break down an outfit</Text>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Share a reel to get started</Text>
        <Text style={styles.cardSub}>Use the OS share sheet on any reel or saved video.</Text>
      </View>
      <Link href={accessToken ? '/share' : '/auth'} asChild>
        <Button title={accessToken ? 'Open share receiver' : 'Sign in'} onPress={() => {}} />
      </Link>
      <Link href="/onboarding">Onboarding</Link>
      <Link href="/profile">Profile</Link>
      <Link href="/saved">Saved</Link>
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 32, fontWeight: '600' },
  sub: { color: colors.textSecondary, fontSize: 15, marginBottom: 16 },
  card: { backgroundColor: colors.surface, borderRadius: 20, padding: 16, borderWidth: 1, borderColor: colors.border, marginBottom: 16 },
  cardTitle: { color: colors.textPrimary, fontSize: 20, fontWeight: '500' },
  cardSub: { color: colors.textSecondary, fontSize: 13, marginTop: 4 },
});
