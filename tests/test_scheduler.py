import datetime as dt

from jarvis.core.tools.scheduler import (
    AddReminderTool,
    CompleteReminderTool,
    DeleteReminderTool,
    ListRemindersTool,
    get_due_reminders,
)


def test_add_and_list_reminder():
    add_result = AddReminderTool().run(text="call mom")
    assert "created" in add_result

    listing = ListRemindersTool().run()
    assert "call mom" in listing
    assert "[pending]" in listing


def test_invalid_due_at_is_rejected():
    result = AddReminderTool().run(text="bad date", due_at="not-a-date")
    assert result.startswith("Error:")


def test_complete_and_delete_reminder():
    add_result = AddReminderTool().run(text="water plants")
    reminder_id = int(add_result.split("#")[1].split()[0])

    complete_result = CompleteReminderTool().run(reminder_id=reminder_id)
    assert "marked done" in complete_result

    listing_without_done = ListRemindersTool().run(include_done=False)
    assert "water plants" not in listing_without_done

    delete_result = DeleteReminderTool().run(reminder_id=reminder_id)
    assert "deleted" in delete_result

    delete_again = DeleteReminderTool().run(reminder_id=reminder_id)
    assert delete_again.startswith("Error:")


def test_get_due_reminders_only_returns_past_due():
    future = (dt.datetime.now() + dt.timedelta(days=1)).isoformat()
    past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat()

    AddReminderTool().run(text="future thing", due_at=future)
    AddReminderTool().run(text="overdue thing", due_at=past)

    due = get_due_reminders()
    due_texts = [r["text"] for r in due]
    assert "overdue thing" in due_texts
    assert "future thing" not in due_texts
