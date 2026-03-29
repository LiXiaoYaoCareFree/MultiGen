export const ADMIN_AUTH_STORAGE_KEY = 'multigen_admin_api_key'

export const ADMIN_AUTH_CONFIG = {
  loginRequired: process.env.NEXT_PUBLIC_ADMIN_LOGIN_REQUIRED === 'true',
  password: process.env.NEXT_PUBLIC_ADMIN_PASSWORD || '',
} as const
