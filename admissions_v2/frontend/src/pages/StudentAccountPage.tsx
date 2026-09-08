import { FormEvent, useState } from "react";
import { login, logout, registerStudent, toErrorMessage } from "../api/client";
import type { AppUser } from "../types";

export default function StudentAccountPage({ user, onUserChange, loading }: {
  user: AppUser | null; onUserChange: (user: AppUser | null) => void; loading: boolean;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (mode === "register" && password !== confirmation) {
      setError("两次输入的密码不一致。");
      return;
    }
    setBusy(true);
    try {
      if (mode === "register") {
        await registerStudent(email, password, name);
        setPassword("");
        setConfirmation("");
        setMode("login");
        setNotice("注册成功，请登录。");
      } else {
        onUserChange(await login(email, password));
        setPassword("");
      }
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError("");
    try { await logout(); onUserChange(null); }
    catch (err) { setError(toErrorMessage(err)); }
    finally { setBusy(false); }
  }

  return <main className="login-shell student-account">
    <section className="login-card">
      <a href="#/student">返回学校查询</a>
      <h1>{user ? "我的账号" : "学生账号"}</h1>
      {loading ? <p role="status">正在加载账号…</p> : user ? <>
        <p className="account-identity">{user.display_name || user.email}</p>
        <p className="account-identity">{user.email}</p>
        <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => void signOut()}>退出登录</button>
      </> : <>
        <div className="account-tabs" role="tablist" aria-label="账号操作">
          {(["login", "register"] as const).map(value => <button key={value} type="button"
            role="tab" aria-selected={mode === value} disabled={busy}
            className={`btn ${mode === value ? "btn-primary" : "btn-ghost"}`}
            onClick={() => { setMode(value); setError(""); setNotice(""); setPassword(""); setConfirmation(""); }}>
            {value === "login" ? "登录" : "注册"}
          </button>)}
        </div>
        <form onSubmit={event => void submit(event)}>
          {mode === "register" && <label className="field-wrap"><span className="field-label">昵称</span>
            <input className="field" autoComplete="nickname" required maxLength={60} value={name} onChange={e => setName(e.target.value)} />
          </label>}
          <label className="field-wrap"><span className="field-label">邮箱</span>
            <input className="field" type="email" autoComplete="username" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)} />
          </label>
          <label className="field-wrap"><span className="field-label">{mode === "register" ? "密码（至少 8 位）" : "密码"}</span>
            <input className="field" type="password" autoComplete={mode === "register" ? "new-password" : "current-password"}
              required minLength={mode === "register" ? 8 : 1} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} />
          </label>
          {mode === "register" && <label className="field-wrap"><span className="field-label">确认密码</span>
            <input className="field" type="password" autoComplete="new-password" required maxLength={128} value={confirmation} onChange={e => setConfirmation(e.target.value)} />
          </label>}
          <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "处理中…" : mode === "register" ? "创建学生账号" : "登录"}</button>
        </form>
      </>}
      {error && <p className="message-box error" role="alert">{error}</p>}
      {notice && <p className="message-box" role="status">{notice}</p>}
    </section>
  </main>;
}
