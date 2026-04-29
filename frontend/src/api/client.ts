import axios from "axios";
import type {
  ConfirmResponse,
  ConfirmedRecord,
  CorrectionEvent,
  DocumentListItem,
  DocumentSummary,
  ExtractResponse,
  FetchPdfResponse,
  FetchPdfSearchResponse,
  FetchPdfProbeResponse,
  FetchPdfTarget,
  QualityMetricsResponse,
  StagingRecord,
  StatsResponse,
  UploadResponse,
} from "../types";

const envBaseUrl = String(import.meta.env.VITE_API_BASE_URL || "").trim().replace(/\/$/, "");
const BASE_URL = envBaseUrl || "http://127.0.0.1:8000";

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 120000,
});

function toErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail) return JSON.stringify(detail);
    return error.message;
  }
  return String(error);
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<UploadResponse>("/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function extractPdf(payload: {
  file_name: string;
  university: string;
  year: string;
  url?: string;
}): Promise<ExtractResponse> {
  const { data } = await client.post<ExtractResponse>("/extract", payload);
  return data;
}

export async function getFetchTargets(): Promise<FetchPdfTarget[]> {
  const { data } = await client.get<FetchPdfTarget[]>("/fetch-pdf/targets");
  return data;
}

export async function searchFetchPdf(payload: {
  university: string;
  year: string;
  page_url?: string;
}): Promise<FetchPdfSearchResponse> {
  const { data } = await client.post<FetchPdfSearchResponse>("/fetch-pdf/search", payload);
  return data;
}

export async function fetchPdf(payload: {
  university: string;
  year: string;
  page_url?: string;
  pdf_url?: string;
}): Promise<FetchPdfResponse> {
  const { data } = await client.post<FetchPdfResponse>("/fetch-pdf", payload);
  return data;
}

export async function probeFetchSources(year: number): Promise<FetchPdfProbeResponse> {
  const { data } = await client.get<FetchPdfProbeResponse>("/fetch-pdf/probe", {
    params: { year },
  });
  return data;
}

export async function getDocuments(params?: {
  q?: string;
  year?: string;
  limit?: number;
  offset?: number;
}): Promise<DocumentListItem[]> {
  const { data } = await client.get<DocumentListItem[]>("/documents", { params });
  return data;
}

export async function getDocumentSummary(docId: number): Promise<DocumentSummary> {
  const { data } = await client.get<DocumentSummary>(`/documents/${docId}/summary`);
  return data;
}

export function documentPdfUrl(docId: number, pageNumber?: number | null): string {
  const page = pageNumber ? `#page=${pageNumber}` : "";
  return `${BASE_URL}/documents/${docId}/pdf${page}`;
}

export function documentPageImageUrl(docId: number, pageNumber?: number | null, zoom = 1): string {
  const page = Math.max(Number(pageNumber || 1), 1);
  return `${BASE_URL}/documents/${docId}/page-image?page=${page}&zoom=${zoom}`;
}

export async function deleteDocument(docId: number): Promise<{
  status: string;
  doc_id: number;
  deleted_records: number;
  deleted_staging: number;
  deleted_pages: number;
}> {
  const { data } = await client.delete(`/documents/${docId}`);
  return data;
}

export async function getStaging(docId: number): Promise<StagingRecord[]> {
  const { data } = await client.get<StagingRecord[]>(`/staging/${docId}`);
  return data;
}

export async function patchStaging(stagingId: number, patch: Record<string, unknown>): Promise<StagingRecord> {
  const { data } = await client.patch<StagingRecord>(`/staging/${stagingId}`, { data: patch });
  return data;
}

export async function deleteStaging(stagingId: number): Promise<{ status: string; id: number }> {
  const { data } = await client.delete<{ status: string; id: number }>(`/staging/${stagingId}`);
  return data;
}

export async function createManualStaging(payload: {
  document_id: number;
  data: Record<string, unknown>;
}): Promise<{ id: number; status: string }> {
  const { data } = await client.post<{ id: number; status: string }>("/staging/manual", payload);
  return data;
}

export async function confirmDoc(docId: number): Promise<ConfirmResponse> {
  const { data } = await client.post<ConfirmResponse>(`/confirm/${docId}`);
  return data;
}

export async function getRecords(params?: {
  university?: string;
  year?: number;
  faculty?: string;
  limit?: number;
  offset?: number;
}): Promise<ConfirmedRecord[]> {
  const { data } = await client.get<ConfirmedRecord[]>("/records", { params });
  return data;
}

export async function getStats(): Promise<StatsResponse> {
  const { data } = await client.get<StatsResponse>("/stats");
  return data;
}

export async function getQualityMetrics(docId?: number): Promise<QualityMetricsResponse> {
  const { data } = await client.get<QualityMetricsResponse>("/metrics/quality", {
    params: docId ? { doc_id: docId } : undefined,
  });
  return data;
}

export async function getCorrectionEvents(params?: {
  doc_id?: number;
  limit?: number;
}): Promise<CorrectionEvent[]> {
  const { data } = await client.get<CorrectionEvent[]>("/metrics/corrections", {
    params,
  });
  return data;
}

export function downloadExcel(params?: { university?: string; year?: number; faculty?: string }): void {
  const search = new URLSearchParams();
  if (params?.university) search.set("university", params.university);
  if (params?.year) search.set("year", String(params.year));
  if (params?.faculty) search.set("faculty", params.faculty);
  const qs = search.toString();
  const url = `${BASE_URL}/export/excel${qs ? `?${qs}` : ""}`;
  window.open(url, "_blank");
}

export async function checkHealth(): Promise<boolean> {
  try {
    const { data } = await client.get<{ status: string }>("/health");
    return data?.status === "healthy";
  } catch {
    return false;
  }
}

export { toErrorMessage };
