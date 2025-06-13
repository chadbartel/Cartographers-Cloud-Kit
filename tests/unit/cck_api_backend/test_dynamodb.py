# Standard Library
from decimal import Decimal

# Third Party
import boto3
import pytest
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from moto import mock_aws

# Local Modules
from api_backend.aws.dynamodb import DynamoDb


def create_test_table_and_data():
    """Helper function to create test table and data within mock context."""
    table_name = "test-table"

    # Create DynamoDB resource and table
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
            {"AttributeName": "sort_key", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "sort_key", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Wait for table to be created (mocked, so instant)
    table.wait_until_exists()

    # Add some test items (using Decimal for numeric values)
    test_items = [
        {
            "id": "test-id-1",
            "sort_key": "a",
            "name": "Test Item 1",
            "value": Decimal("100"),
            "active": True,
        },
        {
            "id": "test-id-1",
            "sort_key": "b",
            "name": "Test Item 2",
            "value": Decimal("200"),
            "active": False,
        },
        {
            "id": "test-id-2",
            "sort_key": "a",
            "name": "Test Item 3",
            "value": Decimal("300"),
            "active": True,
        },
    ]

    for item in test_items:
        table.put_item(Item=item)

    return table_name, test_items


class TestDynamoDbInit:
    """Test cases for DynamoDb initialization."""

    def test_dynamodb_init_success(self):
        """Test successful DynamoDb initialization."""
        with mock_aws():
            # Arrange
            table_name = "test-table"

            # Create a table first
            dynamodb = boto3.resource("dynamodb")
            dynamodb.create_table(
                TableName=table_name,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": "id", "AttributeType": "S"}
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            # Act
            db_client = DynamoDb(table_name=table_name)

            # Assert
            assert db_client.table_name == table_name
            assert db_client._table is not None
            assert db_client._dynamodb is not None

    def test_dynamodb_init_exception(self, monkeypatch):
        """Test DynamoDb initialization exception handling."""
        # Arrange
        table_name = "test-table"

        def mock_boto3_resource(*args, **kwargs):
            raise Exception("Failed to create resource")

        monkeypatch.setattr(
            "api_backend.aws.dynamodb.boto3.resource", mock_boto3_resource
        )

        # Act & Assert
        with pytest.raises(Exception, match="Failed to create resource"):
            DynamoDb(table_name=table_name)


class TestDynamoDbPutItem:
    """Test cases for put_item method."""

    def test_put_item_success(self):
        """Test successful item insertion."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            item = {
                "id": "new-item",
                "sort_key": "new",
                "name": "New Test Item",
                "value": Decimal("999"),
            }

            # Act
            response = db_client.put_item(item)

            # Assert
            assert "ResponseMetadata" in response
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

            # Verify item was actually inserted
            retrieved_item = db_client.get_item(
                {"id": "new-item", "sort_key": "new"}
            )
            assert retrieved_item == item

    def test_put_item_client_error(self, monkeypatch):
        """Test put_item with ClientError."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_put_item(*args, **kwargs):
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ValidationException",
                            "Message": "Invalid item",
                        }
                    },
                    operation_name="PutItem",
                )

            monkeypatch.setattr(db_client._table, "put_item", mock_put_item)

            item = {"id": "test-id", "sort_key": "test"}

            # Act & Assert
            with pytest.raises(ClientError):
                db_client.put_item(item)

    def test_put_item_general_exception(self, monkeypatch):
        """Test put_item with general exception."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_put_item(*args, **kwargs):
                raise Exception("Unexpected error")

            monkeypatch.setattr(db_client._table, "put_item", mock_put_item)

            item = {"id": "test-id", "sort_key": "test"}

            # Act & Assert
            with pytest.raises(Exception, match="Unexpected error"):
                db_client.put_item(item)


class TestDynamoDbGetItem:
    """Test cases for get_item method."""

    def test_get_item_success_existing(self):
        """Test successful retrieval of existing item."""
        with mock_aws():
            # Arrange
            table_name, test_items = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key = {"id": "test-id-1", "sort_key": "a"}

            # Act
            result = db_client.get_item(key)

            # Assert
            assert result is not None
            assert result["id"] == "test-id-1"
            assert result["sort_key"] == "a"
            assert result["name"] == "Test Item 1"
            assert result["value"] == Decimal("100")
            assert result["active"] is True

    def test_get_item_success_nonexistent(self):
        """Test retrieval of non-existent item."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key = {"id": "nonexistent-id", "sort_key": "nonexistent"}

            # Act
            result = db_client.get_item(key)

            # Assert
            assert result is None

    def test_get_item_client_error(self, monkeypatch):
        """Test get_item with ClientError."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_get_item(*args, **kwargs):
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ResourceNotFoundException",
                            "Message": "Table not found",
                        }
                    },
                    operation_name="GetItem",
                )

            monkeypatch.setattr(db_client._table, "get_item", mock_get_item)

            key = {"id": "test-id"}

            # Act & Assert
            with pytest.raises(ClientError):
                db_client.get_item(key)

    def test_get_item_general_exception(self, monkeypatch):
        """Test get_item with general exception."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_get_item(*args, **kwargs):
                raise Exception("Network error")

            monkeypatch.setattr(db_client._table, "get_item", mock_get_item)

            key = {"id": "test-id"}

            # Act & Assert
            with pytest.raises(Exception, match="Network error"):
                db_client.get_item(key)


class TestDynamoDbUpdateItem:
    """Test cases for update_item method."""

    def test_update_item_success_basic(self):
        """Test successful item update with basic parameters."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key = {"id": "test-id-1", "sort_key": "a"}
            update_expression = "SET #n = :new_name, #v = :new_value"
            expression_attribute_names = {"#n": "name", "#v": "value"}
            expression_attribute_values = {
                ":new_name": "Updated Item",
                ":new_value": Decimal("150"),
            }

            # Act
            response = db_client.update_item(
                key=key,
                update_expression=update_expression,
                expression_attribute_names=expression_attribute_names,
                expression_attribute_values=expression_attribute_values,
            )

            # Assert
            assert "Attributes" in response
            updated_item = response["Attributes"]
            assert updated_item["name"] == "Updated Item"
            assert updated_item["value"] == Decimal("150")
            assert updated_item["id"] == "test-id-1"

    def test_update_item_success_no_optional_params(self):
        """Test successful item update without optional parameters."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key = {"id": "test-id-1", "sort_key": "a"}
            update_expression = "SET active = :active"
            expression_attribute_values = {":active": False}

            # Act
            response = db_client.update_item(
                key=key,
                update_expression=update_expression,
                expression_attribute_values=expression_attribute_values,
            )

            # Assert
            assert "Attributes" in response
            updated_item = response["Attributes"]
            assert updated_item["active"] is False

    def test_update_item_success_only_names(self):
        """Test successful item update with only expression attribute names."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key = {"id": "test-id-1", "sort_key": "a"}
            update_expression = "SET #n = :new_name"
            expression_attribute_names = {"#n": "name"}
            expression_attribute_values = {
                ":new_name": "Name with Attribute Names"
            }

            # Act
            response = db_client.update_item(
                key=key,
                update_expression=update_expression,
                expression_attribute_names=expression_attribute_names,
                expression_attribute_values=expression_attribute_values,
            )

            # Assert
            assert "Attributes" in response
            updated_item = response["Attributes"]
            assert updated_item["name"] == "Name with Attribute Names"

    def test_update_item_success_no_optional_attributes(self):
        """Test successful item update without any optional parameters."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key = {"id": "test-id-1", "sort_key": "a"}
            # Use a simple update expression without any attribute names or values
            update_expression = "SET active = active"

            # Act
            response = db_client.update_item(
                key=key,
                update_expression=update_expression,
            )

            # Assert
            assert "Attributes" in response
            updated_item = response["Attributes"]
            assert updated_item["id"] == "test-id-1"

    def test_update_item_client_error(self, monkeypatch):
        """Test update_item with ClientError."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_update_item(*args, **kwargs):
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ConditionalCheckFailedException",
                            "Message": "Condition check failed",
                        }
                    },
                    operation_name="UpdateItem",
                )

            monkeypatch.setattr(
                db_client._table, "update_item", mock_update_item
            )

            key = {"id": "test-id"}
            update_expression = "SET active = :active"
            expression_attribute_values = {":active": False}

            # Act & Assert
            with pytest.raises(ClientError):
                db_client.update_item(
                    key=key,
                    update_expression=update_expression,
                    expression_attribute_values=expression_attribute_values,
                )

    def test_update_item_general_exception(self, monkeypatch):
        """Test update_item with general exception."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_update_item(*args, **kwargs):
                raise Exception("Serialization error")

            monkeypatch.setattr(
                db_client._table, "update_item", mock_update_item
            )

            key = {"id": "test-id"}
            update_expression = "SET active = :active"
            expression_attribute_values = {":active": False}

            # Act & Assert
            with pytest.raises(Exception, match="Serialization error"):
                db_client.update_item(
                    key=key,
                    update_expression=update_expression,
                    expression_attribute_values=expression_attribute_values,
                )


class TestDynamoDbDeleteItem:
    """Test cases for delete_item method."""

    def test_delete_item_success_existing(self):
        """Test successful deletion of existing item."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key = {"id": "test-id-1", "sort_key": "a"}

            # Verify item exists before deletion
            item_before = db_client.get_item(key)
            assert item_before is not None

            # Act
            response = db_client.delete_item(key)

            # Assert
            assert "ResponseMetadata" in response
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

            # Verify item was deleted
            item_after = db_client.get_item(key)
            assert item_after is None

    def test_delete_item_success_nonexistent(self):
        """Test deletion of non-existent item (should succeed)."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key = {"id": "nonexistent-id", "sort_key": "nonexistent"}

            # Act
            response = db_client.delete_item(key)

            # Assert
            assert "ResponseMetadata" in response
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_delete_item_client_error(self, monkeypatch):
        """Test delete_item with ClientError."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_delete_item(*args, **kwargs):
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ConditionalCheckFailedException",
                            "Message": "Condition check failed",
                        }
                    },
                    operation_name="DeleteItem",
                )

            monkeypatch.setattr(
                db_client._table, "delete_item", mock_delete_item
            )

            key = {"id": "test-id"}

            # Act & Assert
            with pytest.raises(ClientError):
                db_client.delete_item(key)

    def test_delete_item_general_exception(self, monkeypatch):
        """Test delete_item with general exception."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_delete_item(*args, **kwargs):
                raise Exception("Connection timeout")

            monkeypatch.setattr(
                db_client._table, "delete_item", mock_delete_item
            )

            key = {"id": "test-id"}

            # Act & Assert
            with pytest.raises(Exception, match="Connection timeout"):
                db_client.delete_item(key)


class TestDynamoDbScan:
    """Test cases for scan method."""

    def test_scan_success_no_parameters(self):
        """Test successful scan without any parameters."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Act
            response = db_client.scan()

            # Assert
            assert "Items" in response
            assert len(response["Items"]) == 3  # All test items
            assert "Count" in response
            assert response["Count"] == 3

    def test_scan_success_with_filter_expression(self):
        """Test successful scan with filter expression."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Only get active items
            filter_expression = Attr("active").eq(True)

            # Act
            response = db_client.scan(filter_expression=filter_expression)

            # Assert
            assert "Items" in response
            assert len(response["Items"]) == 2  # Only active items
            for item in response["Items"]:
                assert item["active"] is True

    def test_scan_success_with_projection_expression(self):
        """Test successful scan with projection expression."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Use simple projection expression without reserved keywords
            projection_expression = "id, sort_key, active"

            # Act
            response = db_client.scan(
                projection_expression=projection_expression
            )

            # Assert
            assert "Items" in response
            assert len(response["Items"]) == 3
            for item in response["Items"]:
                # Should only have projected attributes
                assert "id" in item
                assert "sort_key" in item
                assert "active" in item
                # Should not have name or value
                assert "name" not in item
                assert "value" not in item

    def test_scan_success_with_both_expressions(self):
        """Test successful scan with both filter and projection expressions."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            filter_expression = Attr("value").gt(Decimal("150"))
            projection_expression = "id, active, sort_key"

            # Act
            response = db_client.scan(
                filter_expression=filter_expression,
                projection_expression=projection_expression,
            )

            # Assert
            assert "Items" in response
            # Should get items with value > 150 (test-id-1 with value 200, test-id-2 with value 300)
            assert len(response["Items"]) == 2
            for item in response["Items"]:
                assert "id" in item
                assert "active" in item
                assert "sort_key" in item

    def test_scan_client_error(self, monkeypatch):
        """Test scan with ClientError."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_scan(*args, **kwargs):
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ValidationException",
                            "Message": "Table not found",
                        }
                    },
                    operation_name="Scan",
                )

            monkeypatch.setattr(db_client._table, "scan", mock_scan)

            # Act & Assert
            with pytest.raises(ClientError):
                db_client.scan()

    def test_scan_general_exception(self, monkeypatch):
        """Test scan with general exception."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_scan(*args, **kwargs):
                raise Exception("Memory error")

            monkeypatch.setattr(db_client._table, "scan", mock_scan)

            # Act & Assert
            with pytest.raises(Exception, match="Memory error"):
                db_client.scan()


class TestDynamoDbQuery:
    """Test cases for query method."""

    def test_query_success_basic(self):
        """Test successful basic query."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key_condition = Key("id").eq("test-id-1")

            # Act
            response = db_client.query(key_condition_expression=key_condition)

            # Assert
            assert "Items" in response
            assert len(response["Items"]) == 2  # Two items with test-id-1
            for item in response["Items"]:
                assert item["id"] == "test-id-1"

    def test_query_success_with_filter_expression(self):
        """Test successful query with filter expression."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key_condition = Key("id").eq("test-id-1")
            filter_expression = Attr("active").eq(True)

            # Act
            response = db_client.query(
                key_condition_expression=key_condition,
                filter_expression=filter_expression,
            )

            # Assert
            assert "Items" in response
            assert (
                len(response["Items"]) == 1
            )  # Only active item with test-id-1
            assert response["Items"][0]["active"] is True

    def test_query_success_with_projection_expression(self):
        """Test successful query with projection expression."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key_condition = Key("id").eq("test-id-1")
            projection_expression = "id, sort_key, active"

            # Act
            response = db_client.query(
                key_condition_expression=key_condition,
                projection_expression=projection_expression,
            )

            # Assert
            assert "Items" in response
            assert len(response["Items"]) == 2
            for item in response["Items"]:
                assert "id" in item
                assert "sort_key" in item
                assert "active" in item
                # Should not have name or value
                assert "name" not in item
                assert "value" not in item

    def test_query_success_with_limit(self):
        """Test successful query with limit."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key_condition = Key("id").eq("test-id-1")
            limit = 1

            # Act
            response = db_client.query(
                key_condition_expression=key_condition,
                limit=limit,
            )

            # Assert
            assert "Items" in response
            assert len(response["Items"]) == 1  # Limited to 1 item

    def test_query_success_with_exclusive_start_key(self):
        """Test successful query with exclusive start key."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key_condition = Key("id").eq("test-id-1")

            # First get one item to use as start key
            first_response = db_client.query(
                key_condition_expression=key_condition,
                limit=1,
            )

            # Use first item as exclusive start key for pagination
            exclusive_start_key = {
                "id": first_response["Items"][0]["id"],
                "sort_key": first_response["Items"][0]["sort_key"],
            }

            # Act
            response = db_client.query(
                key_condition_expression=key_condition,
                exclusive_start_key=exclusive_start_key,
            )

            # Assert
            assert "Items" in response
            # Should get remaining items (not including the start key item)
            assert len(response["Items"]) == 1

    def test_query_success_all_parameters(self):
        """Test successful query with all parameters."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            key_condition = Key("id").eq("test-id-1")
            filter_expression = Attr("value").gt(Decimal("50"))
            projection_expression = "id, sort_key, #v"
            limit = 5

            # Act
            response = db_client.query(
                key_condition_expression=key_condition,
                filter_expression=filter_expression,
                projection_expression=projection_expression,
                limit=limit,
            )

            # Assert
            assert "Items" in response
            assert len(response["Items"]) <= limit
            for item in response["Items"]:
                assert "id" in item
                assert "sort_key" in item

    def test_query_client_error(self, monkeypatch):
        """Test query with ClientError."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_query(*args, **kwargs):
                raise ClientError(
                    error_response={
                        "Error": {
                            "Code": "ValidationException",
                            "Message": "Invalid key condition",
                        }
                    },
                    operation_name="Query",
                )

            monkeypatch.setattr(db_client._table, "query", mock_query)

            key_condition = Key("id").eq("test-id-1")

            # Act & Assert
            with pytest.raises(ClientError):
                db_client.query(key_condition_expression=key_condition)

    def test_query_general_exception(self, monkeypatch):
        """Test query with general exception."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_query(*args, **kwargs):
                raise Exception("Connection error")

            monkeypatch.setattr(db_client._table, "query", mock_query)

            key_condition = Key("id").eq("test-id-1")

            # Act & Assert
            with pytest.raises(Exception, match="Connection error"):
                db_client.query(key_condition_expression=key_condition)


class TestDynamoDbBatchWrite:
    """Test cases for batch_write method."""

    def test_batch_write_success(self):
        """Test successful batch write operation."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            batch_items = [
                {
                    "id": "batch-1",
                    "sort_key": "item1",
                    "name": "Batch Item 1",
                    "value": Decimal("10"),
                },
                {
                    "id": "batch-2",
                    "sort_key": "item2",
                    "name": "Batch Item 2",
                    "value": Decimal("20"),
                },
                {
                    "id": "batch-3",
                    "sort_key": "item3",
                    "name": "Batch Item 3",
                    "value": Decimal("30"),
                },
            ]

            # Act
            response = db_client.batch_write(batch_items)

            # Assert
            assert "UnprocessedItems" in response
            assert response["UnprocessedItems"] == {}

            # Verify items were inserted
            for item in batch_items:
                key = {"id": item["id"], "sort_key": item["sort_key"]}
                retrieved_item = db_client.get_item(key)
                assert retrieved_item is not None
                assert retrieved_item["name"] == item["name"]
                assert retrieved_item["value"] == item["value"]

    def test_batch_write_empty_list(self):
        """Test batch write with empty list."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Act
            response = db_client.batch_write([])

            # Assert
            assert "UnprocessedItems" in response
            assert response["UnprocessedItems"] == {}

    def test_batch_write_client_error(self, monkeypatch):
        """Test batch_write with ClientError."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_batch_writer():
                class MockBatchWriter:
                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc_val, exc_tb):
                        pass

                    def put_item(self, Item):
                        raise ClientError(
                            error_response={
                                "Error": {
                                    "Code": "ValidationException",
                                    "Message": "Invalid item format",
                                }
                            },
                            operation_name="BatchWriteItem",
                        )

                return MockBatchWriter()

            monkeypatch.setattr(
                db_client._table, "batch_writer", mock_batch_writer
            )

            items = [{"id": "test", "sort_key": "test"}]

            # Act & Assert
            with pytest.raises(ClientError):
                db_client.batch_write(items)

    def test_batch_write_general_exception(self, monkeypatch):
        """Test batch_write with general exception."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            def mock_batch_writer():
                class MockBatchWriter:
                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc_val, exc_tb):
                        pass

                    def put_item(self, Item):
                        raise Exception("Network timeout")

                return MockBatchWriter()

            monkeypatch.setattr(
                db_client._table, "batch_writer", mock_batch_writer
            )

            items = [{"id": "test", "sort_key": "test"}]

            # Act & Assert
            with pytest.raises(Exception, match="Network timeout"):
                db_client.batch_write(items)


class TestDynamoDbIntegration:
    """Integration test cases testing multiple operations together."""

    def test_full_crud_cycle(self):
        """Test complete CRUD cycle with all operations."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Test item for CRUD operations
            test_item = {
                "id": "crud-test",
                "sort_key": "item",
                "name": "CRUD Test Item",
                "value": Decimal("500"),
                "active": True,
            }

            # CREATE - Put item
            put_response = db_client.put_item(test_item)
            assert put_response["ResponseMetadata"]["HTTPStatusCode"] == 200

            # READ - Get item
            key = {"id": "crud-test", "sort_key": "item"}
            retrieved_item = db_client.get_item(key)
            assert retrieved_item == test_item

            # UPDATE - Update item
            update_expression = "SET #n = :new_name, active = :active"
            expression_attribute_names = {"#n": "name"}
            expression_attribute_values = {
                ":new_name": "Updated CRUD Item",
                ":active": False,
            }

            update_response = db_client.update_item(
                key=key,
                update_expression=update_expression,
                expression_attribute_names=expression_attribute_names,
                expression_attribute_values=expression_attribute_values,
            )

            updated_item = update_response["Attributes"]
            assert updated_item["name"] == "Updated CRUD Item"
            assert updated_item["active"] is False

            # DELETE - Delete item
            delete_response = db_client.delete_item(key)
            assert delete_response["ResponseMetadata"]["HTTPStatusCode"] == 200

            # Verify deletion
            deleted_item = db_client.get_item(key)
            assert deleted_item is None

    def test_query_and_scan_operations(self):
        """Test query and scan operations with filtering."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Test scan with filter
            scan_response = db_client.scan(
                filter_expression=Attr("active").eq(True)
            )
            active_items = scan_response["Items"]
            assert len(active_items) == 2
            for item in active_items:
                assert item["active"] is True

            # Test query with key condition
            query_response = db_client.query(
                key_condition_expression=Key("id").eq("test-id-1")
            )
            queried_items = query_response["Items"]
            assert len(queried_items) == 2
            for item in queried_items:
                assert item["id"] == "test-id-1"

    def test_batch_operations_with_verification(self):
        """Test batch operations and verify results."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Create batch items
            batch_items = []
            for i in range(5):
                item = {
                    "id": f"batch-test-{i}",
                    "sort_key": "item",
                    "name": f"Batch Item {i}",
                    "value": Decimal(str(i * 10)),
                    "active": i % 2 == 0,  # Alternate active status
                }
                batch_items.append(item)

            # Batch write
            batch_response = db_client.batch_write(batch_items)
            assert batch_response["UnprocessedItems"] == {}

            # Verify all items were written
            for item in batch_items:
                key = {"id": item["id"], "sort_key": item["sort_key"]}
                retrieved_item = db_client.get_item(key)
                assert retrieved_item is not None
                assert retrieved_item["name"] == item["name"]

            # Count items with scan
            scan_response = db_client.scan()
            total_items = len(scan_response["Items"])
            # Should have 3 original + 5 batch = 8 total items
            assert total_items == 8


class TestDynamoDbEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def test_empty_key_handling(self):
        """Test handling of empty or invalid keys."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Test with completely empty key
            empty_key = {}

            # Should raise an exception for invalid key
            with pytest.raises((ClientError, Exception)):
                db_client.get_item(empty_key)

    def test_large_item_handling(self):
        """Test handling of items with large data."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Create item with large string data
            large_data = "x" * 1000  # 1KB string
            large_item = {
                "id": "large-item",
                "sort_key": "data",
                "large_field": large_data,
                "value": Decimal("999"),
            }

            # Act - Put and retrieve large item
            put_response = db_client.put_item(large_item)
            assert put_response["ResponseMetadata"]["HTTPStatusCode"] == 200

            key = {"id": "large-item", "sort_key": "data"}
            retrieved_item = db_client.get_item(key)

            # Assert
            assert retrieved_item is not None
            assert retrieved_item["large_field"] == large_data
            assert len(retrieved_item["large_field"]) == 1000

    def test_special_characters_in_data(self):
        """Test handling of special characters in item data."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Create item with special characters
            special_item = {
                "id": "special-chars",
                "sort_key": "test",
                "name": "Test with 特殊字符 and émojis 🎉",
                "description": 'Includes: quotes "\'" and symbols @#$%^&*()',
                "value": Decimal("123"),
            }

            # Act
            put_response = db_client.put_item(special_item)
            assert put_response["ResponseMetadata"]["HTTPStatusCode"] == 200

            key = {"id": "special-chars", "sort_key": "test"}
            retrieved_item = db_client.get_item(key)

            # Assert
            assert retrieved_item is not None
            assert retrieved_item["name"] == "Test with 特殊字符 and émojis 🎉"
            assert (
                retrieved_item["description"]
                == 'Includes: quotes "\'" and symbols @#$%^&*()'
            )

    def test_null_and_boolean_values(self):
        """Test handling of null and boolean values."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Create item with various data types
            mixed_item = {
                "id": "mixed-types",
                "sort_key": "test",
                "bool_true": True,
                "bool_false": False,
                "string_val": "test string",
                "number_val": Decimal("42"),
            }

            # Act
            put_response = db_client.put_item(mixed_item)
            assert put_response["ResponseMetadata"]["HTTPStatusCode"] == 200

            key = {"id": "mixed-types", "sort_key": "test"}
            retrieved_item = db_client.get_item(key)

            # Assert
            assert retrieved_item is not None
            assert retrieved_item["bool_true"] is True
            assert retrieved_item["bool_false"] is False
            assert retrieved_item["string_val"] == "test string"
            assert retrieved_item["number_val"] == Decimal("42")

    def test_numeric_precision(self):
        """Test handling of numeric precision with Decimal values."""
        with mock_aws():
            # Arrange
            table_name, _ = create_test_table_and_data()
            db_client = DynamoDb(table_name=table_name)

            # Create item with various numeric precision values
            precision_item = {
                "id": "precision-test",
                "sort_key": "numbers",
                "decimal_val": Decimal("123.456789"),
                "large_int": Decimal("999999999999999"),
                "negative": Decimal("-500"),
                "zero": Decimal("0"),
            }

            # Act
            put_response = db_client.put_item(precision_item)
            assert put_response["ResponseMetadata"]["HTTPStatusCode"] == 200

            key = {"id": "precision-test", "sort_key": "numbers"}
            retrieved = db_client.get_item(key)

            # Assert
            assert retrieved is not None
            assert retrieved["decimal_val"] == Decimal("123.456789")
            assert retrieved["large_int"] == Decimal("999999999999999")
            assert retrieved["negative"] == Decimal("-500")
            assert retrieved["zero"] == Decimal("0")
