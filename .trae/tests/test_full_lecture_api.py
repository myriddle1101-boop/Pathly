from pathly_server import app


def test_full_lecture_route_is_parallel_and_documented():
    routes = {getattr(route, "path", "") for route in app.routes}
    assert "/api/plans/{plan_id}/days/{day}/full-lecture" in routes
    assert "/api/plans/{plan_id}/days/{day}/annotated-session" in routes
    assert "/api/documents/{document_id}/pages/{page}/render" in routes
    assert "/api/plans/{plan_id}/days/{day}/full-lecture/sections/{section_id}/regenerate" in routes




def test_progress_write_does_not_regenerate_the_lecture():
    import inspect
    from pathly_server import set_full_lecture_section_progress
    source = inspect.getsource(set_full_lecture_section_progress)
    assert "generate_full_lecture" not in source
    assert "reading_count" in source

