import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Screen } from '../src/components/Screen';
import { Chip } from '../src/components/Chip';
import { Button } from '../src/components/Button';
import { SegmentedControl } from '../src/components/SegmentedControl';
import { colors } from '../src/theme/tokens';

// Onboarding: gender -> sizes -> budget tier -> style chips (visual only in Phase 1).
export default function Onboarding() {
  const [gender, setGender] = useState('Women');
  const [styles, setStyles] = useState<string[]>(['Quiet Luxury']);
  const toggle = (s: string) => setStyles((p) => (p.includes(s) ? p.filter((x) => x !== s) : [...p, s]));
  return (
    <Screen>
      <Text style={s.title}>Build your Style DNA</Text>
      <Text style={s.sub}>Department focus</Text>
      <SegmentedControl options={['Women', 'Men', 'Unisex']} value={gender} onChange={setGender} />
      <Text style={s.sub}>Curated aesthetics</Text>
      <View style={s.row}>
        {['Quiet Luxury', 'Dark Academia', 'Minimalist Linen', 'Old Money'].map((t) => (
          <Chip key={t} label={t} selected={styles.includes(t)} onPress={() => toggle(t)} />
        ))}
      </View>
      <Button title="Continue" onPress={() => router.replace('/auth')} />
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '600', marginBottom: 12 },
  sub: { color: colors.textSecondary, fontSize: 13, marginVertical: 10 },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 20 },
});
