from sales_copilot.schemas import AccountRecord, MeetingSummary, TaskRecord


def test_sales_copilot_schema_objects_dump_expected_keys():
    account = AccountRecord(
        name="Acme Robotics",
        industry="Manufacturing",
        size_segment="Mid-Market",
        status="active",
        opportunity_stage="discovery",
    )
    meeting = MeetingSummary(
        account_name="Acme Robotics",
        customer_roles=["CTO"],
        confirmed_needs=["Private deployment"],
        objections=["Budget uncertainty"],
        next_steps=["Send deployment proposal"],
    )
    task = TaskRecord(
        account_name="Acme Robotics",
        title="Send deployment proposal",
        description="Send a tailored proposal before Friday",
        priority="high",
        status="open",
    )

    assert account.model_dump()["name"] == "Acme Robotics"
    assert meeting.model_dump()["customer_roles"] == ["CTO"]
    assert task.model_dump()["priority"] == "high"
