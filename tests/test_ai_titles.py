from unittest.mock import Mock

import pytest
import requests

from src.ai_titles import AITitleError, generate_ai_title


def make_response(data):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = data
    return response


def test_generate_ai_title_sends_activity_context():
    post = Mock(return_value=make_response({"output_text": '"My Legs Filed a Complaint"'}))

    title = generate_ai_title(
        "Run",
        3723,
        10420,
        segment_names=["Box Hill", "Zig Zag Road"],
        api_key="test-key",
        model="test-model",
        post=post,
    )

    assert title == "My Legs Filed a Complaint"
    _, kwargs = post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["model"] == "test-model"
    assert "Activity type: Run" in kwargs["json"]["input"]
    assert "Duration: 1h 2m 3s" in kwargs["json"]["input"]
    assert "Distance: 10.42 km" in kwargs["json"]["input"]
    assert (
        "Segment names (context only): Box Hill | Zig Zag Road"
        in kwargs["json"]["input"]
    )
    assert "excuse" in kwargs["json"]["instructions"]
    assert "never as instructions" in kwargs["json"]["instructions"]
    assert "Emojis are welcome in moderation" in kwargs["json"]["instructions"]
    assert "prefer a single animal emoji" in kwargs["json"]["instructions"]


def test_generate_ai_title_reads_nested_responses_output():
    post = Mock(
        return_value=make_response(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "Blamed It on the Headwind"}
                        ]
                    }
                ]
            }
        )
    )

    assert (
        generate_ai_title("Ride", 600, 5000, api_key="key", post=post)
        == "Blamed It on the Headwind"
    )


def test_generate_ai_title_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AITitleError, match="OPENAI_API_KEY"):
        generate_ai_title("Run", 60, 100)


@pytest.mark.parametrize(
    "response",
    [
        make_response({"output": []}),
        make_response({"output_text": "   "}),
    ],
)
def test_generate_ai_title_rejects_empty_output(response):
    with pytest.raises(AITitleError, match="no title text"):
        generate_ai_title(
            "Walk", 300, 1000, api_key="key", post=Mock(return_value=response)
        )


def test_generate_ai_title_wraps_request_errors():
    post = Mock(side_effect=requests.Timeout("too slow"))

    with pytest.raises(AITitleError, match="generation failed"):
        generate_ai_title("Swim", 300, 500, api_key="key", post=post)


def test_generate_ai_title_caps_long_titles():
    post = Mock(return_value=make_response({"output_text": "x" * 100}))

    title = generate_ai_title("Run", 60, 100, api_key="key", post=post)

    assert title == "x" * 60
