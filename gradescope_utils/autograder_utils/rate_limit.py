import json
from datetime import datetime, timedelta
from typing import Optional, Union
import os


# By default, load the metadata file from the location where it will be when running on Gradescope.
# But, for debugging, you can set the AUTOGRADER_METADATA_FILE environment variable to point to a
# different file.
METADATA_FILE = os.getenv("AUTOGRADER_METADATA_FILE", "/autograder/submission_metadata.json")


def read_metadata():
    # See https://gradescope-autograders.readthedocs.io/en/latest/submission_metadata/ for
    # information about the format of the submission metadata file.
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE) as f:
            return json.load(f)
    else:
        return {}


def submission_datetime(previous_submission: dict) -> datetime:
    # Submission times are formatted like "2017-04-06T14:24:48.087023-07:00"
    return datetime.strptime(previous_submission["submission_time"], "%Y-%m-%dT%H:%M:%S.%f%z")


def prepend_rate_limit_warning(previous_submission: dict, reason: str) -> dict:
    results = previous_submission["results"]
    dummy_test_case = {
        "status": "failed",
        "name": "Submission Limit Exceeded",
        "name_format": "text",
        "output": "WARNING: Rate Limit exceeded. The current submission will not be evaluated. "
        f"Falling back to earlier submission from {previous_submission['submission_time']}. "
        f" Reason: {reason}",
        "output_format": "text",
        "visibility": "visible",  # Optional visibility setting
    }
    results["tests"] = [dummy_test_case] + results.get("tests", [])
    return results


def _int_rank_format(rank: int) -> str:
    if rank % 10 == 1 and rank % 100 != 11:
        return f"{rank}st"
    if rank % 10 == 2 and rank % 100 != 12:
        return f"{rank}nd"
    if rank % 10 == 3 and rank % 100 != 13:
        return f"{rank}rd"
    return f"{rank}th"


def rate_limit_info_message_as_test_result(
    max_total: Optional[int] = None,
    max_per_day: Optional[int] = None,
    max_per_hour: Optional[int] = None,
    plus_one_for_current_submission: bool = False,
) -> Union[None, dict]:
    if max_total is None and max_per_day is None and max_per_hour is None:
        return

    metadata = read_metadata()
    previous_submissions = metadata.get("previous_submissions", [])

    now = datetime.now()
    messages = []
    if max_total is not None:
        total_submissions = len(previous_submissions) + int(plus_one_for_current_submission)
        messages.append(
            f"Cap on total submissions: {max_total}. "
            f"This is your {_int_rank_format(total_submissions)} submission. "
            f"You have {max_total - total_submissions} submissions left (total)."
        )
    if max_per_day is not None:
        yesterday = now - timedelta(days=1)
        last_24_hours_submissions = list(
            filter(
                lambda s: submission_datetime(s).timestamp() > yesterday.timestamp(),
                previous_submissions,
            )
        )
        num_24h_submissions = len(last_24_hours_submissions) + int(plus_one_for_current_submission)
        messages.append(
            f"Cap on submissions per 24h: {max_per_day}. "
            f"In the past 24 hours, you submitted {num_24h_submissions} times. "
            f"You have {max_per_day - num_24h_submissions} attempts left in the current 24h window."
        )
    if max_per_hour is not None:
        last_hour = now - timedelta(hours=1)
        last_hour_submissions = list(
            filter(
                lambda s: submission_datetime(s).timestamp() > last_hour.timestamp(),
                previous_submissions,
            )
        )
        num_1h_submissions = len(last_hour_submissions) + int(plus_one_for_current_submission)
        messages.append(
            f"Cap on submissions per hour: {max_per_hour}. "
            f"In the past hour, you submitted {num_1h_submissions} times. "
            f"You have {max_per_hour - num_1h_submissions} attempts left in the current hour."
        )
    message = "\n\n".join(messages)
    return {
        "status": "passed",
        "name": "Rate Limit Information",
        "name_format": "text",
        "output": message,
        "output_format": "simple_format",
    }


def get_earlier_results_if_rate_limited(
    max_total: Optional[int] = None,
    max_per_day: Optional[int] = None,
    max_per_hour: Optional[int] = None,
) -> Union[None, dict]:
    if max_total is None and max_per_day is None and max_per_hour is None:
        return

    metadata = read_metadata()
    previous_submissions = metadata.get("previous_submissions", [])

    if max_total is not None and len(previous_submissions) >= max_total:
        sorted_submissions = list(sorted(previous_submissions, key=submission_datetime))
        last_valid_result = sorted_submissions[max_total - 1]
        return prepend_rate_limit_warning(
            last_valid_result,
            reason=f"Limit of {max_total} maximum total submissions is in effect. "
            f"You previously submitted {len(sorted_submissions)} times. "
            f"Please contact the course staff if you believe this is an error.",
        )

    now = datetime.now()
    yesterday = now - timedelta(days=1)
    last_24_hours_submissions = list(
        filter(
            lambda s: submission_datetime(s).timestamp() > yesterday.timestamp(),
            previous_submissions,
        )
    )
    if max_per_day is not None and len(last_24_hours_submissions) >= max_per_day:
        sorted_submissions = list(sorted(last_24_hours_submissions, key=submission_datetime))
        last_valid_result = sorted_submissions[max_per_day - 1]
        return prepend_rate_limit_warning(
            last_valid_result,
            reason=f"Limit of {max_per_day} maximum submissions per 24 hours is in effect. "
            f"In the past 24h, you submitted {len(sorted_submissions)} times. "
            f"Please contact the course staff if you believe this is an error.",
        )

    last_hour = now - timedelta(hours=1)
    last_hour_submissions = list(
        filter(
            lambda s: submission_datetime(s).timestamp() > last_hour.timestamp(),
            previous_submissions,
        )
    )
    if max_per_hour is not None and len(last_hour_submissions) >= max_per_hour:
        sorted_submissions = list(sorted(last_hour_submissions, key=submission_datetime))
        last_valid_result = sorted_submissions[max_per_hour - 1]
        return prepend_rate_limit_warning(
            last_valid_result,
            reason=f"Limit of {max_per_hour} maximum submissions per hour is in effect. "
            f"In the past hour, you submitted {len(sorted_submissions)} times. "
            f"Please contact the course staff if you believe this is an error.",
        )

    return None