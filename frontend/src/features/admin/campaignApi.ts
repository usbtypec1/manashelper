import { getJson, isRecord, postJson } from '../../shared/api/http'

export const audiences = ['all', 'allowlist', 'blocklist'] as const
export type Audience = typeof audiences[number]
export const deliveryStatuses = ['pending', 'processing', 'sent', 'failed', 'expired', 'cancelled'] as const
export const retryableStatuses = ['failed', 'expired', 'cancelled'] as const

export type Variant = {
  locale: string | null
  theme: string | null
  text: string
}
type Draft = {
  id: string
  audience: Audience
  user_ids: string[]
  variants: Variant[]
}

export type CampaignSummary = {
  id: string
  created_at: string
  audience: Audience
  preview: string
  counts: Record<string, number>
}

export type CampaignDetail = CampaignSummary & { variants: Variant[]; user_ids: string[] }

type Delivery = { user_id: string; status: string; attempts: number; last_error: string | null }

function isAudience(value: unknown): value is Audience {
  return audiences.some(audience => audience === value)
}

function isCampaignSummary(value: unknown): value is CampaignSummary {
  return isRecord(value) && typeof value.id === 'string' && typeof value.created_at === 'string'
    && !Number.isNaN(Date.parse(value.created_at)) && isAudience(value.audience) && typeof value.preview === 'string'
    && isRecord(value.counts) && Object.values(value.counts).every(count => typeof count === 'number' && Number.isInteger(count) && count >= 0)
}

function isVariant(value: unknown): value is Variant {
  return isRecord(value) && typeof value.text === 'string'
    && (value.locale === null || typeof value.locale === 'string')
    && (value.theme === null || typeof value.theme === 'string')
}

function isDelivery(value: unknown): value is Delivery {
  return isRecord(value) && typeof value.user_id === 'string' && typeof value.status === 'string'
    && typeof value.attempts === 'number' && (value.last_error === null || typeof value.last_error === 'string')
}

function parsePage<T>(
  value: unknown, field: string, isItem: (item: unknown) => item is T,
): { items: T[]; nextCursor: string | null } {
  if (!isRecord(value)) throw new Error('Invalid page')
  const items = value[field]
  if (!Array.isArray(items) || !items.every(isItem)
    || (value.next_cursor !== null && typeof value.next_cursor !== 'string')) {
    throw new Error('Invalid page')
  }
  return { items, nextCursor: value.next_cursor }
}

function withCursor(path: string, name: string, cursor: string | null) {
  return cursor === null ? path : path + '?' + new URLSearchParams({ [name]: cursor })
}

export async function getCampaigns(initData: string, cursor: string | null, signal: AbortSignal) {
  const value = await getJson(withCursor('admin/broadcasts', 'before', cursor), initData, signal)
  return parsePage(value, 'campaigns', isCampaignSummary)
}

export async function getCampaign(initData: string, id: string, signal: AbortSignal): Promise<CampaignDetail> {
  const value = await getJson('admin/broadcasts/' + encodeURIComponent(id), initData, signal)
  if (!isRecord(value)) throw new Error('Invalid broadcast')
  const { variants, user_ids } = value
  if (!isCampaignSummary(value) || !Array.isArray(variants) || !variants.every(isVariant)
    || !Array.isArray(user_ids) || !user_ids.every(id => typeof id === 'string')) {
    throw new Error('Invalid broadcast')
  }
  return { ...value, variants, user_ids }
}

export async function getDeliveries(initData: string, id: string, cursor: string | null, signal: AbortSignal) {
  const path = 'admin/broadcasts/' + encodeURIComponent(id) + '/deliveries'
  const value = await getJson(withCursor(path, 'after', cursor), initData, signal)
  return parsePage(value, 'deliveries', isDelivery)
}

export async function createCampaign(initData: string, draft: Draft): Promise<string> {
  const value = await postJson('admin/broadcasts', initData, draft)
  if (!isRecord(value) || typeof value.id !== 'string') throw new Error('Invalid broadcast')
  return value.id
}

export async function retryCampaign(initData: string, id: string): Promise<number> {
  const value = await postJson('admin/broadcasts/' + encodeURIComponent(id) + '/retry', initData)
  if (!isRecord(value) || typeof value.retried !== 'number') throw new Error('Invalid retry result')
  return value.retried
}
