import { useEffect, useState } from 'react';
import { StyleSheet, Text } from 'react-native';
import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useIdTokenAuthRequest } from 'expo-auth-session/providers/google';
import { Screen } from '../src/components/Screen';
import { Input } from '../src/components/Input';
import { Button } from '../src/components/Button';
import { colors } from '../src/theme/tokens';
import { api } from '../src/api/client';
import { useAuth } from '../src/store/auth';

WebBrowser.maybeCompleteAuthSession();

// Google client IDs come from EXPO_PUBLIC_GOOGLE_* env (Google Cloud Console).
// Unset IDs disable the button with a configuration message instead of crashing.
const ANDROID_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID ?? '';
const WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? '';
const googleConfigured = ANDROID_CLIENT_ID.length > 0 && WEB_CLIENT_ID.length > 0;

export default function Auth() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('register');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setTokens } = useAuth();
  const [, googleResponse, googlePrompt] = useIdTokenAuthRequest({
    androidClientId: ANDROID_CLIENT_ID,
    webClientId: WEB_CLIENT_ID,
  });

  const exchangeGoogleToken = async (idToken: string | undefined) => {
    if (!idToken) {
      setError('Google sign-in returned no token');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.google(idToken);
      await setTokens(res.access_token, res.refresh_token);
      router.replace('/');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Google sign-in failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (googleResponse?.type !== 'success') return;
    // Response-driven async token exchange: the canonical effect job.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void exchangeGoogleToken(googleResponse.params?.id_token as string | undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [googleResponse]);

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
        variant="secondary"
        title="Continue with Google"
        onPress={() => {
          if (!googleConfigured) {
            setError('Google sign-in is not configured in this build');
            return;
          }
          void googlePrompt();
        }}
      />
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
