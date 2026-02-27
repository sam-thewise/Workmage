import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

// Workmage theme: map existing --wm-* palette to Vuetify
const workmageTheme = {
  dark: true,
  colors: {
    primary: '#190056',
    secondary: '#1d0c5a',
    accent: '#608bf7',
    error: '#f87171',
    info: '#608bf7',
    success: '#34d399',
    warning: '#fde68a',
    background: '#120633',
    surface: '#1d0c5a',
    'surface-bright': '#fffdec',
    'surface-variant': '#4f3b99',
    'on-primary': '#fefefe',
    'on-secondary': '#fefefe',
    'on-surface': '#fefefe',
    'on-surface-variant': '#d7d3ee',
    outline: '#4f3b99',
  },
}

export default createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'workmage',
    themes: {
      workmage: workmageTheme,
    },
  },
  defaults: {
    VBtn: {
      variant: 'flat',
    },
    VTextField: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VSelect: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VCard: {
      variant: 'tonal',
    },
  },
})
