export const colors = {
  bg: '#090907',
  surface: '#141210',
  surfaceRaised: '#1E1A15',
  border: '#2E261C',
  brown: '#6C5636',
  brownSoft: 'rgba(108,86,54,0.20)',
  amber: '#B99D73',
  amberPressed: '#A38762',
  amberSoft: 'rgba(185,157,115,0.15)',
  textPrimary: '#F2EBDD',
  textSecondary: '#A89F8E',
  textDisabled: '#5E574B',
  onAmber: '#090907',
  success: '#8FB573',
  warning: '#D9A441',
  error: '#D9695F',
} as const;

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, xxxl: 32 } as const;
export const radius = { chip: 999, button: 14, card: 20, image: 16, sheet: 28 } as const;

export const fonts = {
  display: 'Fraunces_600SemiBold',
  titleM: 'Fraunces_500Medium',
  body: 'Inter_400Regular',
  bodyStrong: 'Inter_600SemiBold',
  label: 'Inter_500Medium',
} as const;
