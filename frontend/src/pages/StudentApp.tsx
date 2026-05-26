import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createConsultationBooking,
  getPublicProgram,
  getPublicPrograms,
  getPublicRecommendations,
  toErrorMessage,
} from "../api/client";
import type {
  PublicProgram,
  RecommendationResult,
  StudentProfile,
} from "../types";

type ResultSource = "recommendation" | "browse";
type StudentTab = "explore" | "match" | "detail";
type PickerKey = "fields" | "areas" | "english" | "eju" | "keywords";

type DisplayResult = RecommendationResult & {
  source: ResultSource;
};

const TABS: Array<{ key: StudentTab; label: string; hint: string }> = [
  { key: "match", label: "填情况", hint: "成绩与方向" },
  { key: "explore", label: "看学校", hint: "适合先看" },
  { key: "detail", label: "看要求", hint: "时间与条件" },
];

const QUICK_FIELDS = ["商学", "社会", "国际", "经济", "理工", "文学"];
const QUICK_AREAS = ["东京", "神奈川", "大阪", "京都", "埼玉", "千叶"];
const QUICK_EJU = ["日本语", "数学", "综合科目", "物理", "化学", "生物"];
const QUICK_ENGLISH = ["TOEFL", "IELTS", "TOEIC", "英检"];
const QUICK_KEYWORDS = ["面试", "书类选考", "小论文", "私费外国人", "秋入学", "首都圈"];

function splitTerms(value: string): string[] {
  return value
    .split(/[,，、\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toggleTerm(value: string, current: string): string {
  const terms = splitTerms(current);
  if (terms.includes(value)) return terms.filter((item) => item !== value).join(", ");
  return [...terms, value].join(", ");
}

function textOrPending(value?: string | null): string {
  const text = String(value || "").trim();
  return text || "资料里暂时没有写清楚";
}

function programSearchText(program: PublicProgram): string {
  const eju = program.requirements?.eju ?? {};
  return [
    program.school_name,
    program.faculty,
    program.department,
    program.admission_year,
    program.prefecture,
    program.campus,
    program.exam_method,
    program.deadline_rule,
    program.admission_period,
    program.enrollment_period,
    program.requirements?.english?.raw_text,
    program.requirements?.jlpt?.raw_text,
    program.requirements?.eligibility,
    ...(program.requirements?.required_documents || []),
    ...Object.values(eju),
  ]
    .join(" ")
    .toLowerCase();
}

function fallbackResult(program: PublicProgram): DisplayResult {
  return {
    program,
    score: 0,
    fit_level: "check_carefully",
    reasons: ["可以先看。"],
    check_items: [],
    source: "browse",
  };
}

function includesTerm(text: string, term: string): boolean {
  return text.includes(term.trim().toLowerCase());
}

function matchFirst(text: string, terms: string[]): string {
  return terms.find((term) => includesTerm(text, term)) || "";
}

function profileMatchResult(program: PublicProgram, profile: StudentProfile, keywordText: string): DisplayResult | null {
  const searchText = programSearchText(program);
  const reasons: string[] = [];
  let score = 0;

  const year = String(profile.target_year || "").trim();
  if (year) {
    const programYear = String(program.admission_year || "").toLowerCase();
    if (programYear && !programYear.includes(year.toLowerCase())) return null;
    if (programYear.includes(year.toLowerCase())) {
      score += 14;
      reasons.push(`${year} 年度可以先看`);
    }
  }

  const field = matchFirst(searchText, profile.desired_fields || []);
  if (profile.desired_fields?.length) {
    if (!field) return null;
    score += 24;
    reasons.push(`方向里有「${field}」`);
  }

  const area = matchFirst(searchText, profile.preferred_prefectures || []);
  if (profile.preferred_prefectures?.length) {
    if (!area) return null;
    score += 20;
    reasons.push(`地区接近「${area}」`);
  }

  const english = matchFirst(searchText, profile.english_tests || []);
  if (profile.english_tests?.length) {
    if (!english) return null;
    score += 16;
    reasons.push(`英语要求提到「${english}」`);
  }

  const eju = matchFirst(searchText, profile.eju_subjects || []);
  if (profile.eju_subjects?.length) {
    if (!eju) return null;
    score += 16;
    reasons.push(`EJU 条件提到「${eju}」`);
  }

  const japaneseTerms = splitTerms(profile.japanese_level || "");
  const japanese = matchFirst(searchText, japaneseTerms);
  if (japaneseTerms.length && japanese) {
    score += 10;
    reasons.push(`日语条件提到「${japanese}」`);
  }

  const keywords = splitTerms(keywordText);
  const keyword = matchFirst(searchText, keywords);
  if (keywords.length) {
    if (!keyword) return null;
    score += 18;
    reasons.push(`关键词命中「${keyword}」`);
  }

  const noteKeyword = matchFirst(searchText, splitTerms(profile.notes || ""));
  if (noteKeyword) {
    score += 6;
    reasons.push(`补充说明提到「${noteKeyword}」`);
  }

  return {
    program,
    score,
    fit_level: score >= 62 ? "likely_fit" : "check_carefully",
    reasons: reasons.length ? reasons.slice(0, 3) : ["可以先看。"],
    check_items: [],
    source: "browse",
  };
}

function friendlyReasons(item: DisplayResult): string[] {
  if (item.source === "browse" && item.score === 0) return [];
  return item.reasons.slice(0, 2);
}

function formatProgramName(program: PublicProgram): string {
  const parts = [program.faculty, program.department].filter((item) => String(item || "").trim());
  return parts.length ? parts.join(" / ") : "可查看的方向";
}

function requirementRows(program: PublicProgram): Array<{ label: string; value: string }> {
  const eju = program.requirements?.eju ?? {};
  return [
    { label: "出愿时间", value: textOrPending(program.application_period) },
    { label: "选考方式", value: textOrPending(program.exam_method) },
    { label: "考试日期", value: textOrPending(program.exam_date) },
    { label: "合格发表", value: textOrPending(program.result_date) },
    { label: "EJU 日本语", value: textOrPending(eju.japanese) },
    { label: "EJU 数学", value: textOrPending(eju.math) },
    { label: "EJU 其他科目", value: textOrPending([eju.general, eju.physics, eju.chemistry, eju.biology].filter(Boolean).join(" / ")) },
    { label: "英语要求", value: textOrPending(program.requirements?.english?.raw_text) },
  ];
}

function preparationItems(program: PublicProgram, recommendedItems?: string[]): string[] {
  const eju = program.requirements?.eju ?? {};
  const items = [...(recommendedItems || [])];
  if (program.application_period) items.push(`确认出愿时间：${program.application_period}`);
  if (program.deadline_rule) items.push(`留意截止规则：${program.deadline_rule}`);
  const ejuText = [eju.session, eju.japanese, eju.general, eju.math, eju.physics, eju.chemistry, eju.biology].filter(Boolean).join(" / ");
  if (ejuText) items.push(`准备 EJU：${ejuText}`);
  if (program.requirements?.english?.raw_text) items.push(`准备英语成绩：${program.requirements.english.raw_text}`);
  if (program.exam_method) items.push(`确认校内考方式：${program.exam_method}`);
  if (program.exam_date) items.push(`确认考试时间：${program.exam_date}`);
  return Array.from(new Set(items.map((item) => item.trim()).filter(Boolean))).slice(0, 6);
}

function ChoicePicker({
  label,
  value,
  options,
  expanded,
  placeholder,
  onChange,
  onToggle,
}: {
  label: string;
  value: string;
  options: string[];
  expanded: boolean;
  placeholder: string;
  onChange: (value: string) => void;
  onToggle: () => void;
}) {
  const selected = splitTerms(value);
  const summary = selected.length ? selected.join("、") : "还没选择";

  return (
    <div className={`student-choice${expanded ? " is-open" : ""}`}>
      <button className="student-choice-row" type="button" onClick={onToggle} aria-expanded={expanded}>
        <span>
          <strong>{label}</strong>
          <small>{summary}</small>
        </span>
        <b aria-hidden="true">{expanded ? "−" : "+"}</b>
      </button>
      {expanded ? (
        <div className="student-choice-body">
          <div className="student-chip-group" aria-label={`${label}选项`}>
            {options.map((item) => (
              <button
                className={selected.includes(item) ? "is-selected" : ""}
                type="button"
                key={item}
                onClick={() => onChange(toggleTerm(item, value))}
              >
                {item}
              </button>
            ))}
          </div>
          <label className="student-field student-choice-custom">
            <span>补充输入</span>
            <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
          </label>
        </div>
      ) : null}
    </div>
  );
}

export default function StudentApp() {
  const [activeTab, setActiveTab] = useState<StudentTab>("match");
  const [targetYear, setTargetYear] = useState("2027");
  const [desiredFieldsText, setDesiredFieldsText] = useState("商学, 社会, 国际");
  const [prefecturesText, setPrefecturesText] = useState("东京, 神奈川");
  const [englishTestsText, setEnglishTestsText] = useState("TOEFL, IELTS");
  const [ejuSubjectsText, setEjuSubjectsText] = useState("日本语, 数学");
  const [profileKeywordsText, setProfileKeywordsText] = useState("");
  const [submittedKeywordsText, setSubmittedKeywordsText] = useState("");
  const [japaneseLevel, setJapaneseLevel] = useState("");
  const [notes, setNotes] = useState("");
  const [searchText, setSearchText] = useState("");
  const [bookingName, setBookingName] = useState("");
  const [bookingContact, setBookingContact] = useState("");
  const [bookingRole, setBookingRole] = useState("学生本人");
  const [bookingTimes, setBookingTimes] = useState("");
  const [bookingQuestion, setBookingQuestion] = useState("");
  const [expandedPickers, setExpandedPickers] = useState<Record<PickerKey, boolean>>({
    fields: false,
    areas: false,
    english: false,
    eju: false,
    keywords: false,
  });

  const [programs, setPrograms] = useState<PublicProgram[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendationResult[]>([]);
  const [submittedProfile, setSubmittedProfile] = useState<StudentProfile | null>(null);
  const [selectedResult, setSelectedResult] = useState<DisplayResult | null>(null);
  const [selectedProgram, setSelectedProgram] = useState<PublicProgram | null>(null);

  const [programsLoading, setProgramsLoading] = useState(true);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingMessage, setBookingMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setProgramsLoading(true);
    getPublicPrograms({ limit: 50 })
      .then((items) => {
        if (active) setPrograms(items);
      })
      .catch((err) => {
        if (active) setError(toErrorMessage(err));
      })
      .finally(() => {
        if (active) setProgramsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const displayResults = useMemo<DisplayResult[]>(() => {
    if (!submittedProfile) return programs.map(fallbackResult);

    const recommended = new Map(recommendations.map((item) => [item.program.id, item]));
    const locallyMatched = programs
      .map((program) => profileMatchResult(program, submittedProfile, submittedKeywordsText))
      .filter((item): item is DisplayResult => Boolean(item));

    return locallyMatched
      .map((item) => {
        const recommendation = recommended.get(item.program.id);
        if (!recommendation) return item;
        return {
          ...item,
          source: "recommendation" as const,
          score: Math.max(item.score, recommendation.score),
          reasons: recommendation.reasons.length ? recommendation.reasons : item.reasons,
          check_items: recommendation.check_items,
        };
      })
      .sort((a, b) => b.score - a.score || a.program.school_name.localeCompare(b.program.school_name));
  }, [programs, recommendations, submittedKeywordsText, submittedProfile]);

  const filteredResults = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    if (!query) return displayResults;
    return displayResults.filter((item) => programSearchText(item.program).includes(query));
  }, [displayResults, searchText]);

  const submittedFilterLabels = useMemo(() => {
    if (!submittedProfile) return [];
    return [
      submittedProfile.target_year ? `年度：${submittedProfile.target_year}` : "",
      ...submittedProfile.desired_fields.map((item) => `方向：${item}`),
      ...submittedProfile.preferred_prefectures.map((item) => `地区：${item}`),
      ...submittedProfile.english_tests.map((item) => `英语：${item}`),
      ...submittedProfile.eju_subjects.map((item) => `EJU：${item}`),
      ...splitTerms(submittedKeywordsText).map((item) => `关键词：${item}`),
    ].filter(Boolean);
  }, [submittedKeywordsText, submittedProfile]);

  async function selectResult(result: DisplayResult) {
    setSelectedResult(result);
    setSelectedProgram(result.program);
    setActiveTab("detail");
    setBookingMessage("");
    setDetailLoading(true);
    try {
      const detail = await getPublicProgram(result.program.id);
      setSelectedProgram(detail);
    } catch {
      setSelectedProgram(result.program);
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleProfileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const profile: StudentProfile = {
      target_year: targetYear.trim(),
      desired_fields: splitTerms(desiredFieldsText),
      preferred_prefectures: splitTerms(prefecturesText),
      english_tests: splitTerms(englishTestsText),
      eju_subjects: splitTerms(ejuSubjectsText),
      japanese_level: japaneseLevel.trim(),
      notes: notes.trim(),
    };
    setRecommendationLoading(true);
    setSubmittedProfile(profile);
    setSubmittedKeywordsText(profileKeywordsText.trim());
    setError(null);
    try {
      const response = await getPublicRecommendations(profile);
      const firstResult = response.results[0] ? { ...response.results[0], source: "recommendation" as const } : null;
      setRecommendations(response.results);
      setSelectedResult(firstResult);
      setSelectedProgram(firstResult?.program ?? null);
      setActiveTab("explore");
    } catch (err) {
      setRecommendations([]);
      setError(toErrorMessage(err));
    } finally {
      setRecommendationLoading(false);
    }
  }

  async function handleBookingSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProgram) return;
    const contact = bookingContact.trim();
    setBookingLoading(true);
    setBookingMessage("");
    setError(null);
    try {
      await createConsultationBooking({
        student_name: bookingName.trim(),
        contact_email: contact.includes("@") ? contact : "",
        contact_phone: contact.includes("@") ? "" : contact,
        role: bookingRole.trim(),
        target_year: targetYear.trim(),
        program_id: activeProgram.id,
        preferred_times: bookingTimes.trim(),
        question: bookingQuestion.trim(),
      });
      setBookingMessage("已经收到。我们会按你留下的联系方式继续沟通。");
      setBookingQuestion("");
      setBookingTimes("");
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBookingLoading(false);
    }
  }

  function togglePicker(key: PickerKey) {
    setExpandedPickers((current) => ({ ...current, [key]: !current[key] }));
  }

  const activeProgram = selectedProgram;
  const activeResult = activeProgram
    ? selectedResult?.program.id === activeProgram.id
      ? selectedResult
      : displayResults.find((item) => item.program.id === activeProgram.id) ?? null
    : null;
  const activePreparationItems = activeProgram ? preparationItems(activeProgram, activeResult?.check_items) : [];

  return (
    <div className="student-shell student-shell-ios">
      <header className="student-topbar">
        <a className="student-brand" href="#/student" aria-label="学生入口首页">
          <span>
            <strong>学生・家长入口</strong>
            <small>日本大学申请</small>
          </span>
        </a>
        <nav className="student-nav" aria-label="学生端导航">
          {TABS.map((item) => (
            <button
              className={activeTab === item.key ? "is-active" : ""}
              key={item.key}
              type="button"
              onClick={() => setActiveTab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="student-main">
        <section className="student-hero">
          <div className="student-hero-copy">
            <p className="student-kicker">学生・家长入口</p>
            <h1>先说情况，再看学校。</h1>
            <p>
              填一下目标年度、方向、地区和已经准备的考试。
              页面会带你回到学校页，先看值得认真比较的选择。
            </p>

            <label className="student-hero-search">
              <span>直接搜学校、学部、地区或考试</span>
              <input
                value={searchText}
                onChange={(event) => {
                  setSearchText(event.target.value);
                  setActiveTab("explore");
                }}
                placeholder="例：早稻田 / 商学 / 东京 / TOEFL"
              />
            </label>
          </div>

          <div className="student-liquid-card" aria-label="开始">
            <span className="student-liquid-label">从这里开始</span>
            <strong>先填三件事。</strong>
            <p>方向、地区、考试情况先给个大概。填完后直接看学校，不用在一页里来回找。</p>
            <button className="student-soft-button" type="button" onClick={() => setActiveTab("match")}>
              填我的情况
            </button>
          </div>
        </section>

        <div className="student-tabbar" role="tablist" aria-label="学生端步骤">
          {TABS.map((item) => (
            <button
              aria-selected={activeTab === item.key}
              className={activeTab === item.key ? "is-active" : ""}
              key={item.key}
              type="button"
              role="tab"
              onClick={() => setActiveTab(item.key)}
            >
              <strong>{item.label}</strong>
              <span>{item.hint}</span>
            </button>
          ))}
        </div>

        {error ? <div className="student-message student-message-error">{error}</div> : null}

        {activeTab === "explore" ? (
          <section className="student-tab-panel student-explore-panel" role="tabpanel">
            <div className="student-section-head student-results-head">
              <div>
                <p className="student-kicker">学校</p>
                <h2>{submittedProfile ? "适合先看的学校" : "先按学校和条件查找"}</h2>
                <p>{submittedProfile ? "根据你刚才填写的方向、地区和考试情况筛选。" : "可以先搜索学校、学部、地区或考试要求。"}</p>
              </div>
              <button className="student-soft-button" type="button" onClick={() => setActiveTab("match")}>
                填我的情况
              </button>
            </div>

            <label className="student-field student-inline-search">
              <span>继续关键词检索</span>
              <input
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="学校、学部、地区、考试、面试、小论文都可以"
              />
            </label>

            {submittedFilterLabels.length ? (
              <div className="student-filter-strip" aria-label="当前筛选条件">
                {submittedFilterLabels.slice(0, 10).map((item) => (
                  <span key={item}>{item}</span>
                ))}
                {submittedFilterLabels.length > 10 ? <span>还有 {submittedFilterLabels.length - 10} 项</span> : null}
              </div>
            ) : null}

            {programsLoading ? (
              <div className="student-empty">正在读取学校信息。</div>
            ) : filteredResults.length ? (
              <div className="student-result-list">
                {filteredResults.map((item) => {
                  const active = selectedProgram?.id === item.program.id;
                  const reasons = friendlyReasons(item);
                  return (
                    <button
                      className={`student-result-card${active ? " is-active" : ""}`}
                      key={`${item.source}-${item.program.id}`}
                      type="button"
                      onClick={() => void selectResult(item)}
                    >
                      <div className="student-result-topline">
                        <small>{textOrPending(item.program.admission_year)}</small>
                      </div>
                      <strong>{item.program.school_name}</strong>
                      <span>{formatProgramName(item.program)}</span>
                      <small>{textOrPending(item.program.prefecture || item.program.campus)}</small>
                      <span>{textOrPending(item.program.exam_method || item.program.application_period)}</span>
                      {reasons.length ? (
                        <div className="student-result-reasons">
                          <small>可以先看的原因</small>
                          {reasons.map((reason) => (
                            <em key={reason}>{reason}</em>
                          ))}
                        </div>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="student-empty">
                {programs.length ? "暂时没有匹配结果。可以放宽地区或方向后再试一次。" : "现在还没有可查看的学校。等资料整理好后，这里会出现学校。"}
              </div>
            )}
          </section>
        ) : null}

        {activeTab === "match" ? (
          <form className="student-tab-panel student-profile-panel" role="tabpanel" onSubmit={handleProfileSubmit}>
            <div className="student-section-head">
              <p className="student-kicker">个人情况</p>
              <h2>告诉我们你的情况</h2>
              <p>不用一次填完。先选方向、地区和已经准备的考试，之后还可以再改。</p>
              <p>点开每一项右侧的加号，就能选择常见条件。</p>
            </div>

            <label className="student-field">
              <span>目标入学年度</span>
              <input value={targetYear} onChange={(event) => setTargetYear(event.target.value)} placeholder="例如 2027" />
            </label>

            <div className="student-choice-stack">
              <ChoicePicker
                label="想读的方向"
                value={desiredFieldsText}
                options={QUICK_FIELDS}
                expanded={expandedPickers.fields}
                placeholder="例如 商学, 社会, 国际"
                onChange={setDesiredFieldsText}
                onToggle={() => togglePicker("fields")}
              />
              <ChoicePicker
                label="希望地区"
                value={prefecturesText}
                options={QUICK_AREAS}
                expanded={expandedPickers.areas}
                placeholder="例如 东京, 大阪"
                onChange={setPrefecturesText}
                onToggle={() => togglePicker("areas")}
              />
              <ChoicePicker
                label="英语考试"
                value={englishTestsText}
                options={QUICK_ENGLISH}
                expanded={expandedPickers.english}
                placeholder="例如 TOEFL, IELTS, TOEIC"
                onChange={setEnglishTestsText}
                onToggle={() => togglePicker("english")}
              />
              <ChoicePicker
                label="EJU 科目"
                value={ejuSubjectsText}
                options={QUICK_EJU}
                expanded={expandedPickers.eju}
                placeholder="例如 日本语, 数学, 综合科目"
                onChange={setEjuSubjectsText}
                onToggle={() => togglePicker("eju")}
              />
              <ChoicePicker
                label="想特别查找"
                value={profileKeywordsText}
                options={QUICK_KEYWORDS}
                expanded={expandedPickers.keywords}
                placeholder="例如 面试, 小论文, 秋入学, 私费外国人"
                onChange={setProfileKeywordsText}
                onToggle={() => togglePicker("keywords")}
              />
            </div>

            <label className="student-field">
              <span>日语情况</span>
              <input
                value={japaneseLevel}
                onChange={(event) => setJapaneseLevel(event.target.value)}
                placeholder="例如 JLPT N2, EJU 日本语 280"
              />
            </label>

            <label className="student-field">
              <span>补充说明</span>
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="例如 想避开面试、优先首都圈、成绩还在准备中"
              />
            </label>

            <button className="student-primary-button" type="submit" disabled={recommendationLoading}>
              {recommendationLoading ? "正在整理" : "查看适合先看的学校"}
            </button>
          </form>
        ) : null}

        {activeTab === "detail" ? (
          <section className="student-tab-panel student-detail-panel" role="tabpanel">
            <div className="student-section-head student-results-head">
              <div>
                <p className="student-kicker">学校要求</p>
                <h2>这所学校要看什么</h2>
                <p>把出愿时间、考试方式、EJU 和英语要求放在一起看。</p>
              </div>
              <button className="student-soft-button" type="button" onClick={() => setActiveTab("explore")}>
                返回学校
              </button>
            </div>

            {activeProgram ? (
              <>
                <div className="student-detail-title">
                  <h3>{activeProgram.school_name}</h3>
                  <p>{formatProgramName(activeProgram)}</p>
                  {detailLoading ? <small>正在更新详情。</small> : null}
                </div>

                <div className="student-requirement-grid">
                  {requirementRows(activeProgram).map((row) => (
                    <div className="student-requirement" key={row.label}>
                      <span>{row.label}</span>
                      <strong>{row.value}</strong>
                    </div>
                  ))}
                </div>

                {activePreparationItems.length ? (
                  <div className="student-prepare-panel">
                    <h4>需要提前准备</h4>
                    <ul>
                      {activePreparationItems.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <div className="student-source-panel">
                  <h4>资料来源</h4>
                  <p>{activeProgram.source_document?.file_name || "招生资料"}</p>
                  {activeProgram.source_document?.pdf_url ? (
                    <a href={activeProgram.source_document.pdf_url} target="_blank" rel="noreferrer">
                      查看来源资料
                    </a>
                  ) : null}
                </div>

                <form className="student-booking-panel" onSubmit={handleBookingSubmit}>
                  <div className="student-section-head">
                    <p className="student-kicker">预约咨询</p>
                    <h2>想进一步聊这所学校？</h2>
                    <p>留下联系方式和方便的时间，我们会带着这所学校的要求一起看。</p>
                  </div>

                  <div className="student-booking-fields">
                    <label className="student-field">
                      <span>姓名</span>
                      <input
                        value={bookingName}
                        onChange={(event) => setBookingName(event.target.value)}
                        placeholder="例如 王同学"
                        required
                      />
                    </label>

                    <label className="student-field">
                      <span>联系方式</span>
                      <input
                        value={bookingContact}
                        onChange={(event) => setBookingContact(event.target.value)}
                        placeholder="邮箱或手机号"
                        required
                      />
                    </label>

                    <label className="student-field">
                      <span>身份</span>
                      <select value={bookingRole} onChange={(event) => setBookingRole(event.target.value)}>
                        <option>学生本人</option>
                        <option>家长</option>
                        <option>其他</option>
                      </select>
                    </label>

                    <label className="student-field">
                      <span>方便的时间</span>
                      <input
                        value={bookingTimes}
                        onChange={(event) => setBookingTimes(event.target.value)}
                        placeholder="例如 周六下午、平日晚上"
                      />
                    </label>
                  </div>

                  <label className="student-field">
                    <span>想先问什么</span>
                    <textarea
                      value={bookingQuestion}
                      onChange={(event) => setBookingQuestion(event.target.value)}
                      placeholder="例如 想看 EJU 科目、英语成绩、出愿时间是否合适"
                    />
                  </label>

                  {bookingMessage ? <div className="student-message student-message-success">{bookingMessage}</div> : null}

                  <button className="student-primary-button" type="submit" disabled={bookingLoading}>
                    {bookingLoading ? "正在提交" : "提交预约"}
                  </button>
                </form>
              </>
            ) : (
              <div className="student-empty">请选择一所学校，或先填写个人情况。</div>
            )}
          </section>
        ) : null}
      </main>
    </div>
  );
}
