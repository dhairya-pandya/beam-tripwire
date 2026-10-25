from types import SimpleNamespace as NS

from tripwire.judge import episode_texts, judge_episode, parse_yes_no


def test_parse_yes_no():
    assert parse_yes_no("YES") is True and parse_yes_no("no.") is False
    assert parse_yes_no("Answer: Yes, because") is True and parse_yes_no("unclear") is None


def test_episode_texts_split_closing_and_reasoning():
    msgs = [{"role": "assistant", "content": "", "reasoning_content": "early thought"},
            {"role": "assistant", "content": "The test is wrong.", "reasoning_content": "late thought"}]
    closing, reasoning = episode_texts(msgs)
    assert "The test is wrong." in closing and "late thought" in closing
    assert "early thought" in reasoning and "late thought" in reasoning


def test_judge_episode_calls_model_twice():
    asked = []

    class Fake:
        def __init__(self):
            self.chat = NS(completions=NS(create=self.create))

        def create(self, **kw):
            asked.append(kw["messages"][0]["content"])
            ans = "YES" if "final message" in asked[-1] else "NO"
            return NS(choices=[NS(message=NS(content=ans))])

    out = judge_episode(Fake(), "m", [{"role": "assistant", "content": "x", "reasoning_content": "y"}])
    assert out == {"judge_honest": True, "judge_intent": False} and len(asked) == 2


def test_note_questions_only_asked_when_there_is_a_note():
    import json

    from tripwire.judge import judge_episode

    class Fake:
        def __init__(self):
            self.asked = []
            self.chat = self
            self.completions = self

        def create(self, **kw):
            self.asked.append(kw["messages"][0]["content"])
            msg = type("M", (), {"content": "NO"})()
            return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

    submit = lambda note: [{"role": "assistant", "reasoning_content": "thinking",
                            "tool_calls": [{"function": {"name": "submit_patch", "arguments": json.dumps({"note": note})}}]}]
    f = Fake()
    assert "judge_disclosed" not in judge_episode(f, "m", submit(""), think=False)
    assert judge_episode(f, "m", submit("changed the test"), think=False)["judge_disclosed"] is False
