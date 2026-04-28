export type NavPage = "run" | "review" | "records";

export interface FetchPdfTarget {
  name: string;
  url: string;
}

export interface FetchPdfCandidate {
  title: string;
  pdf_url: string;
  page_url: string;
  query: string;
  score: number;
  host?: string;
  is_official?: boolean;
  source_kind?: string;
  university?: string;
}

export interface FetchPdfSearchResponse {
  university: string;
  query: string;
  status: string;
  candidates: FetchPdfCandidate[];
}

export interface FetchPdfResponse {
  university: string;
  status: string;
  saved_path: string;
  source_url: string;
  page_url?: string;
  file_name: string;
}

export interface DocumentListItem {
  doc_id: number;
  university_name: string;
  admission_year: string;
  source_url?: string;
  filename: string;
  created_at?: string;
  staging_count: number;
  confirmed_count: number;
  status?: string;
}

export interface DocumentSummary extends DocumentListItem {
  review_count?: number;
  avg_confidence?: number;
}

export interface StatsResponse {
  total_records: number;
  staging_records: number;
  universities: number;
  avg_confidence: number;
}

export interface UploadResponse {
  file_name: string;
  saved_path: string;
}

export interface ExtractResponse {
  doc_id: number;
  status: string;
  records: number;
  failed_pages: Array<{ page: number; error: string }>;
}

export interface ConfirmResponse {
  confirmed: number;
  skipped: number;
}

export interface FieldEvidenceItem {
  text: string;
  page: number | null;
}

export type RiskLevel = "low" | "medium" | "high";

export interface StagingRecord {
  id: number;
  document_id?: number;
  page_number?: number | null;
  university?: string;
  admission_year?: string;
  admission_period?: string;
  faculty?: string;
  department?: string;
  application_period?: string;
  deadline_rule?: string;
  eju_session?: string;
  eju_japanese?: string;
  eju_general?: string;
  eju_math?: string;
  eju_physics?: string;
  eju_chemistry?: string;
  eju_biology?: string;
  english_requirement?: string;
  screening_method?: string;
  screening_schedule?: string;
  result_date?: string;
  enrollment_period?: string;
  prefecture?: string;
  campus?: string;
  confidence?: number;
  needs_review?: number | boolean;
  is_confirmed?: number | boolean;
  field_confidence?: Record<string, number>;
  field_evidence?: Record<string, FieldEvidenceItem>;
  risk_level?: RiskLevel;
  manual_modified_fields?: string[];
  is_reviewed?: number | boolean;
  reviewed_at?: string | null;
  warnings_json?: string[];
  updated_at?: string;
}

export interface ConfirmedRecord {
  id: number;
  university: string;
  admission_year: string;
  faculty: string;
  department: string;
  admission_period?: string;
  application_period?: string;
  english_requirement?: string;
  screening_method?: string;
  result_date?: string;
  prefecture?: string;
  campus?: string;
}
