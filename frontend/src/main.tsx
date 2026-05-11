import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import { Check, ChevronRight, FileText, Gavel, Loader2, Plus, RefreshCw, Search, ShieldCheck, Sparkles } from "lucide-react";
import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { RichTextPlugin } from "@lexical/react/LexicalRichTextPlugin";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { LexicalErrorBoundary } from "@lexical/react/LexicalErrorBoundary";
import { $createParagraphNode, $createTextNode, $getRoot, EditorState } from "lexical";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

type Matter = {
  id: number;
  external_id: string;
  client_name: string;
  court: string;
  county: string;
  eviction_ground: string;
  subsidy_status: string;
  problem_codes: string[];
  special_problem_codes: string[];
};

type CandidateGround = {
  id: number;
  title: string;
  rationale: string;
  elements: string[];
  missing_fact_questions: string[];
  confidence: string;
  status: string;
};

type DraftPackage = {
  id: number;
  title: string;
  status: string;
};

type DraftBlock = {
  id: number;
  kind: string;
  title: string;
  content: string;
  enabled: boolean;
};

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

function App() {
  const [matters, setMatters] = useState<Matter[]>([]);
  const [activeMatterId, setActiveMatterId] = useState<number | null>(null);
  const [grounds, setGrounds] = useState<CandidateGround[]>([]);
  const [packages, setPackages] = useState<DraftPackage[]>([]);
  const [activePackage, setActivePackage] = useState<DraftPackage | null>(null);
  const [blocks, setBlocks] = useState<DraftBlock[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("Ready");

  const activeMatter = matters.find((matter) => matter.id === activeMatterId) ?? null;
  const selectedGroundIds = grounds.filter((ground) => ground.status === "selected").map((ground) => ground.id);
  const draftText = useMemo(() => blocks.filter((block) => block.enabled).map((block) => `${block.title}\n${block.content}`).join("\n\n"), [blocks]);

  async function refreshMatters() {
    const data = await api<Matter[]>("/matters");
    setMatters(data);
    if (!activeMatterId && data.length) setActiveMatterId(data[0].id);
  }

  async function loadMatter(matterId: number) {
    setActiveMatterId(matterId);
    const [groundData, packageData] = await Promise.all([
      api<CandidateGround[]>(`/matters/${matterId}/candidate-grounds?goal_code=motion_to_dismiss`),
      api<DraftPackage[]>(`/matters/${matterId}/draft-packages`),
    ]);
    setGrounds(groundData);
    setPackages(packageData);
    setActivePackage(packageData[0] ?? null);
    if (packageData[0]) {
      const detail = await api<{ package: DraftPackage; blocks: DraftBlock[] }>(`/draft-packages/${packageData[0].id}`);
      setBlocks(detail.blocks);
    } else {
      setBlocks([]);
    }
  }

  async function seedDemo() {
    setLoading(true);
    try {
      const result = await api<{ matter_id: number }>("/seed", { method: "POST" });
      await refreshMatters();
      await loadMatter(result.matter_id);
      setMessage("Demo matter created");
    } finally {
      setLoading(false);
    }
  }

  async function runAudit() {
    if (!activeMatterId) return;
    setLoading(true);
    try {
      const data = await api<CandidateGround[]>(`/matters/${activeMatterId}/audit?goal_code=motion_to_dismiss`, { method: "POST" });
      setGrounds(data);
      setMessage("Matter audit completed");
    } finally {
      setLoading(false);
    }
  }

  async function setGroundStatus(ground: CandidateGround, status: string) {
    const updated = await api<CandidateGround>(`/candidate-grounds/${ground.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    setGrounds((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function createPackage() {
    if (!activeMatterId) return;
    setLoading(true);
    try {
      const pkg = await api<DraftPackage>(`/matters/${activeMatterId}/draft-packages`, {
        method: "POST",
        body: JSON.stringify({ goal_code: "motion_to_dismiss", selected_ground_ids: selectedGroundIds }),
      });
      const detail = await api<{ package: DraftPackage; blocks: DraftBlock[] }>(`/draft-packages/${pkg.id}`);
      setActivePackage(pkg);
      setPackages((current) => [pkg, ...current]);
      setBlocks(detail.blocks);
      setMessage("Draft package created");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshMatters().catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (activeMatterId) {
      loadMatter(activeMatterId).catch((error) => setMessage(error.message));
    }
  }, [activeMatterId]);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Gavel size={20} />
          </span>
          <div>
            <strong>Legal Aid Drafting</strong>
            <span>Landlord/Tenant</span>
          </div>
        </div>
        <nav className="nav-group" aria-label="Primary">
          <button className="nav-item active">
            <FileText size={16} />
            Drafts
          </button>
          <button className="nav-item">
            <Search size={16} />
            Research
          </button>
          <button className="nav-item">
            <ShieldCheck size={16} />
            Review
          </button>
        </nav>
        <button className="primary-button" onClick={seedDemo} disabled={loading}>
          <Plus size={16} />
          Demo Matter
        </button>
        <div className="matter-list">
          {matters.map((matter) => (
            <button
              className={`matter-row ${matter.id === activeMatterId ? "active" : ""}`}
              key={matter.id}
              onClick={() => setActiveMatterId(matter.id)}
            >
              <span>{matter.client_name}</span>
              <small>{matter.court || matter.external_id || "No court set"}</small>
            </button>
          ))}
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <div className="eyebrow">
              <Sparkles size={15} />
              Agentic drafting workspace
            </div>
            <h1>{activeMatter ? activeMatter.client_name : "Select a matter"}</h1>
            <p>
              {activeMatter
                ? `${activeMatter.eviction_ground || "Eviction matter"} · ${activeMatter.county}`
                : "Create the demo matter to exercise the motion workflow."}
            </p>
          </div>
          <div className="status-pill">
            {loading ? <Loader2 className="spin" size={16} /> : <Check size={16} />}
            {message}
          </div>
        </header>

        <section className="case-strip" aria-label="Workflow summary">
          <div className="case-chip">
            <span>Court</span>
            <strong>{activeMatter?.court || "Not set"}</strong>
          </div>
          <ChevronRight size={16} />
          <div className="case-chip">
            <span>Goal</span>
            <strong>Motion to dismiss</strong>
          </div>
          <ChevronRight size={16} />
          <div className="case-chip">
            <span>Selected grounds</span>
            <strong>{selectedGroundIds.length}</strong>
          </div>
          <ChevronRight size={16} />
          <div className="case-chip">
            <span>Draft blocks</span>
            <strong>{blocks.length}</strong>
          </div>
        </section>

        <div className="workflow-grid">
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Ground Review</h2>
                <p>Audit the case, then select the grounds the draft may use.</p>
              </div>
              <button className="icon-button" onClick={runAudit} disabled={!activeMatter || loading} title="Run matter audit">
                <Search size={18} />
              </button>
            </div>
            <div className="ground-list">
              {grounds.length === 0 && <p className="empty">No candidate grounds yet.</p>}
              {grounds.map((ground) => (
                <article className="ground-card" key={ground.id}>
                  <div className="ground-title">
                    <h3>{ground.title}</h3>
                    <span>{Math.round(Number(ground.confidence) * 100)}%</span>
                  </div>
                  <p>{ground.rationale}</p>
                  <ul>
                    {ground.elements.slice(0, 3).map((element) => (
                      <li key={element}>{element}</li>
                    ))}
                  </ul>
                  <div className="button-row">
                    <button onClick={() => setGroundStatus(ground, "selected")} className={ground.status === "selected" ? "selected" : ""}>
                      Use
                    </button>
                    <button onClick={() => setGroundStatus(ground, "needs_facts")} className={ground.status === "needs_facts" ? "selected" : ""}>
                      Needs Facts
                    </button>
                    <button onClick={() => setGroundStatus(ground, "rejected")} className={ground.status === "rejected" ? "selected" : ""}>
                      Reject
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Draft Package</h2>
                <p>Selected grounds become ordered draft blocks.</p>
              </div>
              <button className="icon-button" onClick={createPackage} disabled={!activeMatter || loading} title="Create draft package">
                <FileText size={18} />
              </button>
            </div>
            <div className="package-strip">
              {packages.map((pkg) => (
                <button key={pkg.id} className={activePackage?.id === pkg.id ? "selected" : ""}>
                  {pkg.title}
                </button>
              ))}
              {packages.length === 0 && <span className="empty">No draft package yet.</span>}
            </div>
            <div className="block-list">
              {blocks.map((block) => (
                <article className="block-row" key={block.id}>
                  <span>{block.title}</span>
                  <small>{block.kind}</small>
                </article>
              ))}
            </div>
          </section>
        </div>

        <section className="editor-panel">
          <div className="panel-heading">
            <div>
              <h2>Draft Editor</h2>
              <p>Reviewable text surface for the package blocks.</p>
            </div>
            <button className="icon-button" onClick={() => setMessage("Editor refreshed")} title="Refresh editor">
              <RefreshCw size={18} />
            </button>
          </div>
          <DraftEditor key={activePackage?.id ?? "empty"} initialText={draftText || "Create a draft package to begin."} />
        </section>
      </section>
    </main>
  );
}

function DraftEditor({ initialText }: { initialText: string }) {
  const initialConfig = {
    namespace: "LegalAidDraftEditor",
    theme: {
      paragraph: "editor-paragraph",
    },
    onError(error: Error) {
      throw error;
    },
  };

  function onChange(editorState: EditorState) {
    editorState.read(() => {
      $getRoot().getTextContent();
    });
  }

  return (
    <LexicalComposer initialConfig={initialConfig}>
      <div className="editor-frame">
        <RichTextPlugin
          contentEditable={<ContentEditable className="editor-input" aria-label="Draft editor" />}
          placeholder={<div className="editor-placeholder">Start reviewing the draft...</div>}
          ErrorBoundary={LexicalErrorBoundary}
        />
        <InitialTextPlugin text={initialText} />
        <HistoryPlugin />
        <OnChangePlugin onChange={onChange} />
      </div>
    </LexicalComposer>
  );
}

function InitialTextPlugin({ text }: { text: string }) {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    editor.update(() => {
      const root = $getRoot();
      root.clear();
      text.split("\n").forEach((line) => {
        const paragraph = $createParagraphNode();
        paragraph.append($createTextNode(line));
        root.append(paragraph);
      });
    });
  }, [editor, text]);

  return null;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
