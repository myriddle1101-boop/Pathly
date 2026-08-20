from fastapi.testclient import TestClient

import pathly_server


def read_script():
    return open("pathly-app.js", encoding="utf-8").read()


def read_css():
    return open("pathly-ui.css", encoding="utf-8").read()


def test_home_uses_real_v2_workspace_assets():
    client = TestClient(pathly_server.app)
    html = client.get("/").text
    assert "pathly-app.js?v=151" in html
    assert "pathly-ui.css?v=136" in html
    assert 'src="app.js' not in html
    assert client.get("/pathly-app.js?v=48").status_code == 200
    assert client.get("/pathly-ui.css?v=48").status_code == 200


def test_frontend_connects_complete_o1_to_o6_flow():
    script = read_script()
    for text in [
        "/api/onboarding-drafts",
        "/api/goal-interpretations",
        "/api/workload-estimates",
        "/api/feasibility-decisions",
        "/schedule",
        "Activity Timeline",
    ]:
        assert text in script


def test_responsive_timeline_and_private_library_are_present():
    css = read_css()
    script = read_script()
    assert ".map-v2{display:none}" in css
    assert "timeline-v2" in css
    assert "Private Learning Space" in script
    assert "Your materials are never added to the public knowledge graph" in script


def test_goal_sources_step_is_vertical_ordered_flow():
    script = read_script()
    css = read_css()
    goal = script.split("function goalStep()", 1)[1].split("function interpretationStep", 1)[0]
    assert 'class="goal-flow"' in goal
    assert "Describe the outcome" in goal
    assert "Upload your own materials" in goal
    assert "Choose what Pathly should use" in goal
    assert goal.index("Describe the outcome") < goal.index("Upload your own materials") < goal.index("Choose what Pathly should use")
    assert "source-cards" in goal
    assert "state.sourceMode=this.value;render()" in goal
    assert ".goal-flow{display:grid;gap:18px;width:100%;max-width:none}" in css
    assert ".flow-step .goal-textarea{min-height:118px;resize:vertical}" in css
    assert 'class="goal-textarea" rows="3"' in goal
    assert ".source-cards{grid-template-columns:repeat(3" in css


def test_goal_mapping_and_scope_changes_require_explicit_confirmation():
    script = read_script()
    assert "Candidate mappings are never accepted automatically" in script
    assert "confirmInterpretation" in script
    assert "accepted_private_concepts" in script
    assert "scope_change_draft" in script
    assert "Accept Partial Goal" in script
    assert "Reject and Restore Original Goal" in script


def test_multi_pdf_upload_and_processing_poll_are_present():
    script = read_script()
    assert 'type="file" multiple accept=".pdf,application/pdf"' in script
    assert "Promise.allSettled(files.map" in script
    assert "scheduleDocumentPoll" in script
    assert "Processing files are updated automatically" in script or "Uploaded PDFs stay private" in script


def test_onboarding_question_controls_have_selected_state():
    script = read_script()
    assert 'class="${value==v?"selected":""}"' in script
    assert 'class="${(value||[]).includes(o.value)?"selected":""}"' in script
    assert 'class="${value===o.value?"selected":""}"' in script
    assert "interest_tags" in script
    assert "chooses the application domain for examples" in script
    assert 'interest_tags:["Example domains","affective_defaults","interest_tags"]' in script


def test_stepper_nodes_are_clickable_only_when_reachable():
    script = read_script()
    steps = script.split("function steps(active,reachable=active)", 1)[1].split("function goalStep", 1)[0]
    assert "goOnboardingStep" in steps
    assert "i<=reachable" in steps
    assert "disabled" in steps


def test_capacity_strategy_cards_use_two_step_confirmation():
    script = read_script()
    choose = script.split("function chooseStrategy", 1)[1].split("async function confirmStrategyChoice", 1)[0]
    confirm = script.split("async function confirmStrategyChoice", 1)[1].split("async function confirmPath", 1)[0]
    step = script.split("function decisionStep()", 1)[1].split("function scopeBuilder()", 1)[0]
    assert "state.pendingStrategy={...option,strategy}" in choose
    assert "strategyOption(strategy)" in choose
    assert "/api/" not in choose
    assert "Confirm This Choice" in step
    assert "CONFIRM BEFORE APPLYING" in step
    assert "Current allocation" in step
    assert "After confirmation" in step
    assert "optional consolidation" in step
    assert "selected_strategy:strategy" in confirm
    assert "pending.suggested_days" in confirm
    assert "pending.required_daily_minutes" in confirm


def test_toasts_are_fixed_and_dismissible():
    css = read_css()
    script = read_script()
    assert "v2-toast-stack" in script
    assert "position:fixed" in css
    assert "Dismiss" in script
    assert "state.error=null;render()" in script
    assert "state.notice=null;render()" in script


def test_dashboard_has_map_timeline_toggle():
    script = read_script()
    css = read_css()
    dashboard = script.split("function dashboard()", 1)[1].split("function selectPlan", 1)[0]
    assert 'class="${state.mapMode==="map"?"active":""}"' in dashboard
    assert 'class="${state.mapMode==="timeline"?"active":""}"' in dashboard
    assert 'aria-pressed="${state.mapMode==="map"}"' in dashboard
    assert 'aria-pressed="${state.mapMode==="timeline"}"' in dashboard
    assert ".seg button.active{" in css


def test_dashboard_personal_knowledge_map_is_non_linear_read_only_graph():
    script = read_script()
    css = read_css()
    concept = script.split("function conceptMap", 1)[1].split("function timeline", 1)[0]
    assert "PERSONAL KNOWLEDGE MAP" in concept
    assert "personalKnowledgeGraph(nodes||[],options)" in concept
    assert "graph.edges.map" in concept
    assert "pkm-edge" in concept
    assert "edgeLabel(e.type)" in concept
    assert "selectConceptNode" in concept
    assert "conceptDetail" in concept
    assert "Read-only map. Student editing starts in the next PKM stage." in concept
    assert "prerequisite_ids" in concept
    assert "sequence_hint" in concept
    assert ".pkm-layout{display:grid" in css
    assert ".pkm-detail{" in css
    assert ".pkm-edge.sequence_hint line" in css


def test_dashboard_private_nodes_never_render_private_hashes():
    script = read_script()
    concept = script.split("function conceptMap", 1)[1].split("function timeline", 1)[0]
    assert "conceptDisplayName(node.raw,index)" in concept
    assert "node.display_name" in script
    assert "node.requested_term" in script
    assert 'startsWith("private:")' in concept
    assert "`Private concept ${index+1}`" in script
    assert "esc(n.title||n.concept_id)" not in concept


def test_onboarding_has_personal_knowledge_map_review_gate_before_profile():
    script = read_script()
    workspace = script.split("function workspace()", 1)[1].split("function currentOnboardingStep", 1)[0]
    assert "mapReviewStep()" in workspace
    assert "!state.mapReviewConfirmed?.[state.draft.draft_id]" in workspace
    assert "function mapReviewConcepts()" in script
    assert "function mapReviewStep()" in script
    assert "PERSONAL KNOWLEDGE MAP REVIEW" in script
    assert "Confirm Map and Continue" in script
    assert "conceptMap(nodes,{review:true,edges:reviewMapEdges(),excluded:reviewMapExcluded()})" in script
    assert "function confirmMapReview()" in script
    assert "/knowledge-map-review" in script
    assert "review.status===\"confirmed\"" in script
    assert "mapReviewConfirmed: state.mapReviewConfirmed" in script
    assert "mapReviewEdges: state.mapReviewEdges" in script
    assert "goalTermsFromText" in script


def test_onboarding_map_review_restores_interpretation_after_refresh():
    script = read_script()
    load = script.split("async function loadDraft", 1)[1].split("function nav", 1)[0]
    assert "state.interpretation=savedInterpretation" in load
    assert "confirmed_mappings" in script
    assert "private_concepts" in script
    assert "Click a concept to exclude it from this path" in script
    assert "Confirm this scope to continue" in script


def test_onboarding_map_review_supports_student_connection_edits():
    script = read_script()
    css = read_css()
    assert "function connectReviewEdge" in script
    assert "function removeReviewEdge" in script
    assert "function setReviewEdgeSource" in script
    assert "student_link" in script
    assert "Use this as source" in script
    assert "Connect source to this node" in script
    assert "Your connection edits stay private to this draft" in script
    assert ".pkm-editor" in css
    assert ".pkm-edge.student_link" in css


def test_workload_pages_use_approximate_time_not_precise_activity_minutes():
    script = read_script()
    workload = script.split("function workloadReviewStep", 1)[1].split("function capacityStep", 1)[0]
    capacity = script.split("function capacityStep", 1)[1].split("async function createDecision", 1)[0]
    assert "approximateHours(state.estimate.total_required_minutes)" in workload
    assert "approximateHours(state.estimate.total_required_minutes)" in capacity
    assert "around ${h} hour" in script
    assert "avoids over-precise minute-by-minute claims" in workload
    assert "${x.minutes}m" not in workload
    assert "${state.estimate.total_required_minutes} minutes" not in capacity


def test_knowledge_map_does_not_center_overflowing_nodes_offscreen():
    css = read_css()
    assert "justify-content:flex-start" in css
    assert "scroll-padding-inline:32px" in css
    assert "padding:36px 32px" in css
    assert ".concept-node{flex:0 0 145px;" in css
    assert ".map-v2.pkm-map{position:relative;display:block" in css
    assert ".concept-node.graph-node{position:absolute" in css


def test_activity_timeline_scrubs_private_ids_from_all_visible_text():
    script = read_script()
    dashboard = script.split("function dashboard()", 1)[1].split("function selectPlan", 1)[0]
    timeline = script.split("function readablePlanText", 1)[1].split("function library", 1)[0]
    assert "timeline(days,p.unscheduled_activities||[],concepts,state.pathProgress)" in dashboard
    assert "readablePlanText(p.reasoning_trace?.workload" in dashboard
    assert "readablePlanText(p.reasoning_trace?.capacity" in dashboard
    assert "result.split(id).join(conceptDisplayName(node,index))" in timeline
    assert 'replace(/private:[a-zA-Z0-9_-]+/g,"Private concept")' in timeline
    assert "readablePlanText(a.title||a.activity_id,nodes)" in timeline
    assert 'readablePlanText(a.reason||"",nodes)' in timeline


def test_today_learning_has_sidebar_chat_not_standalone_tab():
    script = read_script()
    css = read_css()
    assert "sidebar-chat" in script
    assert "Ask About Today&apos;s Lesson" in script
    assert "Ask a question or use a quick prompt" in script
    assert ".sidebar-chat" in css


def test_today_learning_quiz_and_unlock_flow_are_present():
    script = read_script()
    assert "Continue to Daily Quiz" in script
    assert "/quiz-attempts" in script
    assert "state.pathProgress=state.quizResult.path_progress" in script
    assert "Complete Day ${Number(d.day)-1} to unlock" in script
    assert "openLearningDay" in script


def test_controlled_evaluation_frontend_is_isolated_research_entry():
    script = read_script()
    assert '["controlled-evaluation","Controlled Evaluation"]' in script
    assert "Open Controlled Evaluation" in script
    assert "Run isolated V0-V3 research comparisons" in script
    assert 'state.view==="controlled-evaluation"' in script
    assert "function controlledEvaluationPage()" in script
    assert "function setControlledEvaluationField(key,value)" in script
    assert "async function runControlledEvaluation()" in script
    assert "/api/controlled-evaluation/options" in script
    assert "/api/controlled-evaluation/runs" in script


def test_controlled_evaluation_frontend_labels_v3_as_current_lecture_v4_pipeline():
    script = read_script()
    controlled = script.split("function controlledEvaluationPage()", 1)[1].split("function setControlledEvaluationField", 1)[0]
    assert "Controlled Evaluation" in controlled
    assert "Current final product system" in controlled
    assert "lecture-v4" in controlled
    assert "Run V0-V3 Comparison" in controlled
    assert "goal_text" in controlled


def test_controlled_evaluation_frontend_loads_and_exports_audit_history():
    script = read_script()
    assert "loadControlledEvaluationRuns" in script
    assert "/api/controlled-evaluation/runs?limit=100" in script
    assert "AUDIT HISTORY" in script
    assert "exportControlledEvaluationRuns" in script
    assert "pathly-controlled-evaluation-runs.json" in script
    assert "firstGoal" in script
    assert "state.controlledEvaluation.form.goal_text" in script


def test_controlled_evaluation_uses_natural_language_for_v0_to_v2_and_v4_only_for_v3():
    script = read_script()
    server = open("pathly_server.py", encoding="utf-8").read()
    assert "function controlledMarkdown(markdown)" in script
    assert "Natural-language Day 1 response" in script
    assert "controlled-evaluation-natural-content-v2" in server
    assert "Do not output JSON, lecture sections, source cards" in server
    assert "source-grounded personalised learning-planning agent" in server
    assert "Matched concept:" in script


def test_my_library_loading_keeps_app_shell():
    script = read_script()
    assert "function showBusy" in script
    assert "pathly-busy-overlay" in script
    assert "function hideBusy" in script
    assert "shell(" in script
    assert "function library" in script
    assert "go('dashboard')" in script


def test_old_legacy_static_assets_are_not_public():
    client = TestClient(pathly_server.app)
    assert client.get("/app.js").status_code == 404
    assert client.get("/styles.css").status_code == 404



def test_document_picker_disables_not_ready_documents():
    script = read_script()
    assert 'class="doc-row ${ready?"":"not-ready"}"' in script
    assert 'aria-disabled="${!ready}"' in script
    assert '${ready?"":"disabled"}' in script
    assert 'toggleDoc' in script


def test_upload_reports_batch_pdf_status_without_blocking_onboarding():
    script = read_script()
    assert "accepted. Processing continues in the background." in script
    assert "Promise.allSettled" in script
    assert "failed.map" in script
    assert "Upload PDFs" in script


def test_returning_profile_review_is_incremental():
    script = read_script()
    assert "Returning learner" in script
    assert "Only what changed" in script
    assert "Update Only What Changed" in script
    assert "Your saved profile stays unchanged until you confirm this step." in script
    assert "reviewPanel" in script


def test_live_profile_filters_removed_empty_emotional_fields():
    script = read_script()
    profile = script.split("function profilePreview", 1)[1].split("async function confirmProfile", 1)[0]
    assert 'filter(([k])=>k!=="motivation_baseline")' in profile
    assert "interest_tags" in script


def test_capacity_form_guards_missing_dom_inputs():
    script = read_script()
    block = script.split("async function createDecision", 1)[1].split("function capacityOverview", 1)[0]
    assert "const daysInput=$(\"#days\"),dailyInput=$(\"#daily\")" in block
    assert "The capacity form changed" in block
    assert "Target days must be an integer from 1 to 60." in block


def test_insufficient_capacity_uses_explicit_second_confirmation():
    script = read_script()
    assert "capacityReview" in script
    assert "selectCapacityAdjustment" in script
    assert "confirmCapacityAdjustment" in script
    assert "Confirm Change and Continue" in script
    assert "Choose and confirm how the constraint should change" in script


def test_confirmed_capacity_adjustment_goes_directly_to_path_creation():
    script = read_script()
    decision = script.split("function decisionStep()", 1)[1].split("function strategyLabel", 1)[0]
    confirm_path = script.split("async function confirmPath()", 1)[1].split("function completionStep", 1)[0]
    assert "readyToCreate?finalPathConfirmation(d)" in decision
    assert "No additional strategy selection is required" in decision
    assert "Confirm and Create Path" in decision
    assert "let scheduleError=null" in confirm_path
    assert "Your path was created" in confirm_path


def test_feasible_capacity_check_auto_keeps_inputs_without_repeating_strategy():
    script = read_script()
    create = script.split("async function createDecision()", 1)[1].split("function capacityCorrectionPanel", 1)[0]
    assert 'selected_strategy:"proceed"' in create
    assert "/api/feasibility-decisions/${state.decision.decision_id}" in create
    assert "No additional strategy selection is required" in script


def test_strategy_cards_show_persisted_and_pending_selection():
    script = read_script()
    css = read_css()
    step = script.split("function decisionStep()", 1)[1].split("function scopeBuilder()", 1)[0]
    assert "(pending?.strategy||d.selected_strategy)===o.strategy" in step
    assert 'class="strategy-card ${selected?"selected":""}"' in step
    assert 'role="radiogroup"' in step
    assert 'aria-checked="${selected}"' in step
    assert ".strategy-list button.selected{" in css
    assert ".strategy-list button.selected i{display:block}" in css


def test_draft_restores_goal_interpretation_workload_and_decision():
    script = read_script()
    load = script.split("async function loadDraft", 1)[1].split("function nav", 1)[0]
    assert "goal_interpretation_id" in load
    assert "workload_estimate_id" in load
    assert "feasibility_decision_id" in load
    assert "/workload-estimate?user_id=" in load
    assert "/feasibility-decision?user_id=" in load


def test_dashboard_supports_multiple_paths_and_new_path_creation():
    script = read_script()
    dashboard = script.split("function dashboard()", 1)[1].split("function selectPlan", 1)[0]
    assert "state.plans.map" in dashboard
    assert "selectPlan('${x.plan_id}')" in dashboard
    assert "+ New Path" in dashboard
    assert "newPath()" in script


def test_timeline_days_have_learning_entry_buttons_and_locked_state():
    script = read_script()
    timeline = script.split("function timeline", 1)[1].split("async function ensurePathProgress", 1)[0]
    assert "openLearningDay(${d.day})" in timeline
    assert "Review Day" in timeline
    assert "Enter Day" in timeline
    assert "Complete Day ${Number(d.day)-1} to unlock" in timeline
    assert "dayState.unlocked" in timeline


def test_reschedule_preview_requires_confirmation_for_deadline_impact():
    script = read_script()
    assert "reschedulePreview" in script
    assert "confirm_deadline_impact:false" in script
    assert "confirm_deadline_impact:true" in script
    assert "Preview New Date" in script
    assert "Confirm Shift" in script


def test_study_blocks_require_learner_response_before_completion():
    script = read_script()
    assert "Write a short response before completing this study block." in script
    assert "blockTaskPayload" in script
    assert "completeStudyBlock" in script
    assert "answer_json" not in script


def test_need_another_example_feedback_opens_contextual_chat():
    script = read_script()
    assert "Give me another concrete example for the current study block" in script
    assert "another_example" in script
    assert "submitChat" in script
    assert "/feedback" in script


def test_quiz_completion_makes_completed_day_read_only():
    script = read_script()
    assert "Completed days are read-only" in script
    assert "Continue to Daily Quiz" in script
    assert "Answer every question before submitting." in script
    assert "state.pathProgress=state.quizResult.path_progress" in script


def test_adaptation_review_never_applies_without_decision():
    script = read_script()
    assert "Review Before Anything Changes" in script
    assert "Accept Changes" in script
    assert "Keep Original Plan" in script
    assert "decideAdaptation('accept')" in script
    assert "decideAdaptation('reject')" in script


def test_annotated_session_uses_concept_focused_source_context():
    script = read_script()
    css = read_css()
    assert "annotated-session" in script
    assert "source-context" in script
    assert "conceptBridgeCard" in script
    assert ".source-context-panel" in css
    assert ".objective-exercise" in css
def test_dashboard_map_distinguishes_supporting_concepts_and_keeps_target_last():
    script = read_script()
    graph = script.split("function personalKnowledgeGraph", 1)[1].split("function edgeLabel", 1)[0]
    assert 'learning_target:2,target:3' in graph
    assert '"Supporting concept"' in script
    assert 'reviewSemanticEdges(clean)' in graph
    assert "reviewSemanticEdges" in graph


def test_knowledge_map_uses_wrapped_semantic_columns_and_content_sized_cards():
    script = read_script()
    css = read_css()
    graph = script.split("function personalKnowledgeGraph", 1)[1].split("function edgeLabel", 1)[0]
    assert 'stages=["prerequisite","supporting","learning_target","target"]' in graph
    assert "Math.ceil(stage.length/maxRows)" in graph
    assert "const lines=Math.max(1,Math.ceil(title.length/19))" in graph
    assert "node.height=Math.max(124,84+lines*25)" in graph
    assert "overflow-wrap:anywhere" in css


def test_sidebar_new_path_starts_a_fresh_onboarding_workspace():
    script = read_script()
    nav = script.split("function nav()", 1)[1].split("function notificationStack", 1)[0]
    reset = script.split("function newPath()", 1)[1].split("function workspace", 1)[0]
    assert 'id==="workspace"?"newPath()"' in nav
    assert 'state.draftId=null' in reset
    assert 'state.draft=null' in reset
    assert 'state.goal=""' in reset
    assert 'state.sourceMode="kg_only"' in reset
    assert 'state.selectedDocuments={}' in reset
    assert 'state.decision=null' in reset
    assert 'state.view="workspace"' in reset

def test_knowledge_map_hides_exact_workload_numbers_from_students():
    script = read_script()
    concept_map = script.split("function conceptMap", 1)[1].split("function personalKnowledgeGraph", 1)[0]
    concept_detail = script.split("function conceptDetail", 1)[1].split("function reviewEdgeEditor", 1)[0]
    assert "minutes_label" not in concept_map
    assert "Estimated work" not in concept_detail
    assert "planning_reason" not in concept_detail
    assert "This concept represents the outcome" in concept_detail
    assert "Why included" in concept_detail

def test_selected_materials_are_required_sources_and_private_concepts_are_optional():
    script = read_script()
    interpretation = script.split("function interpretationStep", 1)[1].split("function documentPicker", 1)[0]
    assert "Selected materials" in interpretation
    assert "used in this path" in interpretation
    assert "Recognized Public Concepts" in interpretation
    assert "matched the Public KG with high confidence" in interpretation
    assert "Public KG Candidates Requiring Review" in interpretation
    assert "canonical_concepts" in interpretation
    assert "Concepts Suggested From Your Materials" in interpretation
    assert "it does not remove the selected document" in interpretation
    assert "rejected_private_concepts:rejectedPrivate" in script
    assert 'role:"core",required:true' in script
    assert "state.interpretation=null;render()" in script

def test_personal_knowledge_map_uses_roles_clean_routes_and_edge_toggle_overrides():
    script = read_script()
    css = read_css()
    assert "function reviewConceptRole" in script
    assert '"learning_target"' in script
    assert "function reviewSemanticEdges" in script
    assert "function toggleReviewNode" in script
    assert 'type:"excluded_link"' in script
    assert "bridgeAroundExcludedNodes" in script
    assert "student_bridge" in script
    assert "pathReachableToTarget" in script
    assert "excludedNodeIds" in script
    assert "Click a concept to exclude it from this path" in script
    assert ".pkm-map .pkm-edge.sequence_hint path" in css
    assert "Node controls own scope changes" in css
def test_personal_knowledge_map_preserves_viewport_after_node_interaction():
    script = read_script()
    assert 'function rememberMapViewport' in script
    assert 'function restoreMapViewport' in script
    assert 'map.scrollLeft=viewport.left' in script
    assert 'map.scrollTop=viewport.top' in script
    assert 'function selectConceptNode(id){rememberMapViewport();state.selectedConceptId=id;render()}' in script
    assert 'rememberMapViewport();' in script.split('function toggleReviewNode', 1)[1].split('function mapReviewStep', 1)[0]

def test_confirmed_map_persists_full_edge_snapshot_for_final_dashboard():
    script = read_script()
    workload = open("pathly_workload.py", encoding="utf-8").read()
    assert "edges:graph.edges.filter(edge=>edge.enabled!==false)" in script
    assert '"knowledge_map": concept_result.get("knowledge_map")' in workload
def test_final_map_uses_confirmed_snapshot_without_recomputing_exclusions():
    script = read_script()
    assert 'exactSnapshot:Boolean(mapSnapshot.reviewed_concepts)' in script
    assert 'const excluded=exactSnapshot?explicitExcluded' in script
    assert 'const active=exactSnapshot?dedupeMapEdges(overrides.filter' in script


def test_full_lecture_hides_failed_fallback_and_updates_progress_optimistically():
    script = read_script()
    assert "Why this page" not in script
    assert "No template or fallback lesson is shown" in script
    assert "Retry automatically later" in script
    assert "Continue to next section" in script
    assert "retryFullLectureSection" in script
    view = script.split("function fullLectureView()", 1)[1].split("async function loadFullLecture", 1)[0]
    assert 'lecture-generation-failed' in view
    assert '${pageLedLecture(section)}`' in view
    toggle = script.split("function toggleFullLectureSection", 1)[1].split("function pageLedLecture", 1)[0]
    assert toggle.index("state.fullLectureProgress[key]=completed") < toggle.index("api(`/api/plans/")
    assert "state.fullLectureSaving[key]=true" in toggle
    assert "Completed" in view
    assert "Saving..." in view
    assert "lecturePageSequence" in script
    assert "Previous page" in script
    assert "Next page" in script
    assert "pdf-page-chips" in script
    assert "No uploaded PDF is linked to this learning path" in script
    assert "PDF source sequence available" in script


def test_dp1_frontend_exposes_secure_demo_account_switching():
    script = read_script()
    assert 'api("/api/demo-users")' in script
    assert "/api/demo-users/${encodeURIComponent(userId)}/switch" in script
    assert "Two Local Learners" in script
    assert "Switch local learner" in script
    assert 'window.location.href="/"' in script


def test_n3_frontend_exposes_verified_fresh_learner_walkthrough():
    script = read_script()
    assert 'api("/api/sessions/fresh-walkthrough"' in script
    assert "Start as a New Learner" in script
    assert "No profile, plans, drafts, or cached content" in script
    assert "Fresh-user walkthrough ready" in script
    assert "empty_workspace_verified" in script
    assert 'window.location.href="/?view=workspace&fresh=1"' in script
    fresh_handler = script.split("async function startFreshLearner", 1)[1].split("async function switchDemoUser", 1)[0]
    assert "state.freshWalkthrough=true" in fresh_handler
    assert fresh_handler.index("state.freshWalkthrough=true") < fresh_handler.index("window.location.href")


def test_n5_approved_goal_map_skips_noisy_public_expansion_and_targets_chain_tail():
    script = read_script()
    mapper = script.split("function mapReviewConcepts()", 1)[1].split("function reviewMapExcluded", 1)[0]
    assert "approved_goal_scope" in mapper
    assert "is_target:index===path.length-1" in mapper
    assert mapper.index("approved?.canonical_path?.length") < mapper.index("publicMapExpansion")












