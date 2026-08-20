"""Persistent chat, quiz, progress, and learner-confirmed adaptation."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
import hashlib, json, os, sqlite3, uuid
from pathlib import Path
from typing import Any
from pathly_backend import CALIBRATED_KG

def now_iso(): return datetime.now(timezone.utc).isoformat()
class LearningLoopNotFoundError(LookupError): pass
class LearningLoopValidationError(ValueError): pass

class LearningLoopStore:
    def __init__(self,db_path): self.db_path=Path(db_path); self.migrate()
    def connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; return c
    def migrate(self):
        with self.connect() as c: c.executescript("""
        CREATE TABLE IF NOT EXISTS learning_day_progress(user_id TEXT NOT NULL,path_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,status TEXT NOT NULL,content_progress REAL NOT NULL DEFAULT 0,actual_minutes INTEGER NOT NULL DEFAULT 0,started_at TEXT,completed_at TEXT,updated_at TEXT NOT NULL,PRIMARY KEY(user_id,path_id,day));
        CREATE TABLE IF NOT EXISTS daily_feedback(feedback_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,path_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,feedback_type TEXT NOT NULL,concept_ids_json TEXT NOT NULL,note TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chat_messages(message_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,path_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,role TEXT NOT NULL,body TEXT NOT NULL,citations_json TEXT NOT NULL,concept_ids_json TEXT NOT NULL,mode TEXT NOT NULL,latency_ms INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_chat_day ON chat_messages(user_id,plan_id,day,created_at);
        CREATE TABLE IF NOT EXISTS daily_quizzes(quiz_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,path_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,source_hash TEXT NOT NULL,quiz_json TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(user_id,plan_id,day,source_hash));
        CREATE TABLE IF NOT EXISTS quiz_attempts(attempt_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,path_id TEXT NOT NULL,plan_id TEXT NOT NULL,day INTEGER NOT NULL,quiz_id TEXT NOT NULL,score REAL NOT NULL,duration_seconds INTEGER NOT NULL,confidence REAL NOT NULL,weak_concepts_json TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_attempt_day ON quiz_attempts(user_id,path_id,day,created_at);
        CREATE TABLE IF NOT EXISTS adaptation_proposals(proposal_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,path_id TEXT NOT NULL,source_plan_id TEXT NOT NULL,status TEXT NOT NULL,proposal_json TEXT NOT NULL,decision_json TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        """)
    def progress_rows(self,user_id,path_id):
        with self.connect() as c: rows=c.execute("SELECT * FROM learning_day_progress WHERE user_id=? AND path_id=? ORDER BY day",(user_id,path_id)).fetchall()
        return [dict(r) for r in rows]
    def upsert_progress(self,*,user_id,path_id,plan_id,day,status,content_progress=None,actual_minutes=None,completed=False):
        stamp=now_iso()
        with self.connect() as c:
            old=c.execute("SELECT * FROM learning_day_progress WHERE user_id=? AND path_id=? AND day=?",(user_id,path_id,int(day))).fetchone()
            c.execute("""INSERT INTO learning_day_progress VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,path_id,day) DO UPDATE SET plan_id=excluded.plan_id,status=excluded.status,content_progress=excluded.content_progress,actual_minutes=excluded.actual_minutes,started_at=COALESCE(learning_day_progress.started_at,excluded.started_at),completed_at=COALESCE(excluded.completed_at,learning_day_progress.completed_at),updated_at=excluded.updated_at""",(user_id,path_id,plan_id,int(day),status,float(content_progress if content_progress is not None else (old['content_progress'] if old else 0)),int(actual_minutes if actual_minutes is not None else (old['actual_minutes'] if old else 0)),old['started_at'] if old else stamp,stamp if completed else (old['completed_at'] if old else None),stamp))
            row=c.execute("SELECT * FROM learning_day_progress WHERE user_id=? AND path_id=? AND day=?",(user_id,path_id,int(day))).fetchone()
        return dict(row)
    def save_feedback(self,p):
        with self.connect() as c: c.execute("INSERT INTO daily_feedback VALUES(?,?,?,?,?,?,?,?,?)",(p['feedback_id'],p['user_id'],p['path_id'],p['plan_id'],p['day'],p['feedback_type'],json.dumps(p['concept_ids'],ensure_ascii=False),p.get('note'),p['created_at']))
        return p
    def feedback(self,user_id,path_id):
        with self.connect() as c: rows=c.execute("SELECT * FROM daily_feedback WHERE user_id=? AND path_id=? ORDER BY created_at",(user_id,path_id)).fetchall()
        return [{**dict(r),'concept_ids':json.loads(r['concept_ids_json'])} for r in rows]
    def save_chat(self,p):
        with self.connect() as c: c.execute("INSERT INTO chat_messages VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(p['message_id'],p['user_id'],p['path_id'],p['plan_id'],p['day'],p['role'],p['body'],json.dumps(p.get('citations',[]),ensure_ascii=False),json.dumps(p.get('concept_ids',[]),ensure_ascii=False),p.get('mode','user'),int(p.get('latency_ms',0)),p['created_at']))
        return p
    def chat(self,user_id,plan_id,day):
        with self.connect() as c: rows=c.execute("SELECT * FROM chat_messages WHERE user_id=? AND plan_id=? AND day=? ORDER BY created_at",(user_id,plan_id,int(day))).fetchall()
        return [{**dict(r),'citations':json.loads(r['citations_json']),'concept_ids':json.loads(r['concept_ids_json'])} for r in rows]
    def save_quiz(self,p):
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO daily_quizzes VALUES(?,?,?,?,?,?,?,?)",(p['quiz_id'],p['user_id'],p['path_id'],p['plan_id'],p['day'],p['source_hash'],json.dumps(p,ensure_ascii=False),p['created_at']))
            row=c.execute("SELECT quiz_json FROM daily_quizzes WHERE user_id=? AND plan_id=? AND day=? AND source_hash=?",(p['user_id'],p['plan_id'],p['day'],p['source_hash'])).fetchone()
        return json.loads(row[0])
    def quiz(self,user_id,plan_id,day):
        with self.connect() as c: row=c.execute("SELECT quiz_json FROM daily_quizzes WHERE user_id=? AND plan_id=? AND day=? ORDER BY created_at DESC LIMIT 1",(user_id,plan_id,int(day))).fetchone()
        return json.loads(row[0]) if row else None
    def save_attempt(self,p):
        with self.connect() as c: c.execute("INSERT INTO quiz_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(p['attempt_id'],p['user_id'],p['path_id'],p['plan_id'],p['day'],p['quiz_id'],p['score'],p['duration_seconds'],p['confidence'],json.dumps(p['weak_concepts'],ensure_ascii=False),json.dumps(p,ensure_ascii=False),p['created_at']))
        return p
    def latest_attempt(self,user_id,path_id,day):
        with self.connect() as c: row=c.execute("SELECT result_json FROM quiz_attempts WHERE user_id=? AND path_id=? AND day=? ORDER BY created_at DESC LIMIT 1",(user_id,path_id,int(day))).fetchone()
        return json.loads(row[0]) if row else None
    def attempts(self,user_id,path_id):
        with self.connect() as c: rows=c.execute("SELECT result_json FROM quiz_attempts WHERE user_id=? AND path_id=? ORDER BY created_at",(user_id,path_id)).fetchall()
        return [json.loads(r[0]) for r in rows]
    def save_proposal(self,p):
        stamp=now_iso()
        with self.connect() as c: c.execute("INSERT INTO adaptation_proposals VALUES(?,?,?,?,?,?,?,?,?)",(p['proposal_id'],p['user_id'],p['path_id'],p['source_plan_id'],p['status'],json.dumps(p,ensure_ascii=False),None,stamp,stamp))
        return p
    def proposal(self,user_id,proposal_id):
        with self.connect() as c: row=c.execute("SELECT * FROM adaptation_proposals WHERE user_id=? AND proposal_id=?",(user_id,proposal_id)).fetchone()
        if not row:return None
        p=json.loads(row['proposal_json']);p['status']=row['status'];p['decision']=json.loads(row['decision_json']) if row['decision_json'] else None;return p
    def decide(self,user_id,proposal_id,status,decision,proposal):
        with self.connect() as c: c.execute("UPDATE adaptation_proposals SET status=?,proposal_json=?,decision_json=?,updated_at=? WHERE user_id=? AND proposal_id=?",(status,json.dumps(proposal,ensure_ascii=False),json.dumps(decision,ensure_ascii=False),now_iso(),user_id,proposal_id))
        return self.proposal(user_id,proposal_id)

class LearningLoopService:
    def __init__(self,backend,daily_service,daily_store,store): self.backend=backend;self.daily=daily_service;self.daily_store=daily_store;self.store=store
    def plan(self,user_id,plan_id):
        r=self.backend.plans.get_plan(plan_id)
        if not r or r['user_id']!=user_id:raise LearningLoopNotFoundError(plan_id)
        return r
    def runtime_plan(self,user_id,path_id):
        runtime=self.daily_store.runtime(user_id,path_id)
        if not runtime:raise LearningLoopNotFoundError(path_id)
        return self.plan(user_id,runtime['active_plan_id']),runtime
    def progress(self,*,user_id,path_id):
        r,runtime=self.runtime_plan(user_id,path_id);rows={int(x['day']):x for x in self.store.progress_rows(user_id,path_id)};dates={int(x['day']):x['scheduled_date'] for x in self.daily_store.dates(path_id)};completed={d for d,x in rows.items() if x['status']=='completed'};out=[];previous=True
        for item in sorted(r['plan'].get('days',[]),key=lambda x:int(x['day'])):
            day=int(item['day']);row=rows.get(day);done=day in completed;unlocked=day==1 or previous;status='completed' if done else ('in_progress' if row and row['status']=='in_progress' else ('unlocked' if unlocked else 'locked'))
            out.append({'day':day,'status':status,'unlocked':unlocked or done,'completed':done,'scheduled_date':dates.get(day),'actual_minutes':int(row['actual_minutes']) if row else 0,'content_progress':float(row['content_progress']) if row else 0,'quiz_attempt':self.store.latest_attempt(user_id,path_id,day)});previous=done
        return {'path_id':path_id,'plan_id':r['plan_id'],'plan_version':r['version'],'status':runtime['status'],'days':out,'next_day':next((x for x in out if x['unlocked'] and not x['completed']),None),'completed_days':len(completed),'total_days':len(out)}
    def assert_unlocked(self,*,user_id,plan_id,day):
        r=self.plan(user_id,plan_id);p=self.progress(user_id=user_id,path_id=r['path_id']);item=next((x for x in p['days'] if x['day']==int(day)),None)
        if not item:raise LearningLoopNotFoundError(f'{plan_id}:day:{day}')
        if not item['unlocked']:raise LearningLoopValidationError('Complete the previous learning day to unlock this day')
        return item
    def start_day(self,*,user_id,plan_id,day):
        r=self.plan(user_id,plan_id);access=self.assert_unlocked(user_id=user_id,plan_id=plan_id,day=day)
        if access['completed']:
            row=next(x for x in self.store.progress_rows(user_id,r['path_id']) if int(x['day'])==int(day))
        else:
            row=self.store.upsert_progress(user_id=user_id,path_id=r['path_id'],plan_id=plan_id,day=day,status='in_progress',content_progress=0)
        return {'progress':row,'path':self.progress(user_id=user_id,path_id=r['path_id'])}
    def sync_content_progress(self,*,user_id,plan_id,day,session):
        r=self.plan(user_id,plan_id); fraction=float((session.get('session_progress') or {}).get('fraction') or 0)
        seconds=sum(int((b.get('progress_state') or {}).get('actual_seconds') or 0) for b in session.get('study_blocks',[]))
        return self.store.upsert_progress(user_id=user_id,path_id=r['path_id'],plan_id=plan_id,day=day,status='in_progress',content_progress=fraction,actual_minutes=round(seconds/60))
    def feedback(self,*,user_id,plan_id,day,feedback_type,concept_ids,note=None,content_progress=None):
        r=self.plan(user_id,plan_id);self.assert_unlocked(user_id=user_id,plan_id=plan_id,day=day)
        if feedback_type not in {'not_understood','too_hard','too_easy','need_example','review_later','content_progress'}:raise LearningLoopValidationError('Unsupported feedback type')
        p={'feedback_id':str(uuid.uuid4()),'user_id':user_id,'path_id':r['path_id'],'plan_id':plan_id,'day':int(day),'feedback_type':feedback_type,'concept_ids':list(dict.fromkeys(concept_ids)),'note':note,'created_at':now_iso()};self.store.save_feedback(p)
        if content_progress is not None:self.store.upsert_progress(user_id=user_id,path_id=r['path_id'],plan_id=plan_id,day=day,status='in_progress',content_progress=max(0,min(1,float(content_progress))))
        return p
    def chat_history(self,*,user_id,plan_id,day):self.assert_unlocked(user_id=user_id,plan_id=plan_id,day=day);return self.store.chat(user_id,plan_id,day)
    def chat(self,*,user_id,plan_id,day,message,intent=None,content_id=None,current_block_id=None,completed_block_ids=None,current_resource_id=None):
        started=datetime.now(timezone.utc);r=self.plan(user_id,plan_id);self.assert_unlocked(user_id=user_id,plan_id=plan_id,day=day);content=self.daily.get_session(user_id=user_id,plan_id=plan_id,day=day);concepts=self._mentions(message,content) or list(content['topic_ids'][:1]);stamp=now_iso();self.store.save_chat({'message_id':str(uuid.uuid4()),'user_id':user_id,'path_id':r['path_id'],'plan_id':plan_id,'day':int(day),'role':'user','body':message,'citations':[],'concept_ids':concepts,'mode':'user','created_at':stamp})
        mode='fallback';reason=None
        try:answer=self._openai_answer(r,content,message,intent,current_block_id,current_resource_id);mode='live'
        except Exception as e:reason=type(e).__name__;answer=self._fallback_answer(content,intent,current_block_id)
        p={'message_id':str(uuid.uuid4()),'user_id':user_id,'path_id':r['path_id'],'plan_id':plan_id,'day':int(day),'role':'assistant','body':answer,'citations':content.get('citations',[])[:4],'concept_ids':concepts,'mode':mode,'fallback_reason':reason,'latency_ms':int((datetime.now(timezone.utc)-started).total_seconds()*1000),'created_at':now_iso(),'context':{'content_id':content_id or content.get('content_id'),'current_block_id':current_block_id,'completed_block_ids':completed_block_ids or [],'current_resource_id':current_resource_id}};self.store.save_chat(p);return p
    @staticmethod
    def _mentions(message,content):
        low=message.lower();return [i for i,l in zip(content.get('topic_ids',[]),content.get('topic_labels',[])) if i.lower() in low or l.lower() in low]
    @staticmethod
    def _fallback_answer(content,intent,current_block_id=None):
        block=next((b for b in content.get('study_blocks',[]) if b.get('block_id')==current_block_id),None) or next(iter(content.get('study_blocks',[])),None);section=(content.get('lesson',{}).get('sections') or [{}])[0];block_content=(block or {}).get('content') or {};prefix={'life_example':'A concrete example','code_example':'A practical application','misconception':'Compare your idea with this key point','simplify':'In simpler terms'}.get(intent,'Based on the current study block');answer=f"{prefix}: {block_content.get('plain_explanation') or block_content.get('task') or block_content.get('connection_task') or section.get('explanation') or content.get('lesson',{}).get('summary','')}"
        example=block_content.get('scenario') or block_content.get('guided_excerpt') or section.get('example')
        if example:answer+=f"\n\nExample or evidence: {example}"
        return answer
    @staticmethod
    def _openai_answer(record,content,message,intent,current_block_id=None,current_resource_id=None):
        key=os.getenv('OPENAI_API_KEY')
        if not key:raise RuntimeError('OPENAI_API_KEY is not configured')
        from openai import OpenAI
        block=next((b for b in content.get('study_blocks',[]) if b.get('block_id')==current_block_id),None);prompt={'goal':record['goal_text'],'profile':record['profile_snapshot'],'session_overview':content.get('session_overview'),'current_block':block,'current_resource_id':current_resource_id,'citations':content.get('citations',[]),'intent':intent,'question':message};response=OpenAI(api_key=key,timeout=25.0,max_retries=0).responses.create(model=os.getenv('PATHLY_CHAT_MODEL',os.getenv('PATHLY_CONTENT_MODEL','gpt-5.4')),input='Answer only from the supplied study block and citations. Be direct, practical, and under 180 words. Cite no invented source.\\n'+json.dumps(prompt,ensure_ascii=False,default=str)[:45000],max_output_tokens=700);return str(response.output_text).strip()
    def confusion_summary(self,*,user_id,path_id):
        counts={};signals={}
        for x in self.store.feedback(user_id,path_id):
            if x['feedback_type'] in {'not_understood','too_hard'}:
                for cid in x['concept_ids']:counts[cid]=counts.get(cid,0)+1;signals.setdefault(cid,[]).append(x['feedback_type'])
        r,_=self.runtime_plan(user_id,path_id)
        for day in r['plan'].get('days',[]):
            for m in self.store.chat(user_id,r['plan_id'],int(day['day'])):
                if m['role']=='user':
                    for cid in m['concept_ids']:counts[cid]=counts.get(cid,0)+1;signals.setdefault(cid,[]).append('chat_question')
        return [{'concept_id':cid,'count':n,'signals':signals[cid]} for cid,n in sorted(counts.items(),key=lambda x:(-x[1],x[0]))]
    def quiz(self,*,user_id,plan_id,day):
        self.assert_unlocked(user_id=user_id,plan_id=plan_id,day=day);self.daily.assert_required_blocks_complete(user_id=user_id,plan_id=plan_id,day=day);cached=self.store.quiz(user_id,plan_id,day)
        if cached:return {**cached,'cache_status':'hit'}
        r=self.plan(user_id,plan_id);content=self.daily.get_session(user_id=user_id,plan_id=plan_id,day=day);completed=[b for b in content.get('study_blocks',[]) if (b.get('progress_state') or {}).get('status')=='completed'];eligible=completed or content.get('study_blocks',[]);labels=content.get('topic_labels') or ['Today?s concept'];ids=content.get('topic_ids') or labels;sections=[]
        for block in eligible:
            body=block.get('content') or {};sections.append({'explanation':body.get('plain_explanation') or body.get('why_it_works') or body.get('task') or body.get('connection_task') or 'This concept belongs to today?s path.','key_points':body.get('self_check') or body.get('focus_questions') or body.get('mastery_checklist') or [],'concept_ids':block.get('concept_ids',[])})
        if not sections:sections=[{}]
        qs=[]
        for index in range(3):
            section=sections[index%len(sections)];cid=(section.get('concept_ids') or ids)[0];label=next((l for i,l in zip(ids,labels) if i==cid),cid);kind=['multiple_choice','true_false','short_application'][index];correct=section.get('explanation') or f'{label} belongs to today?s path.' if index==0 else ('True' if index==1 else None)
            qs.append({'question_id':f'q{index+1}','type':kind,'concept_id':cid,'prompt':f'Which statement best matches {label}?' if index==0 else (f"True or false: {(section.get('key_points') or [label+' is part of today?s path'])[0]}" if index==1 else f"Briefly apply {label} to one of today?s completed activities."),'options':[correct,f'{label} is unrelated to the goal.',f'{label} never needs practice.'] if index==0 else (['True','False'] if index==1 else []),'correct_answer':correct,'expected_terms':[w.lower() for w in label.split()[:3]] if index==2 else [],'explanation':section.get('explanation') or content['lesson'].get('summary'),'source_block_ids':[b['block_id'] for b in eligible if cid in b.get('concept_ids',[])]})
        source=content['source_hash']+'|quiz-v2|'+','.join(b.get('block_id','') for b in eligible);p={'quiz_id':str(uuid.uuid4()),'user_id':user_id,'path_id':r['path_id'],'plan_id':plan_id,'day':int(day),'source_hash':hashlib.sha256(source.encode()).hexdigest(),'questions':qs,'cache_status':'miss','created_at':now_iso()};return self.store.save_quiz(p)
    def submit_quiz(self,*,user_id,plan_id,day,answers,duration_seconds):
        r=self.plan(user_id,plan_id);quiz=self.quiz(user_id=user_id,plan_id=plan_id,day=day);given={str(x['question_id']):x for x in answers};results=[];weak=[];conf=[]
        for q in quiz['questions']:
            a=given.get(q['question_id'],{});value=str(a.get('answer','')).strip();confidence=max(1,min(5,int(a.get('confidence',3))));conf.append(confidence);correct=(bool(value) and any(t in value.lower() for t in q['expected_terms'])) if q['type']=='short_application' else value.lower()==str(q['correct_answer']).lower()
            if not correct:weak.append(q['concept_id'])
            results.append({'question_id':q['question_id'],'concept_id':q['concept_id'],'answer':value,'correct':correct,'confidence':confidence,'time_seconds':int(a.get('time_seconds',0)),'explanation':q['explanation']})
        score=round(100*sum(x['correct'] for x in results)/len(results),2);confidence=round(sum(conf)/len(conf),2);p={'attempt_id':str(uuid.uuid4()),'user_id':user_id,'path_id':r['path_id'],'plan_id':plan_id,'day':int(day),'quiz_id':quiz['quiz_id'],'score':score,'duration_seconds':max(0,int(duration_seconds)),'confidence':confidence,'weak_concepts':list(dict.fromkeys(weak)),'results':results,'strong_mastery':score>=90 and confidence>=4,'created_at':now_iso()};self.store.save_attempt(p);scheduled=self.daily.day(r,day).get('total_minutes',0);self.store.upsert_progress(user_id=user_id,path_id=r['path_id'],plan_id=plan_id,day=day,status='completed',content_progress=1,actual_minutes=max(int(scheduled),int(duration_seconds/60)),completed=True);p['path_progress']=self.progress(user_id=user_id,path_id=r['path_id']);return p
    def create_proposal(self,*,user_id,path_id):
        r,_=self.runtime_plan(user_id,path_id);progress=self.progress(user_id=user_id,path_id=path_id);weak={};strong=[]
        for a in self.store.attempts(user_id,path_id):
            if a['score']<70:
                for cid in a['weak_concepts']:weak.setdefault(cid,[]).append('quiz_below_70')
            for x in a['results']:
                if not x['correct'] and x['confidence']<=2:weak.setdefault(x['concept_id'],[]).append('wrong_low_confidence')
            if a.get('strong_mastery'):strong.extend(x['concept_id'] for x in a['results'] if x['correct'])
        for x in self.confusion_summary(user_id=user_id,path_id=path_id):
            if x['count']>=2:weak.setdefault(x['concept_id'],[]).append('repeated_confusion')
        actions=[{'action':'add_review','concept_id':cid,'minutes':20,'signals':sig,'candidate':self._candidate(cid),'reason':'Weak or repeated-confusion signals require reinforcement.'} for cid,sig in weak.items()]
        if not actions and strong:actions=[{'action':'compress_review','concept_id':cid,'minutes':-10,'signals':['score_at_least_90','confidence_at_least_4'],'reason':'Strong mastery permits a shorter future review.'} for cid in list(dict.fromkeys(strong))[:2]]
        if not actions:actions=[{'action':'keep_plan','concept_id':None,'minutes':0,'signals':['insufficient_adaptation_signal'],'reason':'Current evidence does not justify changing the path.'}]
        total=sum(int(d.get('total_minutes',0)) for d in r['plan'].get('days',[]));p={'proposal_id':str(uuid.uuid4()),'user_id':user_id,'path_id':path_id,'source_plan_id':r['plan_id'],'source_plan_version':r['version'],'status':'pending','actions':actions,'weak_concepts':list(weak),'strong_concepts':list(dict.fromkeys(strong)),'completed_days':progress['completed_days'],'remaining_days':[x['day'] for x in progress['days'] if not x['completed']],'before_total_minutes':total,'minute_impact':sum(int(x['minutes']) for x in actions),'after_total_minutes':total+sum(int(x['minutes']) for x in actions),'reason':'Only the unfinished part of the active path is eligible for change.','created_at':now_iso()};return self.store.save_proposal(p)
    @staticmethod
    def _candidate(cid):
        try:
            from agents.planning_agent import PlanningAgent
            from agents.adaptation_candidate_service import AdaptationCandidateService
            result=AdaptationCandidateService(PlanningAgent(graph_path=str(CALIBRATED_KG),kg_backend='json').repository).suggest_candidates(cid,limit=2);return (result.get('candidates') or [None])[0]
        except Exception:return None
    def proposal(self,*,user_id,proposal_id):
        p=self.store.proposal(user_id,proposal_id)
        if not p:raise LearningLoopNotFoundError(proposal_id)
        return p
    def decide_proposal(self,*,user_id,proposal_id,decision,modifications=None):
        p=self.proposal(user_id=user_id,proposal_id=proposal_id)
        if p['status']!='pending':raise LearningLoopValidationError('This proposal has already been decided')
        if decision not in {'accept','reject','modify'}:raise LearningLoopValidationError('Decision must be accept, reject, or modify')
        dp={'decision':decision,'modifications':modifications or {},'decided_at':now_iso()}
        if decision=='reject':return self.store.decide(user_id,proposal_id,'rejected',dp,p)
        source=self.plan(user_id,p['source_plan_id']);updated=deepcopy(source['plan']);updated.pop('plan_id',None);progress=self.progress(user_id=user_id,path_id=source['path_id']);completed={x['day'] for x in progress['days'] if x['completed']};review_minutes=max(5,int((modifications or {}).get('review_minutes',20)));applied=[]
        for action in p['actions']:
            action=dict(action)
            if action['action']=='add_review':
                target=next((d for d in updated.get('days',[]) if int(d['day']) not in completed),None)
                if target:action['minutes']=review_minutes;target.setdefault('activities',[]).insert(0,{'activity_id':f"adapt-{uuid.uuid4().hex[:10]}",'activity_type':'review','concept_ids':[action['concept_id']],'estimated_minutes':review_minutes,'adaptation':True,'reason':action['reason']});target['total_minutes']=int(target.get('total_minutes',0))+review_minutes;applied.append({**action,'target_day':int(target['day'])})
            elif action['action']=='compress_review':
                for d in updated.get('days',[]):
                    if int(d['day']) in completed:continue
                    a=next((x for x in d.get('activities',[]) if x.get('activity_type')=='review' and action['concept_id'] in x.get('concept_ids',[])),None)
                    if a:reduction=min(10,max(0,int(a['estimated_minutes'])-5));a['estimated_minutes']-=reduction;d['total_minutes']-=reduction;applied.append({**action,'minutes':-reduction,'target_day':int(d['day'])});break
            else:applied.append(action)
        updated.setdefault('adaptation_history',[]).append({'proposal_id':proposal_id,'source_plan_id':source['plan_id'],'applied_actions':applied,'accepted_at':now_iso()});new=self.backend.plans.save_plan(user_id,updated,source['mode'],list(dict.fromkeys(source['sources']+['learner_confirmed_adaptation'])),path_id=source['path_id'],goal_text=source['goal_text'],profile_snapshot=source['profile_snapshot']);runtime=self.daily_store.runtime(user_id,source['path_id']);self.daily_store.save_runtime({'path_id':source['path_id'],'user_id':user_id,'active_plan_id':new['plan_id'],'start_date':runtime['start_date'],'timezone':runtime['timezone'],'status':'active'});p.update({'applied_actions':applied,'new_plan_id':new['plan_id'],'new_plan_version':new['version'],'after_total_minutes':sum(int(d.get('total_minutes',0)) for d in updated.get('days',[]))});result=self.store.decide(user_id,proposal_id,'accepted',dp,p);result['plan']=new;return result


