window.PATHLY_DP4_LOADED = true;
const $ = (s) => document.querySelector(s);
const KEY = "pathly-product-v2";
const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
const requestedParams = new URLSearchParams(window.location.search);
const requestedDailyView = requestedParams.get("daily_view");
const requestedPlanId = requestedParams.get("plan_id");
const requestedDay = Number(requestedParams.get("day") || 0);
const requestedView = requestedParams.get("view");
const state = {
  userId: saved.userId || `learner-${crypto.randomUUID()}`,
  view: requestedDailyView === "lecture-v4" ? "today" : (requestedView || saved.view || "workspace"),
  draftId: saved.draftId || null, demoUsers: [], accountMenuOpen: false,
  controlledEvaluation: {options: null, runs: [], loading: false, result: null, comparison: null, comparisonMode: "day1", activeVersion: "V3", form: (({daily_minutes,...form})=>({user_id: "demo-foundation-learner", goal_text: "", system_version: "V3", temperature: 0.2,...form}))(saved.controlledEvaluationForm || {})},
  freshWalkthrough: Boolean(saved.freshWalkthrough), freshWorkspaceAudit: saved.freshWorkspaceAudit || null,
  draft: null, documents: [], plans: [], currentPlan: null, selectedPlanId: saved.selectedPlanId || null, profile: null, profileLoaded: false, profileError: null,
  goal: "", sourceMode: "kg_only", selectedDocuments: {},
  interpretation: null, answers: {}, estimate: null, decision: null, capacityDraft: null,
  capabilities: null, hydrating: true,
  busy: false, error: null, notice: null, mapMode: "map", scopeMode: false, reviewOpen: {}, editingGoal: false,
  stepOverride: null, capacityReview: false, pendingCapacityChoice: null, pendingStrategy: null,
  mapReviewConfirmed: saved.mapReviewConfirmed || {}, mapReviewEdges: saved.mapReviewEdges || {}, mapReviewExcluded: saved.mapReviewExcluded || {}, edgeEditSource: null, selectedConceptId: null, mapViewport: null,
  today: null, dailyContent: null, fullLecture: null, fullLectureError: null, fullLectureProgress: saved.fullLectureProgress || {}, fullLectureSaving: {}, fullLectureRetryQueue: saved.fullLectureRetryQueue || {}, fullLectureRetrying: {}, fullLectureSourcePages: {}, annotatedSession: null, annotatedError: null, activeReadingId: null, sourceContexts: {}, sourceContextOpen: {}, readingResponses: {}, exerciseResponses: {}, exerciseResults: {}, reschedulePreview: null, pathProgress: null, selectedDay: requestedDay > 0 ? requestedDay : (saved.selectedDay || null),
  lectureV4: null, lectureV4Error: null, lectureV4Loading: false, lectureV4Status: "", v4SectionProgress: saved.v4SectionProgress || {}, v4Saving: {}, v4CurrentSectionId: saved.v4CurrentSectionId || null, v4ScrollPosition: Number(saved.v4ScrollPosition||0), v4ExerciseAnswers: saved.v4ExerciseAnswers || {}, v4ExerciseResults: saved.v4ExerciseResults || {}, v4Retrying: {},
  dailyStage: requestedDailyView === "lecture-v4" ? "lecture-v4" : (saved.dailyStage || "content"), activeBlockId: null, blockStartedAt: null, chatMessages: [], chatPending: false, chatDraft: "", chatError: null, blockAnswers: {}, quiz: null, quizAnswers: {}, quizResult: null, adaptationProposal: null, deletePathCandidate: null, deletePathError: null
};
let documentPollTimer=null;
let fullLectureRetryTimer=null;
const persist = () => localStorage.setItem(KEY, JSON.stringify({
  userId: state.userId, view: state.view, draftId: state.draftId, freshWalkthrough: state.freshWalkthrough, freshWorkspaceAudit: state.freshWorkspaceAudit, selectedPlanId: state.currentPlan?.plan_id || state.selectedPlanId || null, mapReviewConfirmed: state.mapReviewConfirmed, mapReviewEdges: state.mapReviewEdges, mapReviewExcluded: state.mapReviewExcluded, fullLectureProgress: state.fullLectureProgress, fullLectureRetryQueue: state.fullLectureRetryQueue, v4SectionProgress: state.v4SectionProgress, v4CurrentSectionId: state.v4CurrentSectionId, v4ScrollPosition: state.v4ScrollPosition, v4ExerciseAnswers: state.v4ExerciseAnswers, v4ExerciseResults: state.v4ExerciseResults, selectedDay: state.selectedDay, dailyStage: state.dailyStage, controlledEvaluationForm: state.controlledEvaluation.form
}));
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
}[c]));
const api = async (path, options={}) => {
  const headers = {...(options.headers||{})};
  if (!(options.body instanceof FormData)) headers["Content-Type"]="application/json";
  let response;
  let networkError;
  for(let attempt=0;attempt<4;attempt++){
    try{
      response = await fetch(path,{...options,headers,credentials:"same-origin"});
      networkError=null;
      break;
    }catch(error){
      networkError=error;
      if(attempt<3) await new Promise(resolve=>setTimeout(resolve,350*(attempt+1)));
    }
  }
  if(!response){
    const e=new Error(`Pathly could not reach ${path}. The local service may be restarting; use Retry to reconnect.`);
    e.code="network_unavailable";e.cause=networkError;throw e;
  }
  const payload = await response.json().catch(()=>({}));
  if(!response.ok || !payload.ok) {
    const e = new Error(payload?.error?.message || payload?.detail || `Request failed (${response.status})`);
    e.code=payload?.error?.code; e.details=payload?.error?.details; throw e;
  }
  return payload.data;
};
function showBusy(label="Generating your personalized learning experience...") {
  let overlay=document.getElementById("pathly-busy-overlay");
  if(!overlay){
    overlay=document.createElement("div");
    overlay.id="pathly-busy-overlay";
    overlay.className="pathly-busy-overlay";
    overlay.setAttribute("role","status");
    overlay.setAttribute("aria-live","assertive");
    document.body.appendChild(overlay);
  }
  overlay.innerHTML=`<div class="pathly-busy-card"><span class="pathly-busy-spinner" aria-hidden="true"></span><div><b>${esc(label)}</b><span>Please keep this page open. You can continue as soon as this is ready.</span></div></div>`;
}
function hideBusy(){document.getElementById("pathly-busy-overlay")?.remove()}
const act = async (fn,label="Generating your personalized learning experience...") => {
  state.busy=true; state.error=null; state.busyLabel=label;
  document.body.classList.add("pathly-busy");
  showBusy(label);
  try { await fn(); }
  catch(e){ state.error=e.message; }
  finally {
    state.busy=false; state.busyLabel="";
    document.body.classList.remove("pathly-busy");
    hideBusy();
    persist(); render();
  }
};
const pill = (text,kind="") => `<span class="v2-pill ${kind}">${esc(text)}</span>`;

async function hydrate(){
  state.hydrating=true;
  await Promise.allSettled([loadCapabilities(),loadDemoUsers(),loadDocuments(),loadPlans(),loadDraft(),loadProfile()]);
  await loadControlledEvaluationOptions();
  let requestedPlanRestored=false;
  let requestedPlanRestoreError=null;
  if(requestedPlanId&&!state.plans.some(plan=>plan.plan_id===requestedPlanId)){
    try{
      const restored=await api(`/api/plans/${encodeURIComponent(requestedPlanId)}`);
      state.plans.unshift(restored);
      requestedPlanRestored=true;
    }catch(error){
      requestedPlanRestoreError=error.message||"The requested learning path could not be restored.";
      state.lectureV4Error=null;
    }
  }
  const requestedPlan=state.plans.find(plan=>plan.plan_id===requestedPlanId);
  if(state.plans.length&&!state.currentPlan)state.currentPlan=(requestedPlanId?requestedPlan:null)||((state.selectedPlanId)?state.plans.find(plan=>plan.plan_id===state.selectedPlanId):null)||state.plans[0];
  if(requestedPlanId&&!requestedPlan&&state.currentPlan){
    state.notice="That shared learning link belongs to another anonymous workspace, so Pathly opened your latest available path instead.";
    state.dailyStage=requestedDailyView==="lecture-v4"?"lecture-v4":state.dailyStage;
  }else if(requestedPlanRestoreError&&!state.plans.length){
    state.lectureV4Error=requestedPlanRestoreError;
  }
  if(state.currentPlan)await ensurePathProgress(state.currentPlan).catch(()=>null);
  if(state.view==="today"&&state.currentPlan){
    try{
      if(state.dailyStage==="lecture-v4"){
        await loadV4RouteContext(requestedDay||state.selectedDay);
        if(requestedPlanId&&!requestedPlan)syncDailyViewUrl();
        await loadLectureV4();
      }else{
        await loadTodayData(requestedDay||state.selectedDay);
        if(requestedPlanId&&!requestedPlan)syncDailyViewUrl();
        if(state.dailyStage==="lecture-v3")await loadFullLecture();
      }
    }
    catch(error){state.view="dashboard";state.notice="Your learning path is available, but the previous lesson could not be restored. Open an unlocked day from the Activity Timeline to continue."}
  }else if(state.view==="today")state.view="workspace";
  state.hydrating=false;render();
}
async function loadCapabilities(){state.capabilities=await api("/api/capabilities")}
async function loadDemoUsers(){
  try{state.demoUsers=await api("/api/demo-users")}
  catch(_error){state.demoUsers=[]}
}
async function loadControlledEvaluationOptions(){
  if(!state.capabilities?.controlled_evaluation?.available){state.controlledEvaluation.options=null;return}
  try{
    state.controlledEvaluation.options=await api("/api/controlled-evaluation/options");
    const firstGoal=state.controlledEvaluation.options?.goals?.[0]?.goal_text;
    if(!state.controlledEvaluation.form.goal_text&&firstGoal){state.controlledEvaluation.form={...state.controlledEvaluation.form,goal_text:firstGoal};persist()}
  }
  catch(_error){state.controlledEvaluation.options=null}
}
async function loadControlledEvaluationRuns(){
  if(!state.capabilities?.controlled_evaluation?.available){state.controlledEvaluation.runs=[];return}
  try{const payload=await api("/api/controlled-evaluation/runs?limit=100");state.controlledEvaluation.runs=payload.runs||[]}
  catch(_error){state.controlledEvaluation.runs=[]}
}
function exportControlledEvaluationRuns(){
  const blob=new Blob([JSON.stringify(state.controlledEvaluation.runs||[],null,2)],{type:"application/json"});
  const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="pathly-controlled-evaluation-runs.json";link.click();URL.revokeObjectURL(link.href);
}
let v4ScrollTimer=null;
let v4PollTimer=null;
let v4StaleRetryCount=0;
function clearV4Poll(){if(v4PollTimer){clearTimeout(v4PollTimer);v4PollTimer=null}}
function v4GenerationState(lecture){
  const value=String(lecture?.generation_metadata?.generation_state||lecture?.v4_status||"").toLowerCase();
  // A sequential lecture has a ready first section while later sections wait
  // for the learner to complete it.  This is a usable V4 state, not a reason
  // to fall back to the legacy daily-session surface.
  if(["queued","generating","failed","complete","waiting_for_completion"].includes(value))return value;
  return lecture?.lecture_sections?.length?"complete":"not_generated";
}
function scheduleV4Poll(delay=1200){
  clearV4Poll();
  v4PollTimer=setTimeout(async()=>{
    if(state.view!=="today"||state.dailyStage!=="lecture-v4"||!state.today?.plan_id)return;
    try{
      const lecture=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/lecture-v4`);
      state.lectureV4=lecture;
      const phase=v4GenerationState(lecture);
      if(phase==="queued"||phase==="generating"){
        state.lectureV4Status="Preparing your source-grounded lecture...";
        persist();render();scheduleV4Poll();return;
      }
      if((phase==="not_generated"||String(lecture?.v4_status||"").toLowerCase()==="stale")&&lecture?.can_generate&&v4StaleRetryCount<2){
        v4StaleRetryCount+=1;state.lectureV4Loading=true;state.lectureV4Status="Preparing your lecture...";
        const queued=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/lecture-v4/generate`,{method:"POST",body:JSON.stringify({force:false})});
        state.lectureV4=queued;persist();render();scheduleV4Poll(600);return;
      }
      state.lectureV4Loading=false;
      state.lectureV4Status="";
      if(phase==="failed")state.lectureV4Error="The lecture could not be generated. You can retry it without leaving this day.";
      for(const [sectionId,value] of Object.entries(lecture.v4_progress||{}))state.v4SectionProgress[`${state.today.plan_id}:${state.today.current.day}:${sectionId}`]=value.status==="completed";
      persist();render();
    }catch(error){state.lectureV4Loading=false;state.lectureV4Error=error.message||"The lecture could not be refreshed.";persist();render()}
  },delay);
}
window.addEventListener("scroll",()=>{if(state.view!=="today"||state.dailyStage!=="lecture-v4")return;clearTimeout(v4ScrollTimer);v4ScrollTimer=setTimeout(()=>{state.v4ScrollPosition=Math.round(window.scrollY);persist()},180)},{passive:true});

const ACTIVE_DOCUMENT_STATUSES=new Set(["pending","queued","processing","parsing","indexing"]);
function scheduleDocumentPoll(){
  if(documentPollTimer)clearTimeout(documentPollTimer);
  documentPollTimer=null;
  if(!state.documents.some(d=>ACTIVE_DOCUMENT_STATUSES.has(String(d.parse_status||"").toLowerCase())))return;
  documentPollTimer=setTimeout(async()=>{
    try{await loadDocuments();render()}catch(e){state.error=e.message;render()}
  },2000);
}
async function loadDocuments(){
  state.documents=await api(`/api/users/${encodeURIComponent(state.userId)}/documents`);
  const readyIds=new Set(state.documents.filter(d=>d.parse_status==="ready").map(d=>d.document_id));
  Object.keys(state.selectedDocuments).forEach(id=>{if(!readyIds.has(id))delete state.selectedDocuments[id]});
  scheduleDocumentPoll();
}
async function loadProfile(){
  state.profileLoaded=false;state.profileError=null;
  try{state.profile=await api(`/api/profiles/${encodeURIComponent(state.userId)}`)}
  catch(e){if(e.code==="not_found")state.profile=null;else state.profileError=e.message}
  finally{state.profileLoaded=true}
}
async function loadPlans(){
  const rows=await api(`/api/users/${encodeURIComponent(state.userId)}/plans`);
  const latest=new Map();
  rows.forEach(r=>{const old=latest.get(r.path_id);if(!old||r.version>old.version)latest.set(r.path_id,r)});
  state.plans=[...latest.values()].sort((a,b)=>new Date(b.created_at)-new Date(a.created_at));
}
async function loadDraft(){
  if(!state.draftId)return;
  try{
    state.draft=await api(`/api/onboarding-drafts/${state.draftId}?user_id=${encodeURIComponent(state.userId)}`);
    if(state.draft.knowledge_map_review){
      const review=state.draft.knowledge_map_review;
      state.mapReviewExcluded={...(state.mapReviewExcluded||{}),[state.draftId]:review.excluded_concept_ids||[]};
      state.mapReviewEdges={...(state.mapReviewEdges||{}),[state.draftId]:review.edges||[]};
      state.mapReviewConfirmed={...(state.mapReviewConfirmed||{}),[state.draftId]:review.status==="confirmed"};
    }
    state.goal=state.draft.goal_text||"";
    state.answers=state.draft.answers||{};
    state.estimate=null;state.decision=null;state.editingGoal=false;state.pendingStrategy=null;
    if(state.draft.goal_interpretation_id){
      const savedInterpretation=await api(`/api/goal-interpretations/${state.draft.goal_interpretation_id}?user_id=${encodeURIComponent(state.userId)}`).catch(()=>null);
      if(savedInterpretation){
        state.interpretation=savedInterpretation;
        state.sourceMode=savedInterpretation.source_mode||"kg_only";
        state.selectedDocuments={};
        (savedInterpretation.documents||[]).forEach(item=>{state.selectedDocuments[item.document_id]={required:Boolean(item.required)}});
      }
    }
    if(state.draft.workload_estimate_id){
      state.estimate=await api(`/api/onboarding-drafts/${state.draftId}/workload-estimate?user_id=${encodeURIComponent(state.userId)}`).catch(()=>null);
      if(state.estimate){
        if(state.draft.feasibility_decision_id){
          state.decision=await api(`/api/feasibility-decisions/${state.draft.feasibility_decision_id}?user_id=${encodeURIComponent(state.userId)}`).catch(()=>null);
        }
        if(!state.decision){
          state.decision=await api(`/api/workload-estimates/${state.estimate.estimate_id}/feasibility-decision?user_id=${encodeURIComponent(state.userId)}`).catch(()=>null);
        }
        state.editingGoal=state.decision?.selected_strategy==="adjust_outcome";
      }
    }
  }catch(e){state.draftId=null;state.draft=null;state.estimate=null;state.decision=null;state.editingGoal=false}
}
function nav(){
  return `<aside class="v2-side"><button type="button" class="v2-brand" onclick="newPath()" aria-label="Start a new learning path"><b>P</b><span>Pathly<small>LEARNING WORKSPACE</small></span></button>
  <nav>${[
    ["workspace","+ New Path"],["dashboard","Learning Paths"],["today","Today Learning"],["library","My Library"],["profile","Learner Profile"],
    ...(state.capabilities?.controlled_evaluation?.available?[["controlled-evaluation","Controlled Evaluation"]]:[])
  ].map(([id,label])=>`<button class="${state.view===id?"active":""}" onclick="${id==="workspace"?"newPath()":`go('${id}')`}">${label}</button>`).join("")}</nav>
  <div class="privacy">Private Learning Space<br><small>Your materials are never added to the public knowledge graph</small></div></aside>`;
}
function notificationStack(){
  if(!state.error&&!state.notice)return "";
  return `<div class="v2-toast-stack" aria-live="polite" aria-atomic="true">
  ${state.error?`<div class="v2-error v2-toast" role="alert"><div class="v2-toast-copy"><b>Unable to continue</b><span>${esc(state.error)}</span></div>${state.error.includes("Unable to create a secure Pathly session")||state.error.includes("could not reach")?`<button type="button" onclick="startSecureSession()">Retry</button>`:""}<button type="button" aria-label="Dismiss error" onclick="state.error=null;render()">Dismiss</button></div>`:""}
  ${state.notice?`<div class="v2-notice v2-toast" role="status"><div class="v2-toast-copy"><b>Update</b><span>${esc(state.notice)}</span></div><button type="button" aria-label="Dismiss notification" onclick="state.notice=null;render()">Dismiss</button></div>`:""}
  </div>`;
}
function shell(content){
  const current=state.demoUsers.find(user=>user.user_id===state.userId);
  const accountLabel=current?.display_name||(state.freshWalkthrough?"New Learner":"Anonymous learner");
  const choices=state.demoUsers.map(user=>`<button type="button" class="demo-user-choice ${user.user_id===state.userId?"active":""}" onclick="switchDemoUser('${esc(user.user_id)}')"><span><b>${esc(user.display_name)}</b><small>${esc(user.level)} profile</small></span>${user.user_id===state.userId?"<i>Current</i>":""}</button>`).join("");
  const controlledEntry=state.capabilities?.controlled_evaluation?.available?`<button type="button" class="demo-user-choice" onclick="go('controlled-evaluation')"><span><b>Open Controlled Evaluation</b><small>Run isolated V0-V3 research comparisons</small></span></button>`:"";
  return `<div class="v2-shell">${nav()}${notificationStack()}<main class="v2-main"><header><div>${pill("LIVE PRODUCT FLOW","green")}</div>
  <details class="demo-account"><summary><span>${esc(accountLabel)}</span><small>${state.freshWalkthrough&&!state.profile?"Profile not created":esc(state.userId.slice(-8))}</small></summary><div class="demo-account-menu"><p>Experience Pathly</p><button type="button" class="demo-user-choice fresh-learner-choice" onclick="startFreshLearner()"><span><b>Start as a New Learner</b><small>No profile, plans, drafts, or cached content</small></span></button>${controlledEntry}<p>Controlled evaluation profiles 路 Switch local learner</p>${choices}</div></details></header>${content}</main></div>`;
}
async function startFreshLearner(){
  await act(async()=>{
    const fresh=await api("/api/sessions/fresh-walkthrough",{method:"POST",body:JSON.stringify({})});
    if(!fresh.empty_workspace_verified)throw new Error("The new learner workspace did not pass its isolation check.");
    // Update live state before navigation. act() persists in finally; writing
    // localStorage alone here allowed the old state to overwrite the fresh flag.
    state.userId=fresh.user_id;state.view="workspace";state.freshWalkthrough=true;
    state.freshWorkspaceAudit={profile_exists:fresh.profile_exists,plan_count:fresh.plan_count,onboarding_draft_count:fresh.onboarding_draft_count,content_cache_count:fresh.content_cache_count,empty_workspace_verified:true};
    state.draftId=null;state.draft=null;state.profile=null;state.profileLoaded=true;
    state.documents=[];state.plans=[];state.currentPlan=null;state.selectedPlanId=null;
    state.today=null;state.dailyContent=null;state.lectureV4=null;
    persist();
    window.location.href="/?view=workspace&fresh=1";
  },"Creating a completely new learner workspace...");
}
async function switchDemoUser(userId){
  if(!userId||userId===state.userId)return;
  await act(async()=>{
    const selected=await api(`/api/demo-users/${encodeURIComponent(userId)}/switch`,{method:"POST",body:JSON.stringify({})});
    localStorage.setItem(KEY,JSON.stringify({userId:selected.user_id,view:"profile"}));
    window.location.href="/";
  },"Switching learner and loading their private workspace...");
}
async function go(view){
  state.view=view;state.error=null;persist();
  const url=new URL(window.location.href);
  if(view==="today") url.searchParams.set("view","today");
  else { url.searchParams.set("view",view); url.searchParams.delete("daily_view"); url.searchParams.delete("day"); }
  history.replaceState(null,"",url.pathname+"?"+url.searchParams.toString());
  if(view==="profile"){state.profileLoaded=false;render();await loadProfile();render();return}
  if(view==="controlled-evaluation"){render();await loadControlledEvaluationOptions();await loadControlledEvaluationRuns();render();return}
  if(view==="today"){render();await act(async()=>{await loadTodayData(state.selectedDay);if(state.dailyStage==="lecture-v4")await loadLectureV4();});return}
  if(view==="dashboard"&&state.currentPlan){render();await act(()=>ensurePathProgress(state.currentPlan));return}
  render();
}
function newPath(){state.draftId=null;state.draft=null;state.goal="";state.answers={};state.interpretation=null;state.estimate=null;state.decision=null;state.capacityDraft=null;state.sourceMode="kg_only";state.selectedDocuments={};state.scopeMode=false;state.reviewOpen={};state.editingGoal=false;state.stepOverride=null;state.capacityReview=false;state.pendingCapacityChoice=null;state.pendingStrategy=null;state.selectedConceptId=null;state.edgeEditSource=null;state.error=null;state.notice=null;state.view="workspace";persist();render()}

function controlledEvaluationPage(){
  const options=state.controlledEvaluation.options;
  const form=state.controlledEvaluation.form;
  if(!state.capabilities?.controlled_evaluation?.available)return shell(`<section class="v2-card profile-state"><h2>Controlled Evaluation is unavailable</h2><p>This local research mode is disabled in the current environment.</p></section>`);
  if(!options)return shell(`<section class="v2-card profile-state"><div class="agent-orb">P</div><h2>Loading Controlled Evaluation...</h2><p>Pathly is loading the local research configuration.</p></section>`);
  const result=state.controlledEvaluation.result;
  const runs=state.controlledEvaluation.runs||[];
  const visibleRuns=runs.slice(0,12);
  return shell(`<div class="page-head"><div><p class="eyebrow">CONTROLLED EVALUATION</p><h1>Run isolated V0-V3 comparisons</h1><p>This research-only workspace uses fixed demo profiles and approved goals without changing ordinary learner plans.</p></div></div>
  <section class="v2-card"><div class="section-head"><div><p class="eyebrow">EXPERIMENT SETUP</p><h2>Same goal, same profile snapshot, different enabled components</h2></div><span>${esc(options.ablation_version)}</span></div>
  <div class="controlled-setup-grid">
    <label><span>Profile</span><select onchange="setControlledEvaluationField('user_id',this.value)">${(options.profiles||[]).map(item=>`<option value="${esc(item.user_id)}" ${item.user_id===form.user_id?"selected":""}>${esc(item.display_name)}</option>`).join("")}</select></label>
    <label class="controlled-setup-goal"><span>Goal</span><select onchange="setControlledEvaluationField('goal_text',this.value)">${(options.goals||[]).map(item=>`<option value="${esc(item.goal_text)}" ${item.goal_text===form.goal_text?"selected":""}>${esc(item.goal_text)}</option>`).join("")}</select></label>
    <label><span>System version</span><select onchange="setControlledEvaluationField('system_version',this.value)">${(options.systems||[]).map(item=>`<option value="${esc(item.version)}" ${item.version===form.system_version?"selected":""}>${esc(item.version)} - ${esc(item.name)}</option>`).join("")}</select></label>
  </div>
  <p class="muted">Each Planning Agent independently recommends the study cadence, total workload, and learning days. Formal comparisons require live Planning and Content Agent generation; a fallback preview is never counted as a live quality result.</p><div class="scope-actions"><button class="v2-primary" type="button" onclick="runControlledComparison()" ${state.controlledEvaluation.loading?"disabled":""}>${state.controlledEvaluation.loading?"Running V0-V3...":"Run V0-V3 Comparison"}</button><button class="v2-secondary" type="button" onclick="runControlledEvaluation()" ${state.controlledEvaluation.loading?"disabled":""}>Run one version</button></div></section>
  <section class="v2-card"><div class="section-head"><div><p class="eyebrow">CAPABILITY MATRIX</p><h2>Auditable component switches</h2></div><span>Current final product system: V3 = lecture-v4</span></div>
  <div class="controlled-capability-table-wrap"><table class="controlled-capability-table"><thead><tr><th>System</th><th>Profile</th><th>KG</th><th>Teaching assets</th><th>Source grounding</th><th>Purpose</th></tr></thead><tbody>${(options.systems||[]).map(system=>`<tr><th scope="row"><b>${esc(system.version)}</b><span>${esc(system.name)}</span></th><td>${pill(system.profile?"Included":"—",system.profile?"green":"")}</td><td>${pill(system.kg?"Included":"—",system.kg?"green":"")}</td><td>${pill(system.teaching_assets?"Included":"—",system.teaching_assets?"green":"")}</td><td>${pill(system.source_grounding?"Included":"—",system.source_grounding?"green":"")}</td><td>${esc(system.current_final_system?"Current final product system":"Research-only comparison condition")}</td></tr>`).join("")}</tbody></table></div></section>
  ${result?`<section class="v2-card"><div class="section-head"><div><p class="eyebrow">RUN ARTIFACT</p><h2>${esc(result.system_version)} - ${esc(result.goal)}</h2></div>${pill(result.status,result.status==="success"?"green":"")}</div><p><b>Run ID:</b> ${esc(result.run_id)}</p><p><b>Generation mode:</b> ${esc(result.generation_mode||"n/a")}</p><p><b>Product surface:</b> ${esc(result.enabled_components?.product_surface||"none")}</p><p><b>Failure reason:</b> ${esc(result.failure_reason||"None")}</p><details class="lecture-excerpt"><summary><b>Automatic checks</b></summary><pre>${esc(JSON.stringify(result.checks||{},null,2))}</pre></details><details class="lecture-excerpt"><summary><b>Core learning unit</b></summary><pre>${esc(JSON.stringify(result.core_learning_unit,null,2))}</pre></details><details class="lecture-excerpt"><summary><b>Source evidence</b></summary><pre>${esc(JSON.stringify(result.source_evidence||[],null,2))}</pre></details></section>`:`<section class="v2-card profile-state"><h2>No run artifact yet</h2><p>Choose a fixed profile, an approved goal, and one system version to generate an isolated comparison artifact.</p></section>`}
  ${state.controlledEvaluation.comparison?controlledMetricsPanelV2(state.controlledEvaluation.comparison)+controlledComparisonPanelV2(state.controlledEvaluation.comparison):""}
  <section class="v2-card"><div class="section-head"><div><p class="eyebrow">AUDIT HISTORY</p><h2>Saved controlled runs</h2></div><div><span>${runs.length} artifact(s)</span> <button class="v2-secondary" type="button" onclick="exportControlledEvaluationRuns()" ${runs.length?"":"disabled"}>Export JSON</button></div></div>${runs.length?`<div class="controlled-run-list">${visibleRuns.map(run=>`<article><div class="controlled-run-version"><b>${esc(run.system_version||"—")}</b><span>System run</span></div><div class="controlled-run-summary"><h3>${esc(run.goal||"Untitled goal")}</h3><p><code>${esc(run.run_id||"—")}</code><span aria-hidden="true">·</span><time datetime="${esc(run.created_at||"")}">${esc(formatControlledRunTime(run.created_at))}</time></p></div><div class="controlled-run-status">${pill(run.status||"unknown",run.status==="success"?"green":run.status==="failed"?"red":"")} ${pill(run.generation_mode||"unknown")}</div></article>`).join("")}</div>${runs.length>visibleRuns.length?`<p class="muted controlled-run-note">Showing the latest ${visibleRuns.length} of ${runs.length} artifacts. Export JSON includes the complete history.</p>`:""}`:`<p class="muted">Runs created in this demo profile will appear here for comparison and export.</p>`}</section>`);
}

function formatControlledRunTime(value){
  if(!value)return "Time unavailable";
  const date=new Date(value);
  return Number.isNaN(date.getTime())?value:date.toLocaleString([], {year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
}

function controlledV3Visual(result){
  const section=result?.core_learning_unit?.section||result?.core_learning_unit||{};
  const content=section.lecture_content||{};
  const intro=content.concept_introduction||{}, example=content.worked_example||{}, summary=content.summary_connection||{};
  const tabs=[
    ["lesson", "Lesson", `<section class="lecture-teaching-part"><p class="eyebrow">CORE IDEA</p><h3>${esc(intro.hook||section.title||result.goal)}</h3><p>${esc(intro.explanation||section.summary||"")}</p>${(intro.mechanism||[]).length?`<h4>How the mechanism works</h4><ol>${intro.mechanism.map(step=>`<li>${esc(step)}</li>`).join("")}</ol>`:""}${intro.boundaries?`<h4>Boundary</h4><p>${esc(intro.boundaries)}</p>`:""}</section>${content.intuition?`<section class="lecture-teaching-part v4-intuition"><p class="eyebrow">INTUITION</p><p>${esc(content.intuition)}</p></section>`:""}`],
    ["example", "Worked example", `<section class="lecture-teaching-part worked-example"><p class="eyebrow">WORKED EXAMPLE</p><h3>${esc(example.problem||"Apply the concept")}</h3><ol>${(example.steps||[]).map(step=>`<li>${esc(step)}</li>`).join("")}</ol><h4>Solution</h4><p>${esc(example.solution||"")}</p><h4>Why it works</h4><p>${esc(example.why_it_works||"")}</p></section>`],
    ["check", "Objective exercise", `<section class="lecture-teaching-part v4-objective-exercise"><p class="eyebrow">OBJECTIVE EXERCISE</p><h3>Check your understanding</h3>${(content.objective_exercise?.questions||[]).map((q,i)=>`<article class="v4-question"><h4>${i+1}. ${esc(q.prompt)}</h4><ul>${(q.options||[]).map(o=>`<li>${esc(o.text)}</li>`).join("")}</ul></article>`).join("")}</section>`],
    ["source", "Source evidence", `<section class="lecture-teaching-part"><p class="eyebrow">SOURCE EVIDENCE</p>${(result.source_evidence||[]).map(ref=>`<p><b>Page ${esc(ref.page_number||"—")}</b> · ${esc(ref.document_id||ref.resource_id||"Verified source")}</p>`).join("")||"<p>No source evidence is enabled for this version.</p>"}</section>`],
  ];
  const active=state.controlledEvaluation.visualTab||"lesson";
  return `<section class="v2-card controlled-visual"><div class="section-head"><div><p class="eyebrow">LEARNING EXPERIENCE · ${esc(result.system_version)}</p><h2>${esc(section.title||result.goal)}</h2><p class="muted">Rendered from this run artifact; no learner plan or cache is modified.</p></div><button class="v2-secondary" type="button" onclick="state.controlledEvaluation.visual=false;render()">Back to audit JSON</button></div><nav class="controlled-visual-tabs">${tabs.map(([id,label])=>`<button type="button" class="${active===id?"active":""}" onclick="state.controlledEvaluation.visualTab='${id}';render()">${label}</button>`).join("")}</nav><div class="controlled-visual-body">${tabs.find(item=>item[0]===active)?.[2]||tabs[0][2]}</div><section class="lecture-teaching-part v4-summary"><p class="eyebrow">TAKEAWAY</p><p>${esc(summary.summary||"")}</p></section></section>`;
}

function controlledMetricsPanel(comparison){
  const systems=comparison.systems||[];
  const d=comparison.comparison_metrics?.distinguishability||{};
  return `<section class="v2-card controlled-metrics"><div class="section-head"><div><p class="eyebrow">QUALITY COMPARISON</p><h2>Planning and content checks by system</h2></div><button class="v2-secondary" type="button" onclick="exportControlledComparison()">Export comparison JSON</button></div><p class="muted">Structural distinguishability: ${d.passed?"passed":"needs review"} · planning signatures ${esc(d.planning_unique_signatures||0)} · content signatures ${esc(d.content_unique_signatures||0)}</p><div class="controlled-metric-grid">${systems.map(item=>{const m=item.evaluation_metrics||{},p=m.planning||{},c=m.content||{},g=m.grounding||{};return `<article><h3>${esc(item.system_version)}</h3><p><b>Planning:</b> ${p.checks_passed||0}/${p.checks_total||0} checks</p><p><b>Content:</b> ${c.checks_passed||0}/${c.checks_total||0} checks</p><p><b>Grounding:</b> ${g.required?(g.passed?"passed":"failed"):"not enabled"}</p><p><b>Overall:</b> ${esc(item.status||"unknown")}</p></article>`}).join("")}</div></section>`;
}

function controlledMetricsPanelV2(comparison){
  const systems=comparison.systems||[], q=comparison.quality_evaluation||{};
  const qualityBy={};(q.results||[]).forEach(x=>{(qualityBy[x.system_version]??={})[x.dimension]=x});
  return `<section class="v2-card controlled-metrics"><div class="section-head"><div><p class="eyebrow">QUALITY COMPARISON</p><h2>Engineering gates and blind quality scores</h2></div><button class="v2-secondary" type="button" onclick="exportControlledComparison()">Export comparison JSON</button></div><div class="scope-actions"><button class="${state.controlledEvaluation.comparisonMode==="day1"?"v2-primary":"v2-secondary"}" type="button" onclick="state.controlledEvaluation.comparisonMode='day1';render()">Complete Day 1</button><button class="${state.controlledEvaluation.comparisonMode==="matched"?"v2-primary":"v2-secondary"}" type="button" onclick="state.controlledEvaluation.comparisonMode='matched';render()">Matched core-unit diagnostic</button></div><p class="muted">Engineering gates are not educational quality scores. Blind evaluator: ${esc(q.evaluator_model||"not configured")} · ${q.repetitions||3} runs per dimension.</p><div class="controlled-metric-grid">${systems.map(item=>{const m=item.evaluation_metrics||{}, p=m.planning||{}, c=m.content||{}, g=m.grounding||{}, qb=qualityBy[item.system_version]||{}, natural=Boolean(item.day_1?.content_markdown);return `<article><h3>${esc(item.system_version)}</h3><p><b>Contract:</b> ${esc(item.status||"unknown")}</p><p><b>Day 1:</b> ${natural?"Natural response":`${esc(item.day_1?.lecture_sections?.length||item.checks?.day_completeness?.section_count||0)} sections`} · ${esc(item.day_1?.estimated_minutes||item.checks?.time_budget?.estimated_minutes||0)} min</p><p><b>Prerequisites:</b> ${esc(qb.plan_prerequisite_correctness?.mean??"—")}</p><p><b>Completeness:</b> ${esc(qb.content_pedagogical_completeness?.mean??"—")}</p><p><b>Grounding:</b> ${esc(qb.content_source_grounding?.mean??(g.required?(g.passed?"contract pass":"contract fail"):"expected N/A"))}</p><p><b>Personalisation:</b> ${esc(qb.personalisation_depth?.mean??"—")}</p>${Object.values(qb).some(x=>x.low_confidence)?`<small class="muted">Low-confidence judge spread detected</small>`:""}</article>`}).join("")}</div></section>`;
}

function exportControlledComparison(){
  const blob=new Blob([JSON.stringify(state.controlledEvaluation.comparison||{},null,2)],{type:"application/json"});
  const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="pathly-controlled-evaluation-comparison.json";link.click();URL.revokeObjectURL(link.href);
}

function controlledComparisonPanel(comparison){
  const systems=comparison.systems||[], active=state.controlledEvaluation.activeVersion||"V3", result=systems.find(item=>item.system_version===active)||systems[0]||{};
  const unit=result.core_learning_unit||{}, section=unit.section||{}, content=section.lecture_content||{};
  const plan=result.plan||{};
  const metricCards=systems.map(item=>{const m=item.evaluation_metrics||{},p=m.planning||{},c=m.content||{},g=m.grounding||{};return `<article><b>${esc(item.system_version)}</b><span>Planning ${p.checks_passed||0}/${p.checks_total||0}</span><span>Content ${c.checks_passed||0}/${c.checks_total||0}</span><span>Grounding ${g.required?(g.passed?"pass":"fail"):"not enabled"}</span></article>`}).join("");
  const body=active==="V3"?`<section class="lecture-teaching-part"><p class="eyebrow">CORE IDEA</p><h3>${esc(content.concept_introduction?.hook||section.title||result.goal)}</h3><p>${esc(content.concept_introduction?.explanation||"")}</p>${(content.concept_introduction?.mechanism||[]).length?`<h4>How the mechanism works</h4><ol>${content.concept_introduction.mechanism.map(step=>`<li>${esc(step)}</li>`).join("")}</ol>`:""}</section><section class="lecture-teaching-part worked-example"><p class="eyebrow">WORKED EXAMPLE</p><h3>${esc(content.worked_example?.problem||"Apply the concept")}</h3><p>${esc(content.worked_example?.solution||"")}</p></section>`:`<section class="lecture-teaching-part"><p class="eyebrow">CORE IDEA</p><h3>${esc(unit.title||result.goal)}</h3><p>${esc(unit.summary||"")}</p><p>${esc(unit.body||"")}</p></section>`;
  return `<section class="v2-card controlled-comparison"><div class="section-head"><div><p class="eyebrow">END-TO-END ABLATION COMPARISON</p><h2>${esc(comparison.goal)}</h2><p class="muted">Same goal, profile and model. Each Planning Agent recommends its own study workload; only the enabled system components change.</p></div>${pill(comparison.status,comparison.status==="success"?"green":"")}</div><nav class="controlled-visual-tabs">${systems.map(item=>`<button type="button" class="${item.system_version===active?"active":""}" onclick="state.controlledEvaluation.activeVersion='${item.system_version}';render()">${item.system_version} · ${esc(item.enabled_components?.product_surface||item.system_version)}</button>`).join("")}</nav><div class="controlled-comparison-grid"><section class="v2-card"><p class="eyebrow">PLANNING AGENT OUTPUT</p><h3>${esc(plan.core_concept||unit.title||result.goal)}</h3><p>${esc(plan.goal_text||result.goal)}</p><p><b>Path:</b> ${esc((plan.prerequisite_path||unit.prerequisites||[]).join(" → ")||"No explicit prerequisite path")}</p><p><b>Recommended daily study time:</b> ${esc(plan.recommended_daily_minutes||"—")} min</p><p><b>Planning agent:</b> ${esc(plan.planning_agent||"unknown")}</p><p class="muted">Enabled: ${Object.entries(result.enabled_components||{}).filter(([key,value])=>["profile","kg","teaching_assets","source_grounding"].includes(key)&&value).map(([key])=>key).join(", ")||"pure LLM only"}</p></section><section class="v2-card"><p class="eyebrow">CONTENT AGENT OUTPUT</p><p><b>Status:</b> ${esc(result.status||"unknown")} · <b>Mode:</b> ${esc(result.generation_mode||"unknown")} · <b>Agent:</b> ${esc(result.content_contract?.content_agent||result.versions?.content_agent||"unknown")}</p>${body}</section></div><details class="lecture-excerpt"><summary><b>Evidence and checks for ${esc(active)}</b></summary><pre>${esc(JSON.stringify({content_contract:result.content_contract||{},source_evidence:result.source_evidence||[],checks:result.checks||{},versions:result.versions||{}},null,2))}</pre></details></section>`;
}

function controlledMarkdown(markdown){
  const codeBlocks=[];
  let html=esc(markdown||"").replace(/```([^\n]*)\n([\s\S]*?)```/g,(_,language,code)=>{
    const token=`@@PATHLY_CODE_${codeBlocks.length}@@`;
    codeBlocks.push(`<pre class="controlled-code"><code${language.trim()?` data-language="${esc(language.trim())}"`:""}>${code}</code></pre>`);
    return token;
  });
  html=html.replace(/^###\s+(.+)$/gm,"<h4>$1</h4>").replace(/^##\s+(.+)$/gm,"<h3>$1</h3>").replace(/^#\s+(.+)$/gm,"<h2>$1</h2>");
  html=html.replace(/^[-*]\s+(.+)$/gm,"<li>$1</li>");
  html=html.replace(/(<li>.*?<\/li>)(?:\n|$)/gs,"$1");
  html=html.replace(/(?:<li>.*?<\/li>)+/gs,match=>`<ul>${match}</ul>`);
  html=html.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>");
  html=html.split(/\n{2,}/).map(block=>/^<h[234]>|^<ul>|^@@PATHLY_CODE_\d+@@$/.test(block)?block:`<p>${block.replace(/\n/g,"<br>")}</p>`).join("");
  return html.replace(/@@PATHLY_CODE_(\d+)@@/g,(_,index)=>codeBlocks[Number(index)]||"");
}

function controlledComparisonPanelV2(comparison){
  if(state.controlledEvaluation.comparisonMode==="matched") return controlledMatchedPanel(comparison);
  const systems=comparison.systems||[], active=state.controlledEvaluation.activeVersion||"V3", result=systems.find(x=>x.system_version===active)||systems[0]||{};
  const plan=result.plan||{}, day=result.day_1||{}, sections=day.lecture_sections||result.core_learning_unit?.lecture_sections||[];
  const natural=plan.output_format==="natural_markdown"||result.core_learning_unit?.output_format==="natural_markdown";
  const metrics=`<div class="controlled-metric-grid"><article><small>ESTIMATED TOTAL TIME</small><h3>${esc(plan.estimated_total_minutes||"—")} min</h3></article><article><small>ESTIMATED DAYS</small><h3>${esc(plan.estimated_days||"—")}</h3></article><article><small>RECOMMENDED DAILY TIME</small><h3>${esc(plan.recommended_daily_minutes||"—")} min</h3></article><article><small>DAY 1 WORKLOAD</small><h3>${esc(day.estimated_minutes||plan.session_minutes||"—")} min</h3></article><article><small>FEASIBILITY</small><h3>${esc(plan.feasibility?.status||"—")}</h3></article></div>`;
  const sectionCard=(s,i)=>{const c=s.lecture_content||{}, intro=c.concept_introduction||{}, ex=c.worked_example||{}, exercise=c.objective_exercise||{}, summary=c.summary_connection||{}, sourceReader=result.enabled_components?.source_grounding?controlledSourceCarousel(s,result):"";return `<article class="v2-card controlled-day-section"><div class="section-head"><div><p class="eyebrow">SECTION ${i+1} · YOUR LESSON</p><h3>${esc(s.title||s.concept_name||"Learning section")}</h3></div><span>${esc(s.estimated_minutes||0)} min</span></div>${sourceReader}<section class="lecture-teaching-part"><p class="eyebrow">CORE IDEA</p><h4>${esc(intro.hook||s.title||"")}</h4><p>${esc(intro.explanation||s.summary||"")}</p>${(intro.mechanism||[]).length?`<h4>How the mechanism works</h4><ol>${intro.mechanism.map(x=>`<li>${esc(x)}</li>`).join("")}</ol>`:""}${intro.boundaries?`<h4>Boundary</h4><p>${esc(intro.boundaries)}</p>`:""}</section>${c.intuition?`<section class="lecture-teaching-part"><p class="eyebrow">INTUITION</p><p>${esc(c.intuition)}</p></section>`:""}<section class="lecture-teaching-part worked-example"><p class="eyebrow">WORKED EXAMPLE</p><h4>${esc(ex.problem||"Worked application")}</h4><ol>${(ex.steps||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ol><p>${esc(ex.solution||"")}</p><p>${esc(ex.why_it_works||"")}</p></section><section class="lecture-teaching-part v4-objective-exercise"><p class="eyebrow">OBJECTIVE EXERCISE</p>${(exercise.questions||[]).map((q,n)=>`<div class="v4-question"><h4>${n+1}. ${esc(q.prompt||"")}</h4><ul>${(q.options||[]).map(o=>`<li>${esc(o.text||"")}</li>`).join("")}</ul></div>`).join("")}</section><section class="lecture-teaching-part v4-summary"><p class="eyebrow">TAKEAWAY</p><p>${esc(summary.summary||"")}</p></section></article>`};
  const path=plan.prerequisite_path||[];
  const planningBody=natural?`<div class="controlled-markdown">${controlledMarkdown(plan.plan_markdown||"")}</div>`:`<><h3>${esc(plan.core_concept||result.goal||"")}</h3><p><b>Approved concept path:</b> ${esc(path.join(" → "))}</p><p>${esc(plan.planning_rationale||"")}</p></>`;
  const contentBody=natural?`<section class="v2-card controlled-natural-content"><p class="eyebrow">CONTENT AGENT · COMPLETE DAY 1</p><div class="controlled-markdown">${controlledMarkdown(day.content_markdown||result.core_learning_unit?.content_markdown||"")}</div></section>`:`<div class="controlled-day-sections">${sections.length?sections.map(sectionCard).join(""):`<section class="v2-card profile-state"><h3>Full Day 1 unavailable</h3><p>${esc(result.failure_reason||"No sections were generated.")}</p></section>`}</div>`;
  return `<section class="v2-card controlled-comparison"><div class="section-head"><div><p class="eyebrow">END-TO-END ABLATION COMPARISON</p><h2>${esc(comparison.goal||"")}</h2><p class="muted">Each tab is a complete read-only experiment replica. No learner plan or progress is modified.</p></div>${pill(comparison.status,comparison.status==="success"?"green":"")}</div><nav class="controlled-visual-tabs">${systems.map(item=>`<button type="button" class="${item.system_version===active?"active":""}" onclick="state.controlledEvaluation.activeVersion='${item.system_version}';render()">${esc(item.system_version)} · ${esc(item.enabled_components?.product_surface||item.enabled_components?.name||item.system_version)}</button>`).join("")}</nav>${metrics}<div class="controlled-comparison-grid"><section class="v2-card"><p class="eyebrow">PLANNING AGENT OUTPUT</p>${planningBody}${natural?"":`<p class="muted"><b>Enabled:</b> ${Object.entries(result.enabled_components||{}).filter(([k,v])=>["profile","kg","teaching_assets","source_grounding"].includes(k)&&v).map(([k])=>k).join(", ")}</p>`}</section><section class="v2-card"><p class="eyebrow">CONTENT AGENT</p><p><b>Status:</b> ${esc(result.status||"unknown")} · <b>Mode:</b> ${esc(result.generation_mode||"unknown")}</p><p class="muted">${natural?"Natural-language Day 1 response.":`${sections.length} full source-grounded section(s).`}</p></section></div>${contentBody}<details class="lecture-excerpt"><summary><b>Evidence and audit</b></summary><pre>${esc(JSON.stringify({source_evidence:result.source_evidence||[],checks:result.checks||{},versions:result.versions||{},quality_evaluation:comparison.quality_evaluation||{}},null,2))}</pre></details></section>`;
}

function controlledSourceCarousel(section,result){
  const pages=section.source_pages||[];
  if(!pages.length)return "";
  const page=pages[0], isPrivate=page.source_scope==="private"&&page.document_id;
  const imageSrc=isPrivate?`/api/documents/${encodeURIComponent(page.document_id)}/pages/${encodeURIComponent(page.page_number)}/render?user_id=${encodeURIComponent(result.user_id||state.userId)}`:(page.resource_id?`/api/public-resources/${encodeURIComponent(page.resource_id)}/pages/${encodeURIComponent(page.page_number)}/render`:"");
  const guide=(section.lecture_content?.page_walkthrough||[]).find(x=>String(x.page_number)===String(page.page_number))||{};
  return `<section class="v4-source-pages v4-source-carousel"><p class="eyebrow">LEARN FROM THE SOURCE · PAGE ${esc(page.page_number||"—")} OF ${esc(pages.length)}</p><article class="v4-source-page"><div class="section-head"><div><p class="eyebrow">PAGE ${esc(page.page_number||"—")} · ${isPrivate?"Private PDF":"Public PDF"}</p><h3>Selected source page</h3></div></div>${imageSrc?`<div class="v4-pdf-page-frame"><img loading="lazy" src="${imageSrc}" alt="Source page ${esc(page.page_number||"")}"></div>`:`<blockquote class="v4-public-source-text">${esc(page.text||"Source page preview unavailable.")}</blockquote`}<section class="v4-page-annotation"><p class="eyebrow">SOURCE EXPLANATION</p><h4>${esc(guide.what_to_notice||"Central idea")}</h4><p class="v4-math-safe">${esc(guide.explanation||"")}</p>${guide.connection_to_previous?`<p class="v4-page-connection"><b>Connection:</b> ${esc(guide.connection_to_previous)}</p>`:""}</section>${page.text?`<details class="v4-source-transcript"><summary>Text version of this page</summary><blockquote>${esc(page.text)}</blockquote></details>`:""}</article></section>`;
}

function controlledMatchedPanel(comparison){
  const matched=comparison.matched_diagnostic||{}, systems=matched.systems||[], active=state.controlledEvaluation.activeVersion||"V3", result=systems.find(x=>x.system_version===active)||systems[0]||{}, unit=result.core_learning_unit||{}, section=unit.section||unit, lectureContent=section.lecture_content||{}, intro=lectureContent.concept_introduction||{};
  const natural=unit.output_format==="natural_markdown"||Boolean(unit.content_markdown);
  const renderedContent=natural?`<div class="controlled-markdown">${controlledMarkdown(unit.content_markdown||"")}</div>`:`<h3>${esc(intro.hook||section.title||matched.concept||"")}</h3><p>${esc(intro.explanation||unit.summary||unit.body||"")}</p>`;
  return `<section class="v2-card controlled-comparison"><div class="section-head"><div><p class="eyebrow">MATCHED CORE-UNIT DIAGNOSTIC</p><h2>Matched concept: ${esc(matched.concept||comparison.goal||"")}</h2><p class="muted">Every tab is an independent generation for the same canonical concept, not a section copied from the main Day 1 result.</p></div></div><nav class="controlled-visual-tabs">${systems.map(item=>`<button type="button" class="${item.system_version===active?"active":""}" onclick="state.controlledEvaluation.activeVersion='${item.system_version}';render()">${esc(item.system_version)}</button>`).join("")}</nav><div class="controlled-comparison-grid"><section class="v2-card"><p class="eyebrow">DIAGNOSTIC CONTRACT</p><h3>${esc(result.diagnostic_concept||matched.concept||"")}</h3><p><b>Run ID:</b> ${esc(result.run_id||"—")}</p><p><b>Status:</b> ${esc(result.status||"unknown")}</p><p><b>Path:</b> ${esc((result.plan?.prerequisite_path||[]).join(" → ")||"No KG path in this condition")}</p></section><section class="v2-card"><p class="eyebrow">CONTENT AGENT</p>${renderedContent}<p class="muted">Mode: ${esc(result.generation_mode||"unknown")} · Source refs: ${esc((result.source_evidence||[]).length)}</p></section></div><details class="lecture-excerpt"><summary>Matched diagnostic audit</summary><pre>${esc(JSON.stringify({diagnostic_concept_id:matched.diagnostic_concept_id,source_evidence:result.source_evidence||[],note:matched.note||""},null,2))}</pre></details></section>`;
}

function setControlledEvaluationField(key,value){
  state.controlledEvaluation.form={...state.controlledEvaluation.form,[key]:value};
  persist();
}

async function runControlledEvaluation(){
  await act(async()=>{
    state.controlledEvaluation.loading=true;
    await ensureControlledDemoSession();
    const result=await api("/api/controlled-evaluation/runs",{method:"POST",body:JSON.stringify({...state.controlledEvaluation.form,force_regenerate:true,allow_cache:false})});
    state.controlledEvaluation.result=result;
    await loadControlledEvaluationRuns();
    state.notice=`Controlled Evaluation ${result.system_version} finished with status ${result.status}.`;
  },"Running isolated controlled evaluation...");
  state.controlledEvaluation.loading=false;
  persist();
  render();
}

async function runControlledComparison(){
  await act(async()=>{
    state.controlledEvaluation.loading=true;
    await ensureControlledDemoSession();
    const result=await api("/api/controlled-evaluation/comparisons",{method:"POST",body:JSON.stringify({...state.controlledEvaluation.form,force_regenerate:true,allow_cache:false})});
    state.controlledEvaluation.comparison=result;
    state.controlledEvaluation.activeVersion="V3";
    await loadControlledEvaluationRuns();
    state.notice=`V0-V3 comparison finished with status ${result.status}.`;
  },"Running the four end-to-end ablation systems...");
  state.controlledEvaluation.loading=false;persist();render();
}

async function ensureControlledDemoSession(){
  const target=state.controlledEvaluation.form.user_id;
  if(!target||state.userId===target)return;
  const switched=await api(`/api/demo-users/${encodeURIComponent(target)}/switch`,{method:"POST"});
  state.userId=switched.user_id||target;
  persist();
}


function workspace(){
  if(state.editingGoal)return goalStep();
  if(state.stepOverride===1&&state.draft?.status==="profile_confirmed")return confirmedProfileStep();
  if(state.stepOverride===2&&state.estimate)return workloadReviewStep();
  if(state.stepOverride===3&&state.estimate)return capacityStep();
  if(!state.draft)return goalStep();
  if(state.draft.status==="draft"&&!state.mapReviewConfirmed?.[state.draft.draft_id])return mapReviewStep();
  if(state.draft.status==="draft")return questionsStep();
  if(!state.estimate)return workloadStep();
  if(!state.decision)return capacityStep();
  if(state.decision.status!=="confirmed")return decisionStep();
  return completionStep();
}
function currentOnboardingStep(){
  if(!state.draft)return 0;
  if(state.draft.status==="draft")return 1;
  if(!state.estimate)return 2;
  if(!state.decision)return 3;
  return state.decision.status==="confirmed"?5:4;
}
function goOnboardingStep(index){
  const reachable=Math.min(4,currentOnboardingStep());
  if(index>reachable)return;
  state.error=null;state.notice=null;state.scopeMode=false;state.capacityReview=false;state.pendingCapacityChoice=null;state.pendingStrategy=null;
  state.stepOverride=index;
  state.editingGoal=index===0&&Boolean(state.draft);
  if(index===0)state.interpretation=null;
  if(index===1&&state.draft?.status==="draft")state.stepOverride=null;
  if(index===4)state.stepOverride=null;
  render();
}
function steps(active,reachable=active){
  const labels=["Goal & Sources","Learner Profile","Workload","Capacity","Create Path"];
  return `<div class="v2-steps">${labels.map((x,i)=>`<div class="${i<reachable?"done":i===reachable?"current":""} ${i===active?"active":""}"><button type="button" ${i<=reachable?`onclick="goOnboardingStep(${i})"`:"disabled"} ${i===active?'aria-current="step"':""}><i>${i<reachable?"&#10003;":i+1}</i><span>${x}</span></button></div>`).join("")}</div>`;
}
function goalStep(){
  if(state.interpretation && state.interpretation.status!=="confirmed")return interpretationStep();
  const revising=state.editingGoal&&Boolean(state.draft);
  const freshProof=state.freshWalkthrough&&state.freshWorkspaceAudit?.empty_workspace_verified?`<div class="v2-notice fresh-workspace-proof"><b>Fresh-user walkthrough ready</b><span>New identity verified: no Profile, plans, onboarding draft, or cached lecture content. Enter a goal to begin the real onboarding flow.</span></div>`:"";
  return shell(`${freshProof}${steps(0,state.editingGoal?Math.min(4,currentOnboardingStep()):0)}<section class="v2-hero"><p>${revising?"REVISE LEARNING OUTCOME":"NEW LEARNING PATH"}</p><h1>${revising?"What should this learning outcome become?":"What do you want to be able to do?"}</h1>
  <span>${revising?"Your confirmed profile is preserved. Saving this goal invalidates the old workload and capacity decision.":"Confirm your goal and source scope before Pathly estimates the total work."}</span></section>
  <div class="goal-flow"><section class="v2-card flow-step"><div class="flow-step-head"><i>1</i><div><p class="eyebrow">LEARNING GOAL</p><h2>Describe the outcome</h2><span>Start with what you want to be able to do. Pathly estimates the work only after the goal and source scope are clear.</span></div></div>
  <textarea id="goal" class="goal-textarea" rows="3" placeholder="For example: I want to explain and implement a basic neural network independently" oninput="state.goal=this.value">${esc(state.goal)}</textarea></section>
  <section class="v2-card flow-step"><div class="flow-step-head"><i>2</i><div><p class="eyebrow">OPTIONAL MATERIALS</p><h2>Upload your own materials</h2><span>You can skip this and use the public knowledge graph only. Uploaded PDFs stay private to this learning path and can only be selected after processing is ready.</span></div><label class="upload">Upload PDFs<input type="file" multiple accept=".pdf,application/pdf" onchange="uploadFiles(this.files)"></label></div>
  ${documentPicker()}</section>
  <section class="v2-card flow-step"><div class="flow-step-head"><i>3</i><div><p class="eyebrow">SOURCE STRATEGY</p><h2>Choose what Pathly should use</h2><span>This decides whether the plan is built from public KG concepts, your selected private materials, or both.</span></div></div>
  <div class="source-options source-cards">${[
    ["kg_only","Use the public knowledge graph","Best when you want a general plan from the shared course knowledge base."],["private_plus_kg","Use my materials, supplemented by the KG","Best when your uploaded PDFs should shape the path, with public KG filling gaps."],["private_only","Use only my materials","Best when the path should stay limited to your selected documents."]
  ].map(([v,l,d])=>`<label class="${state.sourceMode===v?"selected":""}"><input type="radio" name="source" value="${v}" ${state.sourceMode===v?"checked":""} onchange="state.sourceMode=this.value;render()"><b>${esc(l)}</b><small>${esc(d)}</small></label>`).join("")}</div>
  <div class="flow-actions"><button class="v2-primary" onclick="beginOnboarding()">${revising?"Save Goal and Recalculate Workload":"Continue to Learner Profile"}</button></div></section></div>`);
}
function interpretationStep(){
  const result=state.interpretation;
  const recognizedPublic=[...new Map((result.canonical_concepts||[]).map(item=>[item.concept_id||item.candidate||item.display_name||item.requested_term, item])).values()];
  const mappings=result.confirmation_required||[];
  const privateConcepts=result.private_concepts||[];
  return shell(`${steps(0,state.editingGoal?Math.min(4,currentOnboardingStep()):0)}<section class="v2-hero"><p>GOAL INTERPRETATION</p><h1>Confirm Pathly Interpretation</h1>
  <span>Candidate mappings are never accepted automatically. Review what should enter this path.</span></section>
  <section class="v2-card"><h2>Selected materials 鈥?used in this path</h2><p class="muted">These are the documents you chose. Pathly will use them as learning evidence even if you exclude some extracted concepts below.</p>${(result.documents||[]).length?`<div class="selection-summary">${result.documents.map(item=>pill(item.display_name||"Selected private material","green")).join("")}</div>`:""}<h2>Recognized Public Concepts</h2><p class="muted">These concepts matched the Public KG with high confidence and are included automatically. You do not need to review them here.</p>
  ${recognizedPublic.length?`<div class="selection-summary">${recognizedPublic.map(item=>pill(item.display_name||item.candidate||item.concept_id||item.requested_term||"Public KG concept","green")).join("")}</div>`:`<div class="empty">No public concepts were recognized from this goal yet.</div>`}<h2>Public KG Candidates Requiring Review</h2>
  ${mappings.length?mappings.map((item,index)=>`<label class="doc-row"><input type="checkbox" data-map-index="${index}" checked>
  <span><b>${esc(item.requested_term||item.term||"Target concept")} -> ${esc(item.candidate||"No candidate found")}</b><small>${esc(item.reason||"Please confirm whether this mapping is correct")}</small></span>${pill(item.confidence??"Pending")}</label>`).join(""):`<div class="empty">No public concept mappings require confirmation.</div>`}
  <h2>Concepts Suggested From Your Materials</h2><p class="muted">Choose which extracted concepts should shape this path. Unchecking a concept excludes it from the Knowledge Map and workload; it does not remove the selected document.</p>
  ${privateConcepts.length?privateConcepts.map((item,index)=>`<label class="doc-row"><input type="checkbox" data-private-index="${index}" checked>
  <span><b>${esc(item.display_name||item.requested_term||item.label||item.name||"Unrecognized private concept")}</b><small>Optional path concept from your selected materials. Your documents remain private and available as sources.</small></span>${pill("private")}</label>`).join(""):`<div class="empty">No extra private concepts were found. Selected materials can still support learning content.</div>`}
  <div class="scope-actions"><button class="v2-secondary" onclick="state.interpretation=null;render()">Back to Edit Goal</button><button class="v2-primary" onclick="confirmInterpretationAndBegin()">Confirm and Continue</button></div></section>`);
}
function documentPicker(){
  if(!state.documents.length)return `<div class="empty">No private materials yet. You can continue with the public knowledge graph.</div>`;
  return `<div class="doc-list">${state.documents.map(d=>{const ready=d.parse_status==="ready";const selected=ready&&Boolean(state.selectedDocuments[d.document_id]);return `<label class="doc-row ${ready?"":"not-ready"}"><input type="checkbox" ${selected?"checked":""} ${ready?"":"disabled"} aria-disabled="${!ready}" onchange="toggleDoc('${d.document_id}',this.checked)">
  <span><b>${esc(d.display_name)}</b><small>${ready?`${d.page_count||"?"} pages  /  Ready to use`:`${esc(d.parse_status)}  /  Processing must finish before this material can be used`}</small></span>${pill(ready?"ready":d.parse_status,ready?"green":"")}</label>`}).join("")}</div>`;
}
function syncGoalInput(){const input=$("#goal");if(input)state.goal=input.value}
function toggleDoc(id,on){syncGoalInput();const documentRecord=state.documents.find(d=>d.document_id===id);if(on&&documentRecord?.parse_status!=="ready"){state.error="This document is still processing. Wait until it is ready before selecting it.";render();return}if(on)state.selectedDocuments[id]={required:true};else delete state.selectedDocuments[id];state.interpretation=null;render()}
async function uploadFiles(fileList){
  const files=Array.from(fileList||[]);
  if(!files.length)return;
  syncGoalInput();
  await act(async()=>{
    const results=await Promise.allSettled(files.map(async file=>{
      const body=new FormData();
      body.append("user_id",state.userId);
      body.append("file",file);
      return api("/api/documents",{method:"POST",body});
    }));
    await loadDocuments();
    const succeeded=results.filter(result=>result.status==="fulfilled");
    const failed=results.map((result,index)=>({result,file:files[index]})).filter(item=>item.result.status==="rejected");
    if(succeeded.length){
      state.notice=`${succeeded.length} of ${files.length} PDF${files.length===1?"":"s"} accepted. Processing continues in the background.`;
    }
    if(failed.length){
      const details=failed.map(item=>`${item.file.name}: ${item.result.reason?.message||"Upload failed"}`).join("; ");
      if(!succeeded.length)throw new Error(details);
      state.error=`Some files could not be uploaded: ${details}`;
    }
  });
}
async function beginOnboarding(){
  const goalInput=$("#goal");
  if(!goalInput){state.error="The page state changed. Return to New Path and try again.";render();return}
  const goalValue=goalInput.value.trim();
  if(!goalValue){state.error="Describe your learning goal first.";render();return}
  const selected=Object.keys(state.selectedDocuments);
  const unavailable=selected.filter(id=>state.documents.find(d=>d.document_id===id)?.parse_status!=="ready");
  if(unavailable.length){state.error="Wait for all selected documents to finish processing before continuing.";render();return}
  await act(async()=>{
    state.goal=goalValue;
    let interpretationId=null;
    if(state.sourceMode!=="kg_only"){
      if(!selected.length)throw new Error("Select at least one document for this source mode");
      const result=await api("/api/goal-interpretations",{method:"POST",body:JSON.stringify({
        user_id:state.userId,goal_text:state.goal,source_mode:state.sourceMode,
        documents:selected.map(id=>({document_id:id,role:"core",required:true}))
      })});
      state.interpretation=result;
      if(result.status!=="confirmed")return;
      interpretationId=result.interpretation_id;
    }
    await finishGoal(interpretationId);
  });
}
async function finishGoal(interpretationId){
  if(state.editingGoal&&state.draft){
    const wasConfirmed=state.draft.status==="profile_confirmed";
    state.draft=await api(`/api/onboarding-drafts/${state.draft.draft_id}/revise-goal`,{method:"POST",body:JSON.stringify({
      user_id:state.userId,goal_text:state.goal,goal_interpretation_id:interpretationId
    })});
    state.draftId=state.draft.draft_id;state.answers=state.draft.answers||{};
    state.estimate=null;state.decision=null;state.editingGoal=false;state.pendingStrategy=null;state.interpretation=null;state.stepOverride=null;state.edgeEditSource=null;delete state.mapReviewConfirmed[state.draft.draft_id];delete state.mapReviewEdges[state.draft.draft_id];delete state.mapReviewExcluded[state.draft.draft_id];
    state.notice=wasConfirmed?"Goal updated. Generate a new workload estimate for the revised outcome.":"Goal updated. Continue your learner profile.";
    return;
  }
  await createOnboardingDraft(interpretationId);
}async function createOnboardingDraft(interpretationId){
  state.draft=await api("/api/onboarding-drafts",{method:"POST",body:JSON.stringify({
    user_id:state.userId,goal_text:state.goal,goal_interpretation_id:interpretationId
  })});
  state.draftId=state.draft.draft_id;state.answers=state.draft.answers||{};state.edgeEditSource=null;delete state.mapReviewConfirmed[state.draft.draft_id];delete state.mapReviewEdges[state.draft.draft_id];delete state.mapReviewExcluded[state.draft.draft_id];
}
async function confirmInterpretationAndBegin(){
  await act(async()=>{
    const result=state.interpretation;
    const confirmed={}; const rejected=[];
    (result.confirmation_required||[]).forEach((item,index)=>{
      const term=item.requested_term||item.term;
      if(document.querySelector(`[data-map-index="${index}"]`)?.checked && item.candidate)confirmed[term]=item.candidate;
      else if(term)rejected.push(term);
    });
    const accepted=(result.private_concepts||[]).filter((_,index)=>document.querySelector(`[data-private-index="${index}"]`)?.checked).map(item=>item.private_concept_id);
    const rejectedPrivate=(result.private_concepts||[]).filter((_,index)=>!document.querySelector(`[data-private-index="${index}"]`)?.checked).map(item=>item.private_concept_id);
    state.interpretation=await api(`/api/goal-interpretations/${result.interpretation_id}/confirm`,{method:"POST",body:JSON.stringify({
      user_id:state.userId,confirmed_mappings:confirmed,accepted_private_concepts:accepted,rejected_private_concepts:rejectedPrivate,rejected_terms:rejected
    })});
    await finishGoal(state.interpretation.interpretation_id);
  });
}
const QUESTION_IMPACT={
  math_situation:"This may affect prerequisite coverage, mathematical explanation depth, and learning time.",
  programming_situation:"This may affect coding support, starter examples, practice difficulty, and learning time.",
  abstract_situation:"This may affect the balance between concrete examples and abstract models.",
  logic_situation:"This may affect reasoning scaffolds, worked examples, and checkpoint density.",
  learning_experience:"This may affect prerequisite review, explanation depth, and learning time.",
  learning_style:"This may affect whether lessons lead with explanation, examples, or hands-on practice.",
  preferred_examples:"This chooses the explanation format: situations, business cases, research problems, code, or mathematical derivations.",
  interest_tags:"This chooses the application domain for examples when the topic supports one; it does not change the explanation format.",
  pace_preference:"This may affect session structure and the balance between new material and review.",
  current_confidence:"Used only for this path; it may affect scaffolding and checkpoint density.",
  current_anxiety:"Used only for this path; it may affect task chunking and session pacing.",
  self_regulation:"This may affect review spacing and how sessions resume after interruptions.",
  target_mastery:"This may affect prerequisite coverage, practice depth, and learning time."
};
function questionPrompt(q){
  const impact=QUESTION_IMPACT[q.id];
  if(!impact)return `<h3>${esc(q.prompt)}</h3>`;
  return `<div class="question-title"><h3>${esc(q.prompt)}</h3><span class="question-help-wrap"><button type="button" class="question-help" aria-label="How this answer is used" title="${esc(impact)}">?</button><span class="question-impact" role="tooltip">${esc(impact)}</span></span></div>`;
}
function answerControl(q){
  const value=state.answers[q.id];
  if(q.type==="scale")return `<div class="scale">${[1,2,3,4,5].map(v=>`<button class="${value==v?"selected":""}" onclick="answer('${q.id}',${v})">${v}</button>`).join("")}</div>`;
  if(q.type==="multi_choice")return `<div class="choices">${q.options.map(o=>`<button class="${(value||[]).includes(o.value)?"selected":""}" onclick="multiAnswer('${q.id}','${o.value}')">${esc(o.label)}</button>`).join("")}</div>`;
  return `<div class="choices">${q.options.map(o=>`<button class="${value===o.value?"selected":""}" onclick="answer('${q.id}','${o.value}')">${esc(o.label)}</button>`).join("")}</div>`;
}
const REVIEW_DIMENSIONS={
  math_situation:["Mathematical foundation","cognitive_traits","mathematical_ability"],
  programming_situation:["Programming foundation","cognitive_traits","programming_ability"],
  abstract_situation:["Abstract thinking","cognitive_traits","abstract_thinking"],
  logic_situation:["Logical reasoning","cognitive_traits","logical_reasoning"],
  learning_experience:["General learning foundation","cognitive_traits","general_learning_foundation"],
  learning_style:["Explanation style","affective_defaults","learning_style"],
  preferred_examples:["Explanation formats","affective_defaults","preferred_examples"],
  interest_tags:["Example domains","affective_defaults","interest_tags"],
  pace_preference:["Long-term pace","affective_defaults","pace_preference"],
  self_regulation:["Recovery after interruptions","affective_defaults","self_regulation"]
};
function reviewCurrentValue(id){
  const meta=REVIEW_DIMENSIONS[id]||[id,"",""];
  const value=state.draft?.stable_profile_before?.[meta[1]]?.[meta[2]];
  return Array.isArray(value)?value.join(", "):(value??"Not set");
}
function reviewPanel(){
  if(state.draft.onboarding_type!=="repeat"||state.answers.profile_changed!=="yes")return "";
  const reviewQuestions=(state.draft.profile_review_questions||[]).filter(q=>q.id!=="motivation_level");
  const reviewAnswered=reviewQuestions.some(q=>state.answers[q.id]!==undefined);
  const changes=state.draft.profile_review_changes||[];
  return `<section class="profile-review"><div class="review-head"><div><p class="eyebrow">OPTIONAL PROFILE REVIEW</p><h2>Update Only What Changed</h2><p>Your saved profile stays unchanged until you confirm this step.</p></div>${pill(`${reviewQuestions.filter(q=>state.answers[q.id]!==undefined).length} selected`)}</div>
  <div class="review-list">${reviewQuestions.map(q=>{const active=state.reviewOpen[q.id]||state.answers[q.id]!==undefined;const label=REVIEW_DIMENSIONS[q.id]?.[0]||q.dimension;return `<article class="review-item ${active?"active":""}"><div><small>${esc(label)}</small><b>${esc(reviewCurrentValue(q.id))}</b></div><button class="v2-secondary" onclick="toggleReview('${q.id}')">${active?"Keep saved value":"Update"}</button>${active?`<div class="review-question">${questionPrompt(q)}${answerControl(q)}</div>`:""}</article>`}).join("")}</div>
  <div class="review-diff"><h3>Changes to Confirm</h3>${changes.length?changes.map(change=>`<div><span>${esc(REVIEW_DIMENSIONS[change.answer_id]?.[0]||change.dimension)}</span><del>${esc(Array.isArray(change.before)?change.before.join(", "):change.before??"Not set")}</del><b>-> ${esc(Array.isArray(change.after)?change.after.join(", "):change.after)}</b></div>`).join(""):reviewAnswered?`<p>Reviewed values currently match your saved profile.</p>`:`<p>Select Update beside each dimension that has changed.</p>`}</div></section>`;
}
async function toggleReview(id){
  const active=state.reviewOpen[id]||state.answers[id]!==undefined;
  if(active&&state.answers[id]!==undefined){
    delete state.answers[id];
    state.reviewOpen[id]=false;
    await act(async()=>{state.draft=await api(`/api/onboarding-drafts/${state.draftId}`,{method:"PATCH",body:JSON.stringify({user_id:state.userId,answers:{[id]:null}})});state.answers=state.draft.answers||{}});
    return;
  }
  state.reviewOpen[id]=!active;
  render();
}

function goalTermsFromText(text){
  return [...new Set(String(text||"").toLowerCase().replace(/[^a-z0-9\s-]/g," ").split(/\s+/).filter(w=>w.length>3&&!new Set(["want","learn","able","with","from","that","this","basic","using","about","into","only","path"]).has(w)).slice(0,8))];
}
function publicMapExpansion(terms){
  const normalized=terms.map(x=>String(x).trim().toLowerCase());
  const expansions=[];
  const add=(items)=>items.forEach(display_name=>{
    if(!terms.some(term=>String(term).toLowerCase()===display_name.toLowerCase())&&!expansions.some(item=>item.display_name===display_name))expansions.push({concept_id:display_name,display_name,requested_term:display_name,is_target:false,source_type:"public",estimated_total_minutes:"pending",planning_reason:"Related public KG concept included to make the goal-scoped map actionable."});
  });
  if(normalized.some(x=>x.includes("machine learning")||x==="ml"))add(["Artificial Intelligence","Data in AI","Linear Algebra","Regression","Supervised Learning","Unsupervised Learning","Classification","Gradient Descent","Neural Networks","Deep Learning","Reinforcement Learning"]);
  if(normalized.some(x=>x.includes("neural network")))add(["Linear Algebra","Gradient Descent","Backpropagation","Deep Learning","Convolutional Neural Networks","Recurrent Neural Networks"]);
  if(normalized.some(x=>x.includes("rag")||x.includes("retrieval-augmented")))add(["Embeddings","Vector Databases","Information Retrieval","Large Language Models"]);
  return expansions;
}
function mapName(value){return String(value||"").trim().toLowerCase().replace(/[^a-z0-9]+/g," ").trim()}
function mapEdgeKey(source,target){return `${String(source)}=>${String(target)}`}
function uniqueMapItems(items){const seen=new Set();return items.filter(item=>{const key=String(item.concept_id||item.id||item.display_name||"").toLowerCase();if(!key||seen.has(key))return false;seen.add(key);return true})}
function reviewPrimaryTargetId(items,goal,terms){
  const normalizedGoal=mapName(goal),termNames=new Set((terms||[]).map(mapName));
  const exact=items.find(item=>{const name=mapName(item.display_name||item.requested_term||item.concept_id);return name&&normalizedGoal.includes(name)&&name.length>3});
  const termMatch=items.find(item=>termNames.has(mapName(item.display_name||item.requested_term||item.concept_id)));
  return String((exact||termMatch||items[0]||{}).concept_id||"");
}
function reviewConceptRole(item,primaryId){
  if(String(item.concept_id)===String(primaryId))return "target";
  const name=mapName(item.display_name||item.requested_term||item.concept_id);
  if(new Set(["artificial intelligence","linear algebra","gradient descent","backpropagation","regression","supervised learning"]).has(name))return "prerequisite";
  if(new Set(["classification","unsupervised learning","neural networks","deep learning","reinforcement learning","embeddings","vector databases","information retrieval","large language models"]).has(name))return "learning_target";
  return "supporting";
}
function reviewMapEdges(){const id=state.draft?.draft_id;return id?(state.mapReviewEdges?.[id]||[]):[]}
function saveReviewMapEdges(edges){const id=state.draft?.draft_id;if(!id)return;state.mapReviewEdges={...(state.mapReviewEdges||{}),[id]:edges};persist()}
function mapReviewConcepts(){
  const goal=state.goal||state.draft?.goal_text||"";
  const approved=state.draft?.approved_goal_scope;
  if(approved?.canonical_path?.length){
    const path=approved.canonical_path,names=approved.display_names||[];
    return path.map((conceptId,index)=>({
      concept_id:String(conceptId),display_name:String(names[index]||conceptId),requested_term:String(names[index]||conceptId),
      source_type:"public",estimated_total_minutes:"pending",
      planning_reason:"Approved full-experience canonical chain.",
      prerequisite_ids:index?[String(path[index-1])]:[],
      is_target:index===path.length-1,
      path_role:index===path.length-1?"target":"prerequisite"
    }));
  }
  const terms=((state.draft?.target_terms||[]).filter(Boolean).length?(state.draft?.target_terms||[]):goalTermsFromText(goal)).filter(Boolean);
  const interpretation=state.interpretation||{};
  const candidates=[];
  const add=(raw,source_type="public",reason="Included in this goal-relevant knowledge map.")=>{if(!raw)return;candidates.push({concept_id:String(raw.concept_id||raw.candidate||raw.private_concept_id||raw.id||raw.requested_term||raw.display_name||raw),display_name:raw.display_name||raw.candidate||raw.requested_term||raw.label||raw.name||raw.title||String(raw),requested_term:raw.requested_term||raw.term,source_type:raw.source_type||source_type,estimated_total_minutes:"pending",planning_reason:raw.reason||reason,prerequisite_ids:raw.prerequisite_ids||[]})};
  terms.forEach(term=>add({concept_id:String(term),display_name:String(term),requested_term:String(term)},String(term).startsWith("private:")?"private":"public","Extracted from the confirmed learning goal."));
  (interpretation.canonical_concepts||[]).forEach(item=>add(item,"public","Recognized from the Public KG."));
  (interpretation.confirmed_mappings||interpretation.accepted_mappings||[]).forEach(item=>add(item,"public","Confirmed Public KG mapping."));
  (interpretation.private_concepts||[]).forEach(item=>add(item,"private","Found in a selected private material."));
  const deduped=uniqueMapItems(candidates);
  publicMapExpansion([...terms,...deduped.map(item=>item.display_name)]).forEach(item=>add(item,"public"));
  const all=uniqueMapItems(candidates);
  const primaryId=reviewPrimaryTargetId(all,goal,terms);
  return all.map(item=>({...item,is_target:String(item.concept_id)===primaryId,path_role:reviewConceptRole(item,primaryId)}));
}
function reviewMapExcluded(){const id=state.draft?.draft_id;return id?(state.mapReviewExcluded?.[id]||[]):[]}
function toggleReviewNode(id){
  const nodes=mapReviewConcepts(),node=nodes.find(item=>String(item.concept_id)===String(id));
  if(!node)return;
  rememberMapViewport();
  if(node.is_target){state.selectedConceptId=id;render();return}
  const draftId=state.draft?.draft_id;if(!draftId)return;
  const excluded=new Set(reviewMapExcluded().map(String));
  if(excluded.has(String(id))){
    excluded.delete(String(id));
    // Clear legacy edge-level exclusions touching this node so restoration is
    // complete even for a draft that was edited with the previous UI.
    saveReviewMapEdges(reviewMapEdges().filter(edge=>!(edge.type==="excluded_link"&&(String(edge.source)===String(id)||String(edge.target)===String(id)))));
  }else excluded.add(String(id));
  state.mapReviewExcluded={...(state.mapReviewExcluded||{}),[draftId]:[...excluded]};
  persist();state.selectedConceptId=id;render();
}
function mapReviewStep(){
  const nodes=mapReviewConcepts();
  return shell(`${steps(1,1)}<section class="v2-hero"><p>PERSONAL KNOWLEDGE MAP REVIEW</p><h1>Review the goal-scoped knowledge map</h1><span>Pathly shows only the concepts relevant to this path. Click a connection to exclude or restore that relationship; the primary learning outcome stays fixed.</span></section>
  ${conceptMap(nodes,{review:true,edges:reviewMapEdges(),excluded:reviewMapExcluded()})}
  <section class="v2-card pkm-confirm"><div><p class="eyebrow">CONFIRM BEFORE PROFILE</p><h2>Use this scope for learner profiling and workload planning?</h2><p>Only concepts that remain connected to the primary outcome enter the learning path. Your connection choices stay private to this draft.</p></div><div class="scope-actions"><button class="v2-secondary" onclick="goOnboardingStep(0)">Back to Goal & Sources</button><button class="v2-primary" onclick="confirmMapReview()">Confirm Map and Continue</button></div></section>`);
}
function toggleReviewEdge(source,target){
  const key=mapEdgeKey(source,target),edges=reviewMapEdges(),index=edges.findIndex(edge=>edge.type==="excluded_link"&&mapEdgeKey(edge.source,edge.target)===key);
  if(index>=0)edges.splice(index,1);else edges.push({source,target,type:"excluded_link"});
  saveReviewMapEdges(edges);state.selectedConceptId=source;render();
}
function connectReviewEdge(source,target){if(!source||!target||source===target)return;const edges=reviewMapEdges().filter(edge=>!(edge.source===source&&edge.target===target));edges.push({source,target,type:"student_bridge"});saveReviewMapEdges(edges);state.selectedConceptId=target;render()}
function removeReviewEdge(index){const edges=reviewMapEdges();edges.splice(index,1);saveReviewMapEdges(edges);render()}
function setReviewEdgeSource(id){state.edgeEditSource=id;state.selectedConceptId=id;render()}
async function confirmMapReview(){
  if(!state.draft?.draft_id)return;
  await act(async()=>{
    const concepts=mapReviewConcepts(),graph=personalKnowledgeGraph(concepts,{review:true,edges:reviewMapEdges(),excluded:reviewMapExcluded()});
    state.draft=await api(`/api/onboarding-drafts/${state.draft.draft_id}/knowledge-map-review`,{method:"PUT",body:JSON.stringify({user_id:state.userId,reviewed_concepts:concepts.map(item=>({concept_id:String(item.concept_id),display_name:item.display_name||item.title||item.concept_id,is_target:Boolean(item.is_target),source_type:item.source_type||"public",path_role:item.path_role||"supporting"})),excluded_concept_ids:graph.excludedNodeIds,edges:graph.edges.filter(edge=>edge.enabled!==false)})});
    const review=state.draft.knowledge_map_review||{};
    state.mapReviewExcluded={...(state.mapReviewExcluded||{}),[state.draft.draft_id]:review.excluded_concept_ids||[]};state.mapReviewEdges={...(state.mapReviewEdges||{}),[state.draft.draft_id]:review.edges||[]};state.mapReviewConfirmed={...(state.mapReviewConfirmed||{}),[state.draft.draft_id]:review.status==="confirmed"};state.stepOverride=null;state.selectedConceptId=null;
  });
}
function questionsStep(){
  const qs=(state.draft.questions||[]).filter(q=>q.id!=="current_motivation");
  const visibleIds=new Set(qs.map(q=>q.id));
  const missing=(state.draft.remaining_required||[]).filter(id=>visibleIds.has(id));
  const reviewQuestions=(state.draft.profile_review_questions||[]).filter(q=>q.id!=="motivation_level");
  const needsReviewSelection=state.draft.onboarding_type==="repeat"&&state.answers.profile_changed==="yes"&&!reviewQuestions.some(q=>state.answers[q.id]!==undefined);
  const answered=qs.filter(q=>state.answers[q.id]!==undefined).length;
  const stableIds=new Set(["math_situation","programming_situation","abstract_situation","logic_situation","learning_experience","learning_style","preferred_examples","interest_tags","pace_preference","self_regulation"]);
  let previousGroup="";
  const questionMarkup=qs.map((q,i)=>{const group=stableIds.has(q.id)?"Your learning profile":"This learning path";const heading=group!==previousGroup?`<div class="onboarding-section-heading"><p class="eyebrow">${group==="Your learning profile"?"LONG-TERM PROFILE":"CURRENT PATH"}</p><h2>${group}</h2><span>${group==="Your learning profile"?"Stable preferences and abilities reused across future paths.":"Answers specific to this goal and used only for this path."}</span></div>`:"";previousGroup=group;return `${heading}<div class="question"><small>${i+1}/${qs.length}  /  ${esc(q.dimension)}</small>${questionPrompt(q)}${answerControl(q)}</div>${q.id==="profile_changed"?reviewPanel():""}`}).join("");
  return shell(`${steps(1)}<div class="v2-cols profile-layout"><section class="v2-card"><p class="eyebrow">${state.draft.onboarding_type==="repeat"?"Returning learner  /  Only what changed + this path":"First profile  /  Stable profile + this path"}</p>
  <h1>Make the Plan Fit How You Learn</h1>${questionMarkup}
  ${needsReviewSelection?`<div class="v2-notice">Choose at least one profile dimension to update, or select "No, keep using them."</div>`:""}
  <button class="v2-primary" ${missing.length||needsReviewSelection?"disabled":""} onclick="confirmProfile()">Review and Confirm Profile</button></section>
  <aside class="v2-card sticky"><h2>Live Profile</h2>${profilePreview(state.draft.profile_preview)}
  <hr><b>Current Goal</b><p>${esc(state.goal)}</p><small>${answered}/${qs.length} path questions answered</small></aside></div>`);
}
function profilePreview(p={}){
  const c=p.cognitive_traits||{},a=p.affective_defaults||{};
  return `<div class="profile-grid">${Object.entries(c).map(([k,v])=>`<div><span>${esc(k)}</span><b>${esc(v)}/5</b></div>`).join("")}
  ${Object.entries(a).filter(([k])=>k!=="motivation_baseline").slice(0,5).map(([k,v])=>`<div><span>${esc(k)}</span><b>${esc(Array.isArray(v)?v.join(", "):v)}</b></div>`).join("")}</div>`;
}
async function answer(id,value){state.answers[id]=value;await saveAnswers()}
async function multiAnswer(id,value){const a=new Set(state.answers[id]||[]);a.has(value)?a.delete(value):a.add(value);state.answers[id]=[...a];await saveAnswers()}
async function saveAnswers(){await act(async()=>{state.draft=await api(`/api/onboarding-drafts/${state.draftId}`,{method:"PATCH",body:JSON.stringify({user_id:state.userId,answers:state.answers})});state.answers=state.draft.answers||{}})}
async function confirmProfile(){await act(async()=>{state.draft=await api(`/api/onboarding-drafts/${state.draftId}/confirm-profile`,{method:"POST",body:JSON.stringify({user_id:state.userId})});state.profile=state.draft.profile_snapshot||state.profile;state.profileLoaded=true})}


function approximateHours(minutes){
  const h=Math.max(1,Math.round(Number(minutes||0)/60));
  return `around ${h} hour${h===1?"":"s"}`;
}
function workloadSourceLine(){
  const source=state.estimate?.kg_source||state.estimate?.generation_mode||"planning evidence";
  return `Estimated from your goal, profile, and available ${source} context.`;
}
function mixSummary(){
  const categories=(state.estimate?.activity_mix||[]).filter(x=>x.minutes).map(x=>x.category).slice(0,5);
  if(!categories.length)return `<p class="muted">Includes explanation, examples, practice, review, and assessment.</p>`;
  return `<div class="mix-summary">${categories.map(x=>pill(x)).join("")}</div>`;
}

function workloadStep(){
  return shell(`${steps(2)}<section class="v2-hero"><p>ACTIVITY PLANNER</p><h1>First, calculate the time this goal actually requires</h1><span>Your preferred completion window is not used yet.</span></section>
  <section class="v2-card centered"><div class="agent-orb">A</div><h2>Profile and Goal Scope Confirmed</h2><p>Expand each concept into explanations, examples, practice, code, review, quizzes, projects, and reflection.</p>
  <button class="v2-primary" onclick="generateWorkload()">Generate Full Workload</button></section>`);
}
async function generateWorkload(){await act(async()=>{state.estimate=await api(`/api/onboarding-drafts/${state.draftId}/workload-estimates`,{method:"POST",body:JSON.stringify({user_id:state.userId})})})}
function confirmedProfileStep(){
  return shell(`${steps(1,Math.min(4,currentOnboardingStep()))}<section class="v2-card"><p class="eyebrow">CONFIRMED FOR THIS PATH</p><h1>Learner Profile</h1><p>This snapshot was used to calculate the workload. Return to Goal & Sources to change the outcome, or continue to review the workload.</p>${profilePreview(state.draft.profile_snapshot||state.draft.profile_preview)}
  <div class="scope-actions"><button class="v2-secondary" onclick="goOnboardingStep(0)">Edit Goal & Sources</button><button class="v2-primary" onclick="goOnboardingStep(2)">Continue to Workload</button></div></section>`);
}
function workloadReviewStep(){
  return shell(`${steps(2,Math.min(4,currentOnboardingStep()))}<div class="v2-cols"><section class="v2-card"><p class="eyebrow">CONFIRMED WORKLOAD</p><h1>${approximateHours(state.estimate.total_required_minutes)}</h1><p>${esc(workloadSourceLine())}</p>${mixSummary()}</section>
  <section class="v2-card"><h2>Why this amount of time?</h2><p>Pathly estimates the learning effort at a coarse level before asking for your schedule. The estimate includes concept explanation, examples, practice, review, and a lightweight assessment, but avoids over-precise minute-by-minute claims.</p><div class="scope-actions"><button class="v2-secondary" onclick="goOnboardingStep(1)">Back to Learner Profile</button><button class="v2-primary" onclick="goOnboardingStep(3)">Continue to Capacity</button></div></section></div>`);
}
function mixChart(){
  return mixSummary();
}
function capacityStep(){
  const total=Math.max(1,Number(state.estimate?.total_required_minutes||1));
  const saved=state.capacityDraft||{};
  const daily=Math.min(1440,Math.max(1,Number(saved.daily||state.decision?.max_available_daily_minutes||60)));
  const days=Math.min(60,Math.max(1,Number(saved.days||state.decision?.requested_days||Math.ceil(total/60))));
  state.capacityDraft={days,daily};
  return shell(`${steps(3,Math.min(4,currentOnboardingStep()))}<div class="v2-cols"><section class="v2-card"><p class="eyebrow">FINAL WORKLOAD</p><h1>${approximateHours(state.estimate.total_required_minutes)}</h1>
  <p>${esc(workloadSourceLine())}</p>${mixChart()}
  <div class="explain"><b>Why this amount of time?</b><p>Pathly keeps this as a planning estimate, not an exact promise. The final daily schedule will distribute the work after you choose your target window and sustainable daily study time.</p></div></section>
  <section class="v2-card capacity-controls"><h2>Shape your learning schedule</h2><p class="muted">These two limits are linked to your estimated ${Math.round(total)} minutes of total learning. Move either slider to see the other value update.</p>
  <div class="capacity-slider"><div><b>Days to complete</b><strong id="days-value">${days} days</strong></div><input id="days" type="range" min="1" max="60" step="1" value="${days}" oninput="capacityDaysChanged(this.value)"><small>1 day · 60 days</small></div>
  <div class="capacity-slider"><div><b>Study time per day</b><strong id="daily-value">${daily} min/day</strong></div><input id="daily" type="range" min="1" max="1440" step="1" value="${daily}" oninput="capacityDailyChanged(this.value)"><small>1 minute · 1440 minutes (24 hours)</small></div>
  <div class="capacity-link-note"><b>${days} days × ${daily} min/day = ${days*daily} minutes of capacity</b><span>${days*daily>=total?"This covers the estimated workload.":`You are ${Math.ceil(total-days*daily)} minutes short; add days or daily time.`}</span></div>
  <button class="v2-primary" onclick="createDecision()">Check Feasibility</button></section></div>${state.capacityReview&&state.decision?.status==="insufficient"?capacityCorrectionPanel():""}`);
}
function capacityTotal(){return Math.max(1,Number(state.estimate?.total_required_minutes||1))}
function capacityDaysChanged(raw){
  const days=Math.min(60,Math.max(1,Math.round(Number(raw)||1)));
  const daily=Math.min(1440,Math.max(1,Math.ceil(capacityTotal()/days)));
  state.capacityDraft={days,daily};
  const d=$("#days"),m=$("#daily"); if(d)d.value=days; if(m)m.value=daily;
  const dv=$("#days-value"),mv=$("#daily-value"); if(dv)dv.textContent=`${days} days`; if(mv)mv.textContent=`${daily} min/day`;
  updateCapacityLinkNote(days,daily);
}
function capacityDailyChanged(raw){
  const daily=Math.min(1440,Math.max(1,Math.round(Number(raw)||1)));
  const days=Math.min(60,Math.max(1,Math.ceil(capacityTotal()/daily)));
  state.capacityDraft={days,daily};
  const d=$("#days"),m=$("#daily"); if(d)d.value=days; if(m)m.value=daily;
  const dv=$("#days-value"),mv=$("#daily-value"); if(dv)dv.textContent=`${days} days`; if(mv)mv.textContent=`${daily} min/day`;
  updateCapacityLinkNote(days,daily);
}
function updateCapacityLinkNote(days,daily){
  const note=document.querySelector(".capacity-link-note"); if(!note)return;
  const total=capacityTotal(),capacity=days*daily;
  note.innerHTML=`<b>${days} days × ${daily} min/day = ${capacity} minutes of capacity</b><span>${capacity>=total?"This covers the estimated workload.":`You are ${Math.ceil(total-capacity)} minutes short; add days or daily time.`}</span>`;
}
async function createDecision(){
  const daysInput=$("#days"),dailyInput=$("#daily");
  if(!daysInput||!dailyInput){state.error="The capacity form changed. Return to the workload step and try again.";render();return}
  const requestedDays=Number(daysInput.value),dailyMinutes=Number(dailyInput.value);
  if(!Number.isInteger(requestedDays)||requestedDays<1||requestedDays>60){state.error="Target days must be an integer from 1 to 60.";render();return}
  if(!Number.isFinite(dailyMinutes)||dailyMinutes<1||dailyMinutes>1440){state.error="Daily study time must be between 1 and 1440 minutes.";render();return}
  await act(async()=>{
    state.capacityDraft={days:requestedDays,daily:dailyMinutes};
    state.decision=await api("/api/feasibility-decisions",{method:"POST",body:JSON.stringify({user_id:state.userId,estimate_id:state.estimate.estimate_id,requested_days:requestedDays,max_available_daily_minutes:dailyMinutes})});
    state.pendingCapacityChoice=null;state.pendingStrategy=null;
    if(state.decision.status==="insufficient"){
      state.capacityReview=true;state.stepOverride=3;
    }else{
      state.decision=await api(`/api/feasibility-decisions/${state.decision.decision_id}`,{method:"PATCH",body:JSON.stringify({user_id:state.userId,selected_strategy:"proceed"})});
      state.capacityReview=false;state.stepOverride=null;
    }
  });
}
function capacityCorrectionPanel(){
  const d=state.decision;
  const extend=(d.options||[]).find(o=>o.strategy==="extend_days");
  const increase=(d.options||[]).find(o=>o.strategy==="increase_daily_time");
  const options=[
    extend&&{id:"extend_days",title:`Extend to ${extend.suggested_days} days`,reason:`Keep daily study at ${d.max_available_daily_minutes} minutes.`},
    increase&&{id:"increase_daily_time",title:`Increase to ${increase.required_daily_minutes} minutes/day`,reason:`Keep the ${d.requested_days}-day target.`},
  ].filter(Boolean);
  return `<section class="v2-card capacity-confirm"><p class="eyebrow">SECOND CONFIRMATION REQUIRED</p><h2>Your current capacity is ${Math.abs(d.capacity_gap_minutes)} minutes short</h2><p>Choose and confirm how the constraint should change before continuing to Create Path.</p>
  <div class="strategy-list" role="radiogroup" aria-label="Capacity correction">${options.map(o=>{const selected=state.pendingCapacityChoice===o.id;return `<button type="button" class="strategy-card ${selected?"selected":""}" role="radio" aria-checked="${selected}" onclick="selectCapacityAdjustment('${o.id}')"><i aria-hidden="true">&#10003;</i><b>${esc(o.title)}</b><span>${esc(o.reason)}</span></button>`}).join("")}</div>
  <div class="scope-actions"><button class="v2-secondary" onclick="state.capacityReview=false;state.pendingCapacityChoice=null;state.pendingStrategy=null;render()">Edit Inputs</button><button class="v2-primary" ${state.pendingCapacityChoice?"":"disabled"} onclick="confirmCapacityAdjustment()">Confirm Change and Continue</button></div></section>`;
}
function selectCapacityAdjustment(choice){state.pendingCapacityChoice=choice;render()}
async function confirmCapacityAdjustment(){
  const choice=state.pendingCapacityChoice;
  if(!choice){state.error="Choose a capacity adjustment before continuing.";render();return}
  const option=(state.decision.options||[]).find(o=>o.strategy===choice);
  const body={user_id:state.userId,selected_strategy:choice};
  if(choice==="extend_days")body.requested_days=option?.suggested_days;
  if(choice==="increase_daily_time")body.max_available_daily_minutes=option?.required_daily_minutes;
  await act(async()=>{
    state.decision=await api(`/api/feasibility-decisions/${state.decision.decision_id}`,{method:"PATCH",body:JSON.stringify(body)});
    if(state.decision.status==="insufficient")throw new Error("The selected change is still insufficient. Choose a larger adjustment.");
    state.capacityReview=false;state.pendingCapacityChoice=null;state.pendingStrategy=null;state.stepOverride=null;
    state.notice="Capacity change confirmed. Review the final path decision.";
  });
}
function decisionStep(){
  const d=state.decision; const bad=d.status==="insufficient";
  const scope=d.scope_change_draft;
  const pending=state.pendingStrategy;
  const readyToCreate=Boolean(d.selected_strategy)&&!pending&&!bad&&!["adjust_outcome","set_daily_capacity","save_draft"].includes(d.selected_strategy)&&(d.selected_strategy!=="narrow_scope"||scope?.status==="accepted");
  return shell(`${steps(4)}<section class="v2-card decision ${bad?"bad":"good"}"><div>${pill(d.status,bad?"red":"green")}<h1>${bad?"Current Capacity Is Insufficient":"This Goal Is Feasible"}</h1>
  <p>${esc(d.status_reason)}</p></div><div class="capacity-stats"><div><span>Total workload</span><b>${d.effective_total_minutes}m</b></div><div><span>Recommended daily</span><b>${d.recommended_daily_minutes}m</b></div><div><span>Capacity gap</span><b>${d.capacity_gap_minutes>0?"+":""}${d.capacity_gap_minutes}m</b></div></div></section>
  ${scope?.status==="pending"?scopeReview(scope):state.scopeMode?scopeBuilder():readyToCreate?finalPathConfirmation(d):`<section class="v2-card"><h2>Choose How to Proceed</h2><p>Choose once, review its effect, and confirm it. Pathly will not ask you to select the same timing change again.</p><div class="strategy-list" role="radiogroup" aria-label="Feasibility strategy">${(d.options||[]).map(o=>{const selected=(pending?.strategy||d.selected_strategy)===o.strategy;return `<button class="strategy-card ${selected?"selected":""}" role="radio" aria-checked="${selected}" onclick="chooseStrategy('${o.strategy}')"><i aria-hidden="true">&#10003;</i><b>${esc(strategyLabel(o.strategy))}</b><span>${esc(o.reason)}</span></button>`}).join("")}</div>
  ${pending?strategyConfirmation(pending):""}</section>`}`);
}
function finalPathConfirmation(d){
  const detail=d.selected_strategy==="proceed"?"Your current time window and daily study limit cover the goal. No additional strategy selection is required.":"Your confirmed capacity adjustment is already applied. No additional strategy selection is required.";
  return `<section class="v2-card final-path-confirm"><p class="eyebrow">READY TO CREATE</p><h2>Your timing decision is confirmed</h2><p>${esc(detail)}</p><div class="change-preview"><div><span>Completion window</span><b>${esc(d.requested_days)} days</b></div><div><span>Daily study limit</span><b>${esc(d.max_available_daily_minutes)} minutes/day</b></div></div><div class="scope-actions"><button class="v2-secondary" onclick="goOnboardingStep(3)">Edit Capacity</button><button class="v2-primary" onclick="confirmPath()">Confirm and Create Path</button></div></section>`;
}
function strategyLabel(strategy){
  const labels={paced_consolidation:"Paced consolidation",early_completion:"Early completion",proceed:"Keep current plan",extend_days:"Extend days",increase_daily_time:"Increase daily time",narrow_scope:"Narrow scope",adjust_outcome:"Edit goal"};
  return labels[strategy]||strategy;
}
function strategyOption(strategy){
  return (state.decision?.options||[]).find(o=>o.strategy===strategy)||{};
}
function strategyConfirmation(pending){
  const d=state.decision||{};
  const currentDays=Number(d.requested_days||d.effective_days||0);
  const currentDailyCap=Number(d.max_available_daily_minutes||0);
  const total=Number(d.effective_total_minutes||0);
  const recommended=Number(d.recommended_daily_minutes||0);
  const available=Number(d.available_capacity_minutes||0)||currentDays*currentDailyCap;
  const surplus=Number(pending.optional_consolidation_budget_minutes ?? pending.surplus_minutes ?? Math.max(0,Number(d.capacity_gap_minutes||0)));
  let title=`Confirm ${strategyLabel(pending.strategy)}`;
  let detail="This selection will be saved to the feasibility decision.";
  let before=`Required ${total}m over ${currentDays} day(s): about ${recommended}m/day; capacity ${available}m total (${currentDailyCap}m/day cap)`;
  let after=before;
  if(pending.strategy==="extend_days"){
    const nextDays=Number(pending.suggested_days||pending.days)>currentDays?Math.min(60,Number(pending.suggested_days||pending.days)):Math.min(60,Math.max(currentDays+1,Number(d.minimum_recommended_days||1)));
    const nextRecommended=Math.ceil(total/nextDays);
    title=`Confirm extension to ${nextDays} days`;
    detail="The required work stays unchanged; only the completion window changes.";
    after=`Required ${total}m over ${nextDays} day(s): about ${nextRecommended}m/day; daily cap stays ${currentDailyCap}m`;
  }else if(pending.strategy==="increase_daily_time"){
    const nextDaily=Number(pending.required_daily_minutes||pending.daily)||Number(d.recommended_daily_minutes||currentDailyCap);
    title=`Confirm ${nextDaily} minutes/day`;
    detail="The target date stays unchanged; only the sustainable daily limit changes.";
    after=`Required ${total}m over ${currentDays} day(s): about ${recommended}m/day; new cap ${nextDaily}m/day`;
  }else if(pending.strategy==="paced_consolidation"){
    title="Confirm paced consolidation";
    detail="The core goal workload does not increase. The scheduler may use surplus capacity for optional review, practice, and reinforcement across the full horizon.";
    after=`Keep ${currentDays} day(s). Core average stays ${recommended}m/day; use up to ${surplus}m surplus for optional consolidation within the ${currentDailyCap}m/day cap`;
  }else if(pending.strategy==="early_completion"){
    const nextDays=Number(pending.suggested_days||d.minimum_recommended_days||currentDays);
    const nextDaily=Math.ceil(total/Math.max(1,nextDays));
    const freed=Math.max(0,currentDays-nextDays);
    title=`Confirm early completion in ${nextDays} day(s)`;
    detail="The required work stays unchanged; Pathly schedules it into the shortest honest horizon that fits your daily cap.";
    after=`Finish in ${nextDays} day(s) at about ${nextDaily}m/day, freeing ${freed} day(s) from the requested horizon`;
  }else if(pending.strategy==="proceed"){
    title="Confirm current timing";
    detail="No timing value changes. Surplus capacity remains unused instead of becoming optional consolidation work.";
    after=`Keep ${currentDays} day(s). Core average ${recommended}m/day; leave ${surplus}m surplus unused`;
  }else if(pending.strategy==="adjust_outcome"){
    detail="You will return to Goal & Sources. Workload and capacity change only after the revised goal is saved.";
    after="Goal editor; current plan retained until save";
  }else if(pending.strategy==="narrow_scope"){
    detail="You will create a separate scope proposal. The current goal remains unchanged until that comparison is accepted.";
    after="Scope proposal; current goal retained";
  }
  return `<section class="strategy-confirmation" aria-live="polite"><p class="eyebrow">CONFIRM BEFORE APPLYING</p><h3>${esc(title)}</h3><p>${esc(detail)}</p><div class="change-preview"><div><span>Current allocation</span><b>${esc(before)}</b></div><div><span>After confirmation</span><b>${esc(after)}</b></div></div><div class="scope-actions"><button class="v2-secondary" onclick="state.pendingStrategy=null;render()">Cancel</button><button class="v2-primary" onclick="confirmStrategyChoice()">Confirm This Choice</button></div></section>`;
}
function scopeBuilder(){
  const concepts=state.estimate?.concept_path||[];
  return `<section class="v2-card"><p class="eyebrow">INDEPENDENT SCOPE PROPOSAL</p><h2>Select Content to Remove from This Goal</h2>
  <p>This is only a proposal. Pathly checks prerequisites and required readings; your original goal stays unchanged until you accept.</p>
  <div class="doc-list">${concepts.map((item,index)=>`<label class="doc-row"><input type="checkbox" data-scope-index="${index}">
  <span><b>${esc(item.label||item.name||item.concept_id)}</b><small>${item.is_target?"Target concept":"Prerequisite"}  /  ${esc(item.source||"canonical")}</small></span></label>`).join("")}</div>
  <div class="scope-actions"><button class="v2-secondary" onclick="state.scopeMode=false;render()">Cancel</button><button class="v2-primary" onclick="proposeScope()">Generate Comparison</button></div></section>`;
}
function scopeReview(scope){
  return `<section class="v2-card"><p class="eyebrow">SCOPE COMPARISON</p><h2>Scope Change Comparison</h2>
  <div class="capacity-stats"><div><span>Original workload</span><b>${scope.original_total_minutes}m</b></div><div><span>Proposed</span><b>${scope.proposed_total_minutes}m</b></div><div><span>Reduction</span><b>-${scope.removed_minutes}m</b></div></div>
  <p><b>Removed: </b>${(scope.removed_concept_ids||[]).map(esc).join(", ")}</p><p><b>Retained: </b>${(scope.remaining_concept_ids||[]).map(esc).join(", ")}</p>
  <p>${scope.retained_required_reading?"Required readings are retained":"Required readings need another review"}</p>
  <div class="scope-actions"><button class="v2-secondary" onclick="decideScope('reject')">Reject and Restore Original Goal</button><button class="v2-primary" onclick="decideScope('accept')">Accept Partial Goal</button></div></section>`;
}
async function proposeScope(){
  const concepts=state.estimate?.concept_path||[];
  const removed=concepts.filter((_,index)=>document.querySelector(`[data-scope-index="${index}"]`)?.checked).map(item=>item.concept_id);
  if(!removed.length){state.error="Select at least one concept to remove";render();return}
  await act(async()=>{state.decision=await api(`/api/feasibility-decisions/${state.decision.decision_id}`,{method:"PATCH",body:JSON.stringify({
    user_id:state.userId,selected_strategy:"narrow_scope",scope_remove_concept_ids:removed
  })});state.scopeMode=false});
}
async function decideScope(action){
  await act(async()=>{state.decision=await api(`/api/feasibility-decisions/${state.decision.decision_id}`,{method:"PATCH",body:JSON.stringify({
    user_id:state.userId,scope_change_decision:action
  })});state.scopeMode=false});
}function chooseStrategy(strategy){
  const option=strategyOption(strategy);
  state.pendingStrategy={...option,strategy};
  state.error=null;
  render();
}
async function confirmStrategyChoice(){
  const pending=state.pendingStrategy;
  if(!pending){state.error="Choose a strategy before confirming.";render();return}
  const {strategy}=pending;
  const body={user_id:state.userId,selected_strategy:strategy};
  if(strategy==="extend_days"){
    const current=Number(state.decision?.requested_days||0);
    const fallback=Math.min(60,Math.max(current+1,Number(state.decision?.minimum_recommended_days||1)));
    const nextDays=Number(pending.suggested_days||pending.days||0);
    body.requested_days=nextDays>current?nextDays:fallback;
  }
  if(strategy==="increase_daily_time")body.max_available_daily_minutes=Number(pending.required_daily_minutes||pending.daily||state.decision?.recommended_daily_minutes||0);
  if(strategy==="narrow_scope"){state.pendingStrategy=null;state.error=null;state.scopeMode=true;render();return}
  await act(async()=>{
    state.decision=await api(`/api/feasibility-decisions/${state.decision.decision_id}`,{method:"PATCH",body:JSON.stringify(body)});
    state.pendingStrategy=null;
    if(strategy==="adjust_outcome"){state.notice="Edit the outcome, then recalculate workload.";state.editingGoal=true;state.interpretation=null;}
  });
}async function confirmPath(){await act(async()=>{
  const result=await api(`/api/feasibility-decisions/${state.decision.decision_id}/confirm`,{method:"POST",body:JSON.stringify({user_id:state.userId})});
  state.decision=result.decision;
  let scheduleError=null;
  try{state.currentPlan=await api(`/api/plans/${result.plan.plan_id}/schedule`,{method:"POST",body:JSON.stringify({user_id:state.userId})})}
  catch(error){scheduleError=error;state.currentPlan=result.plan}
  await loadPlans();
  if(scheduleError)state.notice="Your path was created. The Activity Timeline could not be generated yet; reopen this path to retry scheduling.";
  state.view="dashboard";
})}
function completionStep(){return shell(`<section class="v2-card centered"><h1>Path Confirmed</h1><button class="v2-primary" onclick="go('dashboard')">View Learning Paths</button></section>`)}
function requestDeletePath(planId){const record=state.plans.find(x=>x.plan_id===planId);if(!record)return;state.deletePathCandidate=record;state.deletePathError=null;confirmDeletePath()}
function cancelDeletePath(){state.deletePathCandidate=null;state.deletePathError=null;render()}
async function confirmDeletePath(){const record=state.deletePathCandidate;if(!record)return;await act(async()=>{try{await api(`/api/plans/${record.path_id}`,{method:"DELETE",body:JSON.stringify({user_id:state.userId})});state.deletePathCandidate=null;state.deletePathError=null;await loadPlans();if(state.currentPlan?.path_id===record.path_id){const next=state.plans[0]||null;if(next){state.currentPlan=next;state.selectedPlanId=next.plan_id;state.selectedDay=null;state.pathProgress=null;await ensurePathProgress(next)}else{state.currentPlan=null;state.selectedPlanId=null;state.view="workspace"}}render();showNotice("Learning path deleted");}catch(error){state.deletePathError=error.message||"Delete failed";render()}})}

function dashboard(){
  if(!state.plans.length)return shell(`<section class="v2-empty"><h1>No Learning Paths Yet</h1><p>Your path will appear here after onboarding.</p><button class="v2-primary" onclick="newPath()">Create Your First Path</button></section>`);
  const r=state.currentPlan||state.plans[0],p=r.plan||{},days=p.days||[],concepts=p.concept_path||[],reviewFallback=state.draft?.knowledge_map_review||{},mapSnapshot=p.knowledge_map||((reviewFallback.status==="confirmed")?{reviewed_concepts:reviewFallback.reviewed_concepts||[],edges:reviewFallback.edges||[],excluded_concept_ids:reviewFallback.excluded_concept_ids||[]}:{}),mapConcepts=mapSnapshot.reviewed_concepts||concepts;
  return shell(`<div class="page-head"><div><p class="eyebrow">YOUR LEARNING PATHS</p><h1>From Knowledge Relationships to Daily Actions</h1></div><div class="head-actions"><button class="v2-primary" onclick="go('today')">Continue Learning</button><button class="v2-secondary" onclick="newPath()">+ New Path</button></div></div>
  <div class="path-tabs">${state.plans.map(x=>`<div class="path-tab-wrap"><button type="button" class="path-tab ${x.plan_id===r.plan_id?"active":""}" onclick="selectPlan('${x.plan_id}')"><small>v${x.version}</small><b>${esc(x.goal_text)}</b></button><button type="button" class="path-delete" data-delete-path="${esc(x.plan_id)}" aria-label="Delete learning path" title="Delete learning path">馃棏</button></div>`).join("")}</div>
  <section class="v2-hero route"><div>${pill(r.mode,r.mode==="live"?"green":"")}<h1>${esc(r.goal_text)}</h1><p>${concepts.length} concepts  /  ${days.length} active learning days</p></div>
  </section>
  ${conceptMap(mapConcepts,{edges:mapSnapshot.edges||[],excluded:mapSnapshot.excluded_concept_ids||[],exactSnapshot:Boolean(mapSnapshot.reviewed_concepts)})}
  ${timeline(days,p.unscheduled_activities||[],concepts,state.pathProgress)}
  <section class="v2-card reasoning"><h2>Planning Rationale</h2><p>${esc(readablePlanText(p.reasoning_trace?.workload||"Generated from your confirmed goal, learner profile, and concept relationships.",concepts))}</p><p>${esc(readablePlanText(p.reasoning_trace?.capacity||"",concepts))}</p></section>`);
}
async function selectPlan(id){state.currentPlan=state.plans.find(x=>x.plan_id===id);state.selectedPlanId=state.currentPlan?.plan_id||null;state.pathProgress=null;state.selectedDay=null;persist();state.selectedConceptId=null;render();await act(()=>ensurePathProgress(state.currentPlan))}
function conceptMap(nodes,options={}){
  const graph=personalKnowledgeGraph(nodes||[],options);
  const selected=graph.nodes.find(n=>n.node_id===state.selectedConceptId)||graph.nodes.find(n=>n.role==="target")||graph.nodes[0];
  const edgeIndex=new Map();graph.edges.forEach(edge=>{[edge.source,edge.target].forEach(id=>{const related=edgeIndex.get(id)||[];related.push(edge);edgeIndex.set(id,related)})});
  const title=options.review?"Review the personalized scope":"Goal-relevant concept subgraph";
  const subtitle=options.review?"Choose concepts to include in your path. Click a concept to exclude it, then click it again to restore it. The primary target stays fixed.":"Only concepts selected for this learning path are shown. Public KG and private material concepts stay visually separate.";
  const edgeMarkup=graph.edges.map(edge=>`<g class="pkm-edge ${edge.type} ${edge.enabled===false?"disabled":""}"><title>${esc(edge.enabled===false?"Connection omitted with its excluded concept":"Concept relationship")}</title><path d="${edge.d}" role="presentation"></path></g>`).join("");
  return `<section class="v2-card pkm-card"><div class="section-head"><div><p class="eyebrow">PERSONAL KNOWLEDGE MAP</p><h2>${title}</h2><div class="pkm-instruction"><b>${options.review?"Choose your learning scope":"Explore your learning scope"}</b><span>${subtitle}</span></div></div><div class="pkm-legend"><span><i class="public"></i>Public KG</span><span><i class="private"></i>Private material</span><span><i class="prerequisite"></i>Prerequisite</span><span><i class="core"></i>Core learning target</span><span><i class="supporting"></i>Supporting concept</span><span><i class="target"></i>Primary target</span><span><i class="hint"></i>Sequence hint</span>${options.review?'<span><i class="excluded"></i>Excluded connection</span>':''}</div></div><div class="pkm-layout"><div class="map-v2 pkm-map" style="--map-w:${graph.width}px;--map-h:${graph.height}px"><svg class="pkm-edges" viewBox="0 0 ${graph.width} ${graph.height}" aria-label="${options.review?"Editable goal-relevant knowledge map":"Goal-relevant knowledge map"}">${edgeMarkup}</svg>${graph.nodes.map((node,index)=>`<button type="button" class="concept-node graph-node ${node.role} ${node.source_type} ${node.excluded?"excluded":""}" aria-pressed="${node.node_id===selected?.node_id}" aria-label="${esc(options.review&&!node.is_target?(node.excluded?`Restore ${conceptDisplayName(node.raw,index)} to this path`:`Exclude ${conceptDisplayName(node.raw,index)} from this path`):`View ${conceptDisplayName(node.raw,index)}`)}" style="left:${node.x}px;top:${node.y}px;width:${node.width}px;min-height:${node.height}px" onclick="${options.review?`toggleReviewNode('${esc(node.node_id)}')`:`selectConceptNode('${esc(node.node_id)}')`}"><small>${esc(node.excluded?"Excluded from path":node.role_label)}</small><b>${esc(conceptDisplayName(node.raw,index))}</b></button>`).join("")}</div><aside class="pkm-detail">${selected?conceptDetail(selected,edgeIndex.get(selected.node_id)||[],graph.nodes,options):""}</aside></div></section>`;
}
function dedupeMapEdges(edges){const seen=new Set();return edges.filter(edge=>{const key=`${edge.type}:${mapEdgeKey(edge.source,edge.target)}`;if(seen.has(key))return false;seen.add(key);return true})}
function reviewSemanticEdges(nodes){
  const byName=new Map(nodes.map(node=>[mapName(conceptDisplayName(node.raw,node.index)),node]));
  const edges=[];
  const add=(sourceName,targetName,type="sequence_hint")=>{const source=byName.get(mapName(sourceName)),target=byName.get(mapName(targetName));if(source&&target&&source.node_id!==target.node_id)edges.push({source:source.node_id,target:target.node_id,type})};
  nodes.forEach(node=>node.prerequisite_ids.forEach(id=>{if(nodes.some(other=>other.node_id===id))edges.push({source:id,target:node.node_id,type:"prerequisite"})}));
  [["Artificial Intelligence","Machine Learning","prerequisite"],["Data in AI","Machine Learning","sequence_hint"],["Linear Algebra","Gradient Descent","prerequisite"],["Gradient Descent","Neural Networks","prerequisite"],["Backpropagation","Neural Networks","prerequisite"],["Neural Networks","Deep Learning","prerequisite"],["Deep Learning","Machine Learning","sequence_hint"],["Regression","Supervised Learning","prerequisite"],["Supervised Learning","Classification","prerequisite"],["Classification","Machine Learning","sequence_hint"],["Unsupervised Learning","Machine Learning","sequence_hint"],["Reinforcement Learning","Machine Learning","sequence_hint"],["Embeddings","Vector Databases","prerequisite"],["Vector Databases","Information Retrieval","prerequisite"],["Information Retrieval","Large Language Models","sequence_hint"]].forEach(([source,target,type])=>add(source,target,type));
  const primary=nodes.find(node=>node.role==="target");
  if(primary){nodes.filter(node=>node.node_id!==primary.node_id&&!edges.some(edge=>edge.source===node.node_id)).forEach(node=>edges.push({source:node.node_id,target:primary.node_id,type:"sequence_hint"}))}
  return dedupeMapEdges(edges);
}
function pathReachableToTarget(nodes,edges,primaryId){
  const reverse=new Map();edges.filter(edge=>edge.enabled!==false).forEach(edge=>{const list=reverse.get(edge.target)||[];list.push(edge.source);reverse.set(edge.target,list)});
  const reachable=new Set([primaryId]),queue=[primaryId];while(queue.length){const id=queue.shift();(reverse.get(id)||[]).forEach(source=>{if(!reachable.has(source)){reachable.add(source);queue.push(source)}})}return reachable;
}
function bridgeAroundExcludedNodes(baseEdges,excludedIds){
  const excluded=new Set([...excludedIds].map(String)),bridges=[];
  excluded.forEach(nodeId=>{
    const predecessors=baseEdges.filter(edge=>edge.target===nodeId&&!excluded.has(edge.source));
    const successors=baseEdges.filter(edge=>edge.source===nodeId&&!excluded.has(edge.target));
    predecessors.forEach(previous=>successors.forEach(next=>{if(previous.source!==next.target)bridges.push({source:previous.source,target:next.target,type:"student_bridge",generated:true})}));
  });
  return dedupeMapEdges(bridges);
}
// Retained for drafts created with the earlier edge-click interaction.
function bridgeAroundExcludedEdges(baseEdges,disabled){
  return bridgeAroundExcludedNodes(baseEdges,new Set(disabled.map(edge=>edge.source)));
}
function personalKnowledgeGraph(nodes,options={}){
  const rawNodes=(nodes||[]).map((node,index)=>({node,index,id:String(node.concept_id||`concept-${index}`)}));
  const rawById=new Map(rawNodes.map(item=>[item.id,item.node]));
  const declaredTargets=new Set(rawNodes.filter(item=>item.node.is_target).map(item=>item.id));
  const requiredIds=new Set(),frontier=[...declaredTargets];while(frontier.length){const current=rawById.get(frontier.pop())||{};(current.prerequisite_ids||[]).map(String).forEach(id=>{if(rawById.has(id)&&!requiredIds.has(id)){requiredIds.add(id);frontier.push(id)}})}
  const clean=rawNodes.map(({node,index,id})=>{const role=node.path_role||(node.is_target?"target":(requiredIds.has(id)?"prerequisite":"supporting"));const labels={target:"Primary target",learning_target:"Core learning target",prerequisite:"Prerequisite",supporting:"Supporting concept"};return {node_id:id,raw:node,index,source_type:node.source_type||(id.startsWith("private:")?"private":"public"),role,role_label:labels[role]||"Supporting concept",prerequisite_ids:(node.prerequisite_ids||[]).map(String).filter(Boolean)}});
  const rank={prerequisite:0,supporting:1,learning_target:2,target:3};clean.sort((a,b)=>(rank[a.role]-rank[b.role])||(a.index-b.index));clean.forEach((node,index)=>node.index=index);
  const ids=new Set(clean.map(node=>node.node_id)),primary=clean.find(node=>node.role==="target")||clean[0];
  const exactSnapshot=Boolean(options.exactSnapshot);
  const defaultEdges=exactSnapshot?[]:(options.review?reviewSemanticEdges(clean):dedupeMapEdges(clean.flatMap(node=>node.prerequisite_ids.filter(id=>ids.has(id)).map(id=>({source:id,target:node.node_id,type:"prerequisite"})))));
  const overrides=(options.edges||[]).filter(edge=>ids.has(String(edge.source))&&ids.has(String(edge.target))&&String(edge.source)!==String(edge.target)).map(edge=>({source:String(edge.source),target:String(edge.target),type:edge.type||"student_bridge"}));
  const legacyDisabled=overrides.filter(edge=>edge.type==="excluded_link"),disabledKeys=new Set(legacyDisabled.map(edge=>mapEdgeKey(edge.source,edge.target)));
  const explicitExcluded=new Set((options.excluded||[]).map(String));
  const explicitBridges=overrides.filter(edge=>["student_bridge","student_link"].includes(edge.type)).map(edge=>({...edge,type:"student_bridge"}));
  const activeBase=defaultEdges.filter(edge=>!disabledKeys.has(mapEdgeKey(edge.source,edge.target))&&!explicitExcluded.has(edge.source)&&!explicitExcluded.has(edge.target));
  const active=exactSnapshot?dedupeMapEdges(overrides.filter(edge=>edge.type!=="excluded_link"&&!explicitExcluded.has(edge.source)&&!explicitExcluded.has(edge.target))):dedupeMapEdges([...activeBase,...bridgeAroundExcludedNodes(defaultEdges,explicitExcluded),...bridgeAroundExcludedEdges(defaultEdges,legacyDisabled),...explicitBridges]);
  const reachable=primary?pathReachableToTarget(clean,active,primary.node_id):new Set();
  const excluded=exactSnapshot?explicitExcluded:new Set([...explicitExcluded,...clean.filter(node=>node.node_id!==primary?.node_id&&!reachable.has(node.node_id)).map(node=>node.node_id)]);
  clean.forEach(node=>{node.excluded=excluded.has(node.node_id);node.is_target=node.node_id===primary?.node_id});
  const renderEdges=dedupeMapEdges(active.filter(edge=>!excluded.has(edge.source)&&!excluded.has(edge.target)));
  const pad=34,nodeW=210,colGap=96,rowGap=24,maxRows=4;clean.forEach(node=>{const title=conceptDisplayName(node.raw,node.index);const lines=Math.max(1,Math.ceil(title.length/19));node.width=nodeW;node.height=Math.max(124,84+lines*25)});
  const stages=["prerequisite","supporting","learning_target","target"].map(role=>clean.filter(node=>node.role===role)).filter(stage=>stage.length);let nextX=pad;const columns=[];stages.forEach(stage=>{const count=Math.ceil(stage.length/maxRows),stageColumns=Array.from({length:count},()=>[]);stage.forEach((node,index)=>stageColumns[Math.floor(index/maxRows)].push(node));stageColumns.forEach((column,index)=>{column.forEach(node=>node.x=nextX+index*(nodeW+colGap));columns.push(column)});nextX+=count*(nodeW+colGap)+34});
  const columnHeights=columns.map(column=>column.reduce((sum,node)=>sum+node.height,0)+Math.max(0,column.length-1)*rowGap),contentHeight=Math.max(300,...columnHeights);columns.forEach((column,columnIndex)=>{let y=pad+(contentHeight-columnHeights[columnIndex])/2;column.forEach(node=>{node.y=Math.round(y);y+=node.height+rowGap})});
  const width=Math.max(620,nextX-colGap+pad),height=Math.max(360,contentHeight+pad*2),byId=new Map(clean.map(node=>[node.node_id,node]));
  const corridorCounts=new Map();renderEdges.forEach(edge=>{const source=byId.get(edge.source),target=byId.get(edge.target);if(!source||!target)return;const key=`${source.x+source.width}:${target.x}`;corridorCounts.set(key,(corridorCounts.get(key)||0)+1)});const corridorSeen=new Map();
  const shapedEdges=renderEdges.map(edge=>{const source=byId.get(edge.source),target=byId.get(edge.target);if(!source||!target)return null;const x1=source.x+source.width,y1=source.y+source.height/2,x2=target.x,y2=target.y+target.height/2,key=`${x1}:${x2}`,count=corridorCounts.get(key)||1,seen=corridorSeen.get(key)||0;corridorSeen.set(key,seen+1);const mid=Math.round((x1+x2)/2+(seen-(count-1)/2)*14);return {...edge,d:`M ${x1} ${y1} H ${mid} V ${y2} H ${x2}`}}).filter(Boolean);
  return {nodes:clean,edges:shapedEdges,width,height,excludedNodeIds:[...excluded]};
}function edgeLabel(type){return type==="prerequisite"?"prerequisite":type==="student_link"?"student link":"sequence hint"}
function rememberMapViewport(){
  const map=document.querySelector(".pkm-map");
  if(map)state.mapViewport={left:map.scrollLeft,top:map.scrollTop};
}
function restoreMapViewport(){
  const viewport=state.mapViewport;if(!viewport)return;
  requestAnimationFrame(()=>{
    const map=document.querySelector(".pkm-map");
    if(map){map.scrollLeft=viewport.left;map.scrollTop=viewport.top;}
    state.mapViewport=null;
  });
}
function selectConceptNode(id){rememberMapViewport();state.selectedConceptId=id;render()}
function conceptDetail(node,edges,nodes,options={}){
  const related=edges.map(e=>{const other=nodes.find(n=>n.node_id===(e.source===node.node_id?e.target:e.source));return `${edgeLabel(e.type)}: ${other?conceptDisplayName(other.raw,other.index):"related concept"}`});
  const raw=node.raw||{};
  const why=node.role==="target"?"This concept represents the outcome this learning path is designed to reach.":node.role==="prerequisite"?"Included because it provides a foundation for concepts later in this learning path.":"Included because it supports the goal and helps connect the surrounding concepts.";
  return `<h3>${esc(conceptDisplayName(raw,node.index))}</h3>${pill(node.source_type==="private"?"private material":"public KG",node.source_type==="private"?"":"green")} ${pill(node.role_label,node.role==="target"?"green":"")}<dl><div><dt>Source</dt><dd>${esc(node.source_type==="private"?"Selected private materials":"Public KG / canonical plan")}</dd></div><div><dt>Why included</dt><dd>${esc(why)}</dd></div></dl>${related.length?`<h4>Relationships</h4><ul>${related.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:`<p class="muted">No explicit relationship metadata is available for this node yet.</p>`}${options.editable?reviewEdgeEditor(node,nodes):""}<p class="pkm-note">${options.review?"Confirm this scope to continue. Your connection edits stay private to this draft and do not change the public KG.":"Read-only map. Student editing starts in the next PKM stage."}</p>`;
}

function reviewEdgeEditor(node,nodes){
  const source=state.edgeEditSource;
  const sourceNode=nodes.find(n=>n.node_id===source);
  const edges=reviewMapEdges();
  const removable=edges.map((e,index)=>({e,index})).filter(item=>item.e.source===node.node_id||item.e.target===node.node_id);
  const others=nodes.filter(n=>n.node_id!==node.node_id).slice(0,8);
  return `<div class="pkm-editor"><h4>Edit connections</h4><p>${source?`Connection source: ${esc(sourceNode?conceptDisplayName(sourceNode.raw,sourceNode.index):source)}`:"Select this node as a connection source, then choose another node to connect it to."}</p><button class="v2-secondary" onclick="setReviewEdgeSource('${esc(node.node_id)}')">Use this as source</button>${source&&source!==node.node_id?`<button class="v2-primary" onclick="connectReviewEdge('${esc(source)}','${esc(node.node_id)}')">Connect source to this node</button>`:""}<div class="edge-targets">${source===node.node_id?others.map(other=>`<button class="v2-secondary" onclick="connectReviewEdge('${esc(node.node_id)}','${esc(other.node_id)}')">Connect to ${esc(conceptDisplayName(other.raw,other.index))}</button>`).join(""):""}</div>${removable.length?`<div class="edge-removal"><h4>User-edited links</h4>${removable.map(item=>{const other=nodes.find(n=>n.node_id===(item.e.source===node.node_id?item.e.target:item.e.source));return `<button class="v2-secondary" onclick="removeReviewEdge(${item.index})">Remove ${esc(other?conceptDisplayName(other.raw,other.index):"link")}</button>`}).join("")}</div>`:""}</div>`;
}

function conceptDisplayName(node,index=0){
  const candidates=[node.display_name,node.requested_term,node.label,node.name,node.title];
  const readable=candidates.find(value=>value&&!String(value).startsWith("private:"));
  if(readable)return readable;
  if(String(node.concept_id||"").startsWith("private:"))return `Private concept ${index+1}`;
  return node.concept_id||`Concept ${index+1}`;
}
function readablePlanText(value,nodes=[]){
  let result=String(value||"");
  nodes.forEach((node,index)=>{
    const id=String(node.concept_id||"");
    if(id.startsWith("private:"))result=result.split(id).join(conceptDisplayName(node,index));
  });
  return result.replace(/private:[a-zA-Z0-9_-]+/g,"Private concept");
}
function timeline(days,unscheduled,nodes=[],progress=null){
  const states=new Map((progress?.days||[]).map(item=>[Number(item.day),item]));
  return `<section class="v2-card"><div class="timeline-v2">${days.map(d=>{const dayState=states.get(Number(d.day))||{status:Number(d.day)===1?"unlocked":"locked",unlocked:Number(d.day)===1};return `<article class="timeline-day ${dayState.status}"><div class="day-no">DAY ${d.day}<b>${d.total_minutes}m</b>${pill(dayState.status,dayState.status==="completed"?"green":"")}${dayState.scheduled_date?`<small>${esc(dayState.scheduled_date)}</small>`:""}${dayState.content_progress?`<small>${Math.round(Number(dayState.content_progress)*100)}% session complete</small>`:""}</div><div>${d.activities.map(a=>`<div class="activity ${a.optional?"optional":""}"><span>${esc(a.activity_type)}</span><b>${esc(readablePlanText(a.title||a.activity_id,nodes))}</b><small>${a.estimated_minutes}m  /  ${esc(readablePlanText(a.reason||"",nodes))}</small></div>`).join("")}</div><div class="day-entry">${dayState.unlocked?`<button class="v2-primary" onclick="openLearningDay(${d.day})">${dayState.completed?"Review Day":"Enter Day"}</button>`:`<button class="v2-secondary" disabled>Complete Day ${Number(d.day)-1} to unlock</button>`}</div></article>`}).join("")}</div>
  ${unscheduled.length?`<div class="v2-error"><b>Not Yet Scheduled</b><span>${unscheduled.length} activities are preserved. Adjust capacity or the learning window to schedule them.</span></div>`:""}</section>`;
}
async function ensurePathProgress(plan=state.currentPlan){
  if(!plan)return null;
  try{
    state.pathProgress=await api(`/api/paths/${encodeURIComponent(plan.path_id)}/progress?user_id=${encodeURIComponent(state.userId)}`);
  }catch(_error){
    const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone||"UTC";
    const startDate=new Date().toLocaleDateString("en-CA");
    await api(`/api/plans/${encodeURIComponent(plan.plan_id)}/activate`,{method:"POST",body:JSON.stringify({user_id:state.userId,start_date:startDate,timezone})});
    state.pathProgress=await api(`/api/paths/${encodeURIComponent(plan.path_id)}/progress?user_id=${encodeURIComponent(state.userId)}`);
  }
  return state.pathProgress;
}
async function openLearningDay(day){
  const info=(state.pathProgress?.days||[]).find(item=>Number(item.day)===Number(day));
  if(info&&!info.unlocked){state.error=`Complete Day ${Number(day)-1} to unlock this day.`;render();return}
  clearV4Poll();state.selectedDay=Number(day);state.dailyStage="lecture-v4";state.quiz=null;state.quizResult=null;state.chatMessages=[];state.annotatedSession=null;state.annotatedError=null;state.lectureV4=null;state.lectureV4Error=null;state.v4CurrentSectionId=null;state.v4ScrollPosition=0;state.activeReadingId=null;state.sourceContexts={};state.sourceContextOpen={};state.readingResponses={};state.exerciseResponses={};state.exerciseResults={};state.view="today";persist();render();await act(async()=>{await loadV4RouteContext(Number(day));syncDailyViewUrl();await loadLectureV4();});
}
async function loadV4RouteContext(dayOverride=null){
  if(!state.plans.length)await loadPlans();
  if(!state.currentPlan)state.currentPlan=((requestedPlanId||state.selectedPlanId)?state.plans.find(plan=>plan.plan_id===(requestedPlanId||state.selectedPlanId)):null)||state.plans[0]||null;
  const plan=state.currentPlan;
  if(!plan)throw new Error("No learning path is available for Source-Grounded Lecture View v4.");
  try{state.today=await api(`/api/paths/${encodeURIComponent(plan.path_id)}/today?user_id=${encodeURIComponent(state.userId)}`)}
  catch(_error){
    const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone||"UTC";
    const startDate=new Date().toLocaleDateString("en-CA");
    await api(`/api/plans/${encodeURIComponent(plan.plan_id)}/activate`,{method:"POST",body:JSON.stringify({user_id:state.userId,start_date:startDate,timezone})});
    state.today=await api(`/api/paths/${encodeURIComponent(plan.path_id)}/today?user_id=${encodeURIComponent(state.userId)}`);
  }
  state.pathProgress=state.today.progress||await ensurePathProgress(plan);
  const requested=Number(dayOverride||state.pathProgress?.next_day?.day||state.today.current?.day||1);
  const access=(state.pathProgress?.days||[]).find(item=>Number(item.day)===requested);
  const selected=((!access||access.unlocked)&&state.today.day_dates.find(item=>Number(item.day)===requested))||state.today.current;
  if(!selected)throw new Error("The requested learning day is not available for Source-Grounded Lecture View v4.");
  state.today.current=selected;
  state.today.is_overdue=selected.scheduled_date<state.today.today;
  state.selectedDay=Number(selected.day);
  state.selectedPlanId=plan.plan_id;
  const started=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${selected.day}/start`,{method:"POST",body:JSON.stringify({user_id:state.userId})});
  state.pathProgress=started.path||state.pathProgress;
  state.dailyContent={scheduled_minutes:selected.plan_day?.total_minutes||0,topic_labels:selected.plan_day?.focus_topics||[],session_overview:{title:`Day ${selected.day}: ${(selected.plan_day?.focus_topics||[]).join(", ")||plan.goal_text}`},session_progress:{completed_blocks:0,total_blocks:0}};
  persist();
  return state.today;
}async function loadTodayData(dayOverride=null){
  if(!state.plans.length)await loadPlans();
  if(!state.currentPlan)state.currentPlan=state.plans[0]||null;
  const plan=state.currentPlan;
  if(!plan){state.today=null;state.dailyContent=null;return}
  try{
    state.today=await api(`/api/paths/${encodeURIComponent(plan.path_id)}/today?user_id=${encodeURIComponent(state.userId)}`);
  }catch(_error){
    const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone||"UTC";
    const startDate=new Date().toLocaleDateString("en-CA");
    await api(`/api/plans/${encodeURIComponent(plan.plan_id)}/activate`,{method:"POST",body:JSON.stringify({user_id:state.userId,start_date:startDate,timezone})});
    state.today=await api(`/api/paths/${encodeURIComponent(plan.path_id)}/today?user_id=${encodeURIComponent(state.userId)}`);
  }
  state.pathProgress=state.today.progress||await ensurePathProgress(plan);
  const requested=Number(dayOverride||state.selectedDay||state.pathProgress?.next_day?.day||state.today.current.day);
  const access=(state.pathProgress?.days||[]).find(item=>Number(item.day)===requested);
  const selected=(access?.unlocked&&state.today.day_dates.find(item=>Number(item.day)===requested))||state.today.current;
  state.today.current=selected;state.today.is_overdue=selected.scheduled_date<state.today.today;state.selectedDay=Number(selected.day);
  await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${selected.day}/start`,{method:"POST",body:JSON.stringify({user_id:state.userId})});
  state.pathProgress=await ensurePathProgress(plan);
  try{
    state.dailyContent=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${selected.day}/session?user_id=${encodeURIComponent(state.userId)}`);
  }catch(_error){
    await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${selected.day}/content`,{method:"POST",body:JSON.stringify({user_id:state.userId})});
    state.dailyContent=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${selected.day}/session?user_id=${encodeURIComponent(state.userId)}`);
  }
  const available=(state.dailyContent.study_blocks||[]).find(b=>["available","in_progress"].includes(b.progress_state?.status));
  state.activeBlockId=available?.block_id||(state.dailyContent.study_blocks||[])[0]?.block_id||null;state.blockStartedAt=Date.now();
  state.reschedulePreview=null;
  await loadChat();
  if(state.dailyStage==="quiz")await loadQuiz();
}
function renderList(items){return (items||[]).length?`<ul>${items.map(x=>`<li>${esc(typeof x==="string"?x:(x.instruction||x.text||JSON.stringify(x)))}</li>`).join("")}</ul>`:""}
function v4MathExpression(item,block=false){const latex=typeof item==="string"?item:(item?.latex||"");const fallback=typeof item==="string"?item:(item?.text||latex);if(!latex&&!fallback)return "";return `<${block?"div":"span"} class="v4-math-expression ${block?"display":"inline"}" aria-label="${esc(fallback)}"><code>${esc(latex||fallback)}</code>${block&&fallback?`<span class="v4-math-fallback">${esc(fallback)}</span>`:""}</${block?"div":"span"}>`}
function renderV4Math(math){const value=math&&typeof math==="object"?math:{},inline=(value.inline_math||[]).map(item=>v4MathExpression(item)).filter(Boolean),display=(value.display_math||[]).map(item=>`<article class="v4-display-math">${item.label?`<h4>${esc(item.label)}</h4>`:""}${v4MathExpression(item,true)}</article>`).join(""),matrix=value.matrix,derivation=value.derivation_steps||[];if(!inline.length&&!display&&!matrix&&!derivation.length)return "";const matrixHtml=matrix?.rows?.length?`<section class="v4-matrix-wrap"><h4>${esc(matrix.label||"Matrix")}</h4><div class="v4-matrix-scroll"><table>${matrix.rows.map(row=>`<tr>${row.map(cell=>`<td>${esc(cell)}</td>`).join("")}</tr>`).join("")}</table></div></section>`:"";return `<section class="lecture-teaching-part v4-math-panel"><p class="eyebrow">FORMULA AND DIAGRAM BREAKDOWN</p>${inline.length?`<p class="v4-inline-math">${inline.join(" &middot; ")}</p>`:""}${display}${matrixHtml}${derivation.length?`<h4>Work through it</h4><ol class="v4-derivation-steps">${derivation.map(step=>`<li>${esc(step)}</li>`).join("")}</ol>`:""}</section>`}
function renderPedagogyFlow(items){return (items||[]).length?`<div class="pedagogy-flow">${items.map(x=>`<article><b>${esc(x.step||x.title)}</b><p>${esc(x.body||x.description||x.text)}</p></article>`).join("")}</div>`:""}
function blockTask(block){const c=block.content||{};return c.mini_task||c.learner_task||(c.checkpoint?{prompt:c.checkpoint.prompt,placeholder:"Write your answer in your own words...",expected_elements:c.checkpoint.expected_elements||[],minimum_words:12}:null)}
function savedBlockAnswer(block){const id=block.block_id;const local=state.blockAnswers[id];const saved=block.progress_state?.answer;return local??(typeof saved==="string"?saved:(saved?.text||""))}
function renderLearnerTask(block,readOnly=false){const task=blockTask(block);if(!task)return "";const value=savedBlockAnswer(block);return `<div class="learner-task"><div><b>Your response</b><span>${esc(task.minimum_words||12)}+ words recommended</span></div><p>${esc(task.prompt)}</p>${(task.expected_elements||[]).length?`<small>Include: ${esc(task.expected_elements.join(", "))}</small>`:""}<textarea rows="4" ${readOnly?"readonly":""} placeholder="${esc(task.placeholder||"Write your response here...")}" oninput="state.blockAnswers['${esc(block.block_id)}']=this.value">${esc(value)}</textarea></div>`}
function blockTaskPayload(id){return {text:String(state.blockAnswers[id]||"").trim(),saved_at:new Date().toISOString()}}
function renderBlockContent(block){
  const c=block.content||{},type=block.block_type;
  if(type==="concept_lesson")return `${c.opening_question?`<div class="block-hook"><b>Think first</b><p>${esc(c.opening_question)}</p></div>`:""}<p class="block-lead">${esc(c.plain_explanation)}</p>${c.mental_model?`<div class="mental-model"><b>${esc(c.mental_model.title)}</b><p>${esc(c.mental_model.description)}</p></div>`:""}${renderPedagogyFlow(c.learning_flow)}${(c.detailed_explanation||[]).map(x=>`<section class="block-subsection"><h4>${esc(x.heading)}</h4><p>${esc(x.body)}</p></section>`).join("")}${(c.common_misconceptions||[]).length?`<div class="misconceptions"><b>Common misconception</b>${c.common_misconceptions.map(x=>`<p><s>${esc(x.misconception)}</s><br>${esc(x.correction)}</p>`).join("")}</div>`:""}${c.checkpoint?`<div class="checkpoint"><b>Checkpoint</b><p>${esc(c.checkpoint.prompt)}</p></div>`:""}`;
  if(type==="worked_example")return `<div class="block-hook"><b>Scenario</b><p>${esc(c.scenario)}</p></div><h4>Problem</h4><p>${esc(c.problem)}</p><div class="worked-steps">${(c.steps||[]).map(x=>`<div><span>${esc(x.step)}</span><p><b>${esc(x.instruction)}</b><br>${esc(x.explanation)}</p></div>`).join("")}</div><div class="lesson-callout"><b>Worked solution</b><p>${esc(c.solution)}</p><small>${esc(c.why_it_works)}</small></div><div class="checkpoint"><b>Transfer it</b><p>${esc(c.transfer_question)}</p></div>`;
  if(type==="guided_reading")return `<div class="guided-reading"><div class="reading-scope">${pill("required reading","green")}<b>${c.reading_scope?.section_title?esc(c.reading_scope.section_title):"Selected excerpt"}</b><span>${c.reading_scope?.page_start?`Pages ${esc(c.reading_scope.page_start)}${c.reading_scope.page_end&&c.reading_scope.page_end!==c.reading_scope.page_start?`?${esc(c.reading_scope.page_end)}`:""}`:"Retrieved context"}</span></div>${c.why_read?`<div class="lesson-callout"><b>Why read this</b><p>${esc(c.why_read)}</p></div>`:""}<p><b>Before reading:</b> ${esc(c.before_reading)}</p><h4>Focus while you read</h4>${renderList(c.what_to_look_for||c.focus_questions)}<blockquote>${esc(c.guided_excerpt)}</blockquote><div class="checkpoint"><b>After reading</b><p>${esc(c.after_reading_task)}</p></div></div>`;
  if(["guided_practice","coding_task"].includes(type))return `<div class="block-hook"><b>Your task</b><p>${esc(c.task)}</p></div><h4>Instructions</h4>${renderList(c.instructions)}${c.starter_code?`<pre><code>${esc(c.starter_code)}</code></pre>`:""}<div class="practice-grid"><div><b>Expected result</b><p>${esc(c.expected_output)}</p></div><div><b>Hints</b>${renderList(c.hints)}</div></div><h4>Self-check</h4>${renderList(c.self_check)}${c.sample_solution?`<details class="sample-solution"><summary>Compare with a sample solution</summary>${c.sample_solution.code?`<pre><code>${esc(c.sample_solution.code)}</code></pre>`:""}<p>${esc(c.sample_solution.explanation)}</p></details>`:""}`;
  if(type==="retrieval_review")return `<h4>Recall without looking</h4>${renderList(c.retrieval_prompts)}<div class="lesson-callout"><b>Correct common errors</b>${renderList(c.error_correction)}</div><div class="checkpoint"><b>Connect the ideas</b><p>${esc(c.connection_task)}</p></div><p class="muted">${esc(c.recommended_action)}</p>`;
  if(type==="quiz_preparation")return `<h4>Ready-for-quiz checklist</h4>${renderList(c.mastery_checklist)}<h4>Practice questions</h4>${renderList(c.practice_questions)}<p class="muted">${esc(c.ready_when)}</p>`;
  if(type==="project_milestone")return `<div class="block-hook"><b>Deliverable</b><p>${esc(c.deliverable)}</p></div><h4>Milestones</h4>${renderList(c.milestones)}<h4>Acceptance criteria</h4>${renderList(c.acceptance_criteria)}<div class="checkpoint"><p>${esc(c.reflection_prompt)}</p></div>`;
  return `<h4>Reflection</h4>${renderList(c.prompts)}<p>${esc(c.connection_to_goal)}</p>`;
}
function inlineResource(block,c){const resources=[...(c.required_resources||[]),...(c.optional_resources||[])].filter(r=>(r.linked_block_ids||[]).includes(block.block_id));return resources.map(r=>`<article class="inline-resource"><div>${pill(r.usage||"resource",r.usage==="required"?"green":"")} ${r.difficulty?pill(r.difficulty):""}</div><h4>${esc(r.title)}</h4><p>${esc(r.why_selected||r.reason)}</p>${(r.what_to_focus_on||[]).length?`<b>What to focus on</b>${renderList(r.what_to_focus_on)}`:""}<small>${esc(r.estimated_minutes||0)} minutes / ${esc(r.source_type||"learning resource")}</small></article>`).join("")}
function studyBlock(block,index,c,readOnly){const status=block.progress_state?.status||"locked",active=state.activeBlockId===block.block_id;return `<article class="study-block ${status} ${active?"active":""}" id="${esc(block.block_id)}"><button class="block-heading" onclick="selectStudyBlock('${esc(block.block_id)}')" ${status==="locked"?"disabled":""}><span class="block-sequence">${status==="completed"?"&#10003;":index+1}</span><span><small>${esc(block.block_type.replaceAll("_"," "))}</small><b>${esc(block.title)}</b><em>${esc(block.estimated_minutes)} min</em></span><span class="block-status">${esc(status.replaceAll("_"," "))}</span></button>${active&&status!=="locked"?`<div class="block-body">${renderBlockContent(block)}${inlineResource(block,c)}${renderLearnerTask(block,readOnly)}<p class="personalization-reason">Why this format: ${esc(block.personalization_reason)}</p>${readOnly?"":`<div class="block-actions">${[["not_understood","I didn't understand"],["need_example","Need another example"],["too_easy","Too easy"],["review_later","Review later"]].map(([id,label])=>`<button class="v2-secondary" onclick="blockFeedback('${esc(block.block_id)}','${id}')">${label}</button>`).join("")}<button class="v2-primary" onclick="completeStudyBlock('${esc(block.block_id)}')">Complete & Continue</button></div>`}</div>`:""}</article>`}
function selectStudyBlock(id){state.activeBlockId=id;state.blockStartedAt=Date.now();render()}
async function completeStudyBlock(id){const block=(state.dailyContent?.study_blocks||[]).find(b=>b.block_id===id);const task=block?blockTask(block):null;const answer=blockTaskPayload(id);if(task&&!answer.text){state.error="Write a short response before completing this study block.";render();return}await act(async()=>{const actualSeconds=Math.max(1,Math.round((Date.now()-(state.blockStartedAt||Date.now()))/1000));const result=await api(`/api/plans/${state.today.plan_id}/days/${state.today.current.day}/blocks/${encodeURIComponent(id)}/complete`,{method:"POST",body:JSON.stringify({user_id:state.userId,actual_seconds:actualSeconds,answer})});state.dailyContent=result.session;delete state.blockAnswers[id];const next=(state.dailyContent.study_blocks||[]).find(b=>["available","in_progress"].includes(b.progress_state?.status));state.activeBlockId=next?.block_id||id;state.blockStartedAt=Date.now();state.pathProgress=await ensurePathProgress(state.currentPlan)})}
async function blockFeedback(id,type){if(type==="need_example"){try{await api(`/api/plans/${state.today.plan_id}/days/${state.today.current.day}/blocks/${encodeURIComponent(id)}/feedback`,{method:"POST",body:JSON.stringify({user_id:state.userId,feedback_type:type})})}catch(e){state.chatError=e.message}await submitChat("Give me another concrete example for the current study block. Use the lesson context and keep it practical.","another_example");return}await act(async()=>{await api(`/api/plans/${state.today.plan_id}/days/${state.today.current.day}/blocks/${encodeURIComponent(id)}/feedback`,{method:"POST",body:JSON.stringify({user_id:state.userId,feedback_type:type})});state.notice="Feedback saved for this study block."})}
function dailyNavigation(){
  // The learner-facing flow has one final learning experience. Earlier views and
  // the unfinished daily quiz remain available only to internal research routes.
  return ""
}
function dailyHeader(){const t=state.today,current=t.current||{},c=state.dailyContent||{},progress=state.pathProgress||{},sp=c.session_progress||{};return `<div class="page-head daily-head"><div><p class="eyebrow">DAILY LEARNING</p><h1>${esc(c.session_overview?.title||`Day ${current.day}: ${c.topic_labels?.join(", ")||t.goal_text}`)}</h1><p>${esc(current.scheduled_date)} / ${esc(current.plan_day?.total_minutes||c.scheduled_minutes)} minutes ${t.is_overdue?" / Overdue":""}</p></div><div class="head-actions"><span>${sp.completed_blocks||0}/${sp.total_blocks||0} blocks / ${progress.completed_days||0}/${progress.total_days||0} days</span><button class="v2-secondary" onclick="go('dashboard')">Activity Timeline</button></div></div>${dailyNavigation()}`}
function todayLearning(){
  // Deep links to the final learning experience must be authoritative.  During
  // hydration an older persisted daily stage can otherwise overwrite the URL
  // intent and silently render the legacy 0/0 daily-session view.
  if(requestedDailyView==="lecture-v4"&&state.dailyStage!=="lecture-v4"){
    state.dailyStage="lecture-v4";
  }
  if(!state.plans.length)return shell(`<section class="v2-empty"><h1>No Active Learning Path</h1><p>Create and schedule a path before starting daily learning.</p><button class="v2-primary" onclick="newPath()">Create a Learning Path</button></section>`);
  if(!state.today||!state.dailyContent)return shell(`<section class="v2-card profile-state"><div class="agent-orb">P</div><h2>Preparing today&apos;s learning</h2><p>Pathly is resolving the current day, knowledge context, and selected materials.</p></section>`);
  if(state.dailyStage==="quiz")return shell(`${dailyHeader()}${quizPanel()}`);if(state.dailyStage==="annotated")return shell(`${dailyHeader()}${annotatedSourceView()}`);if(state.dailyStage==="lecture-v3")return fullLectureView();if(state.dailyStage==="lecture-v4")return sourceGroundedLectureV4View();if(state.dailyStage!=="content")state.dailyStage="content";
  const t=state.today,current=t.current||{},c=state.dailyContent,retrieval=c.retrieval||{},overview=c.session_overview||{},sp=c.session_progress||{};const attempt=(state.pathProgress?.days||[]).find(x=>Number(x.day)===Number(current.day))?.quiz_attempt,readOnly=Boolean(attempt),requiredDone=Number(sp.required_completed||0)>=Number(sp.required_total||1);
  const optional=(c.optional_resources||[]).length?`<section class="v2-card optional-resources"><div class="section-head"><div><p class="eyebrow">OPTIONAL EXTENSIONS</p><h2>Explore further</h2></div><span>These do not count toward today&apos;s scheduled minutes.</span></div><div class="resource-list expanded">${c.optional_resources.map(r=>`<article><div>${pill("optional")}${r.difficulty?pill(r.difficulty):""}</div><h3>${esc(r.title)}</h3><p>${esc(r.why_selected||r.reason)}</p><small>${esc(r.estimated_minutes||0)} minutes / ${esc(r.source_type||r.source||"resource")}</small></article>`).join("")}</div></section>`:"";
  return shell(`${dailyHeader()}<section class="session-overview v2-card"><div><p class="eyebrow">PERSONALIZED LEARNING SESSION</p><h2>${esc(overview.opening_hook)}</h2><p>${esc(overview.personalization_note)}</p></div><div class="session-progress-ring"><b>${Math.round(Number(sp.fraction||0)*100)}%</b><span>${esc(overview.total_minutes||c.scheduled_minutes)} min planned</span></div><div class="session-progress-bar"><span style="width:${Math.round(Number(sp.fraction||0)*100)}%"></span></div><div class="session-objectives"><b>By the end, you will be able to:</b>${renderList((overview.learning_objectives||[]).map(x=>x.text))}</div></section>${c.generation_mode==="fallback"?`<div class="v2-notice inline-notice"><b>Deterministic fallback</b><span>This complete session was built from the schedule, KG and clean retrieved evidence while the model was unavailable.</span></div>`:""}<div class="daily-layout"><main><section class="study-session">${(c.study_blocks||[]).map((b,i)=>studyBlock(b,i,c,readOnly)).join("")}</section>${optional}<section class="v2-card session-finish"><h2>Finish today&apos;s session</h2><p>${requiredDone?"All required blocks are complete. You are ready for the daily quiz.":`${Number(sp.required_total||0)-Number(sp.required_completed||0)} required block(s) remain.`}</p><button class="v2-primary" ${requiredDone||readOnly?"":"disabled"} onclick="setDailyStage('quiz')">${readOnly?"Day completed":"Continue to Daily Quiz"}</button></section></main><aside class="daily-side">${chatPanel(true)}<section class="v2-card current-source"><p class="eyebrow">CURRENT CONTEXT</p><h2>Sources for this session</h2><p>${Number(retrieval.public_rag_chunks||0)+Number(retrieval.private_rag_chunks||0)} clean teaching evidence chunk(s)</p><p>${esc((retrieval.kg_sources||[]).join(", ")||"fallback KG")}</p></section><section class="v2-card"><p class="eyebrow">SCHEDULE</p><h2>Move this learning day</h2><p>All unfinished dates from this day move together, preserving review intervals.</p><input id="reschedule-date" type="date" value="${esc(current.scheduled_date)}"><button class="v2-secondary" onclick="previewReschedule()">Preview New Date</button>${rescheduleConfirmation()}</section></aside></div><details class="v2-card citation-card"><summary><b>Evidence Used for This Session</b><span>${(c.citations||[]).length} source reference(s)</span></summary>${(c.citations||[]).length?`<div class="citation-list">${c.citations.map(x=>`<article><div>${pill(x.source_type==="private_document"?"private material":"public RAG",x.source_type==="private_document"?"green":"")}<b>${esc(x.concept_id)}</b></div><p>${esc(x.excerpt)}</p><small>${x.page_start?`Page ${esc(x.page_start)}`:"Retrieved chunk"}${x.used_in_teaching===false?" / provenance only":""}</small></article>`).join("")}</div>`:`<p class="muted">No clean retrievable evidence was available; this session uses plan and KG context only.</p>`}</details>`)
}
function fullLectureSectionKey(section){return `${state.today?.plan_id||""}:${state.today?.current?.day||""}:${section.section_id}`}
function fullLectureProgressFor(lecture){const sections=lecture?.lecture_sections||[];const done=sections.filter(s=>state.fullLectureProgress[fullLectureSectionKey(s)]).length;return {done,total:sections.length,fraction:sections.length?done/sections.length:0}}
function replaceFullLectureSection(section){
  if(!state.fullLecture||!section?.section_id)return;
  const index=(state.fullLecture.lecture_sections||[]).findIndex(item=>item.section_id===section.section_id);
  if(index>=0)state.fullLecture.lecture_sections[index]=section;
}
async function retryFullLectureSection(sectionId,{automatic=false}={}){
  const key=`${state.today?.plan_id||""}:${state.today?.current?.day||""}:${sectionId}`;
  if(state.fullLectureRetrying[key])return;
  state.fullLectureRetrying[key]=true;state.error=null;render();
  try{
    const section=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/full-lecture/sections/${encodeURIComponent(sectionId)}/regenerate`,{method:"POST",body:JSON.stringify({user_id:state.userId})});
    replaceFullLectureSection(section);
    delete state.fullLectureRetryQueue[key];
    const ready=section?.content_quality?.status==="complete";
    state.notice=ready?"This lecture section is ready.":(automatic?"Automatic retry finished, but the section still needs a successful model generation.":"The scheduled concept still did not pass quality checks. You can view its PDF source or continue.");
  }catch(error){
    if(error.code==="lecture_section_context_changed"){state.notice="Pathly refreshed this lecture from the unchanged learning plan. Retry the scheduled section again.";state.fullLecture=null;await loadFullLecture()}
    else state.error=error.message
  }
  finally{delete state.fullLectureRetrying[key];persist();render()}
}

function scheduleFullLectureRetry(sectionId){
  const key=`${state.today?.plan_id||""}:${state.today?.current?.day||""}:${sectionId}`;
  state.fullLectureRetryQueue[key]={plan_id:state.today.plan_id,day:Number(state.today.current.day),section_id:sectionId,retry_at:Date.now()+60000};
  state.notice="Pathly will retry this section automatically in about one minute. You can keep reading.";
  persist();resumeFullLectureRetries();render();
}
function resumeFullLectureRetries(){
  if(fullLectureRetryTimer)clearTimeout(fullLectureRetryTimer);
  const entries=Object.entries(state.fullLectureRetryQueue||{});
  if(!entries.length)return;
  const next=entries.sort((a,b)=>Number(a[1].retry_at)-Number(b[1].retry_at))[0];
  const wait=Math.max(0,Number(next[1].retry_at)-Date.now());
  fullLectureRetryTimer=setTimeout(async()=>{
    const [key,item]=next;
    if(state.today?.plan_id===item.plan_id&&Number(state.today?.current?.day)===Number(item.day))await retryFullLectureSection(item.section_id,null,{automatic:true});
    else{delete state.fullLectureRetryQueue[key];persist()}
    resumeFullLectureRetries();
  },Math.min(wait,2147483647));
}
function openFullLectureSource(sectionId){
  const activeLecture=state.dailyStage==="lecture-v4"?state.lectureV4:state.fullLecture;
  const section=(activeLecture?.lecture_sections||[]).find(item=>item.section_id===sectionId);
  if(!section?.document_id||!section?.page_start){state.notice="No PDF page is available for this section.";render();return}
  window.open(`/api/documents/${encodeURIComponent(section.document_id)}/pages/${encodeURIComponent(section.page_start)}/render?user_id=${encodeURIComponent(state.userId)}`,"_blank","noopener");
}
function continueAfterLectureSection(sectionId){
  const sections=state.fullLecture?.lecture_sections||[];
  const index=sections.findIndex(item=>item.section_id===sectionId);
  const next=sections[index+1];
  if(next){document.getElementById(`lecture-${next.section_id}`)?.scrollIntoView({behavior:"smooth",block:"start"});return}
  state.notice="You reached the final lecture section. You can open the Daily Quiz when ready.";render();
}function toggleFullLectureSection(sectionId){
  const key=`${state.today?.plan_id||""}:${state.today?.current?.day||""}:${sectionId}`;
  if(state.fullLectureSaving[key])return;
  const completed=!state.fullLectureProgress[key];
  state.fullLectureProgress[key]=completed;
  state.fullLectureSaving[key]=true;
  persist();render();
  api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/full-lecture/sections/${encodeURIComponent(sectionId)}/progress`,{method:"POST",body:JSON.stringify({user_id:state.userId,completed})})
    .then(saved=>{state.fullLectureProgress[key]=saved.status==="completed";state.notice=completed?"Lecture section saved as complete.":"Lecture section reopened.";})
    .catch(()=>{state.notice="Completion is saved locally and will retry when the server is available.";})
    .finally(()=>{delete state.fullLectureSaving[key];persist();render();});
}
function lecturePageSequence(section){
  const raw=Array.isArray(section.page_sequence)?section.page_sequence:[];
  if(raw.length)return raw.filter(page=>page&&Number(page.page_start)>0);
  const start=Number(section.page_start||0),end=Math.min(Number(section.page_end||start),start+5);
  if(!start)return [];
  return Array.from({length:Math.max(1,end-start+1)},(_,index)=>({page_start:start+index,page_end:start+index,role:index===0?"anchor":"context_after"}));
}
function setLectureSourcePage(sectionId,index){
  const activeLecture=state.dailyStage==="lecture-v4"?state.lectureV4:state.fullLecture;
  const section=(activeLecture?.lecture_sections||[]).find(item=>item.section_id===sectionId);
  const pages=lecturePageSequence(section||{});
  state.fullLectureSourcePages[sectionId]=Math.max(0,Math.min(Number(index)||0,pages.length-1));
  render();
  setTimeout(()=>document.getElementById(`lecture-source-${sectionId}`)?.scrollIntoView({behavior:"smooth",block:"center"}),0);
}
function lecturePageReader(section){
  if(!section.document_id)return "";
  const pages=lecturePageSequence(section);
  if(!pages.length)return "";
  const guide=section.page_led_lesson?.page_sequence_guide||[];
  let index=Number(state.fullLectureSourcePages[section.section_id]);
  if(!Number.isInteger(index)||index<0||index>=pages.length){const anchorIndex=pages.findIndex(page=>page.role==="anchor");index=anchorIndex>=0?anchorIndex:0}
  const page=pages[index],note=guide.find(item=>Number(item.page_start)===Number(page.page_start))||{};
  const chips=pages.map((item,itemIndex)=>`<button type="button" class="${itemIndex===index?"active":""}" onclick="setLectureSourcePage('${esc(section.section_id)}',${itemIndex})">Page ${esc(item.page_start)}${item.role==="anchor"?" 鐠?Anchor":""}</button>`).join("");
  return `<details id="lecture-source-${esc(section.section_id)}" class="pdf-page-reader pdf-sequence-reader" open><summary>Read selected source pages${section.document_title?`: ${esc(section.document_title)}`:""}</summary><div class="pdf-sequence-toolbar"><button class="v2-secondary" type="button" ${index===0?"disabled":""} onclick="setLectureSourcePage('${esc(section.section_id)}',${index-1})">Previous page</button><div class="pdf-page-chips">${chips}</div><button class="v2-secondary" type="button" ${index===pages.length-1?"disabled":""} onclick="setLectureSourcePage('${esc(section.section_id)}',${index+1})">Next page</button></div><div class="pdf-page-context"><span>${esc(page.role==="anchor"?"Anchor page":(page.role==="context_before"?"Previous context":"Following context"))}</span><b>${esc(note.title||page.section_title||`Page ${page.page_start}`)}</b><p>${esc(note.purpose||"Read this page as part of the continuous explanation around the anchor page.")}</p>${(note.key_claims||[]).length?renderList(note.key_claims):""}</div><img loading="lazy" class="pdf-page-image" src="/api/documents/${encodeURIComponent(section.document_id)}/pages/${encodeURIComponent(page.page_start)}/render?user_id=${encodeURIComponent(state.userId)}" alt="Source PDF page ${esc(page.page_start)}"><p class="muted">Page ${esc(page.page_start)} of ${pages.length} selected page(s). ${esc(note.transition||"")}</p></details>`;
}
function pageLedLecture(section){
  const lesson=section.page_led_lesson||{};
  const concept=lesson.concept_explanation||{};
  const recap=lesson.prerequisite_recap||{};
  const reading=lesson.guided_reading||{};
  const worked=lesson.worked_example||{};
  const check=lesson.knowledge_check||{};
  const terms=lesson.key_terms||[];
  const walkthrough=reading.walkthrough||[];
  const hasSource=Boolean(section.source_grounding?.has_real_source);
  const pageReader=lecturePageReader(section);
  return `<div class="lecture-page-led">
    ${concept.overview?`<section class="lecture-core-explanation"><p class="eyebrow">1. CORE EXPLANATION</p><h3>${esc(section.title)}</h3><p>${esc(concept.overview)}</p>${concept.mechanism?`<h4>How it works</h4><p>${esc(concept.mechanism)}</p>`:""}${concept.assumptions_and_boundaries?`<h4>Assumptions and boundaries</h4><p>${esc(concept.assumptions_and_boundaries)}</p>`:""}${concept.concrete_example?`<div class="lesson-callout"><b>Concrete example</b><p>${esc(concept.concrete_example)}</p></div>`:""}</section>`:""}
    ${recap.content?`<section class="lecture-recap"><p class="eyebrow">2. QUICK RECAP</p><h3>${esc(recap.title||"What to recall")}</h3><p>${esc(recap.content)}</p></section>`:""}
    ${hasSource?`<section class="lecture-guided-reading"><p class="eyebrow">3. READ AND OBSERVE</p><h3>${esc(reading.opening_question||"Read the selected source closely.")}</h3>${renderList(reading.observation_steps||[])}${pageReader}</section>`:""}
    ${hasSource&&walkthrough.length?`<section class="lecture-walkthrough"><p class="eyebrow">4. ANNOTATED WALKTHROUGH</p><h3>Read the evidence, then interpret it</h3>${walkthrough.map((item,index)=>`<article><span>${index+1}</span><div><blockquote>${esc(item.source_text)}</blockquote><p>${esc(item.teaching_note)}</p></div></article>`).join("")}</section>`:""}
    ${terms.length?`<section class="lecture-key-terms"><p class="eyebrow">4. KEY TERMS</p><h3>${hasSource?"Vocabulary for this source":"Key vocabulary"}</h3><dl>${terms.map(term=>`<div><dt>${esc(term.term)}</dt><dd>${esc(term.meaning)}</dd></div>`).join("")}</dl></section>`:""}
    <section class="lecture-worked-example"><p class="eyebrow">5. WORK THROUGH AN EXAMPLE</p><h3>${esc(worked.scenario||(hasSource?"Apply the source to a concrete case.":"Work through a concrete case."))}</h3><ol>${(worked.steps||[]).map(step=>`<li>${esc(step)}</li>`).join("")}</ol><div><b>What a strong answer includes</b><p>${esc(worked.solution||section.teaching?.worked_example||"")}</p></div></section>
    <section class="lecture-check"><p class="eyebrow">6. CHECK YOUR UNDERSTANDING</p><h3>${esc(check.prompt||(hasSource?"Explain the page in your own words.":"Explain the concept in your own words."))}</h3><p>Include:</p>${renderList(check.expected_elements||[])}<p class="muted">This check prepares you for the scored quiz; it does not yet count as the daily quiz attempt.</p></section>
    ${lesson.transition?`<section class="lecture-transition"><b>Carry this forward</b><p>${esc(lesson.transition)}</p></section>`:""}
    ${section.source_excerpt?`<details class="lecture-excerpt"><summary>Prepared source excerpt</summary><blockquote>${esc(section.source_excerpt)}</blockquote><p class="muted">This is a cleaned, bounded excerpt from the source, retained for review.</p></details>`:""}
  </div>`;
}
function fullLectureView(){
  const lecture=state.fullLecture;
  if(state.fullLectureError)return shell(`<section class="v2-card"><h2>Full Lecture View v3 is unavailable</h2><p>${esc(state.fullLectureError)}</p><button class="v2-primary" onclick="loadFullLecture()">Try again</button></section>`);
  if(!lecture)return shell(`<section class="v2-card profile-state"><div class="agent-orb">P</div><h2>Preparing Full Lecture View v3</h2><p>Pathly is assembling the source-grounded lecture.</p><button class="v2-primary" onclick="loadFullLecture()">Load Full Lecture</button></section>`);
  const overview=lecture.lecture_overview||{}, progress=fullLectureProgressFor(lecture);
  const pdfSections=(lecture.lecture_sections||[]).filter(section=>section.document_id&&lecturePageSequence(section).length);
  const pdfSourceNotice=pdfSections.length?`<div class="v2-notice inline-notice"><b>PDF source sequence available</b><span>${pdfSections.length} lecture section(s) include selected pages from PDFs. Open 闁炽儲鐝恊ad selected source pages闁?inside those sections.</span></div>`:`<div class="inline-alert warning lecture-source-unavailable"><b>No uploaded PDF is linked to this learning path</b><span>This lecture is using public resources or KG context. To see the related-page PDF reader, open a path created with your uploaded PDFs or create a new path and select those materials.</span></div>`;
  const sections=(lecture.lecture_sections||[]).map((section,index)=>{
    const sectionKey=fullLectureSectionKey(section),done=Boolean(state.fullLectureProgress[sectionKey]),saving=Boolean(state.fullLectureSaving[sectionKey]),quality=section.content_quality||{};
    const unavailable=quality.status&&quality.status!=="complete";
    const body=unavailable
      ? `<div class="inline-alert warning lecture-generation-failed"><b>This section is temporarily unavailable.</b><span>No template or fallback lesson is shown. Pathly can retry this section without changing the rest of your lecture.</span><div class="lecture-retry-actions"><button class="v2-primary" type="button" ${state.fullLectureRetrying[sectionKey]?"disabled":""} onclick="retryFullLectureSection('${esc(section.section_id)}')">${state.fullLectureRetrying[sectionKey]?"Generating...":"Retry now"}</button><button class="v2-secondary" type="button" onclick="scheduleFullLectureRetry('${esc(section.section_id)}')">${state.fullLectureRetryQueue[sectionKey]?"Retry scheduled":"Retry automatically later"}</button>${section.document_id&&section.page_start?`<button class="v2-secondary" type="button" onclick="openFullLectureSource('${esc(section.section_id)}')">View original PDF</button>`:""}<button class="v2-secondary" type="button" onclick="continueAfterLectureSection('${esc(section.section_id)}')">Continue to next section</button></div></div>`
      : `<p class="lecture-concept-intro">${esc(section.teaching?.explanation||"")}</p>${pageLedLecture(section)}`;
    const action=unavailable?"":`<div class="lecture-section-actions"><button class="v2-primary" type="button" ${saving?"disabled":""} onclick="toggleFullLectureSection('${esc(section.section_id)}')">${saving?(done?"Completed 路 Saving...":"Reopening..."):(done?"Mark as not finished":"Complete this section")}</button></div>`;
    return `<article id="lecture-${esc(section.section_id)}" class="study-block v2-card lecture-section ${done?"completed":""}"><div class="section-head"><div><p class="eyebrow">SECTION ${index+1} / ${done?"COMPLETED":"LEARN"}</p><h2>${esc(section.title)}</h2></div><span>${esc(section.estimated_minutes)} min</span></div>${body}${action}</article>`;
  }).join("");
  return shell(`${dailyHeader()}<section class="session-overview v2-card"><div><p class="eyebrow">FULL LECTURE VIEW V3</p><h2>${esc(overview.title||"Full lecture")}</h2><p>${esc(overview.why_this_matters||"")}</p><p class="muted">${esc(lecture.scheduled_minutes)} minutes &middot; ${esc(lecture.generation_metadata?.generation_mode||"fallback")} &middot; ${progress.done}/${progress.total} sections complete</p><div class="session-progress-bar"><span style="width:${Math.round(progress.fraction*100)}%"></span></div></div></section>${pdfSourceNotice}<div class="daily-layout"><main><section class="study-session lecture-v3-sections">${sections}</section><section class="v2-card"><h2>Practice</h2><p>${esc(lecture.practice_set?.items?.[0]?.prompt||"Apply today's concepts to one concrete case.")}</p></section><section class="v2-card"><h2>Knowledge check</h2><p>${esc(lecture.knowledge_check?.items?.[0]?.prompt||"Explain the central mechanism in your own words.")}</p></section></main><aside class="daily-side">${chatPanel(true)}<section class="v2-card"><p class="eyebrow">SOURCE COVERAGE</p><p>${esc(lecture.source_materials?.length||0)} source material(s) &middot; ${esc(lecture.citations?.length||0)} citation(s)</p><p class="muted">Complete each section to build today's lecture progress.</p></section></aside></div>`);
}
async function loadFullLecture(){
  if(!state.today?.plan_id||!state.today?.current?.day)return null;
  await act(async()=>{
    state.fullLectureError=null;
    try{
      state.fullLecture=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/full-lecture?user_id=${encodeURIComponent(state.userId)}`);
      const progress=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/full-lecture/progress?user_id=${encodeURIComponent(state.userId)}`);
      for(const [sectionId,value] of Object.entries(progress.sections||{})){
        state.fullLectureProgress[`${state.today.plan_id}:${state.today.current.day}:${sectionId}`]=value.status==="completed";
      }
      persist();resumeFullLectureRetries();
    }catch(e){state.fullLectureError=e.message||"Full Lecture View v3 is unavailable."}
  },"Generating your full lecture from today's learning context...");
  return state.fullLecture;
}
function v4SectionKey(section){return `${state.today?.plan_id||""}:${state.today?.current?.day||""}:${section.section_id}`}
function focusV4Section(sectionId){state.v4CurrentSectionId=sectionId;persist();document.getElementById(`v4-${sectionId}`)?.scrollIntoView({behavior:"smooth",block:"start"})}
function v4ConceptKey(value){return String(value||"").toLowerCase().replace(/: from source to understanding$/i,"").replace(/[^a-z0-9]+/g," ").trim()}
function v4SourceLinksFor(section,links){
  const ids=(section.concept_ids||[section.concept_id]).filter(Boolean).map(v4ConceptKey);
  const names=[section.concept_name,section.title].filter(Boolean).map(v4ConceptKey);
  return (links||[]).filter(link=>ids.includes(v4ConceptKey(link.concept_id))||names.includes(v4ConceptKey(link.concept_name)));
}
function v4PageLabel(pages){
  const numbers=(pages||[]).map(item=>Number(item.page_number)).filter(Boolean).sort((a,b)=>a-b);
  if(!numbers.length)return "";
  return numbers.length===1?`Page ${numbers[0]}`:`Pages ${numbers[0]}-${numbers[numbers.length-1]}`;
}
function v4SourceStatusCard(section,links){
  const matched=v4SourceLinksFor(section,links).filter(link=>["usable","verified"].includes(link.review_status));
  if(!matched.length)return "";
  return matched.map(link=>{
    const pages=link.page_sequence||[],scope=link.source_scope==="private"?"Private PDF":"Public PDF";
    return `<section class="v4-source-status linked"><div class="v4-source-status-head"><div><p class="eyebrow">SOURCE MATERIAL</p><h3>Selected source pages</h3></div><span class="source-scope-pill ${link.source_scope==="private"?"private":"public"}">${esc(scope)}</span></div><p><b>${esc(v4PageLabel(pages))}</b></p></section>`;
  }).join("");
}function v4AnswerKey(sectionId,questionId){return `${state.today?.plan_id||""}:${state.today?.current?.day||""}:${sectionId}:${questionId}`}
function refreshV4ExerciseUI(sectionId){
  const section=(state.lectureV4?.lecture_sections||[]).find(item=>String(item.section_id)===String(sectionId));
  const root=document.getElementById(`v4-${sectionId}`);
  if(!section||!root)return;
  const questions=section.lecture_content?.objective_exercise?.questions||[];
  const answered=questions.filter(question=>state.v4ExerciseResults[v4AnswerKey(section.section_id,question.question_id)]?.answered).length;
  const correct=questions.filter(question=>state.v4ExerciseResults[v4AnswerKey(section.section_id,question.question_id)]?.correct).length;
  const allCorrect=questions.length>0&&correct===questions.length;
  const summary=root.querySelector('[data-v4-exercise-summary]');
  if(summary)summary.textContent=`${answered}/${questions.length} answered 路 ${correct}/${questions.length} correct`;
  const complete=root.querySelector('button[onclick*="toggleV4Section"]');
  if(complete)complete.disabled=Boolean(state.v4Saving[v4SectionKey(section)])||(!state.v4SectionProgress[v4SectionKey(section)]&&!allCorrect);
  const note=root.querySelector('.lecture-section-actions span');
  if(note)note.hidden=allCorrect;
}
async function setV4ObjectiveAnswer(sectionId,questionId,optionId){
  const key=v4AnswerKey(sectionId,questionId),button=document.activeElement,card=button?.closest?.(".v4-question");
  state.v4ExerciseAnswers[key]=optionId;
  if(card){card.querySelectorAll(".v4-options button").forEach(item=>item.classList.toggle("selected",item===button));card.querySelector(".v4-answer-feedback")?.remove();card.classList.remove("correct","incorrect")}
  try{
    const saved=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/lecture-v4/sections/${encodeURIComponent(sectionId)}/exercises/${encodeURIComponent(questionId)}/answer`,{method:"POST",body:JSON.stringify({answer_id:optionId})});
    state.v4ExerciseResults[key]={answered:true,correct:Boolean(saved.correct)};persist();
    if(card){card.classList.add(saved.correct?"correct":"incorrect");const feedback=document.createElement("p");feedback.className="v4-answer-feedback";feedback.innerHTML=`<b>${saved.correct?"Correct.":"Not quite."}</b> ${esc(saved.explanation||"")}`;card.appendChild(feedback)}
    refreshV4ExerciseUI(sectionId);
  }catch(error){delete state.v4ExerciseAnswers[key];state.error=error.message||"Your answer could not be saved. Please retry.";persist();if(card)card.querySelectorAll(".v4-options button").forEach(item=>item.classList.remove("selected"));}
}
function submitV4ObjectiveExercise(sectionId){return sectionId}
function v4ObjectiveExercise(section){
  const exercise=section.lecture_content?.objective_exercise||{},questions=exercise.questions||[];
  const answered=questions.filter(question=>state.v4ExerciseResults[v4AnswerKey(section.section_id,question.question_id)]?.answered).length;
  const correct=questions.filter(question=>state.v4ExerciseResults[v4AnswerKey(section.section_id,question.question_id)]?.correct).length;
  const openKey=`${state.today?.plan_id||""}:${state.today?.current?.day||""}:${section.section_id}:open`;
  const openResult=state.v4OpenResults?.[openKey];
  return `<section class="lecture-teaching-part v4-objective-exercise"><p class="eyebrow">OBJECTIVE EXERCISE</p><h3>Check the knowledge from this section</h3><p>${esc(exercise.instructions||"")}</p>${questions.map((question,index)=>{const key=v4AnswerKey(section.section_id,question.question_id),selected=state.v4ExerciseAnswers[key],result=state.v4ExerciseResults[key],kind=String(question.question_type||"").replaceAll("_"," ");return `<article class="v4-question ${result?.correct?"correct":(result?.answered?"incorrect":"")}"><p class="eyebrow">${esc(kind)}</p><h4>${index+1}. ${esc(question.prompt)}</h4><div class="v4-options">${(question.options||[]).map(option=>`<button type="button" class="v2-secondary ${String(selected)===String(option.id)?"selected":""}" onclick="setV4ObjectiveAnswer('${esc(section.section_id)}','${esc(question.question_id)}','${esc(option.id)}')">${esc(option.text)}</button>`).join("")}</div>${result?.answered?`<p class="v4-answer-feedback"><b>${result.correct?"Correct.":"Not quite."}</b> ${esc(question.explanation||"")}</p>`:""}</article>`}).join("")}<div class="v4-open-response"><p class="eyebrow">OPEN RESPONSE (OPTIONAL)</p><h4>Explain the main mechanism in your own words</h4><textarea id="v4-open-${esc(section.section_id)}" rows="4" placeholder="Write a short explanation..."></textarea><button type="button" class="v2-secondary" onclick="submitV4OpenAnswer('${esc(section.section_id)}')">Submit for AI feedback</button>${openResult?`<p class="v4-answer-feedback"><b>${openResult.correct?"Good explanation":"Keep developing this idea"}</b> ${esc(openResult.feedback||"")}</p>`:""}</div><p class="muted">Choose an answer to save it and see feedback immediately.</p><div class="lecture-section-actions"><span data-v4-exercise-summary>${answered}/${questions.length} answered &middot; ${correct}/${questions.length} correct</span></div></section>`;
}
async function submitV4OpenAnswer(sectionId){const input=document.getElementById(`v4-open-${sectionId}`);if(!input?.value.trim())return;try{const saved=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/lecture-v4/sections/${encodeURIComponent(sectionId)}/open-answer`,{method:"POST",body:JSON.stringify({answer:input.value.trim()})});state.v4OpenResults={...(state.v4OpenResults||{}),[`${state.today.plan_id}:${state.today.current.day}:${sectionId}:open`]:saved};persist();render()}catch(error){state.error=error.message||"Open-answer feedback is unavailable.";render()}}
function v4SourcePagePanel(section,walkthrough=[]){
  const pages=section.source_pages||[];
  const mathPanel=renderV4Math(section.lecture_content?.math);
  if(!pages.length)return mathPanel;
  const pageGuide=new Map((walkthrough||[]).map(item=>[String(item.page_number),item]));
  const pageCards=pages.map(page=>{
    const isPrivate=page.source_scope==="private"&&page.document_id,isPublic=!isPrivate&&page.resource_id,scope=isPrivate?"Private PDF":"Public PDF",guide=pageGuide.get(String(page.page_number))||{};
    const imageSrc=isPrivate?`/api/documents/${encodeURIComponent(page.document_id)}/pages/${encodeURIComponent(page.page_number)}/render?user_id=${encodeURIComponent(state.userId)}`:(isPublic?`/api/public-resources/${encodeURIComponent(page.resource_id)}/pages/${encodeURIComponent(page.page_number)}/render`:"");
    const sourceText=page.text?`<details class="v4-source-transcript"><summary>Text version of this page</summary><blockquote>${esc(page.text)}</blockquote></details>`:"";
    return `<article class="v4-source-page"><div class="section-head"><div><p class="eyebrow">PAGE ${esc(page.page_number)} &middot; ${esc(scope)}</p><h3>Selected source page</h3></div></div>${imageSrc?`<div class="v4-pdf-page-frame"><img loading="lazy" src="${imageSrc}" alt="Source page ${esc(page.page_number)}"></div>`:`<blockquote class="v4-public-source-text">${esc(page.text||"Source page preview unavailable.")}</blockquote>`}<section class="v4-page-annotation"><p class="eyebrow">SOURCE EXPLANATION</p><h4>${esc(guide.what_to_notice||"Central idea")}</h4><p class="v4-math-safe">${esc(guide.explanation||"")}</p>${guide.connection_to_previous?`<p class="v4-page-connection v4-math-safe"><b>Connection:</b> ${esc(guide.connection_to_previous)}</p>`:""}</section>${sourceText}</article>`;
  }).join("");
  return `<section class="v4-source-pages"><p class="eyebrow">LEARN FROM THE SOURCE</p>${pageCards}${mathPanel}</section>`;
}
// V4 source pages are a compact carousel: the page image, its explanation,
// and its transcript stay together while only one source page is visible.
function v4SourcePagePanel(section,walkthrough=[]){
  const pages=section.source_pages||[],mathPanel=renderV4Math(section.lecture_content?.math);
  if(!pages.length)return mathPanel;
  state.v4SourcePageIndexes=state.v4SourcePageIndexes||{};
  const raw=Number(state.v4SourcePageIndexes[section.section_id]||0),index=Math.max(0,Math.min(pages.length-1,raw)),page=pages[index];
  state.v4SourcePageIndexes[section.section_id]=index;
  const guide=(walkthrough||[]).find(item=>String(item.page_number)===String(page.page_number))||{};
  const isPrivate=page.source_scope==="private"&&page.document_id,isPublic=!isPrivate&&page.resource_id;
  const scope=isPrivate?"Private PDF":"Public PDF";
  const imageSrc=isPrivate?`/api/documents/${encodeURIComponent(page.document_id)}/pages/${encodeURIComponent(page.page_number)}/render?user_id=${encodeURIComponent(state.userId)}`:(isPublic?`/api/public-resources/${encodeURIComponent(page.resource_id)}/pages/${encodeURIComponent(page.page_number)}/render`:"");
  const sourceText=page.text?`<details class="v4-source-transcript"><summary>Text version of this page</summary><blockquote>${esc(page.text)}</blockquote></details>`:"";
  return `<section class="v4-source-pages v4-source-carousel" data-v4-source-carousel="${esc(section.section_id)}"><p class="eyebrow">LEARN FROM THE SOURCE 路 PAGE ${esc(page.page_number)} OF ${esc(pages.length)}</p><button type="button" class="v4-source-carousel-arrow left" aria-label="Previous source page" ${index===0?"disabled":""} onclick="setV4SourcePage('${esc(section.section_id)}',-1)">&#8592;</button><button type="button" class="v4-source-carousel-arrow right" aria-label="Next source page" ${index===pages.length-1?"disabled":""} onclick="setV4SourcePage('${esc(section.section_id)}',1)">&#8594;</button><article class="v4-source-page"><div class="section-head"><div><p class="eyebrow">PAGE ${esc(page.page_number)} 路 ${esc(scope)}</p><h3>Selected source page</h3></div></div>${imageSrc?`<div class="v4-pdf-page-frame"><img loading="lazy" src="${imageSrc}" alt="Source page ${esc(page.page_number)}"></div>`:`<blockquote class="v4-public-source-text">${esc(page.text||"Source page preview unavailable.")}</blockquote`}<section class="v4-page-annotation"><p class="eyebrow">SOURCE EXPLANATION</p><h4>${esc(guide.what_to_notice||"Central idea")}</h4><p class="v4-math-safe">${esc(guide.explanation||"")}</p>${guide.connection_to_previous?`<p class="v4-page-connection v4-math-safe"><b>Connection:</b> ${esc(guide.connection_to_previous)}</p>`:""}</section>${sourceText}</article>${mathPanel}</section>`;
}
function setV4SourcePage(sectionId,delta){
  const section=(state.lectureV4?.lecture_sections||[]).find(item=>String(item.section_id)===String(sectionId));
  if(!section)return;
  const pages=section.source_pages||[];
  state.v4SourcePageIndexes=state.v4SourcePageIndexes||{};
  const current=Number(state.v4SourcePageIndexes[sectionId]||0);
  state.v4SourcePageIndexes[sectionId]=Math.max(0,Math.min(pages.length-1,current+Number(delta||0)));
  const carousel=document.querySelector(`[data-v4-source-carousel="${sectionId}"]`);
  if(!carousel)return;
  const replacement=document.createRange().createContextualFragment(v4SourcePagePanel(section,section.lecture_content?.page_walkthrough||[]));
  carousel.replaceWith(replacement);
}
// Keep the navigation controls inside the PDF frame rather than centred over
// the explanation/transcript that follows it.
function v4SourcePagePanel(section,walkthrough=[]){
  const pages=section.source_pages||[],mathPanel=renderV4Math(section.lecture_content?.math);
  if(!pages.length)return mathPanel;
  state.v4SourcePageIndexes=state.v4SourcePageIndexes||{};
  const index=Math.max(0,Math.min(pages.length-1,Number(state.v4SourcePageIndexes[section.section_id]||0))),page=pages[index];
  state.v4SourcePageIndexes[section.section_id]=index;
  const guide=(walkthrough||[]).find(item=>String(item.page_number)===String(page.page_number))||{};
  const isPrivate=page.source_scope==="private"&&page.document_id,isPublic=!isPrivate&&page.resource_id;
  const scope=isPrivate?"Private PDF":"Public PDF";
  const imageSrc=isPrivate?`/api/documents/${encodeURIComponent(page.document_id)}/pages/${encodeURIComponent(page.page_number)}/render?user_id=${encodeURIComponent(state.userId)}`:(isPublic?`/api/public-resources/${encodeURIComponent(page.resource_id)}/pages/${encodeURIComponent(page.page_number)}/render`:"");
  const sourceText=page.text?`<details class="v4-source-transcript"><summary>Text version of this page</summary><blockquote>${esc(page.text)}</blockquote></details>`:"";
  const pageVisual=imageSrc?`<div class="v4-pdf-page-frame"><img loading="lazy" src="${imageSrc}" alt="Source page ${esc(page.page_number)}"><button type="button" class="v4-source-carousel-arrow left" aria-label="Previous source page" ${index===0?"disabled":""} onclick="setV4SourcePage('${esc(section.section_id)}',-1)">&#8592;</button><button type="button" class="v4-source-carousel-arrow right" aria-label="Next source page" ${index===pages.length-1?"disabled":""} onclick="setV4SourcePage('${esc(section.section_id)}',1)">&#8594;</button></div>`:`<blockquote class="v4-public-source-text">${esc(page.text||"Source page preview unavailable.")}</blockquote>`;
  return `<section class="v4-source-pages v4-source-carousel" data-v4-source-carousel="${esc(section.section_id)}"><p class="eyebrow">LEARN FROM THE SOURCE 路 PAGE ${esc(page.page_number)} OF ${esc(pages.length)}</p><article class="v4-source-page"><div class="section-head"><div><p class="eyebrow">PAGE ${esc(page.page_number)} 路 ${esc(scope)}</p><h3>Selected source page</h3></div></div>${pageVisual}<section class="v4-page-annotation"><p class="eyebrow">SOURCE EXPLANATION</p><h4>${esc(guide.what_to_notice||"Central idea")}</h4><p class="v4-math-safe">${esc(guide.explanation||"")}</p>${guide.connection_to_previous?`<p class="v4-page-connection v4-math-safe"><b>Connection:</b> ${esc(guide.connection_to_previous)}</p>`:""}</section>${sourceText}</article>${mathPanel}</section>`;
}
function v4LearnerAdaptationPanel(content){
  return "";
  const adaptation=content?.learner_adaptation||{},personalization=content?.personalization||{};
  if(!Object.keys(adaptation).length&&!Object.keys(personalization).length)return "";
  const rows=[
    ["璁ょ煡姘村钩",adaptation.prior_knowledge_level||personalization.lesson_depth||"standard"],
    ["璁茶В瀵嗗害",adaptation.explanation_density||personalization.recap_depth||"standard"],
    ["渚嬪瓙椋庢牸",adaptation.example_mode||personalization.explanation_style||"balanced"],
    ["缁冧範鏂瑰紡",adaptation.practice_style||personalization.practice_style||"guided"],
    ["鏈娣卞害",adaptation.terminology_depth||"standard"],
    ["鍏磋叮浣跨敤",adaptation.interest_usage||personalization.interest_usage||"scenario_only"],
  ];
  return `<section class="lecture-teaching-part v4-profile-contrast"><p class="eyebrow">THIS PROFILE IN PRACTICE</p><h3>How this lesson is adapted</h3><dl class="v4-key-terms">${rows.map(([label,value])=>`<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl></section>`;
}
function v4OpeningExample(content,section){
  const opening=content?.opening_example||{},worked=content?.worked_example||{},intro=content?.concept_introduction||{};
  const scenario=opening.scenario||worked.problem||intro.hook||`Consider one situation where ${section?.concept_name||section?.title||"this concept"} matters.`;
  const question=opening.question||"What would have to be true for this situation to work?";
  return `<section class="lecture-teaching-part v4-opening-example"><p class="eyebrow">START WITH AN EXAMPLE</p><h3>${esc(opening.title||"Start with a concrete case")}</h3><p>${esc(scenario)}</p><div class="worked-example"><b>Think about it first</b><p>${esc(question)}</p></div></section>`;
}
function v4ReadySection(section,index,completed,saving){
  const content=section.lecture_content||{},intro=content.concept_introduction||{},recap=content.prerequisite_recap||{},example=content.worked_example||{},summary=content.summary_connection||{};
  const questions=content.objective_exercise?.questions||[];
  const allCorrect=questions.length>0&&questions.every(question=>state.v4ExerciseResults[v4AnswerKey(section.section_id,question.question_id)]?.correct);
  return `<article id="v4-${esc(section.section_id)}" class="study-block v2-card lecture-section v4-lecture-section ${completed?"completed":""}"><div class="section-head"><div><p class="eyebrow">SECTION ${index+1} &middot; ${completed?"COMPLETED":"YOUR LESSON"}</p><h2>${esc(section.title)}</h2></div><span>${esc(section.estimated_minutes)} min</span></div>${v4OpeningExample(content,section)}${recap.explanation?`<section class="lecture-teaching-part"><p class="eyebrow">PREREQUISITE RECAP</p><h3>${esc(recap.title||"What you need first")}</h3><p>${esc(recap.explanation)}</p>${recap.example?`<div class="worked-example"><b>Quick example</b><p>${esc(recap.example)}</p></div>`:""}</section>`:""}<section class="lecture-teaching-part"><p class="eyebrow">CORE IDEA</p><h3>${esc(intro.hook||section.concept_name)}</h3><p>${esc(intro.explanation||"")}</p>${(intro.mechanism||[]).length?`<h4>How the mechanism works</h4><ol>${intro.mechanism.map(step=>`<li>${esc(step)}</li>`).join("")}</ol>`:""}${intro.boundaries?`<h4>Boundary and counterexample</h4><p>${esc(intro.boundaries)}</p>`:""}</section>${v4SourceStatusCard(section,section.source_links||[])}${v4LearnerAdaptationPanel(content)}${v4SourcePagePanel(section,content.page_walkthrough||[])}${content.intuition?`<section class="lecture-teaching-part v4-intuition"><p class="eyebrow">INTUITION</p><p>${esc(content.intuition)}</p></section>`:""}${(content.key_terms||[]).length?`<section class="lecture-teaching-part"><p class="eyebrow">KEY TERMS</p><dl class="v4-key-terms">${content.key_terms.map(item=>`<div><dt>${esc(item.term)}</dt><dd>${esc(item.definition)}</dd></div>`).join("")}</dl></section>`:""}<section class="lecture-teaching-part worked-example"><p class="eyebrow">WORKED EXAMPLE</p><h3>${esc(example.problem||"Apply the concept")}</h3><ol>${(example.steps||[]).map(step=>`<li>${esc(step)}</li>`).join("")}</ol><h4>Solution</h4><p>${esc(example.solution||"")}</p><h4>Why it works</h4><p>${esc(example.why_it_works||"")}</p></section>${content.common_mistake?`<section class="lecture-teaching-part v4-common-mistake"><p class="eyebrow">COMMON MISUNDERSTANDING</p><p>${esc(content.common_mistake)}</p></section>`:""}${v4ObjectiveExercise(section)}<section class="lecture-teaching-part v4-summary"><p class="eyebrow">TAKEAWAY</p><p>${esc(summary.summary||"")}</p>${summary.next_concept_bridge?`<p><b>Next connection:</b> ${esc(summary.next_concept_bridge)}</p>`:""}</section><div class="lecture-section-actions"><button class="v2-primary" ${saving||(!completed&&!allCorrect)?"disabled":""} onclick="toggleV4Section('${esc(section.section_id)}')">${saving?"Saving...":(completed?"Mark as not finished":"Complete v4 section")}</button>${!completed&&!allCorrect?`<span>Answer all objective questions correctly before completing this section.</span>`:""}</div></article>`;
}
function nextReadyV4SectionId(sections,index){
  const next=(sections||[]).slice(index+1).find(item=>item?.v4_status==="ready");
  return next?String(next.section_id):"";
}
function lectureV4MatchesToday(){
  return Boolean(
    state.lectureV4 &&
    state.today?.plan_id &&
    state.today?.current?.day &&
    String(state.lectureV4.plan_id||"")===String(state.today.plan_id) &&
    Number(state.lectureV4.day)===Number(state.today.current.day)
  );
}
function v4UnavailableSection(section,index){
  const sections=state.lectureV4?.lecture_sections || [];
  const attempts=Number(section.retry_attempts||0),limit=Number(section.max_retry_attempts||3),retrying=Boolean(state.v4Retrying[section.section_id]);
  const canRetry=section.retryable!==false&&attempts<limit;
  const reason=section.failure_reason||"This section did not pass its content quality checks.";
  const nextReady=nextReadyV4SectionId(sections,index);
  return `<article id="v4-${esc(section.section_id)}" class="study-block v2-card lecture-section v4-lecture-section needs-attention"><div class="section-head"><div><p class="eyebrow">SECTION ${index+1} &middot; NEEDS ATTENTION</p><h2>${esc(section.title||section.concept_name)}</h2></div><span>${esc(section.estimated_minutes)} min</span></div>${v4SourceStatusCard(section,section.source_links||[])}<section class="v4-repair-panel"><h3>Improving this section</h3><p>${esc(reason)}</p><p class="muted">Repair attempt ${attempts} of ${limit}.</p><div class="v4-view-actions">${canRetry?`<button class="v2-primary" ${retrying?"disabled":""} onclick="retryLectureV4Section('${esc(section.section_id)}')">${retrying?"Repairing this section...":"Repair this section"}</button>`:`<span class="v4-retry-exhausted">No more automatic repair attempts are available.</span>`}<button class="v2-secondary" onclick="setDailyStage('lecture-v3')">Return to v3</button><button class="v2-secondary" ${nextReady?"":"disabled"} onclick="${nextReady?`document.getElementById('v4-${esc(nextReady)}')?.scrollIntoView({behavior:'smooth',block:'start'})`:""}">${nextReady?"Continue to next ready v4 section":"No ready v4 section yet"}</button></div></section></article>`;
}
function sourceGroundedLectureV4View(){
  const lecture=state.lectureV4;
  if(state.lectureV4Error)return shell(`${dailyHeader()}<section class="v2-card v4-state-card"><h2>Your lesson could not be prepared</h2><p>${esc(state.lectureV4Error)}</p><div class="v4-view-actions"><button class="v2-primary" onclick="loadLectureV4(true)">Try again</button></div></section>`);
  if(!lecture)return shell(`${dailyHeader()}<section class="v2-card profile-state"><div class="agent-orb">P</div><h2>Preparing your lesson</h2><p>${esc(state.lectureV4Status||"Pathly is preparing today's learning materials.")}</p><p class="muted">This page will update automatically when your lesson is ready.</p></section>`);
  const generationState=v4GenerationState(lecture),sections=lecture.lecture_sections||[],readyCount=sections.filter(section=>section.v4_status==="ready").length;
  if((generationState==="queued"||generationState==="generating")&&!readyCount){return shell(`${dailyHeader()}<section class="v2-card profile-state"><div class="agent-orb">P</div><h2>Preparing your first learning section</h2><p>${esc(state.lectureV4Status||"Pathly is building today's learning materials.")}</p><p class="generation-progress-label">You’ll begin as soon as this section is ready.</p><p class="muted">The next section will only be prepared after you complete this one.</p></section>`)};
  if(generationState==="failed")return shell(`${dailyHeader()}<section class="v2-card v4-state-card"><h2>Your lesson could not be generated</h2><p>The lesson did not finish preparing. You can try again without leaving this day.</p><div class="v4-view-actions"><button class="v2-primary" ${state.lectureV4Loading?"disabled":""} onclick="loadLectureV4(true)">${state.lectureV4Loading?"Trying again...":"Try again"}</button></div></section>`);
  const visibleSections=sections.filter(section=>section.v4_status!=="waiting_for_previous_section");
  const done=sections.filter(section=>state.v4SectionProgress[v4SectionKey(section)]).length,overview=lecture.lecture_overview||{},mode=lecture.generation_metadata?.generation_mode||"live";
  const cards=visibleSections.map((section,index)=>{const key=v4SectionKey(section);return section.v4_status==="ready"?v4ReadySection(section,index,Boolean(state.v4SectionProgress[key]),Boolean(state.v4Saving[key])):v4UnavailableSection(section,index,visibleSections)}).join("");
  setTimeout(()=>{if(state.dailyStage!=="lecture-v4")return;if(state.v4CurrentSectionId)document.getElementById(`v4-${state.v4CurrentSectionId}`)?.scrollIntoView({block:"start"});else if(state.v4ScrollPosition>0)window.scrollTo({top:state.v4ScrollPosition})},0);
  return shell(`${dailyHeader()}<section class="session-overview v2-card v4-overview"><div><p class="eyebrow">TODAY'S LESSON</p><h2>${esc(overview.title||"Your learning session")}</h2><p>${done}/${sections.length} sections complete</p><div class="session-progress-bar"><span style="width:${sections.length?Math.round(done/sections.length*100):0}%"></span></div></div></section><div class="daily-layout"><main><section class="study-session lecture-v4-sections">${cards}</section></main><aside class="daily-side">${chatPanel(true)}</aside></div>`);
}async function loadLectureV4(force=false){
  if(!state.today?.plan_id||!state.today?.current?.day)return state.lectureV4;
  clearV4Poll();
  if(!lectureV4MatchesToday())state.lectureV4=null;
  v4StaleRetryCount=0;
  state.lectureV4Loading=true;state.lectureV4Error=null;state.lectureV4Status=force?"Regenerating your source-grounded lecture...":"Checking your lecture...";render();
  try{
    if(!force){
      state.lectureV4=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/lecture-v4`);
      const phase=v4GenerationState(state.lectureV4);
      if(phase==="complete"){
        for(const [sectionId,value] of Object.entries(state.lectureV4.v4_progress||{}))state.v4SectionProgress[`${state.today.plan_id}:${state.today.current.day}:${sectionId}`]=value.status==="completed";
        for(const [answerKey,value] of Object.entries(state.lectureV4.v4_exercise_answers||{})){const [sectionId,questionId]=answerKey.split(":");const key=v4AnswerKey(sectionId,questionId);state.v4ExerciseAnswers[key]=value.answer_id;state.v4ExerciseResults[key]={answered:true,correct:Boolean(value.correct)};}
        return state.lectureV4;
      }
      if(phase==="queued"||phase==="generating"){state.lectureV4Status="Preparing your source-grounded lecture...";scheduleV4Poll();return state.lectureV4}
    }
    state.lectureV4=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/lecture-v4/generate`,{method:"POST",body:JSON.stringify({force})});
    const phase=v4GenerationState(state.lectureV4);
    state.lectureV4Status="Preparing your source-grounded lecture...";
    if(phase==="queued"||phase==="generating")scheduleV4Poll();
  }catch(error){state.lectureV4Error=error.message||"Source-Grounded Lecture View v4 is unavailable."}
  finally{state.lectureV4Loading=false;persist();render()}
  return state.lectureV4;
}
function syncDailyViewUrl(){
  const url=new URL(window.location.href);
  if(state.view==="today"&&state.dailyStage==="lecture-v4"){
    url.searchParams.set("daily_view","lecture-v4");
    url.searchParams.set("plan_id",state.today?.plan_id||state.currentPlan?.plan_id||state.selectedPlanId||"");
    url.searchParams.set("day",String(state.today?.current?.day||state.selectedDay||1));
  }else{
    url.searchParams.delete("daily_view");
    url.searchParams.delete("plan_id");
    url.searchParams.delete("day");
  }
  history.replaceState({},"",url);
}
function reviewLectureV4Sources(){
  if(!state.today?.plan_id)return;
  window.open(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/lecture-v4/source-links`,"_blank","noopener");
}
function toggleV4Section(sectionId){
  const key=`${state.today.plan_id}:${state.today.current.day}:${sectionId}`;
  if(state.v4Saving[key])return;
  const restoreScroll=window.scrollY;
  const completed=!state.v4SectionProgress[key];state.v4SectionProgress[key]=completed;state.v4Saving[key]=true;state.v4CurrentSectionId=sectionId;persist();render();
  api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/lecture-v4/sections/${encodeURIComponent(sectionId)}/complete`,{method:"POST",body:JSON.stringify({completed})})
    .then(async saved=>{state.v4SectionProgress[key]=saved.status==="completed";state.notice=completed?(saved.next_section_queued?"Next section is being prepared.":"Section completed."):"Section reopened.";if(saved.next_section_queued){state.lectureV4=null;await loadLectureV4();}})
    .catch(error=>{state.v4SectionProgress[key]=!completed;state.error=error.message})
    .finally(()=>{delete state.v4Saving[key];state.v4ScrollPosition=restoreScroll;persist();render();requestAnimationFrame(()=>window.scrollTo({top:restoreScroll,behavior:"instant"}))});
}
async function retryLectureV4Section(sectionId){
  if(state.v4Retrying[sectionId])return;
  state.v4Retrying[sectionId]=true;state.v4CurrentSectionId=sectionId;state.error=null;render();
  try{
    const queued=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/lecture-v4/sections/${encodeURIComponent(sectionId)}/retry`,{method:"POST",body:JSON.stringify({force:true})});
    state.lectureV4=queued;state.lectureV4Status="Repairing this source-grounded lecture...";state.notice="The section repair has started. This page will update automatically.";scheduleV4Poll();
  }catch(error){state.error=error.message||"This v4 section could not be repaired."}
  finally{delete state.v4Retrying[sectionId];persist();render()}
}async function setDailyStage(stage){
  const done=(state.pathProgress?.days||[]).find(x=>Number(x.day)===Number(state.today?.current?.day))?.quiz_attempt;
  if(done&&stage==="quiz"){state.notice="Completed days are read-only. Open the next unlocked day from the Activity Timeline.";state.dailyStage="content";render();return}
  if(stage!=="lecture-v4")clearV4Poll();
  state.dailyStage=stage==="quiz"?"quiz":(stage==="annotated"?"annotated":(stage==="lecture-v3"?"lecture-v3":(stage==="lecture-v4"?"lecture-v4":"content")));
  syncDailyViewUrl();
  persist();
  render();
  if(state.dailyStage==="quiz")await act(loadQuiz);
  if(state.dailyStage==="annotated"&&!state.annotatedSession)await act(()=>loadAnnotatedSession());
  if(state.dailyStage==="lecture-v3"&&!state.fullLecture)await loadFullLecture();
  if(state.dailyStage==="lecture-v4"){
    state.lectureV4Error=null;
    if(!lectureV4MatchesToday())state.lectureV4=null;
    await loadLectureV4();
  }
}
async function sendFeedback(type){await act(async()=>{await api(`/api/plans/${state.today.plan_id}/days/${state.today.current.day}/feedback`,{method:"POST",body:JSON.stringify({user_id:state.userId,feedback_type:type,concept_ids:state.dailyContent.topic_ids||[]})});state.notice="Feedback saved for this learning day."})}
async function loadChat(){state.chatMessages=await api(`/api/plans/${state.today.plan_id}/days/${state.today.current.day}/chat?user_id=${encodeURIComponent(state.userId)}`)}
function chatPanel(compact=false){
  const currentBlock=(state.dailyContent?.study_blocks||[]).find(b=>b.block_id===state.activeBlockId);
  const disabled=state.chatPending?"disabled":"";
  const history=[...state.chatMessages];
  if(!history.length)history.push({role:"assistant",body:"Hi — I’m Pathly. Ask me to explain a concept, unpack a source page, give an example, or check your reasoning.",citations:[],mode:"welcome"});
  if(state.chatPending)history.push({role:"assistant",body:"Thinking with today's lesson context...",citations:[],mode:"pending"});
  return `<section class="v2-card chat-workspace ${compact?"sidebar-chat":""}"><div class="chat-title"><div class="chat-avatar">P</div><div><p class="eyebrow">PATHLY ASSISTANT</p><h2>Chat about today’s lesson</h2><small>Ask anything about ${esc(currentBlock?.title||"this learning session")}</small></div><span class="chat-status"><i></i> Online</span></div><div class="chat-history" aria-live="polite">${history.map(m=>`<article class="${m.role} ${m.mode==="pending"?"pending":""}"><div class="chat-message-head"><span class="message-avatar">${m.role==="assistant"?"P":"You"}</span><b>${m.role==="assistant"?"Pathly":"You"}</b></div><p>${esc(m.body)}</p>${(m.citations||[]).length?`<small>${m.citations.length} source reference(s)</small>`:""}</article>`).join("")}</div><div class="quick-prompts">${[["simplify","Explain simply"],["life_example","Give an example"],["code_example","Show code"],["misconception","Check my reasoning"]].map(([id,label])=>`<button ${disabled} onclick="sendQuickChat('${id}','${label}')">${label}</button>`).join("")}</div>${state.chatError?`<div class="chat-error">${esc(state.chatError)}</div>`:""}<div class="chat-compose"><textarea id="chat-input" rows="2" placeholder="Message Pathly…" oninput="state.chatDraft=this.value">${esc(state.chatDraft)}</textarea><button class="chat-send" aria-label="Send message" title="Send message" ${disabled} onclick="sendChat()">${state.chatPending?"…":"↑"}</button></div></section>`
}
async function sendQuickChat(intent,message){await submitChat(message,intent)}
async function sendChat(){const message=String(state.chatDraft||$("#chat-input")?.value||"").trim();if(message)await submitChat(message,null)}
async function submitChat(message,intent){
  if(state.chatPending)return;
  const userMessage={role:"user",body:message,citations:[],mode:"user"};
  state.chatPending=true;state.chatError=null;state.chatDraft="";state.chatMessages.push(userMessage);render();
  try{
    const reply=await api('/api/chat',{method:'POST',body:JSON.stringify({user_id:state.userId,plan_id:state.today.plan_id,day:Number(state.today.current.day),message,intent,content_id:state.dailyContent.content_id,current_block_id:state.activeBlockId,completed_block_ids:(state.dailyContent.study_blocks||[]).filter(b=>b.progress_state?.status==='completed').map(b=>b.block_id),current_resource_id:null})});
    state.chatMessages.push(reply);
  }catch(e){state.chatError=e.message||"Pathly could not answer right now.";}
  finally{state.chatPending=false;persist();render();}
}
async function loadQuiz(){state.quiz=await api(`/api/plans/${state.today.plan_id}/days/${state.today.current.day}/quiz?user_id=${encodeURIComponent(state.userId)}`)}
function quizPanel(){if(state.quizResult)return quizResultPanel();if(!state.quiz)return `<section class="v2-card profile-state"><h2>Preparing a stable daily quiz...</h2></section>`;return `<section class="v2-card quiz-workspace"><div class="section-head"><div><p class="eyebrow">DAILY ASSESSMENT</p><h2>Check What You Learned</h2></div>${pill(state.quiz.cache_status||"stable")}</div>${state.quiz.questions.map((q,index)=>`<article class="quiz-question"><small>${index+1}/${state.quiz.questions.length} / ${esc(q.type)}</small><h3>${esc(q.prompt)}</h3>${q.options?.length?`<div class="quiz-options">${q.options.map(option=>`<label><input type="radio" name="${q.question_id}" value="${esc(option)}" onchange="captureQuizAnswer('${q.question_id}',this.value)"><span>${esc(option)}</span></label>`).join("")}</div>`:`<textarea rows="3" oninput="captureQuizAnswer('${q.question_id}',this.value)" placeholder="Write a short application..."></textarea>`}<label class="confidence">Confidence <input id="confidence-${q.question_id}" type="range" min="1" max="5" value="3"><span>1-5</span></label></article>`).join("")}<button class="v2-primary" onclick="submitQuiz()">Submit Quiz & Complete Day</button></section>`}
function captureQuizAnswer(id,value){state.quizAnswers[id]=value}
async function submitQuiz(){const missing=state.quiz.questions.filter(q=>!String(state.quizAnswers[q.question_id]||'').trim());if(missing.length){state.error='Answer every question before submitting.';render();return}await act(async()=>{const answers=state.quiz.questions.map(q=>({question_id:q.question_id,answer:state.quizAnswers[q.question_id],confidence:Number($(`#confidence-${q.question_id}`)?.value||3),time_seconds:0}));state.quizResult=await api(`/api/plans/${state.today.plan_id}/days/${state.today.current.day}/quiz-attempts`,{method:'POST',body:JSON.stringify({user_id:state.userId,answers,duration_seconds:0})});state.pathProgress=state.quizResult.path_progress;state.adaptationProposal=null})}
function quizResultPanel(){const r=state.quizResult,next=r.path_progress?.next_day;return `<section class="v2-card quiz-result"><p class="eyebrow">DAY COMPLETE</p><h1>${Math.round(r.score)}%</h1><p>Average confidence ${esc(r.confidence)}/5</p><div class="result-grid"><div><span>Correct</span><b>${r.results.filter(x=>x.correct).length}/${r.results.length}</b></div><div><span>Weak concepts</span><b>${r.weak_concepts.length?esc(r.weak_concepts.join(', ')):'None detected'}</b></div><div><span>Next day</span><b>${next?`Day ${next.day} unlocked`:'Path complete'}</b></div></div>${r.results.map(x=>`<article class="answer-result ${x.correct?'correct':'incorrect'}"><b>${x.correct?'Correct':'Review needed'} / ${esc(x.concept_id)}</b><p>${esc(x.explanation)}</p></article>`).join('')}<p class="muted">These learning signals are saved for the future Adaptation Agent stage.</p><div class="scope-actions">${next?`<button class="v2-primary" onclick="openLearningDay(${next.day})">Start Day ${next.day}</button>`:''}<button class="v2-secondary" onclick="state.mapMode='timeline';go('dashboard')">See Updated Timeline</button></div></section>`}
async function loadAdaptation(){if(!state.adaptationProposal)state.adaptationProposal=await api(`/api/paths/${state.today.path_id}/adaptation-proposals`,{method:'POST',body:JSON.stringify({user_id:state.userId})})}
function adaptationPanel(){const p=state.adaptationProposal;if(!p)return `<section class="v2-card profile-state"><h2>Analyzing learning signals...</h2></section>`;if(p.status!=="pending")return `<section class="v2-card centered"><h1>${p.status==="accepted"?'Path Updated':'Original Path Kept'}</h1><p>${p.status==="accepted"?`Plan v${p.new_plan_version} is now active. Completed days remain read-only.`:'No plan version was created.'}</p><button class="v2-primary" onclick="state.mapMode='timeline';go('dashboard')">View Activity Timeline</button></section>`;return `<section class="v2-card adaptation-review"><div class="section-head"><div><p class="eyebrow">ADAPTATION AGENT</p><h2>Review Before Anything Changes</h2></div>${pill('pending confirmation')}</div><div class="adapt-stats"><div><span>Before</span><b>${p.before_total_minutes}m</b></div><div><span>Impact</span><b>${p.minute_impact>=0?'+':''}${p.minute_impact}m</b></div><div><span>After</span><b>${p.after_total_minutes}m</b></div></div><div class="adapt-actions">${p.actions.map(a=>`<article><div>${pill(a.action,a.action==="add_review"?'red':'green')}<b>${esc(a.concept_id||'Current path')}</b></div><p>${esc(a.reason)}</p><small>${esc((a.signals||[]).join(', '))}${a.target_day?` / Day ${a.target_day}`:''}</small></article>`).join('')}</div><p>${esc(p.reason)}</p><label>Review minutes if accepted <input id="adapt-minutes" type="number" min="5" max="120" value="20"></label><div class="scope-actions"><button class="v2-primary" onclick="decideAdaptation('accept')">Accept Changes</button><button class="v2-secondary" onclick="decideAdaptation('modify')">Accept With My Minutes</button><button class="v2-secondary" onclick="decideAdaptation('reject')">Keep Original Plan</button></div></section>`}
async function decideAdaptation(decision){await act(async()=>{const minutes=Number($("#adapt-minutes")?.value||20);state.adaptationProposal=await api(`/api/adaptation-proposals/${state.adaptationProposal.proposal_id}/decision`,{method:'POST',body:JSON.stringify({user_id:state.userId,decision,modifications:decision==='modify'?{review_minutes:minutes}:{}})});if(state.adaptationProposal.plan){await loadPlans();state.currentPlan=state.plans.find(x=>x.plan_id===state.adaptationProposal.plan.plan_id)||state.plans[0];await ensurePathProgress(state.currentPlan)}})}
function rescheduleConfirmation(){
  const p=state.reschedulePreview;if(!p||!p.requires_confirmation)return "";
  const last=p.proposed_day_dates?.[p.proposed_day_dates.length-1];
  return `<div class="deadline-confirm"><p class="eyebrow">DEADLINE IMPACT</p><h3>This shift crosses the deadline</h3><p>The final scheduled day would move to ${esc(last?.scheduled_date)} instead of the confirmed deadline ${esc(p.deadline)}. Nothing has changed yet.</p><div class="scope-actions"><button class="v2-primary" onclick="confirmReschedule()">Confirm Shift</button><button class="v2-secondary" onclick="cancelReschedule()">Keep Current Dates</button></div></div>`;
}
async function previewReschedule(){
  const input=$("#reschedule-date");if(!input?.value)return;
  await act(async()=>{
    const result=await api(`/api/paths/${encodeURIComponent(state.today.path_id)}/days/${state.today.current.day}/reschedule`,{method:"POST",body:JSON.stringify({user_id:state.userId,new_date:input.value,confirm_deadline_impact:false})});
    if(result.requires_confirmation)state.reschedulePreview=result;
    else{state.notice="The remaining learning dates were shifted together.";await loadTodayData()}
  });
}
async function confirmReschedule(){
  const p=state.reschedulePreview;if(!p)return;
  const row=p.proposed_day_dates.find(x=>Number(x.day)===Number(state.today.current.day));
  await act(async()=>{
    await api(`/api/paths/${encodeURIComponent(state.today.path_id)}/days/${state.today.current.day}/reschedule`,{method:"POST",body:JSON.stringify({user_id:state.userId,new_date:row.scheduled_date,confirm_deadline_impact:true})});
    state.notice="The deadline impact was confirmed and the remaining dates were shifted.";await loadTodayData();
  });
}
function cancelReschedule(){state.reschedulePreview=null;render()}
function library(){
  return shell(`<div class="page-head"><div><p class="eyebrow">PRIVATE LIBRARY</p><h1>My Learning Materials</h1><p>Each document belongs only to this anonymous secure space and is never written to the public KG.</p></div><label class="upload big">Upload PDFs<input type="file" multiple accept=".pdf,application/pdf" onchange="uploadFiles(this.files)"></label></div>
  <section class="v2-card">${state.documents.length?`<div class="library-grid">${state.documents.map(d=>`<article><div class="file-icon">PDF</div><div><h3>${esc(d.display_name)}</h3><p>${esc(d.parse_status)}  /  ${d.page_count||"?"} pages  /  ${Math.ceil((d.size_bytes||0)/1024)} KB</p>${pill(d.index_status||"pending",d.index_status==="ready"?"green":"")}</div><div><button onclick="retryDoc('${d.document_id}')">Retry</button><button class="danger" onclick="deleteDoc('${d.document_id}')">Delete</button></div></article>`).join("")}</div>`:`<div class="empty">No materials uploaded yet</div>`}</section>`);
}
async function retryDoc(id){await act(async()=>{await api(`/api/documents/${id}/retry`,{method:"POST",body:JSON.stringify({user_id:state.userId})});await loadDocuments()})}
async function deleteDoc(id){if(!confirm("Deleting this document also removes its private index and mappings. Continue?"))return;await act(async()=>{await api(`/api/documents/${id}?user_id=${encodeURIComponent(state.userId)}`,{method:"DELETE"});await loadDocuments()})}
const PROFILE_LABELS={mathematical_ability:"Mathematical foundation",programming_ability:"Programming foundation",abstract_thinking:"Abstract thinking",logical_reasoning:"Logical reasoning",general_learning_foundation:"General learning foundation",learning_style:"Explanation style",preferred_examples:"Explanation formats",pace_preference:"Long-term pace",self_regulation:"Recovery after interruptions",interest_tags:"Example domains"};
function profileValue(value){return Array.isArray(value)?(value.length?value.join(", "):"Not set"):(value??"Not set")}
function profileTraitGrid(values,score=false){
  return `<div class="long-profile-grid">${Object.entries(values).map(([key,value])=>`<div><span>${esc(PROFILE_LABELS[key]||key)}</span><b>${esc(profileValue(value))}${score?"/5":""}</b></div>`).join("")}</div>`;
}
function profileEvidence(records={}){
  const visible=Object.entries(records).filter(([key])=>key!=="motivation_baseline");
  if(!visible.length)return `<div class="empty compact">No inference evidence has been recorded yet.</div>`;
  return `<div class="evidence-list">${visible.map(([key,record])=>`<article><div><b>${esc(PROFILE_LABELS[key]||key)}</b><small>${esc(record.reason||"Confirmed learner information")}</small></div><div>${pill(record.confirmed?"confirmed":"inferred",record.confirmed?"green":"")}<small>${Math.round(Number(record.confidence||0)*100)}% confidence  /  ${esc(record.evidence_source||record.source||"profile")}</small></div></article>`).join("")}</div>`;
}
function profilePage(){
  const head=`<div class="page-head"><div><p class="eyebrow">LEARNER PROFILE</p><h1>Long-Term Learner Profile</h1><p>Stable foundations and preferences are reused across learning paths. Goals, target mastery and timing stay with each individual path.</p></div></div>`;
  if(!state.profileLoaded)return shell(`${head}<section class="v2-card profile-state"><div class="agent-orb">P</div><h2>Loading your saved profile...</h2></section>`);
  if(state.profileError)return shell(`${head}<section class="v2-card profile-state"><h2>Profile temporarily unavailable</h2><p>${esc(state.profileError)}</p><button class="v2-primary" onclick="go('profile')">Try Again</button></section>`);
  if(!state.profile)return shell(`${head}<section class="v2-card profile-state"><h2>No long-term profile yet</h2><p>Complete your first onboarding to create reusable foundations and learning preferences.</p><button class="v2-primary" onclick="newPath()">Create My First Path</button></section>`);
  const p=state.profile,c=p.cognitive_traits||{},a={...(p.affective_defaults||{})};delete a.motivation_baseline;delete a.confidence_baseline;delete a.anxiety_baseline;delete a.daily_minutes;delete a.daily_time_minutes;
  const updated=p.updated_at||p.created_at;
  const demoCards=state.demoUsers.length?`<section class="v2-card demo-profile-switcher"><div class="section-head"><div><p class="eyebrow">CONTROLLED PROFILE COMPARISON</p><h2>Two Local Learners</h2></div><span>Plans and progress stay separate</span></div><div class="demo-profile-grid">${state.demoUsers.map(user=>`<article class="${user.user_id===state.userId?"active":""}"><small>${esc(user.level.toUpperCase())}</small><h3>${esc(user.display_name)}</h3><p>${user.level==="foundation"?"Concrete-first, guided practice, education examples.":"Model-first, compact derivations, research and code examples."}</p><button class="v2-secondary" ${user.user_id===state.userId?"disabled":""} onclick="switchDemoUser('${esc(user.user_id)}')">${user.user_id===state.userId?"Current learner":"Switch to this learner"}</button></article>`).join("")}</div></section>`:"";
  return shell(`${head}${demoCards}<section class="profile-summary"><div><span>Profile version</span><b>v${esc(p.profile_version||2)}</b></div><div><span>Reusable dimensions</span><b>${Object.keys(c).length+Object.keys(a).length}</b></div><div><span>Last updated</span><b>${updated?esc(new Date(updated).toLocaleDateString()):"Saved"}</b></div><button class="v2-primary" onclick="newPath()">Review Profile in a New Path</button></section>
  <div class="profile-detail-cols"><section class="v2-card"><p class="eyebrow">COGNITIVE FOUNDATIONS</p><h2>How You Approach New Concepts</h2>${profileTraitGrid(c,true)}</section><section class="v2-card"><p class="eyebrow">LEARNING PREFERENCES</p><h2>How Pathly Should Teach You</h2>${profileTraitGrid(a,false)}</section></div>
  <section class="v2-card profile-evidence"><div class="section-head"><div><p class="eyebrow">EXPLAINABILITY</p><h2>Why Pathly Holds These Values</h2></div><span>Every inferred value keeps its source and confidence.</span></div>${profileEvidence(p.inference_records||{})}</section>`);
}
function render(){
  const app=$("#app"); if(!app)return;

  if(state.view==="dashboard")app.innerHTML=dashboard();
  else if(state.view==="today")app.innerHTML=todayLearning();
  else if(state.view==="library")app.innerHTML=library();
  else if(state.view==="profile")app.innerHTML=profilePage();
  else if(state.view==="controlled-evaluation")app.innerHTML=controlledEvaluationPage();
  else app.innerHTML=workspace();
  restoreMapViewport();
  app.querySelectorAll("[data-daily-stage]").forEach(tab=>tab.addEventListener("click",()=>setDailyStage(tab.dataset.dailyStage)));
  app.querySelectorAll("[data-delete-path]").forEach(button=>button.addEventListener("click",event=>{event.preventDefault();event.stopPropagation();requestDeletePath(button.dataset.deletePath)}));
  queueMathTypeset(app);
}
function queueMathTypeset(root){
  if(!window.MathJax?.typesetPromise)return;
  try{window.MathJax.typesetClear?.([root]);window.MathJax.typesetPromise([root]).catch(()=>{});}catch(_){/* MathJax may still be loading. */}
}
Object.assign(window,{state,go,newPath,startFreshLearner,switchDemoUser,goOnboardingStep,uploadFiles,toggleDoc,toggleReview,beginOnboarding,confirmInterpretationAndBegin,confirmMapReview,setReviewEdgeSource,connectReviewEdge,removeReviewEdge,answer,multiAnswer,confirmProfile,generateWorkload,createDecision,selectCapacityAdjustment,confirmCapacityAdjustment,chooseStrategy,confirmStrategyChoice,proposeScope,decideScope,confirmPath,selectPlan,requestDeletePath,cancelDeletePath,confirmDeletePath,openLearningDay,setDailyStage,sendFeedback,sendQuickChat,sendChat,captureQuizAnswer,submitQuiz,decideAdaptation,previewReschedule,confirmReschedule,cancelReschedule,retryDoc,deleteDoc,loadAnnotatedSession,loadFullLecture,toggleFullLectureSection,selectAnnotatedReading,refreshAnnotatedSession,completeAnnotatedReading,submitAnnotatedExercise,loadSourceContext,askAboutReading,loadLectureV4,reviewLectureV4Sources,toggleV4Section,retryLectureV4Section,setV4SourcePage,loadControlledEvaluationOptions,loadControlledEvaluationRuns,exportControlledEvaluationRuns,setControlledEvaluationField,runControlledEvaluation,render});
render();

async function startSecureSession(){
  state.busy=true;state.error=null;state.busyLabel="Preparing your secure learning space...";
  document.body.classList.add("pathly-busy");
  showBusy(state.busyLabel);
  try{
    const session=await api("/api/sessions/anonymous",{method:"POST",body:JSON.stringify({})});
    const previousUserId=state.userId;
    state.userId=session.user_id;
    if(previousUserId&&previousUserId!==session.user_id){
      state.draftId=null;state.draft=null;state.documents=[];state.plans=[];state.currentPlan=null;
      state.interpretation=null;state.estimate=null;state.decision=null;state.pathProgress=null;
      state.today=null;state.dailyContent=null;state.selectedDay=null;
      if((state.view==="today"||state.view==="dashboard")&&requestedDailyView!=="lecture-v4")state.view="workspace";
    }
    persist();
  }catch(error){
    state.error="Unable to create a secure Pathly session. Check that the local service is running, then retry.";
    return;
  }finally{
    state.busy=false;state.busyLabel="";
    document.body.classList.remove("pathly-busy");
    hideBusy();
    render();
  }
  await hydrate();
}
startSecureSession();
window.startSecureSession=startSecureSession;












async function loadAnnotatedSession(force=false){
  if(!state.today?.plan_id||!state.today?.current?.day)return null;
  state.annotatedError=null;
  try{
    const base=`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/annotated-session`;
    state.annotatedSession=force
      ? await api(base,{method:"POST",body:JSON.stringify({user_id:state.userId,force:true})})
      : await api(`${base}?user_id=${encodeURIComponent(state.userId)}`);
    state.activeReadingId=state.activeReadingId||(state.annotatedSession.reading_sequence||[])[0]?.reading_id||null;
  }catch(e){
    state.annotatedError=e.message||"Annotated Source View is unavailable.";
  }
  return state.annotatedSession;
}
function sourceBadge(type){return pill(type==="private_document"?"private PDF":(type==="public_rag"?"public RAG":"generated"),type==="private_document"?"green":"")}
function readingResponseValue(id){return state.readingResponses[id]||""}
function exerciseResponseValue(id){return state.exerciseResponses[id]||{answers:{}}}
function sourceContextPanel(reading){
  const ctx=state.sourceContexts[reading.reading_id];
  if(!state.sourceContextOpen[reading.reading_id])return "";
  if(!ctx)return `<section class="source-context-panel"><div class="section-head compact"><div><p class="eyebrow">SOURCE CONTEXT</p><h3>Loading source context</h3></div></div><p>Pathly is loading nearby source chunks for this reading.</p></section>`;
  const chunks=(ctx.context_chunks||[]).map(chunk=>`<article class="source-context-chunk ${chunk.selected?"selected":""}"><div><b>${chunk.selected?"Selected excerpt":"Nearby context"}</b><span>${chunk.page_start?`Page ${esc(chunk.page_start)}${chunk.page_end&&chunk.page_end!==chunk.page_start?`-${esc(chunk.page_end)}`:""}`:"Retrieved chunk"}</span></div><p>${esc(chunk.text)}</p></article>`).join("");
  const targets=(ctx.annotation_targets||[]).map(x=>`<li><b>${esc(x.label)}</b><span>${esc(x.instruction)}</span></li>`).join("");
  return `<section class="source-context-panel"><div class="section-head compact"><div><p class="eyebrow">SOURCE CONTEXT</p><h3>${esc(ctx.document_title||ctx.source_label||"Source material")}</h3><small>${esc(ctx.reading_scope?.label||"selected context")}</small></div>${sourceBadge(ctx.source_type)}</div><div class="source-access-note">${esc(ctx.access?.reason||"Only the selected source context is shown here.")}</div>${targets?`<ul class="annotation-targets">${targets}</ul>`:""}<div class="source-context-list">${chunks}</div></section>`;
}
function annotatedReadingCard(reading,index){
  const done=reading.progress_state?.status==="completed";
  const active=state.activeReadingId===reading.reading_id;
  const focus=(reading.focus_questions||[]).map(q=>`<li>${esc(q)}</li>`).join("");
  const terms=(reading.pathly_annotation?.key_terms||reading.key_terms||[]).map(t=>`<li><b>${esc(t.term)}</b><span>${esc(t.meaning)}</span></li>`).join("");
  const expansion=reading.teaching_expansion||{};
  const walkthrough=(reading.source_walkthrough||[]).map(step=>`<article class="walkthrough-step"><div><b>Source line ${esc(step.step)}</b><p>${esc(step.source_line)}</p></div><div><h4>What this means</h4><p>${esc(step.what_it_means)}</p><h4>Why it matters</h4><p>${esc(step.why_it_matters)}</p><small>${esc(step.check_yourself)}</small></div></article>`).join("");
  const readWay=(reading.pathly_annotation?.read_this_way||[]).map(x=>`<li>${esc(x)}</li>`).join("");
  const traps=(expansion.common_traps||[]).map(x=>`<li>${esc(x)}</li>`).join("");
  return `<article class="annotated-reading ${active?"active":""} ${done?"completed":""}"><div class="annotated-reading-head" onclick="selectAnnotatedReading('${esc(reading.reading_id)}')"><span>${index+1}</span><div><p class="eyebrow">${esc(reading.source_type||"source")}</p><h3>${esc(reading.title||reading.section_title||"Annotated source")}</h3><small>${esc(reading.estimated_minutes)} min / ${esc(reading.reading_scope?.label||"selected excerpt")}</small></div><b>${done?"completed":"open"}</b></div>${active?`<div class="annotated-reading-body"><div class="source-summary">${sourceBadge(reading.source_type)}<p>${esc(reading.pathly_annotation?.plain_explanation||"This source is the primary material for this part of the lesson.")}</p></div><section class="teaching-expansion"><h4>First, learn the idea</h4><p>${esc(expansion.concept_intro||reading.pathly_annotation?.plain_explanation||"")}</p><h4>Mental model</h4><p>${esc(expansion.mental_model||"Ask what goes in, what changes, and what comes out.")}</p><h4>How the concept works in this material</h4><p>${esc(expansion.worked_interpretation||reading.pathly_annotation?.teaching_note||"")}</p><h4>Where this concept is used</h4><p>${esc(expansion.source_to_goal||reading.pathly_annotation?.why_it_matters||"")}</p>${traps?`<div class="common-traps"><b>Common traps</b><ul>${traps}</ul></div>`:""}</section><section class="source-reader"><div class="section-head compact"><div><p class="eyebrow">SOURCE EXCERPT</p><h3>${esc(reading.document_title||reading.source_label)}</h3></div><span>${esc(reading.reading_scope?.label||"retrieved excerpt")}</span></div><blockquote>${esc(reading.cleaned_excerpt||"No clean excerpt was available for this source.")}</blockquote></section>${walkthrough?`<section class="source-walkthrough"><h3>Annotated walkthrough</h3>${walkthrough}</section>`:""}${sourceContextPanel(reading)}<div class="annotation-panel"><h4>Read this way</h4>${readWay?`<ol>${readWay}</ol>`:`<p>${esc(reading.pathly_annotation?.read_for||"Identify the definition, mechanism, use case, and limitation.")}</p>`}</div>${focus?`<h4>Focus questions</h4><ul>${focus}</ul>`:""}${terms?`<h4>Key terms</h4><ul class="key-term-list">${terms}</ul>`:""}<label class="inline-label">Your reading note<textarea rows="4" oninput="state.readingResponses['${esc(reading.reading_id)}']=this.value" placeholder="${esc(reading.learner_task?.placeholder||"Write one useful takeaway from this source...")}">${esc(readingResponseValue(reading.reading_id))}</textarea></label><div class="block-actions"><button class="v2-secondary" onclick="loadSourceContext('${esc(reading.reading_id)}')">View source context</button><button class="v2-secondary" onclick="askAboutReading('${esc(reading.reading_id)}')">Ask about this concept</button><button class="v2-primary" onclick="completeAnnotatedReading('${esc(reading.reading_id)}')">${done?"Update study note":"Mark concept studied"}</button></div></div>`:""}</article>`;
}
function conceptBridgeCard(bridge){return `<article class="concept-bridge"><h4>${esc(bridge.title||bridge.display_name||bridge.concept_label)}</h4><p>${esc(bridge.explanation)}</p>${bridge.learner_takeaway?`<p><b>Takeaway:</b> ${esc(bridge.learner_takeaway)}</p>`:""}${(bridge.prerequisites||[]).length?`<small>Prerequisites: ${esc(bridge.prerequisites.join(", "))}</small>`:""}</article>`}
function exerciseAnswerValue(exerciseId, questionId){return (state.exerciseResponses[exerciseId]?.answers||{})[questionId]}
function setExerciseAnswer(exerciseId, questionId, value, multi=false){
  const current=state.exerciseResponses[exerciseId]||{answers:{}};
  if(multi){
    const arr=Array.isArray(current.answers[questionId])?[...current.answers[questionId]]:[];
    const idx=arr.indexOf(value);
    if(idx>=0)arr.splice(idx,1);else arr.push(value);
    current.answers[questionId]=arr;
  }else current.answers[questionId]=value;
  state.exerciseResponses[exerciseId]=current;
  render();
}
function objectiveQuestion(exercise, question, index){
  const value=exerciseAnswerValue(exercise.exercise_id, question.question_id);
  const result=(state.exerciseResults[exercise.exercise_id]?.grading?.results||[]).find(x=>x.question_id===question.question_id);
  const options=(question.options||[]).map(option=>{
    const checked=question.question_type==="multi_select"?Array.isArray(value)&&value.includes(option.id):value===option.id;
    const type=question.question_type==="multi_select"?"checkbox":"radio";
    return `<label class="objective-option ${checked?"selected":""}"><input type="${type}" name="${esc(question.question_id)}" ${checked?"checked":""} onchange="setExerciseAnswer('${esc(exercise.exercise_id)}','${esc(question.question_id)}','${esc(option.id)}',${question.question_type==="multi_select"})"><span>${esc(option.text)}</span></label>`;
  }).join("");
  return `<article class="objective-question ${result?result.correct?"correct":"incorrect":""}"><div><b>Question ${index+1}</b>${result?`<span>${result.correct?"Correct":"Review"}</span>`:""}</div><p>${esc(question.prompt)}</p><div class="objective-options">${options}</div>${result?`<p class="objective-feedback">${esc(result.explanation)}</p>`:""}</article>`;
}
function exerciseCard(exercise){
  const result=state.exerciseResults[exercise.exercise_id];
  const questions=exercise.questions||[];
  const answered=questions.filter(q=>exerciseAnswerValue(exercise.exercise_id,q.question_id)!==undefined).length;
  return `<article class="annotated-exercise objective-exercise"><div><p class="eyebrow">${esc(exercise.exercise_type||"objective check")}</p><h3>${esc(exercise.title||"Concept check")}</h3><small>${answered}/${questions.length} answered</small></div><p>${esc(exercise.prompt)}</p>${(exercise.instructions||[]).length?`<ul>${exercise.instructions.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:""}<div class="objective-question-list">${questions.map((q,i)=>objectiveQuestion(exercise,q,i)).join("")}</div><button class="v2-primary" ${answered<questions.length?"disabled":""} onclick="submitAnnotatedExercise('${esc(exercise.exercise_id)}')">Submit objective check</button>${result?`<div class="exercise-result ${result.grading?.passed?"passed":"needs-review"}"><b>Score: ${Math.round(Number(result.grading?.score||0)*100)}%</b><p>${esc(result.grading?.passed?"Passed. You can apply this concept in the current topic.":"Review the concept notes and try again.")}</p><ul>${(result.grading?.results||[]).map(x=>`<li>${esc(x.question_id)}: ${x.correct?"correct":"incorrect"}</li>`).join("")}</ul></div>`:""}</article>`;
}
function annotatedSourceView(){
  const c=state.annotatedSession;
  if(state.annotatedError)return `<section class="v2-card"><h2>Annotated Source View is unavailable</h2><p>${esc(state.annotatedError)}</p><button class="v2-primary" onclick="refreshAnnotatedSession()">Try again</button></section>`;
  if(!c)return `<section class="v2-card profile-state"><div class="agent-orb">P</div><h2>Preparing Annotated Source View</h2><p>Pathly is connecting today's schedule to source excerpts and exercises.</p><button class="v2-primary" onclick="refreshAnnotatedSession()">Load Source View</button></section>`;
  const overview=c.session_overview||{};
  const progress=c.annotated_progress||{};
  return `<section class="annotated-overview v2-card"><div><p class="eyebrow">ANNOTATED SOURCE VIEW V2</p><h2>${esc(overview.title||"Source-guided learning session")}</h2><p>${esc(overview.learning_goal||overview.opening_hook||"Use source materials to learn today's concepts.")}</p></div><div class="session-progress-ring small"><b>${Math.round(Number(progress.fraction||0)*100)}%</b><span>${esc(progress.completed_readings||0)}/${esc(progress.total_readings||0)} sources</span></div></section><div class="annotated-layout"><main><section class="v2-card"><div class="section-head"><div><p class="eyebrow">CONCEPT-FIRST READING</p><h2>Concept-focused source lesson</h2></div><button class="v2-secondary" onclick="refreshAnnotatedSession(true)">Regenerate v2</button></div>${(c.reading_sequence||[]).map(annotatedReadingCard).join("")||`<p class="muted">No source-backed reading units are available for this day.</p>`}</section><section class="v2-card"><p class="eyebrow">CONCEPT BRIDGES</p><h2>How these sources connect to the concepts</h2><div class="bridge-grid">${(c.concept_bridges||[]).map(conceptBridgeCard).join("")||`<p class="muted">No concept bridge was generated.</p>`}</div></section><section class="v2-card"><p class="eyebrow">CONCEPT CHECK</p><h2>Exercises</h2><div class="exercise-list">${(c.guided_exercises||[]).map(exerciseCard).join("")||`<p class="muted">No exercises were generated for this source-first view.</p>`}</div></section></main><aside class="daily-side">${chatPanel(true)}<section class="v2-card current-source"><p class="eyebrow">SOURCE COVERAGE</p><h2>Evidence used</h2><p>${esc(c.generation_metadata?.private_rag_chunks||0)} private chunk(s), ${esc(c.generation_metadata?.public_rag_chunks||0)} public chunk(s)</p><p>${esc(c.generation_metadata?.generation_mode||"fallback")}</p></section></aside></div>`;
}
function selectAnnotatedReading(id){state.activeReadingId=id;render()}
async function refreshAnnotatedSession(force=false){await act(()=>loadAnnotatedSession(force))}
async function completeAnnotatedReading(id){
  await act(async()=>{
    const result=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/annotated-session/readings/${encodeURIComponent(id)}/complete`,{method:"POST",body:JSON.stringify({user_id:state.userId,status:"completed",response:{note:state.readingResponses[id]||""}})});
    state.annotatedSession=result.session;
    state.notice="Reading progress saved.";
  });
}
async function submitAnnotatedExercise(id){
  await act(async()=>{
    const answer=state.exerciseResponses[id]||{answers:{}};
    const result=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/annotated-session/exercises/${encodeURIComponent(id)}/submit`,{method:"POST",body:JSON.stringify({user_id:state.userId,answer})});
    state.exerciseResults[id]=result;
    state.notice=`Objective check submitted: ${Math.round(Number(result.grading?.score||0)*100)}%.`;
  });
}
async function loadSourceContext(id){
  state.sourceContextOpen[id]=true;
  render();
  if(!state.sourceContexts[id]){
    await act(async()=>{
      state.sourceContexts[id]=await api(`/api/plans/${encodeURIComponent(state.today.plan_id)}/days/${state.today.current.day}/annotated-session/readings/${encodeURIComponent(id)}/source-context?user_id=${encodeURIComponent(state.userId)}`);
    });
  }else render();
}
function askAboutReading(id){
  const reading=(state.annotatedSession?.reading_sequence||[]).find(x=>x.reading_id===id);
  state.chatDraft=reading?`Help me understand this concept material: ${reading.title}. ${reading.pathly_annotation?.read_for||""}`:"Help me understand this source.";
  render();
}




















