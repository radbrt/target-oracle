""" Attempt at making some standard Target Tests. """
# flake8: noqa
import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from singer_sdk.testing import sync_end_to_end

from target_oracle.target import TargetOracle
from target_oracle.tests.samples.aapl.aapl import Fundamentals
from target_oracle.tests.samples.sample_tap_countries.countries_tap import (
    SampleTapCountries,
)


@pytest.fixture()
def oracle_config():
    return {
        "schema": "SYSTEM",
        "user": "SYSTEM",
        "password": "P@55w0rd",
        "host": "localhost",
        "port": "1521",
        "database": "XE",
        "write_column_comments": True
    }


@pytest.fixture
def oracle_target(oracle_config) -> TargetOracle:
    return TargetOracle(config=oracle_config)


def singer_file_to_target(file_name, target) -> None:
    """Singer file to Target, emulates a tap run
    Equivalent to running cat file_path | target-name --config config.json.
    Note that this function loads all lines into memory, so it is
    not good very large files.
    Args:
        file_name: name to file in .tests/data_files to be sent into target
        Target: Target to pass data from file_path into..
    """
    file_path = Path(__file__).parent / Path("./data_files") / Path(file_name)
    buf = io.StringIO()
    with redirect_stdout(buf):
        with open(file_path, "r") as f:
            for line in f:
                print(line.rstrip("\r\n"))  # File endings are here,
                # and print adds another line ending so we need to remove one.
    buf.seek(0)
    target.listen(buf)


# TODO should set schemas for each tap individually so we don't collide
# Test name would work well
@pytest.mark.skip(
    reason="TODO: Something with identity, doesn't make sense. external API, skipping"
)
def test_countries_to_oracle(oracle_config):
    tap = SampleTapCountries(config={}, state=None)
    target = TargetOracle(config=oracle_config)
    sync_end_to_end(tap, target)

@pytest.mark.skip("SQLalchemy and object column types don't work well together")
def test_aapl_to_oracle(oracle_config):
    tap = Fundamentals(config={}, state=None)
    target = TargetOracle(config=oracle_config)
    sync_end_to_end(tap, target)


# TODO this test should throw an exception
def test_record_before_schema(oracle_target):
    with pytest.raises(Exception) as e_info:
        file_name = "record_before_schema.singer"
        singer_file_to_target(file_name, oracle_target)


# TODO this test should throw an exception
def test_invalid_schema(oracle_target):
    with pytest.raises(Exception) as e_info:
        file_name = "invalid_schema.singer"
        singer_file_to_target(file_name, oracle_target)


# TODO this test should throw an exception
def test_record_missing_key_property(oracle_target):
    with pytest.raises(Exception) as e_info:
        file_name = "record_missing_key_property.singer"
        singer_file_to_target(file_name, oracle_target)


# TODO this test should throw an exception
def test_record_missing_required_property(oracle_target):
    with pytest.raises(Exception) as e_info:
        file_name = "record_missing_required_property.singer"
        singer_file_to_target(file_name, oracle_target)


# TODO test that data is correctly set
# see target-sqllit/tests/test_target_sqllite.py
# @pytest.mark.skip(reason="Waiting for SDK to handle this")
def test_column_camel_case(oracle_target):
    file_name = "camelcase.singer"
    singer_file_to_target(file_name, oracle_target)


# TODO test that data is correctly set
@pytest.mark.skip(reason="Waiting for SDK to handle this")
def test_special_chars_in_attributes(oracle_target):
    file_name = "special_chars_in_attributes.singer"
    singer_file_to_target(file_name, oracle_target)


# TODO test that data is correctly set
def test_optional_attributes(oracle_target):
    file_name = "optional_attributes.singer"
    singer_file_to_target(file_name, oracle_target)


# Test that schema without properties (no columns) fails
def test_schema_no_properties(oracle_target):
    with pytest.raises(Exception) as e_info:
        file_name = "schema_no_properties.singer"
        singer_file_to_target(file_name, oracle_target)


# TODO test that data is correct
def test_schema_updates(oracle_target):
    file_name = "schema_updates.singer"
    singer_file_to_target(file_name, oracle_target)


# TODO test that data is correct
def test_multiple_state_messages(oracle_target):
    file_name = "multiple_state_messages.singer"
    singer_file_to_target(file_name, oracle_target)


# TODO test that data is correct
@pytest.mark.skip(reason="TODO")
def test_relational_data(oracle_target):
    file_name = "user_location_data.singer"
    singer_file_to_target(file_name, oracle_target)

    file_name = "user_location_upsert_data.singer"
    singer_file_to_target(file_name, oracle_target)


# TODO test that data is correct
def test_no_primary_keys(oracle_target):
    file_name = "no_primary_keys.singer"
    singer_file_to_target(file_name, oracle_target)

    file_name = "no_primary_keys_append.singer"
    singer_file_to_target(file_name, oracle_target)


# TODO test that data is correct
def test_duplicate_records(oracle_target):
    with pytest.raises(Exception) as e_info:
        file_name = "duplicate_records.singer"
        singer_file_to_target(file_name, oracle_target)


@pytest.mark.skip(reason="Arrays of arrays not supported")
def test_array_data(oracle_target):
    file_name = "array_data.singer"
    singer_file_to_target(file_name, oracle_target)


@pytest.mark.skip(reason="TODO")
def test_encoded_string_data(oracle_target):
    file_name = "encoded_strings.singer"
    singer_file_to_target(file_name, oracle_target)

@pytest.mark.skip(reason="Something about objects not supported")
def test_tap_appl(oracle_target):
    file_name = "tap_aapl.singer"
    singer_file_to_target(file_name, oracle_target)


@pytest.mark.skip(reason="TODO")
def test_tap_countries(oracle_target):
    file_name = "tap_countries.singer"
    singer_file_to_target(file_name, oracle_target)


def test_missing_value(oracle_target):
    file_name = "missing_value.singer"
    singer_file_to_target(file_name, oracle_target)


@pytest.mark.skip(reason="TODO")
def test_large_int(oracle_target):
    file_name = "large_int.singer"
    singer_file_to_target(file_name, oracle_target)


def test_db_schema(oracle_target):
    file_name = "target_schema.singer"
    singer_file_to_target(file_name, oracle_target)


def test_column_comments(oracle_target):
    file_name = "column_comments.singer"
    singer_file_to_target(file_name, oracle_target)