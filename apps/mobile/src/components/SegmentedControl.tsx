import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radius } from '../theme/tokens';

type Props = { options: string[]; value: string; onChange: (v: string) => void };

export function SegmentedControl({ options, value, onChange }: Props) {
  return (
    <View style={styles.track}>
      {options.map((o) => {
        const active = o === value;
        return (
          <Pressable key={o} onPress={() => onChange(o)} style={[styles.seg, active && styles.active]}>
            <Text style={[styles.label, active && styles.activeLabel]}>{o}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  track: { flexDirection: 'row', backgroundColor: colors.surface, borderRadius: radius.button, height: 44, padding: 4 },
  seg: { flex: 1, alignItems: 'center', justifyContent: 'center', borderRadius: 10 },
  active: { backgroundColor: colors.brown, borderWidth: 1, borderColor: colors.amber },
  label: { color: colors.textSecondary, fontSize: 13, fontWeight: '500' },
  activeLabel: { color: colors.amber },
});
