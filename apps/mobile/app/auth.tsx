import { useState } from 'react';
import { StyleSheet, Text } from 'react-native';
import { router } from 'expo-router';
import { Screen } from '../src/components/Screen';
import { Input } from '../src/components/Input';
import { Button } from '../src/components/Button';
import { colors } from '../src/theme/tokens';
import { api } from '../src/api/client';
import { useAuth } from '../src/store/auth';

export default function Auth() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('register');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setTokens } = useAuth();

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = mode === 'register' ? await api.register(email, password) : await api.login(email, password);
      await setTokens(res.access_token, res.refresh_token);
      router.replace('/');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Auth failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      <Text style={s.title}>{mode === 'register' ? 'Create account' : 'Welcome back'}</Text>
      {error ? <Text style={s.error}>{error}</Text> : null}
      <Input label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" placeholder="you@example.com" />
      <Input label="Password" value={password} onChangeText={setPassword} secureTextEntry placeholder="••••••••" />
      <Button title={mode === 'register' ? 'Register' : 'Login'} onPress={submit} loading={loading} />
      <Button
        variant="text"
        title={mode === 'register' ? 'Have an account? Log in' : 'New here? Register'}
        onPress={() => setMode(mode === 'register' ? 'login' : 'register')}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  title: { color: colors.textPrimary, fontSize: 24, fontWeight: '600', marginBottom: 16 },
  error: { color: colors.error, marginBottom: 12 },
});
