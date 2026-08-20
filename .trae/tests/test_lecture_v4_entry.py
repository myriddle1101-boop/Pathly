from pathlib import Path

from fastapi.testclient import TestClient

import pathly_server


ROOT = Path(__file__).resolve().parents[1]


def test_v4_query_uses_main_today_learning_app():
    client = TestClient(pathly_server.app)
    response = client.get("/?daily_view=lecture-v4&plan_id=plan-1&day=1")
    assert response.status_code == 200
    assert "pathly-app.js?v=133" in response.text
    assert "lecture-v4.js" not in response.text


def test_standalone_v4_script_is_not_public():
    client = TestClient(pathly_server.app)
    response = client.get("/lecture-v4.js")
    assert response.status_code == 404


def test_v4_is_an_in_page_button_with_normal_hydration():
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    assert 'tab.addEventListener("click",()=>setDailyStage(tab.dataset.dailyStage))' in source
    assert 'if(id==="lecture-v4")return `<a' not in source
    assert "Restoring Source-Grounded Lecture View v4" not in source
    assert 'history.replaceState({},"",url)' in source
    assert 'if(state.dailyStage==="lecture-v4")' in source
    assert "lectureV4MatchesToday()" in source
    assert "await loadLectureV4()" in source
    assert "Load v4</button>" not in source


def test_v4_functions_are_top_level_and_not_nested_in_v3_loader():
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    v3_start = source.index("async function loadFullLecture(){")
    v4_start = source.index("function v4SectionKey", v3_start)
    v3_return = source.index("return state.fullLecture;", v3_start)
    assert v3_return < v4_start
    assert source.count("async function loadLectureV4(force=false)") == 1
    assert source.count("function toggleV4Section(sectionId)") == 1

def test_v4_generation_does_not_use_false_restoration_timeout():
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    assert "v4 restoration timed out" not in source
    assert "state.lectureV4=null" in source
    assert "state.lectureV4Error=null;" in source



def test_v4_pdf_pages_fit_and_lossy_text_is_secondary():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    styles = (ROOT / "pathly-ui.css").read_text(encoding="utf-8")
    assert "pathly-ui.css?v=130" in index
    assert "v4-pdf-page-frame" in source
    assert "v4-source-transcript" in source
    assert "Text version of this page" in source
    assert ".v4-pdf-page-frame img,.v4-source-page img" in styles
    assert "max-width:100%" in styles

def test_v4_page_guidance_is_colocated_with_each_source_page():
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    styles = (ROOT / "pathly-ui.css").read_text(encoding="utf-8")
    assert "function v4SourcePagePanel(section,walkthrough=[])" in source
    assert "SOURCE EXPLANATION" in source
    assert "WHAT THIS PAGE IS SHOWING" not in source
    assert "v4-source-page-grid" not in source.split("function v4SourcePagePanel(section,walkthrough=[])", 1)[1].split("function v4ReadySection", 1)[0]
    assert "Connection:" in source
    assert "v4-page-annotation" in source
    assert "v4-public-source-text" in source
    assert "PAGE-BY-PAGE EXPLANATION" not in source
    assert "v118: colocated page guidance" in styles
    assert "v121: restored section-local v4 publishing" in styles

def test_normal_product_flow_has_no_dedicated_g0_frontend_launcher():
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    assert "requestedGoldenCase" not in source
    assert "/api/golden-cases/g0" not in source


def test_v4_requested_plan_owner_mismatch_falls_back_to_current_session_plan():
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    assert "That shared learning link belongs to another anonymous workspace" in source
    assert "requestedPlanId&&!requestedPlan&&state.currentPlan" in source
    assert "syncDailyViewUrl()" in source


def test_enter_day_starts_runtime_then_opens_v4_without_generating_v3():
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    entry = source.split("async function openLearningDay(day){", 1)[1].split("async function loadV4RouteContext", 1)[0]
    context = source.split("async function loadV4RouteContext(dayOverride=null){", 1)[1].split("async function loadTodayData", 1)[0]
    assert 'state.dailyStage="lecture-v4"' in entry
    assert "await loadV4RouteContext(Number(day))" in entry
    assert "syncDailyViewUrl()" in entry
    assert "await loadLectureV4()" in entry
    assert "/days/${selected.day}/start" in context
    assert context.index('/days/${selected.day}/start') < context.index("state.dailyContent=")
    assert "/days/${selected.day}/content" not in entry
    assert "/days/${selected.day}/content" not in context
    assert "loadFullLecture" not in entry
    assert "loadFullLecture" not in context


def test_v4_route_identity_and_refresh_state_are_persisted():
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    assert 'url.searchParams.set("daily_view","lecture-v4")' in source
    assert 'url.searchParams.set("plan_id"' in source
    assert 'url.searchParams.set("day"' in source
    assert 'requestedDailyView === "lecture-v4" ? "today"' in source
    assert 'requestedDailyView === "lecture-v4" ? "lecture-v4"' in source
    assert "v4CurrentSectionId: saved.v4CurrentSectionId" in source
    assert "v4ScrollPosition: Number(saved.v4ScrollPosition||0)" in source


def test_existing_onboarding_questions_have_non_intrusive_impact_hints():
    source = (ROOT / "pathly-app.js").read_text(encoding="utf-8")
    styles = (ROOT / "pathly-ui.css").read_text(encoding="utf-8")
    assert "const QUESTION_IMPACT=" in source
    assert "function questionPrompt(q)" in source
    assert 'aria-label="How this answer is used"' in source
    assert "question-impact" in styles
    assert "question-help" in styles
