"""Hybrid calendar activation and cached daily learning content."""
from __future__ import annotations
import hashlib, json, os, re, sqlite3, uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from pathly_backend import CALIBRATED_KG, GLOBAL_KG
from pathly_documents import _hash_embedding

def now_iso(): return datetime.now(timezone.utc).isoformat()
class DailyLearningNotFoundError(LookupError): pass
class DailyLearningValidationError(ValueError): pass


CONTENT_CONTRACT_VERSION = "daily-content-v2"
CONTENT_GENERATOR_VERSION = "content-agent-v7"

ACTIVITY_BLOCK_TYPES = {
    "explanation": "concept_lesson",
    "example": "worked_example",
    "required_reading": "guided_reading",
    "practice": "guided_practice",
    "code": "coding_task",
    "review": "retrieval_review",
    "quiz": "quiz_preparation",
    "project": "project_milestone",
    "reflection": "reflection",
}


class EvidencePreparer:
    """Turn retrieved chunks into bounded teaching evidence, never raw lesson copy."""

    EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
    DOI = re.compile(r"\b(?:https?://)?doi\.org/\S+|\bdoi:\s*\S+", re.I)
    REFERENCES = re.compile(r"^\s*(?:references|bibliography)\s*$", re.I)
    NOISE = re.compile(
        r"\b(?:copyright|all rights reserved|proceedings of|university|institute|"
        r"department of|arxiv preprint|corresponding author)\b",
        re.I,
    )

    @classmethod
    def clean(cls, text: str) -> tuple[str, list[str]]:
        raw = str(text or "").replace("\x00", " ")
        flags: list[str] = []
        if cls.EMAIL.search(raw): flags.append("email_removed")
        if cls.DOI.search(raw): flags.append("doi_removed")
        raw = cls.EMAIL.sub("", raw)
        raw = cls.DOI.sub("", raw)
        lines = []
        for line in raw.splitlines():
            compact = " ".join(line.split())
            if not compact: continue
            if cls.REFERENCES.match(compact):
                flags.append("references_truncated")
                break
            words = compact.split()
            capitalized = sum(1 for word in words if word[:1].isupper())
            if cls.NOISE.search(compact) and (len(words) < 28 or capitalized > len(words) * .55):
                flags.append("metadata_line_removed")
                continue
            if len(words) >= 8 and capitalized > len(words) * .8:
                flags.append("author_line_removed")
                continue
            lines.append(compact)
        cleaned = re.sub(r"\s+", " ", " ".join(lines)).strip(" ,;:-")
        if len(cleaned) > 900:
            cleaned = cleaned[:900].rsplit(" ", 1)[0] + "?"
            flags.append("bounded_excerpt")
        if len(cleaned.split()) < 8: flags.append("insufficient_teaching_text")
        return cleaned, list(dict.fromkeys(flags))

    @classmethod
    def prepare(cls, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared, seen = [], set()
        for context in contexts:
            concept_id = str(context.get("concept_id") or "")
            chunks = [*(context.get("private_chunks") or []), *(context.get("public_chunks") or [])]
            for item in chunks:
                metadata = item.get("metadata") or {}
                clean_text, flags = cls.clean(str(item.get("text") or ""))
                signature = hashlib.sha256(clean_text.lower().encode()).hexdigest() if clean_text else ""
                if not clean_text or signature in seen or "insufficient_teaching_text" in flags: continue
                seen.add(signature)
                distance = item.get("distance")
                relevance = max(0.0, min(1.0, 1.0 - float(distance))) if isinstance(distance, (int, float)) else 0.7
                prepared.append({
                    "evidence_id": str(item.get("id") or item.get("chunk_id") or f"evidence-{len(prepared)+1}"),
                    "concept_id": concept_id,
                    "clean_text": clean_text,
                    "source_type": "private_document" if item.get("private") else "public_rag",
                    "document_id": metadata.get("document_id"),
                    "resource_id": metadata.get("resource_id"),
                    "page_start": metadata.get("page_start"),
                    "page_end": metadata.get("page_end"),
                    "section_title": metadata.get("section_title") or metadata.get("heading"),
                    "relevance_score": round(relevance, 4),
                    "evidence_role": "concept_explanation",
                    "quality_flags": flags,
                    "safe_for_direct_excerpt": not any(flag in flags for flag in ("author_line_removed", "metadata_line_removed", "references_truncated")),
                })
        return prepared[:20]

class DailyLearningStore:
    def __init__(self,db_path): self.db_path=Path(db_path); self.migrate()
    def connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c
    def migrate(self):
        with self.connect() as c: c.executescript("""
        CREATE TABLE IF NOT EXISTS path_runtime(path_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,active_plan_id TEXT NOT NULL,start_date TEXT NOT NULL,timezone TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_path_runtime_user ON path_runtime(user_id,updated_at);
        CREATE TABLE IF NOT EXISTS path_day_dates(path_id TEXT NOT NULL,day INTEGER NOT NULL,scheduled_date TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(path_id,day));
        CREATE TABLE IF NOT EXISTS daily_contents(content_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,path_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,source_hash TEXT NOT NULL,content_json TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(user_id,plan_id,day,source_hash));
        CREATE INDEX IF NOT EXISTS idx_daily_content_lookup ON daily_contents(user_id,plan_id,day,created_at);
        CREATE TABLE IF NOT EXISTS daily_sessions(session_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,path_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,content_id TEXT NOT NULL,contract_version TEXT NOT NULL,status TEXT NOT NULL,session_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(user_id,plan_id,day,content_id));
        CREATE TABLE IF NOT EXISTS daily_study_blocks(block_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,user_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,activity_id TEXT NOT NULL,sequence INTEGER NOT NULL,required INTEGER NOT NULL,block_json TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_daily_blocks ON daily_study_blocks(user_id,plan_id,day,sequence);
        CREATE TABLE IF NOT EXISTS study_block_progress(user_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,block_id TEXT NOT NULL,status TEXT NOT NULL,progress REAL NOT NULL DEFAULT 0,actual_seconds INTEGER NOT NULL DEFAULT 0,answer_json TEXT,feedback_json TEXT,started_at TEXT,completed_at TEXT,updated_at TEXT NOT NULL,PRIMARY KEY(user_id,plan_id,day,block_id));
        CREATE TABLE IF NOT EXISTS prepared_evidence(evidence_id TEXT NOT NULL,content_id TEXT NOT NULL,user_id TEXT NOT NULL,evidence_json TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(evidence_id,content_id));
        CREATE TABLE IF NOT EXISTS resource_interactions(interaction_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,resource_id TEXT NOT NULL,action TEXT NOT NULL,metadata_json TEXT NOT NULL,created_at TEXT NOT NULL);
        """)
    def save_runtime(self,p):
        stamp=now_iso()
        with self.connect() as c:
            old=c.execute("SELECT created_at FROM path_runtime WHERE path_id=?",(p["path_id"],)).fetchone()
            c.execute("""INSERT INTO path_runtime VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(path_id) DO UPDATE SET user_id=excluded.user_id,active_plan_id=excluded.active_plan_id,start_date=excluded.start_date,timezone=excluded.timezone,status=excluded.status,updated_at=excluded.updated_at""",(p["path_id"],p["user_id"],p["active_plan_id"],p["start_date"],p["timezone"],p.get("status","active"),old[0] if old else stamp,stamp))
        return self.runtime(p["user_id"],p["path_id"])
    def runtime(self,user_id,path_id):
        with self.connect() as c: row=c.execute("SELECT * FROM path_runtime WHERE user_id=? AND path_id=?",(user_id,path_id)).fetchone()
        return dict(row) if row else None
    def replace_dates(self,path_id,rows):
        stamp=now_iso()
        with self.connect() as c:
            c.execute("DELETE FROM path_day_dates WHERE path_id=?",(path_id,)); c.executemany("INSERT INTO path_day_dates VALUES(?,?,?,?)",[(path_id,int(r["day"]),r["scheduled_date"],stamp) for r in rows])
    def dates(self,path_id):
        with self.connect() as c: rows=c.execute("SELECT day,scheduled_date FROM path_day_dates WHERE path_id=? ORDER BY day",(path_id,)).fetchall()
        return [dict(r) for r in rows]
    def is_day_completed(self,user_id,path_id,day):
        try:
            with self.connect() as c: row=c.execute("SELECT status FROM learning_day_progress WHERE user_id=? AND path_id=? AND day=?",(user_id,path_id,int(day))).fetchone()
        except sqlite3.OperationalError: return False
        return bool(row and row[0]=="completed")
    def latest_content(self,user_id,plan_id,day):
        with self.connect() as c: row=c.execute("SELECT content_json FROM daily_contents WHERE user_id=? AND plan_id=? AND day=? ORDER BY created_at DESC LIMIT 1",(user_id,plan_id,int(day))).fetchone()
        return json.loads(row[0]) if row else None
    def content_by_hash(self,user_id,plan_id,day,source_hash):
        with self.connect() as c: row=c.execute("SELECT content_json FROM daily_contents WHERE user_id=? AND plan_id=? AND day=? AND source_hash=?",(user_id,plan_id,int(day),source_hash)).fetchone()
        return json.loads(row[0]) if row else None
    def save_content(self,p):
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO daily_contents VALUES(?,?,?,?,?,?,?,?)",(p["content_id"],p["user_id"],p["path_id"],p["plan_id"],p["day"],p["source_hash"],json.dumps(p,ensure_ascii=False),p["created_at"]))
            row=c.execute("SELECT content_json FROM daily_contents WHERE user_id=? AND plan_id=? AND day=? AND source_hash=?",(p["user_id"],p["plan_id"],p["day"],p["source_hash"])).fetchone()
        return json.loads(row[0])
    def save_session(self, payload):
        stamp = now_iso(); session_id = f"session:{payload['content_id']}"
        with self.connect() as c:
            c.execute("""INSERT OR REPLACE INTO daily_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(
                session_id,payload['user_id'],payload['path_id'],payload['plan_id'],int(payload['day']),payload['content_id'],payload.get('contract_version',CONTENT_CONTRACT_VERSION),'available',json.dumps(payload,ensure_ascii=False),stamp,stamp))
            c.execute("DELETE FROM daily_study_blocks WHERE session_id=?",(session_id,))
            c.executemany("INSERT OR REPLACE INTO daily_study_blocks VALUES(?,?,?,?,?,?,?,?,?)",[(b['block_id'],session_id,payload['user_id'],payload['plan_id'],int(payload['day']),b['activity_id'],int(b['sequence']),1 if b.get('required',True) else 0,json.dumps(b,ensure_ascii=False)) for b in payload.get('study_blocks',[])])
            c.executemany("INSERT OR REPLACE INTO prepared_evidence VALUES(?,?,?,?,?)",[(e['evidence_id'],payload['content_id'],payload['user_id'],json.dumps(e,ensure_ascii=False),stamp) for e in payload.get('prepared_evidence',[])])
        return self.session(payload['user_id'],payload['plan_id'],payload['day'])
    def session(self,user_id,plan_id,day):
        with self.connect() as c: row=c.execute("SELECT session_json FROM daily_sessions WHERE user_id=? AND plan_id=? AND day=? ORDER BY created_at DESC LIMIT 1",(user_id,plan_id,int(day))).fetchone()
        return json.loads(row[0]) if row else None
    def block_progress(self,user_id,plan_id,day):
        with self.connect() as c: rows=c.execute("SELECT * FROM study_block_progress WHERE user_id=? AND plan_id=? AND day=?",(user_id,plan_id,int(day))).fetchall()
        return [{**dict(r),'answer':json.loads(r['answer_json']) if r['answer_json'] else None,'feedback':json.loads(r['feedback_json']) if r['feedback_json'] else None} for r in rows]
    def save_block_progress(self,*,user_id,plan_id,day,block_id,status,progress,actual_seconds=0,answer=None,feedback=None):
        stamp=now_iso()
        with self.connect() as c:
            old=c.execute("SELECT * FROM study_block_progress WHERE user_id=? AND plan_id=? AND day=? AND block_id=?",(user_id,plan_id,int(day),block_id)).fetchone()
            started=(old['started_at'] if old else None) or stamp
            completed=stamp if status=='completed' else (old['completed_at'] if old else None)
            c.execute("""INSERT INTO study_block_progress VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,plan_id,day,block_id) DO UPDATE SET status=excluded.status,progress=excluded.progress,actual_seconds=excluded.actual_seconds,answer_json=COALESCE(excluded.answer_json,study_block_progress.answer_json),feedback_json=COALESCE(excluded.feedback_json,study_block_progress.feedback_json),started_at=COALESCE(study_block_progress.started_at,excluded.started_at),completed_at=excluded.completed_at,updated_at=excluded.updated_at""",(user_id,plan_id,int(day),block_id,status,float(progress),int(actual_seconds),json.dumps(answer,ensure_ascii=False) if answer is not None else None,json.dumps(feedback,ensure_ascii=False) if feedback is not None else None,started,completed,stamp))
        return next(x for x in self.block_progress(user_id,plan_id,day) if x['block_id']==block_id)
    def save_resource_interaction(self,p):
        with self.connect() as c: c.execute("INSERT INTO resource_interactions VALUES(?,?,?,?,?,?,?,?)",(p['interaction_id'],p['user_id'],p['plan_id'],int(p['day']),p['resource_id'],p['action'],json.dumps(p.get('metadata',{}),ensure_ascii=False),p['created_at']))
        return p

    def document_ids(self,path_id):
        try:
            with self.connect() as c: rows=c.execute("SELECT document_id FROM path_document_links WHERE path_id=?",(path_id,)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [str(r[0]) for r in rows]

class DailyLearningService:
    def __init__(self,backend,store,documents,document_service,*,today_provider=None,context_provider=None,model_generator=None):
        self.backend=backend; self.store=store; self.documents=documents; self.document_service=document_service; self.today_provider=today_provider or date.today; self.context_provider=context_provider; self.model_generator=model_generator
    def plan(self,user_id,plan_id):
        r=self.backend.plans.get_plan(plan_id)
        if not r or r["user_id"]!=user_id: raise DailyLearningNotFoundError(plan_id)
        return r
    def day(self,r,day):
        found=next((x for x in r["plan"].get("days",[]) if int(x.get("day",0))==int(day)),None)
        if not found: raise DailyLearningNotFoundError(f"{r['plan_id']}:day:{day}")
        return found
    def activate(self,*,user_id,plan_id,start_date=None,timezone_name="UTC"):
        r=self.plan(user_id,plan_id); days=r["plan"].get("days") or []
        if not days: raise DailyLearningValidationError("Only a scheduled plan can be activated")
        try: start=date.fromisoformat(start_date) if start_date else self.today_provider()
        except ValueError as e: raise DailyLearningValidationError("start_date must use YYYY-MM-DD") from e
        runtime=self.store.save_runtime({"path_id":r["path_id"],"user_id":user_id,"active_plan_id":plan_id,"start_date":start.isoformat(),"timezone":timezone_name or "UTC","status":"active"})
        if not self.store.dates(r["path_id"]): self.store.replace_dates(r["path_id"],[{"day":x["day"],"scheduled_date":(start+timedelta(days=int(x["day"])-1)).isoformat()} for x in days])
        return {**runtime,"day_dates":self.store.dates(r["path_id"])}
    def today(self,*,user_id,path_id):
        runtime=self.store.runtime(user_id,path_id)
        if not runtime: raise DailyLearningNotFoundError(path_id)
        r=self.plan(user_id,runtime["active_plan_id"]); by_day={int(x["day"]):x for x in r["plan"].get("days",[])}; dated=[{**x,"day":int(x["day"]),"plan_day":by_day[int(x["day"])]} for x in self.store.dates(path_id) if int(x["day"]) in by_day]
        if not dated: raise DailyLearningNotFoundError(path_id)
        today=self.today_provider().isoformat(); due=[x for x in dated if x["scheduled_date"]<=today]; current=(due or dated)[0]
        return {"path_id":path_id,"plan_id":r["plan_id"],"plan_version":r["version"],"goal_text":r["goal_text"],"today":today,"current":current,"is_overdue":current["scheduled_date"]<today,"day_dates":dated,"timezone":runtime["timezone"],"status":runtime["status"]}
    def reschedule(self,*,user_id,path_id,day,new_date,confirm_deadline_impact=False):
        runtime=self.store.runtime(user_id,path_id)
        if not runtime: raise DailyLearningNotFoundError(path_id)
        r=self.plan(user_id,runtime["active_plan_id"]); rows=self.store.dates(path_id); current=next((x for x in rows if int(x["day"])==int(day)),None)
        if not current: raise DailyLearningNotFoundError(f"{path_id}:day:{day}")
        try: delta=(date.fromisoformat(new_date)-date.fromisoformat(current["scheduled_date"])).days
        except ValueError as e: raise DailyLearningValidationError("new_date must use YYYY-MM-DD") from e
        proposed=[{**x,"scheduled_date":(date.fromisoformat(x["scheduled_date"])+timedelta(days=delta)).isoformat() if int(x["day"])>=int(day) else x["scheduled_date"]} for x in rows]; deadline=(r["plan"].get("feasibility") or {}).get("deadline"); exceeds=bool(deadline and max(x["scheduled_date"] for x in proposed)>deadline)
        result={"path_id":path_id,"day":int(day),"delta_days":delta,"deadline":deadline,"exceeds_deadline":exceeds,"requires_confirmation":exceeds and not confirm_deadline_impact,"proposed_day_dates":proposed}
        if result["requires_confirmation"]: return result
        self.store.replace_dates(path_id,proposed); return {**result,"day_dates":proposed,"confirmed":True}
    def prior_learning_signals(self,user_id,path_id):
        completed=[]; weak=[]; confusions=[]; feedback=[]
        try:
            with self.store.connect() as c:
                completed=[int(r[0]) for r in c.execute("SELECT day FROM learning_day_progress WHERE user_id=? AND path_id=? AND status='completed' ORDER BY day",(user_id,path_id)).fetchall()]
                for row in c.execute("SELECT weak_concepts_json FROM quiz_attempts WHERE user_id=? AND path_id=? ORDER BY created_at",(user_id,path_id)).fetchall(): weak.extend(json.loads(row[0] or "[]"))
                for row in c.execute("SELECT feedback_type,concept_ids_json FROM daily_feedback WHERE user_id=? AND path_id=? ORDER BY created_at",(user_id,path_id)).fetchall():
                    ids=json.loads(row[1] or "[]");feedback.append({"feedback_type":row[0],"concept_ids":ids});
                    if row[0] in {"not_understood","too_hard"}: confusions.extend(ids)
                for row in c.execute("SELECT concept_ids_json FROM chat_messages WHERE user_id=? AND path_id=? AND role='user' ORDER BY created_at",(user_id,path_id)).fetchall(): confusions.extend(json.loads(row[0] or "[]"))
        except sqlite3.OperationalError: pass
        return {"completed_days":completed,"weak_concepts":list(dict.fromkeys(weak)),"confusion_concepts":list(dict.fromkeys(confusions)),"feedback":feedback[-20:]}

    def get_content(self,*,user_id,plan_id,day):
        self.day(self.plan(user_id,plan_id),day); cached=self.store.latest_content(user_id,plan_id,day)
        if not cached: raise DailyLearningNotFoundError(f"{plan_id}:day:{day}:content")
        return cached
    def generate_content(self,*,user_id,plan_id,day,force=False):
        r=self.plan(user_id,plan_id); plan_day=self.day(r,day)
        nodes=r["plan"].get("concept_path") or []
        labels={str(n.get("concept_id")):self.concept_label(n,index) for index,n in enumerate(nodes,1)}
        topics=[]
        for activity in plan_day.get("activities",[]): topics.extend(str(x) for x in activity.get("concept_ids",[]))
        topics=list(dict.fromkeys(topics))
        if not topics: raise DailyLearningValidationError("The scheduled day has no concepts")
        profile=self.backend.profiles.get_profile(user_id)
        profile_data=profile if isinstance(profile,dict) else (profile.model_dump() if hasattr(profile,"model_dump") else vars(profile))
        prior_signals=self.prior_learning_signals(user_id,r["path_id"])
        profile_data={**profile_data,"prior_learning_signals":prior_signals}
        contexts=[self.context(user_id,r["path_id"],topic,profile) for topic in topics]
        evidence=EvidencePreparer.prepare(contexts)
        resources=self.build_resources(r,plan_day,contexts,evidence,labels)
        profile_version=profile_data.get("profile_version") or r["profile_snapshot"].get("profile_version",1)
        source={
            "contract_version":CONTENT_CONTRACT_VERSION,"generator_version":CONTENT_GENERATOR_VERSION,
            "user":{"user_id":user_id,"profile_version":profile_version,"profile_snapshot":profile_data},
            "path":{"path_id":r["path_id"],"plan_id":plan_id,"plan_version":r["version"],"goal_text":r["goal_text"]},
            "day":{"day":int(day),"scheduled_minutes":int(plan_day.get("total_minutes") or 0),"activities":plan_day.get("activities",[])},
            "concepts":r["plan"].get("concept_path") or [],"kg_context":[c.get("kg_context") for c in contexts],
            "retrieved_evidence":evidence,"recommended_resources":resources,"prior_learning_signals":prior_signals,
        }
        if force: source["force_nonce"]=str(uuid.uuid4())
        source_hash=hashlib.sha256(json.dumps(source,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
        if not force:
            cached=self.store.content_by_hash(user_id,plan_id,day,source_hash)
            if cached: return self.with_session_progress({**cached,"cache_status":"hit"})
        base=self.plan_session(r,plan_day,contexts,evidence,resources,labels,profile_data)
        mode="fallback"; reason=None
        try:
            generated=self.model_generator(source) if self.model_generator else self.openai_session(r,plan_day,contexts,evidence,resources,labels,profile_data,base)
            session=self.merge_live_session(base,generated)
            self.validate_session(plan_day,session)
            block_modes=[b.get("generation_mode","live") for b in session.get("study_blocks",[])]
            mode="live" if block_modes and all(x=="live" for x in block_modes) else ("mixed" if any(x=="live" for x in block_modes) else "fallback")
            if mode!="live": reason="partial_block_fallback" if mode=="mixed" else "all_blocks_failed_quality_gate"
        except Exception as exc:
            reason=type(exc).__name__; session=base
        lesson=self.legacy_lesson(session)
        payload={
            "contract_version":CONTENT_CONTRACT_VERSION,"content_id":str(uuid.uuid4()),"user_id":user_id,
            "path_id":r["path_id"],"plan_id":plan_id,"plan_version":r["version"],"day":int(day),
            "goal_text":r["goal_text"],"scheduled_minutes":int(plan_day.get("total_minutes") or 0),
            "topic_ids":topics,"topic_labels":[labels.get(x,x) for x in topics],
            "session_overview":session["session_overview"],"study_blocks":session["study_blocks"],
            "required_resources":session["required_resources"],"optional_resources":session["optional_resources"],
            "followup_tasks":session["followup_tasks"],"prepared_evidence":evidence,
            "lesson":lesson,"resources":[*session["required_resources"],*session["optional_resources"]],
            "citations":self.citations_from_contexts(contexts,evidence),
            "retrieval":{"kg_sources":list(dict.fromkeys(c.get("kg_source","unavailable") for c in contexts)),"public_rag_chunks":sum(1 for e in evidence if e["source_type"]=="public_rag"),"private_rag_chunks":sum(1 for e in evidence if e["source_type"]=="private_document")},
            "source_hash":source_hash,"generation_mode":mode,"fallback_reason":reason,"cache_status":"miss","created_at":now_iso(),
        }
        payload["generation_metadata"]={
            "generation_mode":mode,"cache_status":"miss","content_contract_version":CONTENT_CONTRACT_VERSION,
            "generator_version":CONTENT_GENERATOR_VERSION,"profile_version":profile_version,"source_hash":source_hash,
            **payload["retrieval"],"fallback_reason":reason,
        }
        saved=self.store.save_content(payload); self.store.save_session(saved)
        return self.with_session_progress(saved)

    def get_session(self,*,user_id,plan_id,day):
        record=self.plan(user_id,plan_id); self.day(record,day)
        session=self.store.session(user_id,plan_id,day)
        completed=self.store.is_day_completed(user_id,record["path_id"],day)
        generator=(session.get("generation_metadata") or {}).get("generator_version") if session else None
        if session and (completed or generator==CONTENT_GENERATOR_VERSION): return self.with_session_progress(session)
        if not completed:
            return self.generate_content(user_id=user_id,plan_id=plan_id,day=day)
        content=self.get_content(user_id=user_id,plan_id=plan_id,day=day)
        if content.get("contract_version")==CONTENT_CONTRACT_VERSION:
            self.store.save_session(content); session=content
        else: session=self.upgrade_legacy_content(content)
        return self.with_session_progress(session)

    def with_session_progress(self,payload):
        if not payload.get("study_blocks"): return payload
        progress={x["block_id"]:x for x in self.store.block_progress(payload["user_id"],payload["plan_id"],payload["day"])}
        blocks=[]
        first_open=True
        for block in payload["study_blocks"]:
            row=progress.get(block["block_id"])
            status=row["status"] if row else ("available" if first_open else "locked")
            if status=="completed": first_open=True
            elif status in {"available","in_progress"}: first_open=False
            blocks.append({**block,"progress_state":row or {"status":status,"progress":1 if status=="completed" else 0,"actual_seconds":0}})
        completed=sum(1 for b in blocks if b["progress_state"]["status"]=="completed")
        required=[b for b in blocks if b.get("required",True)]
        return {**payload,"study_blocks":blocks,"session_progress":{"completed_blocks":completed,"total_blocks":len(blocks),"required_completed":sum(1 for b in required if b["progress_state"]["status"]=="completed"),"required_total":len(required),"fraction":round(completed/len(blocks),4) if blocks else 0}}

    def assert_required_blocks_complete(self,*,user_id,plan_id,day):
        session=self.get_session(user_id=user_id,plan_id=plan_id,day=day)
        remaining=[b for b in session.get("study_blocks",[]) if b.get("required",True) and (b.get("progress_state") or {}).get("status")!="completed"]
        if remaining: raise DailyLearningValidationError(f"Complete {len(remaining)} required study block(s) before taking the quiz")
        return session

    def update_block(self,*,user_id,plan_id,day,block_id,status,progress=None,actual_seconds=0,answer=None,feedback=None):
        session=self.get_session(user_id=user_id,plan_id=plan_id,day=day)
        block=next((b for b in session.get("study_blocks",[]) if b["block_id"]==block_id),None)
        if not block: raise DailyLearningNotFoundError(block_id)
        if status not in {"available","in_progress","completed","skipped_optional"}: raise DailyLearningValidationError("Unsupported study block status")
        if status=="skipped_optional" and block.get("required",True): raise DailyLearningValidationError("Required study blocks cannot be skipped")
        value=1 if status in {"completed","skipped_optional"} else max(0,min(1,float(progress or 0)))
        row=self.store.save_block_progress(user_id=user_id,plan_id=plan_id,day=day,block_id=block_id,status=status,progress=value,actual_seconds=actual_seconds,answer=answer,feedback=feedback)
        refreshed=self.get_session(user_id=user_id,plan_id=plan_id,day=day)
        blocks=refreshed["study_blocks"]
        current_index=next(i for i,b in enumerate(blocks) if b["block_id"]==block_id)
        if status in {"completed","skipped_optional"} and current_index+1<len(blocks):
            nxt=blocks[current_index+1]
            if nxt["progress_state"]["status"]=="locked":
                self.store.save_block_progress(user_id=user_id,plan_id=plan_id,day=day,block_id=nxt["block_id"],status="available",progress=0)
        return {"block_progress":row,"session":self.get_session(user_id=user_id,plan_id=plan_id,day=day)}

    def regenerate_block(self,*,user_id,plan_id,day,block_id):
        session=self.get_session(user_id=user_id,plan_id=plan_id,day=day)
        block=next((b for b in session.get("study_blocks",[]) if b["block_id"]==block_id),None)
        if not block: raise DailyLearningNotFoundError(block_id)
        mode="fallback"; reason=None; replacement={**block,"content":dict(block.get("content") or {})}
        try:
            if not os.getenv("OPENAI_API_KEY"): raise RuntimeError("OPENAI_API_KEY is not configured")
            r=self.plan(user_id,plan_id); profile=self.backend.profiles.get_profile(user_id); profile_data=profile if isinstance(profile,dict) else (profile.model_dump() if hasattr(profile,"model_dump") else vars(profile))
            mini={"session_overview":session["session_overview"],"study_blocks":[block],"required_resources":session.get("required_resources",[]),"optional_resources":session.get("optional_resources",[]),"followup_tasks":session.get("followup_tasks",[])}
            generated=self.openai_session(r,self.day(r,day),[],session.get("prepared_evidence",[]),{"required":session.get("required_resources",[]),"optional":session.get("optional_resources",[])},{},profile_data,mini)
            replacement=generated["study_blocks"][0]; mode="live"
        except Exception as exc: reason=type(exc).__name__
        updated=[]
        for item in session["study_blocks"]: updated.append(replacement if item["block_id"]==block_id else {k:v for k,v in item.items() if k!="progress_state"})
        clean={k:v for k,v in session.items() if k not in {"session_progress"}}
        clean["study_blocks"]=updated; clean["lesson"]=self.legacy_lesson(clean); clean["generation_mode"]="mixed" if mode=="live" else clean.get("generation_mode","fallback"); clean.setdefault("block_generation",{})[block_id]={"mode":mode,"fallback_reason":reason,"generated_at":now_iso()}
        self.store.save_session(clean)
        return {"block":replacement,"generation_mode":mode,"fallback_reason":reason,"session":self.get_session(user_id=user_id,plan_id=plan_id,day=day)}

    def resource_context(self,*,user_id,resource_id):
        with self.store.connect() as c:
            rows=c.execute("SELECT session_json FROM daily_sessions WHERE user_id=? ORDER BY created_at DESC",(user_id,)).fetchall()
        for row in rows:
            session=json.loads(row[0])
            resource=next((x for x in [*(session.get("required_resources") or []),*(session.get("optional_resources") or [])] if x.get("resource_id")==resource_id),None)
            if resource:
                evidence=[e for e in session.get("prepared_evidence",[]) if e.get("resource_id")==resource_id or (resource.get("document_id") and e.get("document_id")==resource.get("document_id"))]
                return {"resource":resource,"evidence":evidence}
        raise DailyLearningNotFoundError(resource_id)

    def resources(self,*,user_id,plan_id,day): return self.generate_content(user_id=user_id,plan_id=plan_id,day=day).get("resources",[])
    def context(self,user_id,path_id,concept_id,profile):
        if self.context_provider: return self.context_provider(user_id=user_id,path_id=path_id,concept_id=concept_id,profile=profile)
        kg={}; kg_source="unavailable"; errors=[]; attempts=[]
        if os.getenv("NEO4J_PASSWORD"): attempts.append(("neo4j",None))
        graph=CALIBRATED_KG if CALIBRATED_KG.exists() else GLOBAL_KG; attempts.append(("json",str(graph)))
        for kind,path in attempts:
            try:
                from agents.planning_agent import PlanningAgent
                kg=PlanningAgent(graph_path=path,kg_backend=kind).repository.get_concept_context(concept_id,similar_limit=5)
                if kg.get("concept"): kg_source=kind; break
            except Exception as exc: errors.append(f"{kind}:{type(exc).__name__}")
        resources=[]
        if profile and kg:
            try:
                from agents.resource_recommendation_service import ResourceRecommendationService
                resources=ResourceRecommendationService().rank_resources(concept_id,profile,kg,top_k=3)
            except Exception as exc: errors.append(f"resources:{type(exc).__name__}")
        public=[]
        try:
            from infra.rag_repository import RAGRepository
            public=RAGRepository().get_chunks_by_topic(concept_id,top_k=3)
        except Exception as exc: errors.append(f"public_rag:{type(exc).__name__}")
        return {"concept_id":concept_id,"kg_context":kg,"kg_source":kg_source,"recommended_resources":resources,"public_chunks":public,"private_chunks":self.private_chunks(user_id,path_id,concept_id),"errors":errors}
    def private_chunks(self,user_id,path_id,concept_id):
        document_ids=self.store.document_ids(path_id)
        if not document_ids: return []
        try:
            collection=self.document_service._chroma_collection(user_id); rows=[]
            for document_id in document_ids:
                result=collection.query(query_embeddings=[_hash_embedding(concept_id)],n_results=2,where={"document_id":document_id})
                for chunk_id,text,metadata,distance in zip(result.get("ids",[[]])[0],result.get("documents",[[]])[0],result.get("metadatas",[[]])[0],result.get("distances",[[]])[0]): rows.append({"id":chunk_id,"text":text,"metadata":metadata,"distance":distance,"private":True})
            return sorted(rows,key=lambda x:x.get("distance",1))[:5]
        except Exception:
            rows=[]
            for document_id in document_ids: rows.extend(self.documents.get_chunks(user_id,document_id)[:2])
            return [{"id":x["chunk_id"],"text":x["text"],"metadata":{"document_id":x["document_id"],"page_start":x.get("page_start"),"page_end":x.get("page_end")},"private":True} for x in rows[:5]]
    @staticmethod
    def concept_label(node,index):
        concept_id=str(node.get("concept_id") or "")
        for key in ("display_name","requested_term","label","name","title"):
            value=str(node.get(key) or "").strip()
            if value and not value.startswith("private:"): return value
        return f"Private concept {index}" if concept_id.startswith("private:") else concept_id or f"Concept {index}"

    @staticmethod
    def block_id_for(record,plan_day,activity,sequence):
        raw="|".join([str(record.get("path_id","")),str(record.get("plan_id","")),str(plan_day.get("day","")),str(activity.get("activity_id") or ""),str(activity.get("activity_type") or ""),str(sequence)])
        suffix=hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
        return f'block-day{int(plan_day["day"])}-{int(sequence):02d}-{suffix}'

    @staticmethod
    def resources_from(contexts):
        output=[]; seen=set()
        for context in contexts:
            for item in context.get("recommended_resources",[]):
                resource_id=str(item.get("id") or item.get("resource_id") or "")
                if resource_id and resource_id not in seen:
                    seen.add(resource_id); output.append({"resource_id":resource_id,"title":item.get("title") or item.get("filename") or resource_id,"resource_type":item.get("type") or "learning_resource","type":item.get("type") or "learning_resource","difficulty":item.get("resource_difficulty"),"source_type":"kg_resource","source":context.get("kg_source"),"reason":item.get("match_reason"),"estimated_minutes":item.get("estimated_minutes")})
        return output[:8]

    @classmethod
    def build_resources(cls,record,plan_day,contexts,evidence,labels):
        recommended=cls.resources_from(contexts); required=[]; optional=[]; used=set()
        readings=[a for a in plan_day.get("activities",[]) if a.get("activity_type")=="required_reading"]
        for index,activity in enumerate(readings,1):
            concept_ids=[str(x) for x in activity.get("concept_ids",[])]
            refs=activity.get("source_refs") or []
            ref=refs[0] if refs else {}
            candidate=next((e for e in evidence if (not concept_ids or e.get("concept_id") in concept_ids) and (not ref.get("document_id") or e.get("document_id")==ref.get("document_id"))),None)
            resource_id=str(ref.get("resource_id") or ref.get("document_id") or (candidate or {}).get("resource_id") or (candidate or {}).get("document_id") or f"required-reading-{plan_day['day']}-{index}")
            fallback_title="Required reading: "+(labels.get(concept_ids[0],concept_ids[0]) if concept_ids else "today's topic")
            title=str(ref.get("title") or ref.get("filename") or activity.get("title") or fallback_title)
            block_id=cls.block_id_for(record,plan_day,activity,int(plan_day.get('activities',[]).index(activity))+1)
            page_start=ref.get("page_start") or (candidate or {}).get("page_start"); page_end=ref.get("page_end") or (candidate or {}).get("page_end")
            required.append({"resource_id":resource_id,"usage":"required","linked_block_ids":[block_id],"title":title,"resource_type":"private_pdf" if (ref.get("document_id") or (candidate or {}).get("source_type")=="private_document") else "learning_resource","type":"private_pdf" if ref.get("document_id") else "learning_resource","source_type":(candidate or {}).get("source_type") or ("private_document" if ref.get("document_id") else "scheduled_reading"),"document_id":ref.get("document_id") or (candidate or {}).get("document_id"),"difficulty":ref.get("difficulty"),"estimated_minutes":int(activity.get("estimated_minutes") or 0),"reading_scope":{"page_start":page_start,"page_end":page_end,"section_title":ref.get("section_title") or (candidate or {}).get("section_title")},"why_selected":activity.get("reason") or "This source is part of the confirmed workload for today.","reason":activity.get("reason") or "Required by the confirmed learning path.","what_to_focus_on":["Identify the central claim.","Connect the reading to today's concept."],"after_reading_question":"What is the most important idea from this reading, in your own words?","access":{"type":"internal_document_viewer" if ref.get("document_id") else "retrieved_context","available":bool(candidate or ref)}})
            used.add(resource_id)
        for item in recommended:
            if item["resource_id"] in used: continue
            optional.append({**item,"usage":"optional","linked_block_ids":[],"why_selected":item.get("reason") or "This resource matches today's topic and your learner profile.","reason":item.get("reason") or "Optional extension for today's topic.","access":{"type":"resource_reference","available":True}})
        return {"required":required,"optional":optional[:5]}

    @staticmethod
    def citations_from_prepared(evidence):
        return [{"citation_id":e["evidence_id"],"chunk_id":e["evidence_id"],"concept_id":e["concept_id"],"source_type":e["source_type"],"document_id":e.get("document_id"),"resource_id":e.get("resource_id"),"page_start":e.get("page_start"),"page_end":e.get("page_end"),"excerpt":e["clean_text"][:240]} for e in evidence[:10]]

    @classmethod
    def citations_from_contexts(cls,contexts,evidence):
        output=cls.citations_from_prepared(evidence); seen={x["chunk_id"] for x in output}
        for context in contexts:
            for item in [*(context.get("private_chunks") or []),*(context.get("public_chunks") or [])]:
                chunk_id=str(item.get("id") or item.get("chunk_id") or "")
                if not chunk_id or chunk_id in seen: continue
                clean,flags=EvidencePreparer.clean(str(item.get("text") or "")); metadata=item.get("metadata") or {}
                if not clean: continue
                seen.add(chunk_id);output.append({"citation_id":chunk_id,"chunk_id":chunk_id,"concept_id":context["concept_id"],"source_type":"private_document" if item.get("private") else "public_rag","document_id":metadata.get("document_id"),"resource_id":metadata.get("resource_id"),"page_start":metadata.get("page_start"),"page_end":metadata.get("page_end"),"excerpt":clean[:240],"quality_flags":flags,"used_in_teaching":False})
        return output[:10]

    @staticmethod
    def profile_note(profile):
        style=str(profile.get("learning_style") or profile.get("preferred_style") or "mixed").replace("_"," ")
        examples=profile.get("preferred_examples") or []
        example_text=f" with {', '.join(str(x).replace('_',' ') for x in examples[:2])} examples" if examples else ""
        return f"This session uses a {style} approach{example_text}, matched to your saved learning preferences."

    @classmethod
    def plan_session(cls,record,plan_day,contexts,evidence,resources,labels,profile):
        day=int(plan_day["day"]); activities=plan_day.get("activities") or []; blocks=[]
        by_concept={c["concept_id"]:c for c in contexts}; evidence_by={}
        for item in evidence: evidence_by.setdefault(item["concept_id"],[]).append(item)
        required_by_block={bid:r for r in resources["required"] for bid in r.get("linked_block_ids",[])}
        for sequence,activity in enumerate(activities,1):
            activity_type=str(activity.get("activity_type") or "practice")
            concept_ids=[str(x) for x in activity.get("concept_ids",[])]
            names=[labels.get(x,x) for x in concept_ids] or ["today's topic"]
            block_id=cls.block_id_for(record,plan_day,activity,sequence)
            related_evidence=[e for cid in concept_ids for e in evidence_by.get(cid,[])][:3]
            block={"block_id":block_id,"activity_id":str(activity.get("activity_id") or f"activity-{day}-{sequence}"),"activity_type":activity_type,"block_type":ACTIVITY_BLOCK_TYPES.get(activity_type,"guided_practice"),"sequence":sequence,"title":cls.block_title(activity_type,names,activity),"concept_ids":concept_ids,"estimated_minutes":int(activity.get("estimated_minutes") or 0),"required":not bool(activity.get("optional")),"completion_rule":{"type":"learner_confirmation","minimum_interactions":1},"content":cls.fallback_block_content(activity_type,names,concept_ids,by_concept,related_evidence,required_by_block.get(block_id),profile,day),"source_refs":[e["evidence_id"] for e in related_evidence],"personalization_reason":cls.personalization_reason(activity_type,profile)}
            blocks.append(block)
        session={"session_overview":{"title":f"Day {day}: {' and '.join([labels.get(c['concept_id'],c['concept_id']) for c in contexts[:2]])}","opening_hook":f"How can today's ideas help you move closer to {record['goal_text']}?","learning_objectives":[{"objective_id":f"objective-{i}","text":f"Use {labels.get(c['concept_id'],c['concept_id'])} in today's scheduled activities.","concept_ids":[c["concept_id"]],"mastery_action":"apply" if any(b["activity_type"] in {"practice","code","project"} and c["concept_id"] in b["concept_ids"] for b in blocks) else "explain"} for i,c in enumerate(contexts,1)],"prerequisite_recap":cls.prerequisite_recaps(contexts,labels),"personalization_note":cls.profile_note(profile),"total_minutes":int(plan_day.get("total_minutes") or sum(b["estimated_minutes"] for b in blocks))},"study_blocks":blocks,"required_resources":resources["required"],"optional_resources":resources["optional"],"followup_tasks":[{"task_id":f"followup-day-{day}","type":"reflection","prompt":"Write down one idea you can now explain and one question you still have.","optional":True}]}
        cls.validate_session(plan_day,session)
        return session

    @staticmethod
    def block_title(activity_type,names,activity):
        prefix={"explanation":"Learn","example":"Worked example","required_reading":"Read","practice":"Practice","code":"Code","review":"Review","quiz":"Prepare for the quiz","project":"Project milestone","reflection":"Reflect on"}.get(activity_type,"Explore")
        raw=str(activity.get("title") or "")
        if raw and ":" in raw: raw=raw.split(":",1)[1].strip()
        return f"{prefix}: {raw or ' & '.join(names)}"

    @staticmethod
    def personalization_reason(activity_type,profile):
        style=str(profile.get("learning_style") or profile.get("preferred_style") or "mixed").replace("_"," ")
        programming=profile.get("programming_ability") or profile.get("programming_foundation")
        if activity_type=="code" and programming: return f"The starter structure is adjusted for programming foundation {programming}/5."
        return f"The {activity_type.replace('_',' ')} format supports your {style} learning preference."

    @staticmethod
    def prerequisite_recaps(contexts,labels):
        out=[]; seen=set()
        for context in contexts:
            kg=context.get("kg_context") or {}
            candidates=kg.get("prerequisites") or kg.get("prerequisite_concepts") or []
            for item in candidates[:2]:
                cid=str(item.get("concept_id") or item.get("id") or item.get("name") if isinstance(item,dict) else item)
                if not cid or cid in seen: continue
                seen.add(cid); name=labels.get(cid,cid)
                out.append({"concept_id":cid,"title":f"Quick recap: {name}","content":f"Recall how {name} supports the concept you are about to study. Focus on the relationship, not memorizing an isolated definition.","estimated_minutes":0})
        return out[:3]

    @staticmethod
    def fallback_block_content(activity_type,names,concept_ids,by_concept,evidence,resource,profile,day):
        name=" and ".join(names)
        concept=next(((by_concept.get(cid,{}).get("kg_context") or {}).get("concept") or {} for cid in concept_ids),{})
        definition=str(concept.get("description") or concept.get("summary") or f"{name} is a confirmed part of this learning path.")
        excerpt=evidence[0]["clean_text"] if evidence else ""
        refs=[e["evidence_id"] for e in evidence]
        interests=profile.get("interest_tags") or profile.get("preferred_examples") or ["your learning goal"]
        if isinstance(interests,str): interests=[interests]
        interest_text=", ".join([str(x).replace("_"," ") for x in interests[:2]]) or "your learning goal"
        def task(prompt,placeholder,expected=None):
            return {"prompt":prompt,"placeholder":placeholder,"expected_elements":expected or ["concept meaning","reasoning","example"],"minimum_words":18}
        if activity_type=="explanation":
            return {
                "opening_question":f"Where would {name} show up in a real task, and what would break if you misunderstood it?",
                "plain_explanation":definition,
                "learning_flow":[
                    {"step":"Intuition","body":f"Start with the job {name} performs. In this path, treat it as a tool for moving from raw information toward a useful decision or model behavior, not as a term to memorize."},
                    {"step":"Mechanism","body":f"To reason about {name}, identify the input, the transformation, and the output. Then ask which assumptions must hold for that transformation to be valid."},
                    {"step":"Concrete example","body":f"In a {interest_text} scenario, use {name} to explain one observed result: what data or signal comes in, what the system does with it, and what the learner or model can do next."},
                    {"step":"Boundary","body":f"A concept is not mastered when you can repeat its name. You should also know when {name} is not enough and what prerequisite or next concept is needed."},
                ],
                "mental_model":{"title":f"A working model of {name}","description":f"Think of {name} as a small machine with three labels: input, operation, output. If you cannot fill in all three labels, slow down before moving on.","visual_spec":{"type":"relationship_diagram","nodes":concept_ids,"edges":[]}},
                "detailed_explanation":[
                    {"heading":"What it means","body":definition,"source_refs":refs},
                    {"heading":"How to use it today","body":f"When you meet {name} in the activities below, do not only define it. Use it to make a prediction, interpret an example, or decide what should happen next.","source_refs":refs},
                    {"heading":"How it connects to the path","body":f"This block prepares you to use {name} in later exercises. Keep a note of which earlier idea it depends on and which later task it unlocks.","source_refs":refs},
                ],
                "prerequisite_connections":[],
                "common_misconceptions":[{"misconception":f"Recognizing the term {name} means it is already mastered.","correction":"Mastery means you can explain the purpose, apply it in a small task, and notice a case where it does not apply."}],
                "mini_task":task(f"Write 2-3 sentences that teach {name} to someone one step behind you. Include what it does and one example.",f"{name} means... It helps when... For example...",["definition","use case","example"]),
                "self_check":["Can I explain the input, operation, and output?","Can I give one example without copying the text?","Can I name one common mistake?"],
                "checkpoint":{"prompt":f"Explain {name} in your own words and name one use.","expected_elements":["purpose","application"]},
            }
        if activity_type=="example":
            return {
                "scenario":f"Use {name} in a small decision connected to {interest_text}.",
                "problem":f"Identify what {name} contributes and what evidence would show that it worked.",
                "steps":[
                    {"step":1,"instruction":"State the input and desired result.","explanation":"A clear boundary makes the concept easier to apply."},
                    {"step":2,"instruction":f"Apply the central idea of {name}.","explanation":definition},
                    {"step":3,"instruction":"Check the result and explain the connection.","explanation":"The explanation is part of the worked solution."},
                ],
                "solution":f"A sound solution names the role of {name}, applies it to the scenario, and checks the result against the goal.",
                "why_it_works":definition,
                "learner_task":task(f"Create your own tiny example using {name}. Keep it concrete: input, action, output.","Input: ...\nAction: ...\nOutput: ...",["input","action","output"]),
                "transfer_question":f"Where else could the same reasoning about {name} be used?",
            }
        if activity_type=="required_reading":
            return {
                "resource_id":(resource or {}).get("resource_id"),
                "reading_scope":(resource or {}).get("reading_scope") or {},
                "why_read":f"Read this because it provides source-grounded context for {name}, so the lesson is not only based on a generated summary.",
                "what_to_look_for":(resource or {}).get("what_to_focus_on") or [f"How the source defines or uses {name}","One example, assumption, or limitation you can reuse later"],
                "before_reading":f"Before reading, write one sentence about what you already believe about {name}.",
                "focus_questions":(resource or {}).get("what_to_focus_on") or [f"How does the source define {name}?",f"What evidence or example supports the explanation?"],
                "guided_excerpt":excerpt[:700] if excerpt else "No clean direct excerpt was available. Use the linked reading scope and focus questions.",
                "learner_task":task(f"After reading, write the central claim about {name} and one question you still have.","Central claim: ...\nMy question: ...",["central claim","remaining question"]),
                "after_reading_task":(resource or {}).get("after_reading_question") or f"Summarize the central claim about {name} in your own words.",
            }
        if activity_type in {"practice","code"}:
            code=activity_type=="code"
            return {
                "task":f"{'Implement a small example of' if code else 'Apply'} {name} and explain your result.",
                "instructions":["Restate the goal in your own words.",f"Use the core idea of {name} to complete the task.","Check the result and describe what it means."],
                "starter_code":f"# Starter for {name}\n# 1. Define a small input\n# 2. Apply the concept\n# 3. Print and explain the result\n" if code else "",
                "expected_output":f"A result plus a short explanation showing how it demonstrates {name}.",
                "hints":["Start with the smallest possible example.","If stuck, return to the plain explanation and identify the input and output."],
                "learner_task":task(f"Write your answer or result for this {activity_type} block. Include one sentence explaining why it works.","My result: ...\nWhy it works: ...",["result","explanation"]),
                "self_check":["Did you complete every instruction?","Can you explain the result without copying the lesson?"],
                "sample_solution":{"collapsed_by_default":True,"code":"# Compare your work with the three-step structure above." if code else "","explanation":f"A complete response applies {name}, checks the result, and explains why the result follows."},
            }
        if activity_type=="review":
            return {"review_source_days":list(range(max(1,day-3),day)),"retrieval_prompts":[f"Without looking back, define {name}.",f"Give one example and one non-example of {name}."],"error_correction":[f"If your definition only repeats the name, add its purpose and use."],"learner_task":task(f"Answer one retrieval prompt from memory before checking the lesson again.","From memory: ...",["recall","correction"]),"connection_task":f"Connect {name} to another concept in the current path.","recommended_action":f"Return to the earliest completed explanation of {name} if recall remains difficult."}
        if activity_type=="quiz":
            return {"mastery_checklist":[f"I can explain {name}.",f"I can apply {name} to a new example.",f"I can identify a common misconception about {name}."],"practice_questions":[f"What is the role of {name}?",f"When would you use {name}?"],"learner_task":task(f"Answer one practice question before opening the formal quiz.","My answer: ...",["answer","reason"]),"ready_when":"You can answer both questions without reopening the explanation."}
        if activity_type=="project":
            return {"deliverable":f"Create a small artifact that uses {name}.","milestones":["Define the problem and success condition.","Build the smallest working version.","Explain one design decision and one limitation."],"acceptance_criteria":[f"The artifact visibly uses {name}.","The result is explained, not only presented."],"learner_task":task("Paste or describe the artifact you produced and one limitation.","Artifact/result: ...\nLimitation: ...",["artifact","limitation"]),"reflection_prompt":"What would you improve with another iteration?"}
        return {"prompts":[f"What changed in your understanding of {name}?",f"What remains uncertain?",f"Where could you apply this next?"],"learner_task":task("Write a short reflection before finishing this block.","I learned...\nI still wonder...",["learning","question"]),"connection_to_goal":f"Use the reflection to connect today's work back to {name} and the overall goal."}
    @staticmethod
    def validate_session(plan_day,session):
        blocks=session.get("study_blocks") or []
        activities=plan_day.get("activities") or []
        if len(blocks)<len(activities): raise DailyLearningValidationError("Every scheduled activity must have a study block")
        covered={b.get("activity_id") for b in blocks}
        missing=[str(a.get("activity_id")) for a in activities if str(a.get("activity_id")) not in covered]
        if missing: raise DailyLearningValidationError(f"Study blocks do not cover activities: {', '.join(missing)}")
        expected=sum(int(a.get("estimated_minutes") or 0) for a in activities if not a.get("optional"))
        actual=sum(int(b.get("estimated_minutes") or 0) for b in blocks if b.get("required",True))
        if expected!=actual: raise DailyLearningValidationError(f"Required block minutes {actual} do not match scheduled minutes {expected}")
        if int(session.get("session_overview",{}).get("total_minutes") or 0)!=int(plan_day.get("total_minutes") or expected): raise DailyLearningValidationError("Session total does not match scheduled day total")
        for block in blocks:
            if not block.get("block_id") or not block.get("content"): raise DailyLearningValidationError("Every study block needs an id and content")
        return True

    @classmethod
    def merge_live_session(cls,base,generated):
        if not isinstance(generated,dict): raise ValueError("Content model returned invalid JSON")
        if generated.get("study_blocks"):
            live={**base,**{k:v for k,v in generated.items() if k in {"session_overview","study_blocks","required_resources","optional_resources","followup_tasks"}}}
            base_by={b["activity_id"]:b for b in base["study_blocks"]}
            normalized=[]
            for index,item in enumerate(live["study_blocks"]):
                fallback=base_by.get(str(item.get("activity_id"))) or base["study_blocks"][min(index,len(base["study_blocks"])-1)]
                normalized.append({**fallback,**item,"block_id":fallback["block_id"],"activity_id":fallback["activity_id"],"estimated_minutes":fallback["estimated_minutes"],"required":fallback["required"],"sequence":fallback["sequence"],"content":item.get("content") or fallback["content"]})
            live["study_blocks"]=normalized
            return live
        if generated.get("sections"):
            session={**base,"session_overview":{**base["session_overview"],"title":generated.get("title") or base["session_overview"]["title"]}}
            sections=generated.get("sections") or []
            for index,block in enumerate(session["study_blocks"]):
                if block["block_type"]=="concept_lesson" and sections:
                    section=sections[min(index,len(sections)-1)]
                    block["content"]={**block["content"],"plain_explanation":section.get("explanation") or block["content"].get("plain_explanation"),"detailed_explanation":[{"heading":section.get("title") or block["title"],"body":section.get("explanation") or "","source_refs":block.get("source_refs",[])}],"checkpoint":{"prompt":section.get("application") or block["content"]["checkpoint"]["prompt"],"expected_elements":section.get("key_points") or []}}
            return session
        raise ValueError("Content model returned neither study_blocks nor legacy sections")

    @classmethod
    def legacy_lesson(cls,session):
        sections=[]
        for block in session.get("study_blocks",[]):
            content=block.get("content") or {}; explanation=content.get("plain_explanation") or content.get("why_it_works") or content.get("before_reading") or content.get("task") or content.get("connection_task") or content.get("connection_to_goal") or "Complete this scheduled learning activity."
            example=content.get("scenario") or content.get("guided_excerpt") or content.get("expected_output") or ""
            application=content.get("after_reading_task") or content.get("task") or (content.get("checkpoint") or {}).get("prompt") or content.get("reflection_prompt") or "Complete this block and explain what you learned."
            points=content.get("self_check") or content.get("focus_questions") or content.get("mastery_checklist") or []
            sections.append({"section_id":block["block_id"],"title":block["title"],"explanation":explanation,"example":example,"application":application,"key_points":points[:4]})
        overview=session["session_overview"]
        return {"title":overview["title"],"objectives":[x["text"] for x in overview.get("learning_objectives",[])],"sections":sections,"summary":"Complete each required study block, use the linked resources, and record questions before taking the daily quiz."}

    def upgrade_legacy_content(self,content):
        r=self.plan(content["user_id"],content["plan_id"]); plan_day=self.day(r,content["day"]); labels={cid:label for cid,label in zip(content.get("topic_ids",[]),content.get("topic_labels",[]))}; contexts=[{"concept_id":cid,"kg_context":{},"kg_source":"legacy","recommended_resources":[],"public_chunks":[],"private_chunks":[]} for cid in content.get("topic_ids",[])]; resources={"required":[],"optional":[{**x,"usage":"optional","linked_block_ids":[]} for x in content.get("resources",[])]}; base=self.plan_session(r,plan_day,contexts,[],resources,labels,r.get("profile_snapshot") or {}); session=self.merge_live_session(base,content.get("lesson") or {}); upgraded={**content,"contract_version":CONTENT_CONTRACT_VERSION,"session_overview":session["session_overview"],"study_blocks":session["study_blocks"],"required_resources":session["required_resources"],"optional_resources":session["optional_resources"],"followup_tasks":session["followup_tasks"],"prepared_evidence":[]}; self.store.save_session(upgraded); return upgraded

    @staticmethod
    def content_schema(value):
        if isinstance(value,dict): return {key:DailyLearningService.content_schema(item) for key,item in value.items()}
        if isinstance(value,list): return [DailyLearningService.content_schema(value[0])] if value else ["string"]
        if isinstance(value,bool): return "boolean"
        if isinstance(value,(int,float)): return "number"
        return "string"

    @staticmethod
    def validate_teaching_block(block):
        content=block.get("content") or {}; kind=block.get("block_type"); minutes=max(1,int(block.get("estimated_minutes") or 1))
        def words(value): return len(re.findall(r"\b\w+\b",str(value or "")))
        if kind=="concept_lesson":
            total=words(content.get("plain_explanation"))+sum(words(x.get("body")) for x in content.get("detailed_explanation",[]))+words((content.get("mental_model") or {}).get("description"))
            minimum=max(140,minutes*10)
            plain_words=words(content.get("plain_explanation")); mental_words=words((content.get("mental_model") or {}).get("description")); detailed=content.get("detailed_explanation",[]); misconceptions=content.get("common_misconceptions",[])
            required_sections=3 if minutes>=20 else 2
            required_misconceptions=1
            teaching_text=" ".join([str(block.get("title") or ""),str(content.get("plain_explanation") or ""),str((content.get("mental_model") or {}).get("description") or "")]+[str(x.get("body") or "") for x in detailed]).lower()
            named=[str(cid).lower() for cid in block.get("concept_ids",[]) if cid and not str(cid).startswith("private:")]
            topic_ok=not named or any(name in teaching_text for name in named)
            if total<minimum or plain_words<70 or mental_words<35 or len(detailed)<required_sections or len(misconceptions)<required_misconceptions or not topic_ok: raise ValueError(f"concept lesson failed quality/relevance: total={total}/{minimum}, plain={plain_words}/70, mental={mental_words}/35, sections={len(detailed)}/{required_sections}, misconceptions={len(misconceptions)}/{required_misconceptions}, topic_ok={topic_ok}")
        elif kind=="worked_example":
            if len(content.get("steps",[]))<3 or words(content.get("solution"))<60: raise ValueError("worked example lacks a taught solution")
        elif kind=="guided_reading":
            if len(content.get("focus_questions",[]))<2 or words(content.get("guided_excerpt"))<40: raise ValueError("guided reading lacks usable reading content")
        elif kind in {"guided_practice","coding_task"}:
            if len(content.get("instructions",[]))<3 or len(content.get("self_check",[]))<2 or words(content.get("task"))<12: raise ValueError("practice is not executable")
        elif kind=="retrieval_review" and len(content.get("retrieval_prompts",[]))<2: raise ValueError("review lacks retrieval prompts")
        return True

    @classmethod
    def openai_session(cls,record,plan_day,contexts,evidence,resources,labels,profile,base):
        api_key=os.getenv("OPENAI_API_KEY")
        if not api_key: raise RuntimeError("OPENAI_API_KEY is not configured")
        from openai import OpenAI
        client=OpenAI(api_key=api_key,timeout=75.0,max_retries=0); blocks=[]
        for fallback in base["study_blocks"]:
            relevant=[e for e in evidence if e["concept_id"] in fallback["concept_ids"]][:5]
            minutes=int(fallback["estimated_minutes"]); target_words=max(360,min(1200,minutes*18)) if fallback["block_type"]=="concept_lesson" else max(180,min(700,minutes*10)); token_budget=max(3200,min(6500,target_words*3))
            request={"audience":"The learner. Write directly to the learner and teach the subject now.","overall_learning_goal_context":record["goal_text"],"current_concepts_to_teach":fallback["concept_ids"],"current_block_title":fallback["title"],"profile":profile,"immutable_metadata":{"block_id":fallback["block_id"],"activity_id":fallback["activity_id"],"activity_type":fallback["activity_type"],"block_type":fallback["block_type"],"sequence":fallback["sequence"],"concept_ids":fallback["concept_ids"],"estimated_minutes":fallback["estimated_minutes"],"required":fallback["required"]},"required_output":{"title":"specific student-facing title","content":cls.content_schema(fallback["content"]),"personalization_reason":"one concise learner-facing sentence"},"clean_evidence":relevant,"target_teaching_words":target_words,"rules":["This is finished student-facing learning material, not a lesson plan for a teacher.","Do not copy a one-sentence KG definition as the lesson. Expand it into a self-contained explanation that teaches meaning, mechanism, examples, boundaries, and application.","The current_concepts_to_teach are the main subject. The overall learning goal is only application context; never replace the current concept with a broad explanation of the overall goal.","Name and explain every current concept explicitly in the title and teaching body.","Actually explain the ideas, demonstrate the reasoning, and carry the learner through examples step by step.","Every block must include a concrete learner action: mini_task or learner_task with prompt, placeholder, expected_elements, and minimum_words when the schema includes that field.","Do not write teacher-facing instructions. Write the actual explanation, worked answer, guided reading prompt, or learner task the student will use on the page.","Never write meta-instructions such as 'place the concept between what you know', 'complete the scheduled practice', or advice about how a teacher should teach.","Use your general domain knowledge to teach accurately. Use supplied evidence for source-grounded claims and never invent a citation, page, URL, study result, or quotation.","For a concept lesson, write multiple substantial explanatory subsections, a concrete mental model, at least one detailed misconception correction, and a meaningful checkpoint.","For a worked example, solve a real example with at least three explicit steps and explain why each step works.","For practice or code, give a self-contained task with concrete inputs, instructions, hints, expected result, self-check, and a usable solution.",f"Write at least {target_words} teaching words across the explanation, mental model, and detailed subsections so the learner receives a real lesson rather than an outline.","Keep block_id, activity_id, activity_type, block_type, required, sequence, concept_ids, and estimated_minutes unchanged.","Return one JSON object with exactly title, content, and personalization_reason, matching required_output."]}
            block=fallback;block_mode="fallback";block_reason=None;block_error_detail=None;repair_note="";best_candidate=None;best_score=-1
            for attempt in range(2):
                prompt="Generate finished Pathly learning material that teaches the learner directly. Return JSON only.\n"+json.dumps({**request,"repair_note":repair_note},ensure_ascii=False,default=str)[:60000]
                try:
                    response=client.responses.create(model=os.getenv("PATHLY_CONTENT_MODEL","gpt-5.4"),input=prompt,max_output_tokens=token_budget);text=str(response.output_text).strip()
                    if text.startswith("```"):text=text.split("\n",1)[1].rsplit("```",1)[0]
                    candidate=json.loads(text);candidate={**fallback,**candidate,"block_id":fallback["block_id"],"activity_id":fallback["activity_id"],"activity_type":fallback["activity_type"],"block_type":fallback["block_type"],"estimated_minutes":fallback["estimated_minutes"],"required":fallback["required"],"sequence":fallback["sequence"],"content":candidate.get("content") or {}}
                    candidate_score=len(re.findall(r"\b\w+\b",json.dumps(candidate.get("content") or {},ensure_ascii=False)))
                    if candidate_score>best_score: best_candidate,best_score=candidate,candidate_score
                    cls.validate_teaching_block(candidate);block=candidate;block_mode="live";block_reason=None;break
                except Exception as exc:
                    block_reason=type(exc).__name__;block_error_detail=str(exc)[:500];repair_note=f"The previous response failed the teaching-quality check: {str(exc)[:240]}. Expand and correct it; do not return meta-instructions."
            if block_mode=="fallback" and best_candidate is not None:
                try:
                    cls.validate_teaching_block(best_candidate);block=best_candidate;block_mode="live";block_reason=None;block_error_detail=None
                except Exception:
                    pass
            blocks.append({**block,"generation_mode":block_mode,"fallback_reason":block_reason,"fallback_detail":block_error_detail})
        return {**base,"study_blocks":blocks}












