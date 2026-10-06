import { Stack } from 'expo-router';
import { useFonts as useFraunces, Fraunces_600SemiBold, Fraunces_500Medium } from '@expo-google-fonts/fraunces';
import { useFonts as useInter, Inter_400Regular, Inter_600SemiBold, Inter_500Medium } from '@expo-google-fonts/inter';

export default function Layout() {
  const [fLoaded] = useFraunces({ Fraunces_600SemiBold, Fraunces_500Medium });
  const [iLoaded] = useInter({ Inter_400Regular, Inter_600SemiBold, Inter_500Medium });
  if (!fLoaded || !iLoaded) return null;
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#090907' } }} />;
}
