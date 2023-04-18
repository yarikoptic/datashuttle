import datetime
import re
from typing import List, Union

from . import utils

# --------------------------------------------------------------------------------------------------------------------
# Format Sub / Ses Names
# --------------------------------------------------------------------------------------------------------------------


def format_names(
    names: Union[List[str], str],
    prefix: str,
) -> List[str]:
    """
    Check a single or list of input session or subject names.
    First check the type is correct, next prepend the prefix
    sub- or ses- to entries that do not have the relevant prefix.
    Finally, check for duplicates.

    :param names: str or list containing sub or ses names (e.g. to make dirs)
    :param prefix: "sub" or "ses" - this defines the prefix checks.
    """
    if type(names) not in [str, list] or any(
        [not isinstance(ele, str) for ele in names]
    ):
        utils.raise_error(
            "Ensure subject and session names are list of strings, or string"
        )

    if isinstance(names, str):
        names = [names]

    if any([" " in ele for ele in names]):
        utils.raise_error("sub or ses names cannot include spaces.")

    prefixed_names = ensure_prefixes_on_list_of_names(names, prefix)

    if len(prefixed_names) != len(set(prefixed_names)):
        utils.raise_error(
            "Subject and session names but all be unique (i.e. there are no"
            " duplicates in list input)"
        )

    prefixed_names = update_names_with_range_to_flag(prefixed_names, prefix)

    update_names_with_datetime(prefixed_names)

    return prefixed_names


# Handle @TO@ flags  -------------------------------------------------------


def update_names_with_range_to_flag(
    names: List[str], prefix: str
) -> List[str]:
    """
    Given a list of names, check if they contain the @TO@ keyword.
    If so, expand to a range of names. Names including the @TO@
    keyword must be in the form prefix-num1@num2. The maximum
    number of leading zeros are used to pad the output
    e.g.
    sub-01@003 becomes ["sub-001", "sub-002", "sub-003"]

    Input can also be a mixed list e.g.
    names = ["sub-01", "sub-02@TO@04", "sub-05@TO@10"]
    will output a list of ["sub-01", ..., "sub-10"]
    """
    new_names = []

    for i, name in enumerate(names):

        if "@TO@" in name:

            check_name_is_formatted_correctly(name, prefix)

            prefix_tag = re.search(f"{prefix}[0-9]+@TO@[0-9]+", name)[0]  # type: ignore
            tag_number = prefix_tag.split(f"{prefix}")[1]

            name_start_str, name_end_str = name.split(tag_number)

            if "@TO@" not in tag_number:
                utils.raise_error(
                    f"@TO@ flag must be between two numbers in the {prefix} tag."
                )

            left_number, right_number = tag_number.split("@TO@")

            if int(left_number) >= int(right_number):
                utils.raise_error(
                    "Number of the subject to the  left of @TO@ flag "
                    "must be small than number to the right."
                )

            names_with_new_number_inserted = (
                make_list_of_zero_padded_names_across_range(
                    left_number, right_number, name_start_str, name_end_str
                )
            )
            new_names += names_with_new_number_inserted

        else:
            new_names.append(name)

    return new_names


def check_name_is_formatted_correctly(name: str, prefix: str) -> None:
    """
    Check the input string is formatted with the @TO@ key
    as expected.
    """
    first_key_value_pair = name.split("_")[0]
    expected_format = re.compile(f"{prefix}[0-9]+@TO@[0-9]+")

    if not re.fullmatch(expected_format, first_key_value_pair):
        utils.raise_error(
            f"The name: {name} is not in required format for @TO@ keyword. "
            f"The start must be  be {prefix}<NUMBER>@TO@<NUMBER>)"
        )


def make_list_of_zero_padded_names_across_range(
    left_number: str, right_number: str, name_start_str: str, name_end_str: str
) -> List[str]:
    """
    Numbers formatted with the @TO@ keyword need to have
    standardised leading zeros on the output. Here we take
    the maximum number of leading zeros and apply or
    all numbers in the range.
    """
    max_leading_zeros = max(
        num_leading_zeros(left_number), num_leading_zeros(right_number)
    )

    all_numbers = [*range(int(left_number), int(right_number) + 1)]

    all_numbers_with_leading_zero = [
        str(number).zfill(max_leading_zeros + 1) for number in all_numbers
    ]

    names_with_new_number_inserted = [
        f"{name_start_str}{number}{name_end_str}"
        for number in all_numbers_with_leading_zero
    ]

    return names_with_new_number_inserted


def num_leading_zeros(string: str) -> int:
    """int() strips leading zeros"""
    return len(string) - len(str(int(string)))


# Handle @DATE@, @DATETIME@, @TIME@ flags -------------------------------------------------


def update_names_with_datetime(names: List[str]) -> None:
    """
    Replace @DATE@ and @DATETIME@ flag with date and datetime respectively.

    Format using key-value pair for bids, i.e. date-20221223_time-
    """
    date = str(datetime.datetime.now().date().strftime("%Y%m%d"))
    format_date = f"date-{date}"

    time_ = datetime.datetime.now().time().strftime("%H%M%S")
    format_time = f"time-{time_}"

    for i, name in enumerate(names):

        if "@DATETIME@" in name:  # must come first
            name = add_underscore_before_after_if_not_there(name, "@DATETIME@")
            datetime_ = f"{format_date}_{format_time}"
            names[i] = name.replace("@DATETIME@", datetime_)

        elif "@DATE@" in name:
            name = add_underscore_before_after_if_not_there(name, "@DATE@")
            names[i] = name.replace("@DATE@", format_date)

        elif "@TIME@" in name:
            name = add_underscore_before_after_if_not_there(name, "@TIME@")
            names[i] = name.replace("@TIME@", format_time)


def add_underscore_before_after_if_not_there(string: str, key: str) -> str:
    """
    If names are passed with @DATE@, @TIME@, or @DATETIME@
    but not surrounded by underscores, check and insert
    if required. e.g. sub-001@DATE@ becomes sub-001_@DATE@
    or sub-001@DATEid-101 becomes sub-001_@DATE_id-101
    """
    key_len = len(key)
    key_start_idx = string.index(key)

    # Handle left edge
    if string[key_start_idx - 1] != "_":
        string_split = string.split(key)  # assumes key only in string once
        assert (
            len(string_split) == 2
        ), f"{key} must not appear in string more than once."

        string = f"{string_split[0]}_{key}{string_split[1]}"

    updated_key_start_idx = string.index(key)
    key_end_idx = updated_key_start_idx + key_len

    if key_end_idx != len(string) and string[key_end_idx] != "_":
        string = f"{string[:key_end_idx]}_{string[key_end_idx:]}"

    return string


def ensure_prefixes_on_list_of_names(
    names: Union[List[str], str], prefix: str
) -> List[str]:
    """
    Make sure all elements in the list of names are
    prefixed with the prefix typically "sub-" or "ses-"
    """
    n_chars = len(prefix)
    return [
        prefix + name if name[:n_chars] != prefix else name for name in names
    ]
