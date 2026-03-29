import {ADMIN_AUTH_CONFIG, ADMIN_AUTH_STORAGE_KEY} from '@/config/auth.config'

export function getStoredAdminApiKey(): string {
  if (typeof window === 'undefined') {
    return ''
  }
  const key = sessionStorage.getItem(ADMIN_AUTH_STORAGE_KEY) || ''
  return key || ADMIN_AUTH_CONFIG.password || ''
}

export function withAdminApiKeyQuery(url: string): string {
  const adminApiKey = getStoredAdminApiKey()
  if (!adminApiKey) {
    return url
  }
  const connector = url.includes('?') ? '&' : '?'
  return `${url}${connector}admin_api_key=${encodeURIComponent(adminApiKey)}`
}
