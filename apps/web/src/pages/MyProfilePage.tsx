/** 168 v1.1 — 我的资料（当前登录用户可维护） */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";
import { apiGet, apiPatch } from "../api/client";

type Profile = {
  subject: string;
  displayName?: string;
  email?: string | null;
  phone?: string | null;
  title?: string | null;
};

type MeResp = {
  subject: string;
  profile?: Profile;
  displayName?: string;
  email?: string | null;
  phone?: string | null;
  title?: string | null;
};

type ProfileForm = Pick<Profile, "displayName" | "email" | "phone" | "title">;

function businessTitle(value: string) {
  return value.replace(/\s*\bBearer\b\s*/gi, "").trim();
}

function normalizedForm(form: ProfileForm) {
  return {
    displayName: (form.displayName || "").trim(),
    email: (form.email || "").trim(),
    phone: (form.phone || "").trim(),
    title: (form.title || "").trim(),
  };
}

export function MyProfilePage() {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [title, setTitle] = useState("");
  const [initial, setInitial] = useState<ProfileForm | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setErr("");
    try {
      const me = await apiGet<MeResp>("/v1/me");
      const p = me.profile || me;
      const next = {
        displayName: p.displayName || me.displayName || "",
        email: p.email || me.email || "",
        phone: p.phone || me.phone || "",
        title: businessTitle(p.title || me.title || ""),
      };
      setDisplayName(next.displayName);
      setEmail(next.email);
      setPhone(next.phone);
      setTitle(next.title);
      setInitial(next);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const current = normalizedForm({ displayName, email, phone, title });
  const dirty = initial !== null && JSON.stringify(current) !== JSON.stringify(normalizedForm(initial));

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onSave() {
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await apiPatch("/v1/me/profile", {
        ...current,
      });
      setMsg("已保存");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageChrome
      title="我的资料"
      lede="维护本人姓名、邮箱、手机与职务"
    >
      {err ? <p className="aos-error">{err}</p> : null}
      {msg ? <p className="aos-muted">{msg}</p> : null}

      <div className="aos-profile-form">
        <label>
          姓名
          <input
            className="aos-input"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="例如 本机开发者"
            aria-label="姓名"
          />
        </label>
        <label>
          邮箱
          <input
            className="aos-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@company.com"
            aria-label="邮箱"
          />
        </label>
        <label>
          手机
          <input
            className="aos-input"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="13800138000"
            aria-label="手机"
          />
        </label>
        <label>
          职务 / 说明
          <input
            className="aos-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="例如 本机登录账号"
            aria-label="职务"
          />
        </label>
        <button
          type="button"
          className="btn-primary"
          disabled={busy || !dirty}
          onClick={() => void onSave()}
        >
          {busy ? "保存中…" : "保存"}
        </button>
      </div>

      <p className="aos-muted" style={{ marginTop: "1rem" }}>
        <Link to="/workspace/members">工作区成员</Link>
        {" · "}
        保存后，成员列表中会显示你更新后的姓名与联系方式。
      </p>
    </PageChrome>
  );
}
