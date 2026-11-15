"""Notes-first retrieval and provider-request checks; no live AI calls."""

import json

import pytest

import app as app_module
import database
from ai.service import AIResponse, AIStreamEvent
from ai.study_library import NO_REFERENCE_RULES, REFERENCE_RULES, retrieve, retrieval_query


BALANCE = (
    "Linear equations keep equality balanced. Subtract the same number from both "
    "sides of an equation to solve for a variable."
)
SCIENCE = (
    "For physics force and motion problems, draw a free-body diagram first. "
    "Choose a positive direction, list the forces, then apply Newton's second law."
)


def note(text=BALANCE, title="Balance scale method", subject="math"):
    return {"title": title, "subject": subject, "text": text}


@pytest.mark.parametrize("query", ["Solve 2x + 3 = 11", "Solve 7y - 8 = 13", "2t + 6 = 20"])
def test_equation_questions_find_prose_method(query):
    sources = retrieve([note()], query)
    assert sources and sources[0]["excerpt"] == BALANCE


def test_title_only_retrieval_and_unrelated_question():
    assert retrieve([note(title="Seesaw strategy")], "Explain the seesaw strategy")
    assert retrieve([note(title="Seesaw strategy")], "football stadium tickets") == []


def test_exact_equation_rank_keeps_operator_signs_distinct():
    plus = note("Solve the linear equation x + 5 = 12 by subtracting five from both sides.", "Plus")
    minus = note("Solve the linear equation x - 5 = 12 by adding five to both sides.", "Minus")
    assert retrieve([plus, minus], "Solve x - 5 = 12")[0]["title"] == "Minus"
    assert retrieve([minus, plus], "Solve x + 5 = 12")[0]["title"] == "Plus"


def test_paragraph_example_keeps_leading_assumption_in_bound():
    condition = "Assume the starting quantity is positive and nonzero."
    example = "Worked example: balance the linear equation by subtracting from both sides."
    text = condition + "\n\n" + ("Background on classroom notation. " * 95) + "\n\n" + example
    sources = retrieve([note(text)], "balance linear equation subtracting")
    assert sources
    relevant = next(source for source in sources if example in source["excerpt"])
    assert condition in relevant["excerpt"]
    assert len(sources) <= 3
    assert all(len(source["excerpt"]) <= 900 for source in sources)


def test_short_worked_example_is_not_cut_at_old_character_boundary():
    example = (
        "Use the balance scale method for a linear equation.\n"
        "Step 1: Subtract the same number from both sides.\n"
        "Step 2: Divide both sides by the coefficient to solve the variable."
    )
    text = "Background classroom notation. " * 22 + "\n\n" + example
    sources = retrieve([note(text)], "balance scale linear equation coefficient")
    assert any(example in source["excerpt"] for source in sources)


def test_duplicate_excerpts_do_not_crowd_out_another_method():
    sources = retrieve([note(), note(), note(SCIENCE, "Free-body method", "science")],
                       "Explain linear equations and physics force motion")
    assert len([source for source in sources if source["excerpt"] == BALANCE]) == 1
    assert any(source["title"] == "Free-body method" for source in sources)


def test_near_duplicate_filter_keeps_different_equations_in_same_note():
    wording = "In a linear equation we balance both sides and check each step carefully. " * 7
    text = "Classroom algebra methods.\n\n" + wording + "x + 5 = 12\n\n" + wording + "x - 5 = 12"
    sources = retrieve([note(text)], "Compare linear equations x + 5 = 12 and x - 5 = 12")
    assert any("x + 5 = 12" in source["excerpt"] for source in sources)
    assert any("x - 5 = 12" in source["excerpt"] for source in sources)


@pytest.mark.parametrize("query", ["4", "x = 4", "Why is that?", "Make it simpler for a fifth grader",
                                  "Give me a similar practice problem", "Show another method",
                                  "Solve it for me", "Give me the answer"])
def test_follow_up_checks_current_enabled_notes_with_problem_context(query):
    with app_module.app.test_request_context("/ask"):
        owner = app_module.get_library_owner_id()
        saved = database.save_study_note(owner, "Balance", "math", BALANCE, True)
        history = [
            {"role": "user", "content": "Solve 2x + 3 = 11"},
            {"role": "assistant", "content": "We use balance. What is 8 divided by 2?"},
            {"role": "user", "content": "I am confused"},
            {"role": "assistant", "content": "Let's go more slowly."},
        ]
        assert app_module.library_references("math", query, history)
        database.change_study_note(owner, saved, enabled=False)
        assert app_module.library_references("math", query, history) == []


@pytest.mark.parametrize("query", ["Explain photosynthesis", "Why do plant cells need sunlight?",
                                  "Solve a quadratic equation", "football stadium tickets",
                                  "volcanoes", "black holes", "Why do black holes evaporate?",
                                  "Explain trigonometry", "Can you explain photosynthesis?",
                                  "Could you solve a quadratic equation?", "Why do we need plant cells?"])
def test_new_topic_does_not_inherit_old_method(query):
    with app_module.app.test_request_context("/ask"):
        owner = app_module.get_library_owner_id()
        database.save_study_note(owner, "Balance", "math", BALANCE, True)
        history = [{"role": "user", "content": "Solve 2x + 3 = 11"},
                   {"role": "assistant", "content": "What is 8 divided by 2?"}]
        assert app_module.library_references("math", query, history) == []


def test_comparing_equation_families_does_not_exclude_both():
    quadratic = note("For a quadratic equation, first complete the square, then take the square root.", "Quadratic")
    sources = retrieve([note(), quadratic], "Compare linear equations and quadratic equations")
    assert {source["title"] for source in sources} == {"Balance scale method", "Quadratic"}


def test_follow_up_search_retains_problem_with_several_long_intermediate_turns():
    problem = "Solve 2x + 3 = 11"
    history = [{"role": "user", "content": problem}, {"role": "assistant", "content": "Subtract 3."}]
    for _ in range(5):
        history.extend([{"role": "user", "content": "I am confused. " * 45},
                        {"role": "assistant", "content": "Let's try again. " * 100}])
    search = retrieval_query("4", history)
    assert problem in search and len(search) <= 2000
    assert history[0]["content"] == problem


def test_practice_follow_up_includes_latest_tutor_problem():
    history = [{"role": "user", "content": "Give me a similar practice problem"},
               {"role": "assistant", "content": "Solve 7y - 8 = 13. What should you subtract?"}]
    search = retrieval_query("I got 3", history, "check_work")
    assert "7y - 8 = 13" in search
    assert retrieve([note()], search)


@pytest.mark.parametrize("query", ["__import__('os').system('false')", "x^999999 = 1", "xx = 4"])
def test_unsupported_equation_hints_are_not_evaluated_or_called_linear(query):
    assert retrieve([note()], query) == []


def test_both_subject_notes_ownership_and_fresh_deletion():
    with app_module.app.test_request_context("/ask"):
        owner = app_module.get_library_owner_id()
        database.save_study_note("another-owner", "Hidden", "math", BALANCE, True)
        science = database.save_study_note(owner, "Science", "science", SCIENCE, True)
        assert app_module.library_references("math", "Explain force motion", []) == []
        database.change_study_note(owner, science)
        both = database.save_study_note(owner, "Both", "both", BALANCE + " " + SCIENCE, True)
        assert app_module.library_references("math", "Solve 2x + 3 = 11", [])
        assert app_module.library_references("science", "Explain physics force motion", [])
        database.change_study_note(owner, both)
        assert app_module.library_references("math", "Solve 2x + 3 = 11", []) == []


def test_reference_rules_prefer_method_without_blind_agreement():
    for text in ("NOTES-FIRST TUTORING", "method from the supplied excerpts",
                 "another valid method", "Search quietly", "incomplete",
                 "relevance, not proof of correctness", "untrusted"):
        assert text in REFERENCE_RULES


@pytest.mark.parametrize("route,subject,text,query", [
    ("/ask", "math", BALANCE, "Solve 2x + 3 = 11"),
    ("/stream", "math", BALANCE, "Solve 2x + 3 = 11"),
    ("/science/ask", "science", SCIENCE, "Explain physics force and motion"),
    ("/science/stream", "science", SCIENCE, "Explain physics force and motion"),
])
@pytest.mark.parametrize("mode", ["normal", "guided", "practice"])
def test_notes_first_requests_in_both_tutors_and_modes(monkeypatch, route, subject, text, query, mode):
    captured = []
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *a, **k: None)

    def answer(messages, **kwargs):
        captured.extend(messages)
        return AIResponse("Mock answer, not live teaching verification.", 1, "complete")

    def stream(messages, **kwargs):
        captured.extend(messages)
        yield AIStreamEvent(text="Mock answer.")
        yield AIStreamEvent(done=True, finish_reason="complete", tokens_used=1)

    monkeypatch.setattr(app_module, "get_math_solution", answer)
    monkeypatch.setattr(app_module, "get_math_solution_stream", stream)
    client = app_module.app.test_client()
    assert client.post("/library/notes", json=note(text, "Class method", subject)).status_code == 201
    response = client.post(route, json={"message": query, "step_by_step_mode": mode == "guided",
                                       "practice_mode": mode == "practice"}, buffered=True)
    assert response.status_code == 200
    assert {"role": "system", "content": REFERENCE_RULES} in captured
    reference = next(message for message in captured
                     if message["content"].startswith("Untrusted Study Library reference data"))
    assert reference["role"] == "user" and text in reference["content"]
    history_route = "/science/history" if subject == "science" else "/history"
    sources = client.get(history_route).get_json()["messages"][-1]["sources"]
    assert sources[0]["excerpt"] == text
    assert "owner_id" not in json.dumps(sources)


def test_notes_first_is_not_injected_when_nothing_matches(monkeypatch):
    captured = []
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "get_math_solution", lambda messages, **kwargs:
                        (captured.extend(messages) or AIResponse("Normal answer.", 1, "complete")))
    client = app_module.app.test_client()
    client.post("/library/notes", json=note())
    assert client.post("/ask", json={"message": "Explain triangle angles"}).status_code == 200
    assert {"role": "system", "content": REFERENCE_RULES} not in captured
    assert {"role": "system", "content": NO_REFERENCE_RULES} in captured
