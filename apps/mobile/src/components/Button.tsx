import React from 'react';
import { Pressable, StyleSheet, Text, ActivityIndicator } from 'react-native';
import { colors, radius } from '../theme/tokens';

type Props = {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'text';
  loading?: boolean;
  disabled?: boolean;
};

export function Button({ title, onPress, variant = 'primary', loading, disabled }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.base,
        variant === 'primary' && styles.primary,
        variant === 'secondary' && styles.secondary,
        variant === 'text' && styles.textBtn,
        pressed && variant === 'primary' && { backgroundColor: colors.amberPressed },
        (disabled || loading) && styles.disabled,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={colors.onAmber} />
      ) : (
        <Text
          style={[
            styles.label,
            variant === 'text' ? { color: colors.amber } : variant === 'secondary' ? { color: colors.textPrimary } : null,
          ]}
        >
          {title}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: { height: 52, borderRadius: radius.button, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  primary: { backgroundColor: colors.amber },
  secondary: { borderWidth: 1, borderColor: colors.brown, backgroundColor: 'transparent' },
  textBtn: { height: 44 },
  disabled: { backgroundColor: colors.brownSoft },
  label: { color: colors.onAmber, fontSize: 15, fontWeight: '600' },
});
