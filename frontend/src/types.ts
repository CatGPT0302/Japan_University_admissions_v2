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
  source_origin?: string;
  registry_note?: string;
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

export interface FetchPdfProbeItem {
  university: string;
  seed_url: string;
  query: string;
  status: string;
  candidate_count: number;
  top_candidate_pdf: string;
  top_candidate_page: string;
  registry_count: number;
  registry_has_top_candidate: boolean;
  is_new_pdf_candidate: boolean;
  error?: string;
}

export interface FetchPdfProbeResponse {
  checked_at: string;
  year: number;
  target_count: number;
  new_candidate_count: number;
  error_count: number;
  probes: FetchPdfProbeItem[];
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

export interface QualityFieldCoverage {
  field: string;
  filled: number;
  fill_rate: number;
  modified: number;
  modified_rate: number;
}

export interface ConfidenceCalibrationBin {
  bucket: string;
  total: number;
  corrected: number;
  corrected_rate: number;
}

export interface QualityMetricsResponse {
  doc_id?: number | null;
  total_staging_records: number;
  risk_distribution: {
    high: number;
    medium: number;
    low: number;
    [key: string]: number;
  };
  field_coverage: QualityFieldCoverage[];
  confidence_calibration: ConfidenceCalibrationBin[];
  top_modified_fields: Array<{ field: string; count: number }>;
}

export interface CorrectionEvent {
  id: number;
  staging_id: number;
  document_id: number;
  university: string;
  admission_year: string;
  field_name: string;
  old_value: string;
  new_value: string;
  page_number?: number | null;
  editor: string;
  created_at: string;
}

export interface UploadResponse {
  file_name: string;
  saved_path: string;
}

export interface ExtractResponse {
  doc_id: number;
  status: string;
  university?: string;
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
}
