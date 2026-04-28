import { useEffect, useMemo, useRef, useState } from "react";
import {
  extractPdf,
  fetchPdf,
  getFetchTargets,
  probeFetchSources,
  searchFetchPdf,
  toErrorMessage,
  uploadPdf,
} from "../api/client";
import type {
  FetchPdfCandidate,
  FetchPdfProbeResponse,
  FetchPdfTarget,
} from "../types";

interface Props {
  onDone: (docId: number) => void;
}

type SourceMode = "upload" | "search" | "direct";
type Step =
  | "idle"
  | "searching"
  | "downloading"
  | "uploading"
  | "extracting"
  | "done"
  | "error";

interface RunResult {
  doc_id: number;
  records: number;
  failed: number;
  university?: string;
  file_name?: string;
  source_url?: string;
}

function modeTitle(mode: SourceMode): string {
  if (mode === "upload") return "Local PDF upload";
  if (mode === "search") return "Guided PDF search";
  return "Direct PDF link";
}

function stepLabel(step: Step): string {
  if (step === "searching") return "Searching";
  if (step === "downloading") return "Downloading";
  if (step === "uploading") return "Uploading";
  if (step === "extracting") return "Extracting";
  if (step === "done") return "Ready for review";
  if (step === "error") return "Needs attention";
  return "Waiting";
}

function candidateKindLabel(candidate: FetchPdfCandidate): string {
  if (candidate.source_kind === "registry_pdf") return "Registry PDF";
  if (candidate.source_kind === "registry_page_pdf") return "Registry source page";
  if (candidate.source_kind === "direct_pdf") return "Direct PDF";
  return "Discovered source";
}

function candidateTrustLabel(candidate: FetchPdfCandidate): string {
  if (candidate.source_origin === "maintained_registry") return "Maintained source";
  if (candidate.is_official) return "Likely official";
  return "Needs manual check";
}

export default function RunPage({ onDone }: Props) {
  const [sourceMode, setSourceMode] = useState<SourceMode>("upload");
  const [targets, setTargets] = useState<FetchPdfTarget[]>([]);
  const [selectedTarget, setSelectedTarget] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [university, setUniversity] = useState("");
  const [year, setYear] = useState("2026");
  const [pageUrl, setPageUrl] = useState("");
  const [pdfUrl, setPdfUrl] = useState("");
  const [step, setStep] = useState<Step>("idle");
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [candidates, setCandidates] = useState<FetchPdfCandidate[]>([]);
  const [selectedCandidateUrl, setSelectedCandidateUrl] = useState("");
  const [probeResult, setProbeResult] = useState<FetchPdfProbeResponse | null>(null);
  const [probeLoading, setProbeLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void loadTargets();
  }, []);

  async function loadTargets() {
    try {
      setTargets(await getFetchTargets());
    } catch {
      setTargets([]);
    }
  }

  function resetRunState(options?: { keepCandidates?: boolean }) {
    setStep("idle");
    setResult(null);
    setError("");
    if (!options?.keepCandidates) {
      setCandidates([]);
      setSelectedCandidateUrl("");
      setSearchQuery("");
    }
  }

  function handleFile(nextFile: File | null) {
    if (!nextFile || !nextFile.name.toLowerCase().endsWith(".pdf")) return;
    setFile(nextFile);
    resetRunState();
  }

  async function runUpload() {
    if (!file) return;
    setError("");
    setResult(null);
    try {
      setStep("uploading");
      const uploaded = await uploadPdf(file);
      setStep("extracting");
      const extracted = await extractPdf({
        file_name: uploaded.file_name,
        university: "",
        year,
      });
      setResult({
        doc_id: extracted.doc_id,
        records: extracted.records,
        failed: extracted.failed_pages?.length ?? 0,
        university: extracted.university || "",
        file_name: uploaded.file_name,
      });
      setStep("done");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  async function runSearch() {
    if (!university) return;
    setError("");
    setResult(null);
    setCandidates([]);
    setSelectedCandidateUrl("");
    try {
      setStep("searching");
      const searched = await searchFetchPdf({
        university,
        year,
        page_url: pageUrl || undefined,
      });
      setSearchQuery(searched.query);
      setCandidates(searched.candidates || []);
      if (searched.candidates?.length) {
        setSelectedCandidateUrl(searched.candidates[0].pdf_url);
        setStep("idle");
      } else {
        setError("No usable PDF candidates were found. Try refining the university name, adding a source page, or switch to direct PDF mode.");
        setStep("error");
      }
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  async function runProbe() {
    setProbeLoading(true);
    setError("");
    try {
      const probe = await probeFetchSources(Number(year) || 2026);
      setProbeResult(probe);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setProbeLoading(false);
    }
  }

  async function processPdfCandidate(candidate: FetchPdfCandidate) {
    setError("");
    setResult(null);
    try {
      setStep("downloading");
      const fetched = await fetchPdf({
        university,
        year,
        page_url: candidate.page_url || pageUrl || undefined,
        pdf_url: candidate.pdf_url,
      });
      setStep("extracting");
      const extracted = await extractPdf({
        file_name: fetched.file_name,
        university,
        year,
        url: fetched.source_url || candidate.pdf_url,
      });
      setResult({
        doc_id: extracted.doc_id,
        records: extracted.records,
        failed: extracted.failed_pages?.length ?? 0,
        university: extracted.university || university,
        file_name: fetched.file_name,
        source_url: fetched.source_url || candidate.pdf_url,
      });
      setStep("done");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  async function runDirectPdf() {
    if (!university || !pdfUrl) return;
    setError("");
    setResult(null);
    try {
      setStep("downloading");
      const fetched = await fetchPdf({
        university,
        year,
        page_url: pageUrl || undefined,
        pdf_url: pdfUrl,
      });
      setStep("extracting");
      const extracted = await extractPdf({
        file_name: fetched.file_name,
        university,
        year,
        url: fetched.source_url || pdfUrl,
      });
      setResult({
        doc_id: extracted.doc_id,
        records: extracted.records,
        failed: extracted.failed_pages?.length ?? 0,
        university: extracted.university || university,
        file_name: fetched.file_name,
        source_url: fetched.source_url || pdfUrl,
      });
      setStep("done");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  const busy =
    step === "searching" ||
    step === "downloading" ||
    step === "uploading" ||
    step === "extracting";
  const readyToUpload = Boolean(file && !busy);
  const readyToSearch = Boolean(university && !busy);
  const selectedCandidate =
    candidates.find((item) => item.pdf_url === selectedCandidateUrl) || null;
  const readyToConfirmCandidate = Boolean(selectedCandidate && !busy);
  const readyToDirectRun = Boolean(university && pdfUrl && !busy);

  const statusBlock = useMemo(() => {
    if (step === "done" && result) {
      return {
        tone: "success" as const,
        title: `${result.records} extracted rows are ready for review`,
        description:
          result.failed > 0
            ? `${result.failed} page(s) still need attention. Send this document to Review next so the risky parts are handled first.`
            : `The extraction completed cleanly. Move to Review to validate fields before confirmation.`,
      };
    }
    if (step === "error") {
      return {
        tone: "danger" as const,
        title: "This intake run needs intervention",
        description:
          "The source page, PDF link, or uploaded file could not be processed. Adjust the source path and retry without affecting backend data.",
      };
    }
    if (step === "searching") {
      return {
        tone: "info" as const,
        title: "Searching for candidate PDFs",
        description:
          "The system is gathering likely admissions PDFs first. Nothing is confirmed until you choose a candidate.",
      };
    }
    if (step === "downloading") {
      return {
        tone: "info" as const,
        title: "Fetching source PDF",
        description:
          "Once the file lands successfully, extraction continues automatically.",
      };
    }
    if (step === "uploading") {
      return {
        tone: "info" as const,
        title: "Uploading file into intake",
        description:
          "The PDF is being staged for extraction. No database schema or downstream records are changed here.",
      };
    }
    if (step === "extracting") {
      return {
        tone: "info" as const,
        title: "Normalizing fields for the review queue",
        description:
          "Admissions data is being turned into reviewable rows with evidence and confidence metadata.",
      };
    }
    return {
      tone: "neutral" as const,
      title: sourceMode === "search" ? "Search, compare, then confirm one source" : "Start the next intake run",
      description:
        sourceMode === "upload"
          ? "Best when operations already has the official PDF locally and wants the fastest route into staging."
          : sourceMode === "direct"
            ? "Best when the exact PDF URL is already known and you want to skip discovery."
            : "Best when the source still needs to be found and compared before extraction starts.",
    };
  }, [result, sourceMode, step]);

  const modeCards: Array<{ key: SourceMode; title: string; desc: string; kicker: string }> = [
    {
      key: "upload",
      title: "Upload an official PDF",
      desc: "Fastest path for known files. Drag in the source and let the system detect the university automatically.",
      kicker: "Fast lane",
    },
    {
      key: "search",
      title: "Search and shortlist",
      desc: "Use registry targets and guided search to compare candidate PDFs before one is processed.",
      kicker: "Controlled discovery",
    },
    {
      key: "direct",
      title: "Use a direct PDF URL",
      desc: "Paste the exact document link when the team already verified the source outside the app.",
      kicker: "Manual precision",
    },
  ];

  const statusToneClass = `tone-banner ${statusBlock.tone}`;

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="hero-grid">
          <div>
            <div className="section-eyebrow">Step 1 · Run</div>
            <h2 className="section-title">Intake and extraction</h2>
            <p className="section-copy">
              Start each admissions document with a clean intake path. This view now frames the workflow like an internal
              operations dashboard: choose the source lane, confirm the file, then hand off structured rows to Review.
            </p>
          </div>

          <div className="progress-stack">
            <div className="mini-stat">
              <span className="mini-stat-label">Current lane</span>
              <span className="mini-stat-value">{modeTitle(sourceMode)}</span>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Run status</span>
              <span className="mini-stat-value">{stepLabel(step)}</span>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Review handoff</span>
              <span className="mini-stat-value">{result ? "Prepared" : "Pending"}</span>
            </div>
          </div>
        </div>
      </section>

      <section className={statusToneClass}>
        <div>
          <h3 className="tone-title">{statusBlock.title}</h3>
          <p className="tone-copy">{statusBlock.description}</p>
        </div>
        <div className="status-grid">
          <div className="status-pill">
            <span>Mode</span>
            <strong>{modeTitle(sourceMode)}</strong>
          </div>
          <div className="status-pill">
            <span>University</span>
            <strong>{sourceMode === "upload" ? result?.university || "Auto detect" : university || "Not set"}</strong>
          </div>
          <div className="status-pill">
            <span>Year</span>
            <strong>{year || "Not set"}</strong>
          </div>
          <div className="status-pill">
            <span>Workflow</span>
            <strong>{stepLabel(step)}</strong>
          </div>
        </div>
      </section>

      <section className="mode-grid">
        {modeCards.map((item) => {
          const active = sourceMode === item.key;
          return (
            <button
              key={item.key}
              className={`mode-card${active ? " is-active" : ""}`}
              onClick={() => {
                setSourceMode(item.key);
                resetRunState();
              }}
              type="button"
            >
              <span className="mode-kicker">{item.kicker}</span>
              <div className="mode-title">{item.title}</div>
              <div className="mode-copy">{item.desc}</div>
            </button>
          );
        })}
      </section>

      <section className="panel">
        <div className="toolbar-flex" style={{ marginBottom: 14 }}>
          <div>
            <h3 className="panel-title">Source configuration</h3>
            <p className="panel-copy">
              Keep the source clear before extraction starts. The layout stays visual, but the backend contract remains untouched.
            </p>
          </div>
          <span className="badge badge-gray">{sourceMode === "search" ? "Human approval required" : "Single source path"}</span>
        </div>

        <div className="input-grid">
          {sourceMode === "upload" ? (
            <div className="field-wrap input-span-2">
              <span className="field-label">University detection</span>
              <div className="summary-box" style={{ background: "rgba(241, 245, 249, 0.9)", border: "1px solid rgba(148, 163, 184, 0.18)" }}>
                <strong style={{ display: "block", marginBottom: 6 }}>Auto detected from the uploaded PDF</strong>
                <span className="helper-text" style={{ color: "var(--ink2)" }}>
                  Upload mode is intentionally light on manual inputs so the ops team can move quickly and fix anything later in Review.
                </span>
              </div>
            </div>
          ) : (
            <label className="field-wrap">
              <span className="field-label">University</span>
              <input
                value={university}
                onChange={(event) => {
                  setUniversity(event.target.value);
                  resetRunState();
                }}
                placeholder="Example: Meiji University"
                className="field"
              />
            </label>
          )}

          <label className="field-wrap">
            <span className="field-label">Admission year</span>
            <input
              value={year}
              onChange={(event) => {
                setYear(event.target.value);
                resetRunState();
              }}
              placeholder="2026"
              className="field"
            />
          </label>

          {sourceMode === "search" && (
            <>
              <label className="field-wrap">
                <span className="field-label">Registry shortcut</span>
                <select
                  value={selectedTarget}
                  onChange={(event) => {
                    const next = event.target.value;
                    const matched = targets.find((item) => item.name === next);
                    setSelectedTarget(next);
                    if (next) setUniversity(next);
                    setPageUrl(matched?.url || "");
                    resetRunState();
                  }}
                  className="field-select"
                >
                  <option value="">Optional preset</option>
                  {targets.map((target) => (
                    <option key={target.name} value={target.name}>
                      {target.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field-wrap">
                <span className="field-label">Source page URL</span>
                <input
                  value={pageUrl}
                  onChange={(event) => {
                    setPageUrl(event.target.value);
                    resetRunState();
                  }}
                  placeholder="Optional but improves source quality"
                  className="field"
                />
              </label>
            </>
          )}

          {sourceMode === "direct" && (
            <>
              <label className="field-wrap input-span-2">
                <span className="field-label">Direct PDF URL</span>
                <input
                  value={pdfUrl}
                  onChange={(event) => {
                    setPdfUrl(event.target.value);
                    resetRunState();
                  }}
                  placeholder="https://example.edu/guideline.pdf"
                  className="field"
                />
              </label>

              <label className="field-wrap input-span-2">
                <span className="field-label">Origin page URL</span>
                <input
                  value={pageUrl}
                  onChange={(event) => {
                    setPageUrl(event.target.value);
                    resetRunState();
                  }}
                  placeholder="Optional landing page for traceability"
                  className="field"
                />
              </label>
            </>
          )}
        </div>
      </section>

      {sourceMode === "upload" && (
        <>
          <section
            className={`dropzone${dragging ? " is-dragging" : ""}${file ? " is-filled" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              handleFile(event.dataTransfer.files[0]);
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              style={{ display: "none" }}
              onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
            />
            <div className="dropzone-icon">{file ? "✓" : "PDF"}</div>
            <h3 className="dropzone-title">{file ? file.name : "Drop a source PDF here"}</h3>
            <p className="dropzone-copy">
              {file
                ? "The file is staged locally. Use the action below to start extraction and produce review rows."
                : "Click or drag in the official admissions PDF. Uploading only starts when you explicitly run intake."}
            </p>
          </section>

          <section className="panel">
            <div className="toolbar-flex">
              <div>
                <h3 className="panel-title">Upload lane action</h3>
                <p className="panel-copy">
                  This lane is optimized for operations teams who already have the authoritative file and want the shortest handoff into staging.
                </p>
              </div>
              <button className="btn btn-primary" disabled={!readyToUpload} onClick={() => void runUpload()} type="button">
                {step === "uploading" || step === "extracting" ? "Processing..." : "Start extraction"}
              </button>
            </div>
          </section>
        </>
      )}

      {sourceMode === "search" && (
        <section className="panel">
          <div className="toolbar-flex" style={{ marginBottom: 16 }}>
            <div>
              <h3 className="panel-title">Search before processing</h3>
              <p className="panel-copy">
                Keep the workflow safe: shortlist candidate PDFs first, then manually choose the source that should flow into staging.
              </p>
            </div>
            <div className="inline-actions">
              <button className="btn btn-primary" disabled={!readyToSearch} onClick={() => void runSearch()} type="button">
                {step === "searching" ? "Searching..." : "Find candidate PDFs"}
              </button>
              <button className="btn btn-ghost" disabled={probeLoading || busy} onClick={() => void runProbe()} type="button">
                {probeLoading ? "Checking..." : "Probe maintained sources"}
              </button>
            </div>
          </div>

          {probeResult && (
            <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.95)", border: "1px solid rgba(148, 163, 184, 0.18)", marginBottom: 14 }}>
              <div className="split-row" style={{ marginBottom: 8 }}>
                <strong>Source probe summary</strong>
                <span className="muted-text mono">{probeResult.checked_at}</span>
              </div>
              <div className="status-grid" style={{ marginBottom: 12 }}>
                <div className="status-pill">
                  <span>Targets</span>
                  <strong>{probeResult.target_count}</strong>
                </div>
                <div className="status-pill">
                  <span>New PDFs</span>
                  <strong>{probeResult.new_candidate_count}</strong>
                </div>
                <div className="status-pill">
                  <span>Errors</span>
                  <strong>{probeResult.error_count}</strong>
                </div>
                <div className="status-pill">
                  <span>Year</span>
                  <strong>{probeResult.year}</strong>
                </div>
              </div>
              <div className="correction-stack">
                {probeResult.probes
                  .filter((item) => item.is_new_pdf_candidate || item.status === "error")
                  .slice(0, 8)
                  .map((item) => (
                    <div key={`${item.university}-${item.seed_url}`} className="candidate-card">
                      <div className="candidate-head">
                        <div>
                          <h4 className="candidate-title">{item.university}</h4>
                          <div className="candidate-meta">{item.status}</div>
                        </div>
                        {item.top_candidate_pdf && (
                          <a className="btn btn-ghost" href={item.top_candidate_pdf} target="_blank" rel="noreferrer">
                            Open candidate
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                {probeResult.probes.every((item) => !item.is_new_pdf_candidate && item.status !== "error") && (
                  <div className="empty-state">
                    <h4 className="empty-title">No notable source changes</h4>
                    <p className="empty-copy">The maintained source set looks stable for this probe window.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {searchQuery && (
            <div className="message-box info" style={{ marginBottom: 14 }}>
              Search query used: <span className="mono">{searchQuery}</span>
            </div>
          )}

          {candidates.length > 0 && (
            <div className="candidate-stack">
              {candidates.map((candidate, index) => {
                const active = selectedCandidateUrl === candidate.pdf_url;
                return (
                  <label key={candidate.pdf_url} className={`candidate-card${active ? " is-active" : ""}`}>
                    <div className="candidate-head">
                      <div style={{ display: "flex", gap: 12, minWidth: 0 }}>
                        <input
                          type="radio"
                          name="pdf-candidate"
                          checked={active}
                          onChange={() => setSelectedCandidateUrl(candidate.pdf_url)}
                          style={{ marginTop: 2 }}
                        />
                        <div>
                          <h4 className="candidate-title">Candidate {index + 1}</h4>
                          <div className="candidate-meta">{candidate.title || candidate.pdf_url}</div>
                        </div>
                      </div>

                      <div className="inline-actions">
                        <span className={candidate.is_official ? "badge badge-green" : "badge badge-amber"}>{candidateTrustLabel(candidate)}</span>
                        <span className="badge badge-gray">{candidateKindLabel(candidate)}</span>
                        <span className="badge badge-blue">Score {candidate.score}</span>
                      </div>
                    </div>

                    <div className="info-grid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 12 }}>
                      <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.9)", border: "1px solid rgba(148, 163, 184, 0.16)" }}>
                        <div className="field-label">PDF URL</div>
                        <div className="muted-text mono">{candidate.pdf_url}</div>
                      </div>
                      <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.9)", border: "1px solid rgba(148, 163, 184, 0.16)" }}>
                        <div className="field-label">Source page</div>
                        <div className="muted-text mono">{candidate.page_url || "Not provided"}</div>
                      </div>
                    </div>

                    <div className="candidate-meta" style={{ marginTop: 10 }}>
                      {candidate.host ? `Host: ${candidate.host}. ` : ""}
                      {candidate.registry_note ? `Registry note: ${candidate.registry_note}` : "Manual review stays in control until you confirm this source."}
                    </div>

                    <div className="inline-actions" style={{ marginTop: 12 }}>
                      <a
                        href={candidate.pdf_url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-ghost"
                        onClick={(event) => event.stopPropagation()}
                      >
                        Preview PDF
                      </a>
                      {candidate.page_url && candidate.page_url !== candidate.pdf_url && (
                        <a
                          href={candidate.page_url}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-ghost"
                          onClick={(event) => event.stopPropagation()}
                        >
                          Open source page
                        </a>
                      )}
                    </div>
                  </label>
                );
              })}

              <div className="toolbar-flex">
                <p className="panel-copy" style={{ maxWidth: 720 }}>
                  Candidate confirmation is the safety checkpoint in this workflow. Extraction only starts after a person explicitly approves the selected PDF.
                </p>
                <button
                  className="btn btn-primary"
                  disabled={!readyToConfirmCandidate}
                  onClick={() => selectedCandidate && void processPdfCandidate(selectedCandidate)}
                  type="button"
                >
                  {step === "downloading" || step === "extracting" ? "Processing..." : "Confirm source and extract"}
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {sourceMode === "direct" && (
        <section className="panel">
          <div className="toolbar-flex">
            <div>
              <h3 className="panel-title">Direct source run</h3>
              <p className="panel-copy">
                Use this only when the team already has a verified PDF URL and wants a predictable one-step handoff into extraction.
              </p>
            </div>
            <button className="btn btn-primary" disabled={!readyToDirectRun} onClick={() => void runDirectPdf()} type="button">
              {step === "downloading" || step === "extracting" ? "Processing..." : "Process direct PDF"}
            </button>
          </div>
        </section>
      )}

      {step === "done" && result && (
        <section className="tone-banner success">
          <div>
            <h3 className="tone-title">Review handoff is ready</h3>
            <p className="tone-copy">
              {result.records} rows were staged
              {result.university ? ` for ${result.university}` : ""}.{" "}
              {result.failed > 0
                ? `${result.failed} page(s) still need closer review.`
                : "No obvious failed pages were reported in this run."}
            </p>
          </div>
          <div className="inline-actions">
            <button className="btn btn-green" onClick={() => onDone(result.doc_id)} type="button">
              Open Review
            </button>
            {result.source_url && (
              <a href={result.source_url} target="_blank" rel="noreferrer" className="btn btn-ghost">
                Open source
              </a>
            )}
          </div>
        </section>
      )}

      {step === "error" && (
        <section className="message-box error">
          {error || "This intake attempt could not be completed. Check the source inputs and retry."}
        </section>
      )}

      <section className="panel">
        <div className="toolbar-flex">
          <div>
            <h3 className="panel-title">Recommended operator flow</h3>
            <p className="panel-copy">
              Use upload when you already own the file, search when the source still needs human approval, and direct mode when the PDF URL is already trusted.
            </p>
          </div>
          <span className="badge badge-gray">No backend logic changes</span>
        </div>
      </section>
    </div>
  );
}
