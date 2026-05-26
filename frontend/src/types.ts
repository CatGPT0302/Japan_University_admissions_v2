export type NavPage = "run" | "review" | "records" | "exports" | "bookings" | "quality";
export type OwnerPage = NavPage;
export type AppRole = "owner_admin" | "partner_staff";

export interface AppUser {
  id: number;
  organization_id: number;
  organization_name: string;
  email: string;
  display_name: string;
  role: AppRole;
  status: string;
}

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

export interface AgentSource {
  input_kind: "file_name" | "pdf_url" | "page_url" | "search" | string;
  file_name?: string;
  selected_pdf_url?: string;
  selected_page_url?: string;
  selection_reason?: string;
  query?: string;
  candidates?: FetchPdfCandidate[];
}

export interface AgentDraftJson {
  status: string;
  doc_id?: number | null;
  source: AgentSource;
  records: number;
  quality_status?: "ok" | "needs_review" | "failed";
  quality_message?: string;
  warnings?: string[];
  review_required: boolean;
  next_step: "human_review" | string;
}

export interface AgentRunSuccessResponse {
  status: string;
  doc_id: number;
  source: AgentSource;
  records: number;
  quality_status?: "ok" | "needs_review" | "failed";
  quality_message?: string;
  warnings?: string[];
  draft_json: AgentDraftJson;
}

export interface AgentNeedsSourceConfirmationResponse {
  status: "needs_source_confirmation";
  candidates: FetchPdfCandidate[];
  university: string;
  year: string;
  source?: AgentSource;
}

export type AgentRunResponse = AgentRunSuccessResponse | AgentNeedsSourceConfirmationResponse;

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

export interface QualityOverviewResponse {
  overall_status: string;
  language_requirement_coverage: Record<string, { checked: number; passed: number }>;
  per_seed_thin_coverage: Array<{ seed: string; field: string; checked: number; minimum: number }>;
  quality_todo: Array<{
    priority?: number;
    action?: string;
    field?: string;
    seed?: string;
    checked?: number;
    minimum?: number;
    details?: string;
  }>;
  next_owner_action?: Record<string, unknown> | null;
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

export interface SourceReviewItem {
  item_id: string;
  stem: string;
  university: string;
  admission_year: string;
  admission_type: string;
  source_type?: string;
  source_url: string;
  status: "changed" | "failed" | "marker_mismatch" | "not_pdf" | string;
  old_sha256?: string;
  new_sha256?: string;
  checked_at: string;
  error?: string;
  missing_markers?: string[];
  recommended_action: string;
  status_label?: string;
  owner_summary?: string;
  likely_changed_areas?: string[];
  next_steps?: string[];
  attention_level?: "needs_review" | "source_check" | "watch" | string;
  review_status: "open" | "reviewed" | "needs_reextract" | "deferred" | string;
  review_note?: string;
  review_updated_at?: string;
  confirmed_records_unchanged: boolean;
}

export interface SourceReviewResponse {
  generated_at: string;
  summary: {
    needs_review: number;
    changed?: number;
    failed?: number;
    marker_mismatch?: number;
    not_pdf?: number;
    open?: number;
    reviewed?: number;
    needs_reextract?: number;
    deferred?: number;
    [key: string]: number | undefined;
  };
  items: SourceReviewItem[];
  confirmed_records_unchanged: boolean;
}

export interface SourceWatchlistItem {
  stem: string;
  id: string;
  university: string;
  admission_year: string;
  admission_type: string;
  source_type: string;
  source_url: string;
  cached_path: string;
  source_candidates: string[];
  last_known_sha256: string;
  last_checked_at: string;
  check_status?: "never_checked" | "stale" | "recent" | string;
  days_since_checked?: number | null;
  source_note: string;
  markers: string[];
  receipt_status: string;
}

export interface SourceWatchlistResponse {
  summary: {
    total: number;
    by_type: Record<string, number>;
    metadata_gaps: Record<string, number>;
    stale_check_days?: number;
    oldest_checked_at?: string;
  };
  items: SourceWatchlistItem[];
}

export interface SourceCheckRunResponse {
  checked_at: string;
  summary: Record<string, number>;
  review_queue: SourceReviewResponse;
}

export interface SourceReviewStateResponse {
  item_id: string;
  review_status: "open" | "reviewed" | "needs_reextract" | "deferred" | string;
  note: string;
  updated_at: string;
}

export interface SourceReviewReextractResponse {
  status: string;
  doc_id?: number | null;
  records: number;
  quality_status?: "ok" | "needs_review" | "failed";
  review_required: boolean;
  source?: AgentSource;
}

export interface SourceReviewAcceptResponse {
  status: "accepted" | string;
  receipt: {
    stem: string;
    old_sha256: string;
    sha256: string;
    accepted_at: string;
    confirmed_records_unchanged: boolean;
  };
  review_state: SourceReviewStateResponse;
  confirmed_records_unchanged: boolean;
}

export interface UploadResponse {
  file_name: string;
  original_file_name?: string;
  saved_path: string;
}

export interface ExtractResponse {
  doc_id: number;
  status: string;
  university?: string;
  records: number;
  failed_pages: Array<{ page: number; error: string }>;
  quality_status?: "ok" | "needs_review" | "failed";
  quality_message?: string;
  warnings?: string[];
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

export interface ExportPreviewResponse {
  summary: {
    records: number;
    universities: number;
    years: string[];
    faculties: number;
  };
  rows: ConfirmedRecord[];
}

export interface ExportOptionItem {
  value: string;
  count: number;
}

export interface ExportOptionsResponse {
  universities: ExportOptionItem[];
  years: ExportOptionItem[];
  faculties: ExportOptionItem[];
}

export type FitLevel = "likely_fit" | "check_carefully" | "high_risk";

export interface PublicProgramRisk {
  level: RiskLevel;
  reasons: string[];
}

export interface PublicProgram {
  id: number;
  school_name: string;
  admission_year: string;
  admission_period?: string;
  faculty: string;
  department: string;
  application_period?: string;
  deadline_rule?: string;
  exam_method?: string;
  exam_date?: string;
  result_date?: string;
  enrollment_period?: string;
  prefecture?: string;
  campus?: string;
  requirements: {
    eju: {
      session?: string;
      japanese?: string;
      general?: string;
      math?: string;
      physics?: string;
      chemistry?: string;
      biology?: string;
    };
    english: {
      raw_text?: string;
    };
    jlpt: {
      raw_text?: string;
    };
    eligibility?: string;
    required_documents: string[];
  };
  risk: PublicProgramRisk;
  risk_level?: RiskLevel;
  confidence?: number | null;
  evidence?: Record<string, { text?: string; page?: number | null; source?: string }>;
  source_document: {
    id?: number | null;
    file_name?: string;
    pdf_url?: string;
  };
}

export interface StudentProfile {
  target_year?: string;
  desired_fields: string[];
  preferred_prefectures: string[];
  english_tests: string[];
  eju_subjects: string[];
  japanese_level?: string;
  notes?: string;
}

export interface RecommendationResult {
  program: PublicProgram;
  score: number;
  fit_level: FitLevel;
  reasons: string[];
  check_items: string[];
}

export interface RecommendationResponse {
  profile: StudentProfile;
  results: RecommendationResult[];
}

export interface ConsultationBookingRequest {
  student_name: string;
  contact_email?: string;
  contact_phone?: string;
  role?: string;
  target_year?: string;
  program_id?: number | null;
  preferred_times?: string;
  question?: string;
}

export interface ConsultationBookingResponse {
  status: "received";
  id: number;
}

export type ConsultationBookingStatus = "new" | "contacted" | "done" | "closed";

export interface AdminConsultationBooking {
  id: number;
  student_name: string;
  contact_email?: string;
  contact_phone?: string;
  role?: string;
  target_year?: string;
  program_id?: number | null;
  preferred_times?: string;
  question?: string;
  status: ConsultationBookingStatus;
  owner_note?: string;
  next_action_at?: string;
  created_at: string;
  school_name?: string;
  faculty?: string;
  department?: string;
  admission_year?: string;
}

export interface ApiCenterKey {
  id: number;
  client_name: string;
  masked_key: string;
  scopes: string[];
  status: string;
  created_at: string;
  last_used_at?: string;
}

export interface ApiUsageLog {
  method: string;
  path: string;
  scope: string;
  status_code: number;
  created_at: string;
}

export interface ApiCenterResponse {
  organization: {
    id: number;
    name: string;
    status: string;
    plan: string;
  };
  settings: {
    api_base_url?: string;
    contact_email?: string;
    notes?: string;
  };
  api_keys: ApiCenterKey[];
  recent_usage: ApiUsageLog[];
  usage_summary: {
    total: number;
    success: number;
    needs_check: number;
    submission_total: number;
    submissions_by_status: Record<string, number>;
  };
  allowed_scopes: string[];
}

export interface ApiKeyCreateResponse {
  key_id: number;
  secret: string;
  masked_key: string;
  scopes: string[];
}

export type SubmissionStatus =
  | "submitted"
  | "processing"
  | "needs_owner_review"
  | "confirmed"
  | "needs_more_info"
  | "failed";

export interface AdminSubmission {
  id: number;
  organization_name: string;
  client_name?: string;
  university: string;
  admission_year?: string;
  pdf_url?: string;
  page_url?: string;
  file_name?: string;
  original_file_name?: string;
  notes?: string;
  processing_status: SubmissionStatus;
  status?: SubmissionStatus;
  document_id?: number | null;
  created_at: string;
  updated_at: string;
  workflow_status?: string;
  records?: number;
}
