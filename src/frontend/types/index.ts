export interface User {
  id: string
  email: string
}

export interface AuthResponse {
  token: string
}

export interface RegisterRequest {
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface InterestBlock {
  id: string
  title: string
  description: string
  sortOrder: number
}

export interface InterestRequest {
  title: string
  description: string
  sortOrder?: number
}

export interface Profile {
  version: number
  interests: InterestBlock[]
}

export interface BriefingArticle {
  article_id: string
  title: string
  source_name: string
  url: string
  rank: number
  display_score: number | null
  summary: string | null
  priority: string | null
  explanation: string | null
}

export interface Briefing {
  id: string
  user_id: string
  status: string
  article_count: number
  executive_summary: string | null
  profile_version: number
  generated_at: string | null
  created_at: string | null
  articles: BriefingArticle[]
}

export interface BriefingHistoryItem {
  id: string
  status: string
  article_count: number
  has_summary: boolean
  generated_at: string | null
  created_at: string | null
}

export interface IngestionResult {
  fetched: number
  extracted: number
  new: number
  embedded: number
}

export interface IngestionTriggerResponse {
  status: string
  result: IngestionResult
}

export interface IngestionStatus {
  running: boolean
  last_result: IngestionResult | null
  last_run_at: string | null
}

export interface ScoringUserResult {
  user_id: string | null
  candidates_retrieved: number
  reranked: number
  llm_scored: number
  summarized: number
  stored: number
}

export interface ScoringTriggerResponse {
  status: string
  results: ScoringUserResult[]
}

export interface ScoringStatus {
  running: boolean
  last_results: ScoringUserResult[] | null
  last_run_at: string | null
}

export interface ApiError {
  error?: string
  errors?: string[]
  detail?: string
}
