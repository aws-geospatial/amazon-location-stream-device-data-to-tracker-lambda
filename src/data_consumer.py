# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import base64
import boto3
import logging
import json
import os
from botocore.exceptions import ClientError, ParamValidationError
from jsonpath_ng import jsonpath, parse

# Initiate a location client calling Location service in the same region
location_client = boto3.client("location")

logger = logging.getLogger()
logger.setLevel("INFO")

DEVICE_POSITION_UPDATE_MAX_BATCH_SIZE = 10
DEVICE_POSITION_UPDATE_MAX_PROPERTIES_COUNT = 3

# Get JSONPath from env variables or use default value if the env variable does not exist.
device_id_path = os.getenv("DEVICE_ID_PATH") or "$.DeviceId"
position_path_longitude = os.getenv("POSITION_PATH_LONGITUDE") or "$.Position[0]"
position_path_latitude = os.getenv("POSITION_PATH_LATITUDE") or "$.Position[1]"
sample_time_path = os.getenv("SAMPLE_TIME_PATH") or "$.Time"
horizontal_accuracy_path = (
    os.getenv("HORIZONTAL_ACCURACY_PATH") or "$.HorizontalAccuracy"
)
position_properties_path = os.getenv("POSITION_PROPERTIES_PATH") or "$.Properties"
tracker_name = os.getenv("TRACKER_NAME")


def lambda_handler(event, context):
    """
    This is a Lambda handler that processes records from Kinesis data streams and publishes to an Amazon Location Service tracker resource.
    It is advisable to monitor the performance of this Lambda in production environment.
    See https://docs.aws.amazon.com/lambda/latest/dg/with-kinesis.html#events-kinesis-metrics for how Kinesis-Lambda mapping works.
    See https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics.html about how to work with Lambda metrics.

    Parameters:
    - event: The Lambda event. In this case, must be a Kinesis data event.
    - context: Context of the request.
    """
    updates = []
    for record in event["Records"]:
        update = transform_record_to_update(record)
        if len(update) == 0:
            continue
        updates.append(update)
        logger.info(f"Added update {update} to batch request.")
        if len(updates) == DEVICE_POSITION_UPDATE_MAX_BATCH_SIZE:
            call_batch_update_device_position(updates)
            updates = []

    if len(updates) > 0:
        call_batch_update_device_position(updates)


def call_batch_update_device_position(updates):
    logger.info(
        f"Calling BatchUpdateDevicePosition for tracker {tracker_name} with updates {updates}."
    )
    try:
        location_client.batch_update_device_position(
            TrackerName=tracker_name, Updates=updates
        )
    except ParamValidationError as validation_error:
        raise ValueError(
            f"A parameter validation error occurred: {validation_error}. Failed to update device positions for records {updates}."
        )
    except ClientError as client_error:
        raise ClientError(
            f"A client side error occurred: {client_error}. Failed to update device positions for records {updates}."
        )
    except Exception as error:
        raise Exception(
            f"An unexpected error occurred: {error}. Failed to update device positions for records {updates}."
        )


def transform_record_to_update(record):
    # Decode and process the record
    payload = base64.b64decode(record["kinesis"]["data"])
    decoded_data = payload.decode("utf-8")
    data = json.loads(decoded_data)

    # Retrieve values using JSONPath
    device_id_matches = [match.value for match in parse(device_id_path).find(data)]
    position_longitude_matches = [
        match.value for match in parse(position_path_longitude).find(data)
    ]
    position_latitude_matches = [
        match.value for match in parse(position_path_latitude).find(data)
    ]
    sample_time_matches = [match.value for match in parse(sample_time_path).find(data)]
    horizontal_accuracy_matches = [
        match.value for match in parse(horizontal_accuracy_path).find(data)
    ]
    position_properties_matches = [
        match.value for match in parse(position_properties_path).find(data)
    ]

    if not (
        device_id_matches
        and sample_time_matches
        and position_longitude_matches
        and position_latitude_matches
    ):
        missing_fields = []
        if not device_id_matches:
            missing_fields.append("DeviceId")
        if not sample_time_matches:
            missing_fields.append("SampleTime")
        if not position_longitude_matches:
            missing_fields.append("Longitude")
        if not position_latitude_matches:
            missing_fields.append("Latitude")
        logger.info(
            f"ERROR: Failed to find required input fields ({', '.join(missing_fields)}). "
            f"Ignoring this record."
        )
        return {}

    update = {
        "DeviceId": device_id_matches[0],
        "SampleTime": sample_time_matches[0],
        "Position": [
            float(position_longitude_matches[0]),
            float(position_latitude_matches[0]),
        ],
    }

    if len(position_properties_matches) > 0:
        update["PositionProperties"] = {}
        if (
            len(position_properties_matches[0])
            > DEVICE_POSITION_UPDATE_MAX_PROPERTIES_COUNT
        ):
            logger.info(
                f"ERROR: PositionProperties cannot have more than {DEVICE_POSITION_UPDATE_MAX_PROPERTIES_COUNT} "
                f"properties in it for BatchUpdateDevicePositions. Ignoring this record. "
                f"Properties: {position_properties_matches[0]}"
            )
        else:
            for key, val in position_properties_matches[0].items():
                update["PositionProperties"][key] = (
                    val if isinstance(val, str) else json.dumps(val)
                )
    if len(horizontal_accuracy_matches) > 0:
        update["Accuracy"] = {
            "Horizontal": horizontal_accuracy_matches[0]
        }
    return update
