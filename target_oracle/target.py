"""Oracle target class."""

from __future__ import annotations

from singer_sdk.target_base import SQLTarget
from singer_sdk import typing as th

from target_oracle.sinks import (
    OracleSink,
)


class TargetOracle(SQLTarget):
    """Sample target for Oracle."""

    name = "target-oracle"
    config_jsonschema = th.PropertiesList(
        th.Property(
            "sqlalchemy_url",
            th.StringType,
            secret=True,  # Flag config as protected.
            description="SQLAlchemy connection string",
        ),
        th.Property(
            "driver_name",
            th.StringType,
            default="oracle+cx_oracle",
            description="SQLAlchemy driver name",
        ),
        th.Property(
            "username",
            th.StringType,
            secret=True,  # Flag config as protected.
            description="Oracle username",
        ),
        th.Property(
            "password",
            th.StringType,
            secret=True,  # Flag config as protected.
            description="Oracle password",
        ),
        th.Property(
            "host",
            th.StringType,
            description="Oracle host",
        ),
        th.Property(
            "port",
            th.StringType,
            description="Oracle port",
        ),
        th.Property(
            "database",
            th.StringType,
            description="Oracle database",
        ),
        th.Property(
            "prefer_float_over_numeric",
            th.BooleanType,
            description="Use float data type for numbers (otherwise number type is used)",
            default=False
        ),
        th.Property(
            "table_prefix", th.StringType, description="Prefix to add to table name"
        )
    ).to_dict()

    default_sink_class = OracleSink


if __name__ == "__main__":
    TargetOracle.cli()
