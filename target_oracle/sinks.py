"""Oracle target sink class, which handles writing streams."""

from __future__ import annotations

from singer_sdk.sinks import SQLSink
from singer_sdk.connectors import SQLConnector
import sqlalchemy
from typing import Any, Dict, Iterable, List, Optional, cast
from sqlalchemy.dialects import oracle
from singer_sdk.helpers._typing import get_datelike_property_type
from sqlalchemy.schema import PrimaryKeyConstraint
from sqlalchemy import Column

class OracleConnector(SQLConnector):
    """The connector for Oracle.

    This class handles all DDL and type conversions.
    """

    allow_column_add: bool = True  # Whether ADD COLUMN is supported.
    allow_column_rename: bool = True  # Whether RENAME COLUMN is supported.
    allow_column_alter: bool = True  # Whether altering column types is supported.
    allow_merge_upsert: bool = True  # Whether MERGE UPSERT is supported.
    allow_temp_tables: bool = True  # Whether temp tables are supported.

    def get_sqlalchemy_url(self, config: dict) -> str:
        """Generates a SQLAlchemy URL for Oracle.

        Args:
            config: The configuration for the connector.
        """

        if config.get("sqlalchemy_url"):
            return config["sqlalchemy_url"]

        connection_url = sqlalchemy.engine.url.URL.create(
            drivername="oracle+cx_oracle",
            username=config["user"],
            password=config["password"],
            host=config["host"],
            port=config["port"],
            database=config["database"],
        )
        return connection_url

    def to_sql_type(self, jsonschema_type: dict) -> sqlalchemy.types.TypeEngine:  # noqa
        """Convert JSON Schema type to a SQL type.
        Args:
            jsonschema_type: The JSON Schema object.
        Returns:
            The SQL type.
        """
        if self._jsonschema_type_check(jsonschema_type, ("string",)):
            datelike_type = get_datelike_property_type(jsonschema_type)
            if datelike_type:
                if datelike_type == "date-time":
                    return cast(
                        sqlalchemy.types.TypeEngine, sqlalchemy.types.TIMESTAMP()
                    )
                if datelike_type in "time":
                    return cast(sqlalchemy.types.TypeEngine, sqlalchemy.types.TIME())
                if datelike_type == "date":
                    return cast(sqlalchemy.types.TypeEngine, sqlalchemy.types.DATE())

            maxlength = jsonschema_type.get("maxLength", 255)
            return cast(
                sqlalchemy.types.TypeEngine, sqlalchemy.types.VARCHAR(maxlength)
            )

        if self._jsonschema_type_check(jsonschema_type, ("integer",)):
            return cast(sqlalchemy.types.TypeEngine, sqlalchemy.types.INTEGER())
        if self._jsonschema_type_check(jsonschema_type, ("number",)):
            return cast(sqlalchemy.types.TypeEngine, sqlalchemy.types.NUMERIC(22, 16))
        if self._jsonschema_type_check(jsonschema_type, ("boolean",)):
            return cast(sqlalchemy.types.TypeEngine, oracle.VARCHAR(1))

        if self._jsonschema_type_check(jsonschema_type, ("object",)):
            return cast(sqlalchemy.types.TypeEngine, sqlalchemy.types.VARCHAR(2000))

        if self._jsonschema_type_check(jsonschema_type, ("array",)):
            return cast(sqlalchemy.types.TypeEngine, sqlalchemy.types.VARCHAR(2000))

        return cast(sqlalchemy.types.TypeEngine, sqlalchemy.types.VARCHAR(2000))


    def _jsonschema_type_check(
        self, jsonschema_type: dict, type_check: tuple[str]
    ) -> bool:
        """Return True if the jsonschema_type supports the provided type.
        Args:
            jsonschema_type: The type dict.
            type_check: A tuple of type strings to look for.
        Returns:
            True if the schema suports the type.
        """
        if "type" in jsonschema_type:
            if isinstance(jsonschema_type["type"], (list, tuple)):
                for t in jsonschema_type["type"]:
                    if t in type_check:
                        return True
            else:
                if jsonschema_type.get("type") in type_check:
                    return True

        if any(t in type_check for t in jsonschema_type.get("anyOf", ())):
            return True

        return False


    def _create_empty_column(
        self,
        full_table_name: str,
        column_name: str,
        sql_type: sqlalchemy.types.TypeEngine,
    ) -> None:
        """Create a new column.
        Args:
            full_table_name: The target table name.
            column_name: The name of the new column.
            sql_type: SQLAlchemy type engine to be used in creating the new column.
        Raises:
            NotImplementedError: if adding columns is not supported.
        """
        if not self.allow_column_add:
            raise NotImplementedError("Adding columns is not supported.")

        if column_name.startswith("_"):
            column_name = f"x{column_name}"
        create_column_clause = sqlalchemy.schema.CreateColumn(
            sqlalchemy.Column(
                column_name,
                sql_type,
            )
        )

        try:
            self.connection.execute(
                f"""ALTER TABLE { str(full_table_name) }
                ADD { str(create_column_clause) } """
            )

        except Exception as e:
            raise RuntimeError(
                f"Could not create column '{create_column_clause}' "
                f"on table '{full_table_name}'."
            ) from e

    def create_temp_table_from_table(self, from_table_name, temp_table_name):
        """Temp table from another table."""

        try:
            self.connection.execute(
                f"""DROP TABLE {temp_table_name}"""
            )
        except Exception as e:
            pass
        
        ddl = f"""
            CREATE TABLE {temp_table_name} AS (
                SELECT * FROM {from_table_name}
                WHERE 1=0
            )
        """

        self.connection.execute(ddl)

    def create_empty_table(
        self,
        full_table_name: str,
        schema: dict,
        primary_keys: list[str] | None = None,
        partition_keys: list[str] | None = None,
        as_temp_table: bool = False,
    ) -> None:
        """Create an empty target table.
        Args:
            full_table_name: the target table name.
            schema: the JSON schema for the new table.
            primary_keys: list of key properties.
            partition_keys: list of partition keys.
            as_temp_table: True to create a temp table.
        Raises:
            NotImplementedError: if temp tables are unsupported and as_temp_table=True.
            RuntimeError: if a variant schema is passed with no properties defined.
        """
        if as_temp_table:
            raise NotImplementedError("Temporary tables are not supported.")

        _ = partition_keys  # Not supported in generic implementation.

        _, schema_name, table_name = self.parse_full_table_name(full_table_name)
        meta = sqlalchemy.MetaData(schema=schema_name)
        columns: list[sqlalchemy.Column] = []
        primary_keys = primary_keys or []
        try:
            properties: dict = schema["properties"]
        except KeyError:
            raise RuntimeError(
                f"Schema for '{full_table_name}' does not define properties: {schema}"
            )

        for property_name, property_jsonschema in properties.items():
            is_primary_key = property_name in primary_keys
            columns.append(
                sqlalchemy.Column(
                    property_name,
                    self.to_sql_type(property_jsonschema)
                )
            )
        
        if primary_keys:
            pk_constraint = PrimaryKeyConstraint(*primary_keys, name=f"{table_name}_PK")
            _ = sqlalchemy.Table(table_name, meta, *columns, pk_constraint)
        else:
            _ = sqlalchemy.Table(table_name, meta, *columns)

        meta.create_all(self._engine)


    def merge_sql_types(  # noqa
        self, sql_types: list[sqlalchemy.types.TypeEngine]
    ) -> sqlalchemy.types.TypeEngine:  # noqa
        """Return a compatible SQL type for the selected type list.
        Args:
            sql_types: List of SQL types.
        Returns:
            A SQL type that is compatible with the input types.
        Raises:
            ValueError: If sql_types argument has zero members.
        """
        if not sql_types:
            raise ValueError("Expected at least one member in `sql_types` argument.")

        if len(sql_types) == 1:
            return sql_types[0]

        # Gathering Type to match variables
        # sent in _adapt_column_type
        current_type = sql_types[0]
        # sql_type = sql_types[1]

        # Getting the length of each type
        # current_type_len: int = getattr(sql_types[0], "length", 0)
        sql_type_len: int = getattr(sql_types[1], "length", 0)
        if sql_type_len is None:
            sql_type_len = 0

        # Convert the two types given into a sorted list
        # containing the best conversion classes
        sql_types = self._sort_types(sql_types)

        # If greater than two evaluate the first pair then on down the line
        if len(sql_types) > 2:
            return self.merge_sql_types(
                [self.merge_sql_types([sql_types[0], sql_types[1]])] + sql_types[2:]
            )

        assert len(sql_types) == 2
        # Get the generic type class
        for opt in sql_types:
            # Get the length
            opt_len: int = getattr(opt, "length", 0)
            generic_type = type(opt.as_generic())

            if isinstance(generic_type, type):
                if issubclass(
                    generic_type,
                    (sqlalchemy.types.String, sqlalchemy.types.Unicode),
                ):
                    # If length None or 0 then is varchar max ?
                    if (
                        (opt_len is None)
                        or (opt_len == 0)
                        or (opt_len >= current_type.length)
                    ):
                        return opt
                elif isinstance(
                    generic_type,
                    (sqlalchemy.types.String, sqlalchemy.types.Unicode),
                ):
                    # If length None or 0 then is varchar max ?
                    if (
                        (opt_len is None)
                        or (opt_len == 0)
                        or (opt_len >= current_type.length)
                    ):
                        return opt
                # If best conversion class is equal to current type
                # return the best conversion class
                elif str(opt) == str(current_type):
                    return opt

        raise ValueError(
            f"Unable to merge sql types: {', '.join([str(t) for t in sql_types])}"
        )


    def _adapt_column_type(
        self,
        full_table_name: str,
        column_name: str,
        sql_type: sqlalchemy.types.TypeEngine,
    ) -> None:
        """Adapt table column type to support the new JSON schema type.
        Args:
            full_table_name: The target table name.
            column_name: The target column name.
            sql_type: The new SQLAlchemy type.
        Raises:
            NotImplementedError: if altering columns is not supported.
        """
        current_type: sqlalchemy.types.TypeEngine = self._get_column_type(
            full_table_name, column_name
        )

        # Check if the existing column type and the sql type are the same
        if str(sql_type) == str(current_type):
            # The current column and sql type are the same
            # Nothing to do
            return

        # Not the same type, generic type or compatible types
        # calling merge_sql_types for assistnace
        compatible_sql_type = self.merge_sql_types([current_type, sql_type])

        if str(compatible_sql_type).split(" ")[0] == str(current_type).split(" ")[0]:
            # Nothing to do
            return

        if not self.allow_column_alter:
            raise NotImplementedError(
                "Altering columns is not supported. "
                f"Could not convert column '{full_table_name}.{column_name}' "
                f"from '{current_type}' to '{compatible_sql_type}'."
            )
        try:
            self.connection.execute(
                f"""ALTER TABLE { str(full_table_name) }
                MODIFY ({ str(column_name) } { str(compatible_sql_type) })"""
            )
        except Exception as e:
            raise RuntimeError(
                f"Could not convert column '{full_table_name}.{column_name}' "
                f"from '{current_type}' to '{compatible_sql_type}'."
            ) from e


class OracleSink(SQLSink):
    """Oracle target sink class."""

    soft_delete_column_name = "x_sdc_deleted_at"
    version_column_name = "x_sdc_table_version"
    connector_class = OracleConnector

    @property
    def schema_name(self) -> Optional[str]:
        """Return the schema name or `None` if using names with no schema part.
        Returns:
            The target schema name.
        """
        # Look for a default_target_scheme in the configuraion fle
        default_target_schema: str = self.config.get("default_target_schema", None)
        parts = self.stream_name.split("-")

        # 1) When default_target_scheme is in the configuration use it
        # 2) if the streams are in <schema>-<table> format use the
        #    stream <schema>
        # 3) Return None if you don't find anything
        if default_target_schema:
            return default_target_schema

        # Schema name not detected.
        return None

    def process_batch(self, context: dict) -> None:
        """Process a batch with the given batch context.
        Writes a batch to the SQL target. Developers may override this method
        in order to provide a more efficient upload/upsert process.
        Args:
            context: Stream partition or context dictionary.
        """
        # First we need to be sure the main table is already created

        if self.key_properties:
            self.logger.info(f"Preparing table {self.full_table_name}")
            self.connector.prepare_table(
                full_table_name=self.full_table_name,
                schema=self.schema,
                primary_keys=self.key_properties,
                as_temp_table=False,
            )

            tmp_table_name = self.full_table_name + "_temp"

            # Create a temp table (Creates from the table above)
            self.logger.info(f"Creating temp table {self.full_table_name}")
            self.connector.create_temp_table_from_table(
                from_table_name=self.full_table_name,
                temp_table_name=tmp_table_name
            )


            # Insert into temp table
            self.bulk_insert_records(
                full_table_name=tmp_table_name,
                schema=self.schema,
                records=context["records"],
            )
            # Merge data from Temp table to main table
            self.logger.info(f"Merging data from temp table to {self.full_table_name}")
            self.merge_upsert_from_table(
                from_table_name=tmp_table_name,
                to_table_name=self.full_table_name,
                schema=self.schema,
                join_keys=self.key_properties,
            )

        else:
            self.bulk_insert_records(
                full_table_name=self.full_table_name,
                schema=self.schema,
                records=context["records"],
            )

    def merge_upsert_from_table(
        self,
        from_table_name: str,
        to_table_name: str,
        schema: dict,
        join_keys: List[str],
    ) -> Optional[int]:
        """Merge upsert data from one table to another.
        Args:
            from_table_name: The source table name.
            to_table_name: The destination table name.
            join_keys: The merge upsert keys, or `None` to append.
            schema: Singer Schema message.
        Return:
            The number of records copied, if detectable, or `None` if the API does not
            report number of records affected/inserted.
        """
        # TODO think about sql injeciton,
        # issue here https://github.com/MeltanoLabs/target-postgres/issues/22

        join_condition = " and ".join(
            [f"temp.{key} = target.{key}" for key in join_keys]
        )

        update_stmt = ", ".join(
            [
                f"target.{key} = temp.{key}"
                for key in schema["properties"].keys()
                if key not in join_keys
            ]
        )  # noqa

        merge_sql = f"""
            MERGE INTO {to_table_name} target
            USING {from_table_name} temp
            ON ({join_condition})
            WHEN MATCHED THEN
                UPDATE SET
                    { update_stmt }
            WHEN NOT MATCHED THEN
                INSERT ({", ".join(schema["properties"].keys())})
                VALUES ({", ".join([f"temp.{key}" for key in schema["properties"].keys()])})
        """

        self.connection.execute(merge_sql)

        self.connection.execute("COMMIT")

        self.connection.execute(f"DROP TABLE {from_table_name}")

    def bulk_insert_records(
        self,
        full_table_name: str,
        schema: dict,
        records: Iterable[Dict[str, Any]],
    ) -> Optional[int]:
        """Bulk insert records to an existing destination table.
        The default implementation uses a generic SQLAlchemy bulk insert operation.
        This method may optionally be overridden by developers in order to provide
        faster, native bulk uploads.
        Args:
            full_table_name: the target table name.
            schema: the JSON schema for the new table, to be used when inferring column
                names.
            records: the input records.
        Returns:
            True if table exists, False if not, None if unsure or undetectable.
        """
        insert_sql = self.generate_insert_statement(
            full_table_name,
            schema,
        )
        if isinstance(insert_sql, str):
            insert_sql = sqlalchemy.text(insert_sql)

        self.logger.info("Inserting with SQL: %s", insert_sql)

        columns = self.column_representation(schema)

        # temporary fix to ensure missing properties are added
        insert_records = []
        for record in records:
            insert_record = {}
            # for column in columns:
            #     conformed_colname = self.conform_name(column.name)
            #     insert_record[conformed_colname] = record.get(conformed_colname)

            for key in record.keys():
                conformed_key = self.conform_name(key)
                insert_record[conformed_key] = record.get(key)
            insert_records.append(insert_record)

        self.connection.execute(insert_sql, insert_records)
        self.connection.execute("COMMIT")

        if isinstance(records, list):
            return len(records)  # If list, we can quickly return record count.

        return None  # Unknown record count.


    def column_representation(
        self,
        schema: dict,
    ) -> List[Column]:
        """Returns a sql alchemy table representation for the current schema."""
        columns: list[Column] = []
        conformed_properties = self.conform_schema(schema)["properties"]
        for property_name, property_jsonschema in conformed_properties.items():
            columns.append(
                Column(
                    property_name,
                    self.connector.to_sql_type(property_jsonschema),
                )
            )
        return columns