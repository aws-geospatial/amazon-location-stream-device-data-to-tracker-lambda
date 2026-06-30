# Amazon Location Kinesis Stream To Tracker App

This is a easy-to-setup stack to help the user connect streaming device position data from Kinesis Data Stream to Amazon Location service.

This app can be deployed to any existing service or app that uses Kinesis Data Stream to stream device position data to Amazon Location.

It will create a Tracker and a Lambda function to stream data to the tracker, along with the necessary permissions.

## Deploying from AWS console

1. Search for AWS Serverless Application Repository.
2. Select "Available applications" on the left side panel.
3. Search for "kinesis-stream-device-data-to-location-tracker". You may need to check "Show apps that create custom IAM roles or resource policies" to see the application.
4. Enter the required parameters, then click "Deploy". A new web browser window/tab will pop up.
5. Monitor the "Deployment Status" on the new window.

## Explanation of the Parameters

`TrackerName`: Name of the [Amazon Location Tracker](https://docs.aws.amazon.com/location/latest/developerguide/start-tracking.html) to be created.

`EventBridgeEnabled`: Whether EventBridge integration is turned on. It may incur additional costs by leaving it on unused.

`KinesisStreamKmsKeyArn`: Optional. The ARN of the customer-managed KMS key (CMK) used for server-side encryption of your source Kinesis data stream. See [Encrypted Kinesis streams](#encrypted-kinesis-streams-customer-managed-kms-keys) below. Leave blank if your stream is unencrypted or uses the AWS-managed key (`aws/kinesis`).

Note that this app requires a [Kinesis Data Stream](https://docs.aws.amazon.com/streams/latest/dev/getting-started.html) as an input. 

The app supports custom event structure via [JSONPath-ng](https://pypi.org/project/jsonpath-ng/).

See [Kinesis documentation for Lambda consumers](https://docs.aws.amazon.com/lambda/latest/dg/with-kinesis.html) for more information about fine-tuning the system.

## Customization of Kinesis Data Stream event structure

By default, this supports data defined in the following structure:

```json
    {
        "DeviceId": "<your device id>",
        "Position": [<some longitude, some latitude>],
        "Time": "<the update's timestamp in ISO 8601 format (https://www.iso.org/iso-8601-date-and-time-format.html)>",
        "Properties": {
            "key1": val1,
            "key2": val2,
            "key3": val3
        },
        "HorizontalAccuracy": <some number>
    }
```

These are one-to-one mapped to parameters of [BatchUpdateDevicePosition API](https://docs.aws.amazon.com/location/latest/APIReference/API_BatchUpdateDevicePosition.html).

For example, the SampleTime API parameter is populated by the source event's Time property by default. $.Time is a JSONPath expression targeting Time in the source event JSON above.

List of paths that are configurable:

* `PathToDeviceId` maps to the `DeviceId` parameter of the API. Default is `$.DeviceId`.
* `PathToDevicePositionLongitude` maps to the first element of the `Position` parameter of the API. Default is `$.Position[0]`.
* `PathToDevicePositionLatitude` maps to the second element of the `Position` parameter of the API. Default is `$.Position[1]`.
* `PathToSampleTime` maps to the `SampleTime` parameter of the API. Default is `$.Time`.
* `PathToHorizontalAccuracy` maps to the `Accuracy` parameter, specifically the `Horizontal` key. Default is `$.HorizontalAccuracy`. `Horizontal` is the only type of accuracy supported by the API.
* `PathToPositionProperties` maps to the `PositionProperties` parameter of the API.

## Encrypted Kinesis streams (customer-managed KMS keys)

If your source Kinesis data stream uses [server-side encryption](https://docs.aws.amazon.com/streams/latest/dev/server-side-encryption.html) with a **customer-managed KMS key (CMK)**, the function's execution role needs `kms:Decrypt` on that key so the event source can read records.

1. Set the `KinesisStreamKmsKeyArn` parameter to the CMK ARN (the underlying key ARN of the form `arn:aws:kms:<region>:<account>:key/<key-id>` — **not** an alias ARN, and the per-region key ARN actually used by the stream). The function is then granted only `kms:Decrypt`, scoped to that single key, and only for requests carrying the stream's encryption context (`kms:EncryptionContext:aws:kinesis:arn` equal to `KinesisStreamArn`).
2. The CMK's own [key policy](https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html) must also allow `kms:Decrypt` for this function's execution role principal — granting it in this template's IAM policy is necessary but not sufficient. Kinesis passes the encryption context `aws:kinesis:arn` (the stream ARN) on every KMS call it makes on the consumer's behalf.

If your stream is unencrypted or uses the AWS-managed key (`aws/kinesis`), leave `KinesisStreamKmsKeyArn` blank. No KMS permissions are granted in that case.

`kms:GenerateDataKey` is intentionally **not** granted: this app only consumes (reads) records, and `GenerateDataKey` is a producer-side permission. To check whether your stream uses a CMK, run `aws kinesis describe-stream-summary --stream-name <name>` and look at `EncryptionType` (`KMS`) and `KeyId`.

## Upgrade notes

**Upgrading from a version before 1.1.0:** Earlier versions granted the function broad KMS permissions (`kms:Decrypt` and `kms:GenerateDataKey`) on every key in the account/region. Starting in 1.1.0 these are scoped to least privilege: `kms:GenerateDataKey` is removed entirely, and `kms:Decrypt` is granted only when you provide `KinesisStreamKmsKeyArn`, scoped to that one key and to requests carrying the stream's encryption context.

> ⚠️ **If your source stream is encrypted with a customer-managed KMS key, you must set `KinesisStreamKmsKeyArn` when you upgrade**, or the function will silently stop processing records (it will no longer be able to decrypt them). On update via the Serverless Application Repository console, make sure the new parameter is populated rather than left at its empty default. Deployments using an unencrypted stream or the AWS-managed `aws/kinesis` key are unaffected.

## Deploying for Private Development

To publish your own adaptions to the Serverless Application Repository as a private application, run the following:

```bash
# create a bucket if necessary and ensure that it has an appropriate bucket policy, similar to the one below
aws s3 mb s3://<bucket> --region <region>
AWS_REGION=<region> S3_BUCKET=<bucket> make publish
```

`<bucket>` must be readable by the Serverless Application Repository. This can be achieved by applying the following policy to the bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "serverlessrepo.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::<bucket>/*",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "<account-id>"
        }
      }
    }
  ]
}
```

Note that the `Condition` is added as a best practice to prevent the potential [confused deputy problem](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html).
Since this app is being deployed as a private application, the `aws:SourceAccount` should point to the account in which this app is deployed to.

Once this runs successfully, you'll be able to view the application on Serverless Application Repository console under "private applications" and deploy it.

## Monitoring

It is advisable to monitor the performance of this Lambda in production environment.

See [Lambda documentation](https://docs.aws.amazon.com/lambda/latest/dg/with-kinesis.html#events-kinesis-metrics) for what Kinesis-Lambda metrics are available.

See [Lambda Metrics documentation](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics.html) about how to work with Lambda metrics.

For this particular app, Lambda's `IteratorAge` metric would be an important metric to monitor. `IteratorAge` describes the age of the latest Kinesis record consumed by the Lambda function.
It can be used to monitor if the consumer is working. An increased `IteratorAge` indicates either increased latency or error in the system.

## Logging

The Lambda function created by this app has [CloudWatch](https://aws.amazon.com/cloudwatch/) logging enabled by default. Steps to see the logs:
1. Go to `CloudWatch` on AWS console.
2. Select `Log groups` on the left side panel.
3. Look for a log group that starts with `/aws/lambda/serverlessrepo-kinesis-st-TrackingDataConsumer`. 
This contains log output from the Lambda function, including details on the conditions described below.

## Error Handling

This app logs failed executions or invalid position updates into its log group, and retries twice on errors.

Note that this app calls BatchUpdateDevicePosition API. Retries on that API may result in the same position update being processed multiple times.
Amazon Location handles this case by only storing the most recent position update.

If `IteratorAge` climbs while there are **no** entries in the Lambda's log group, the most likely cause is a customer-managed-KMS-encrypted stream without decrypt access: confirm `KinesisStreamKmsKeyArn` is set to the stream's CMK ARN (see [Encrypted Kinesis streams](#encrypted-kinesis-streams-customer-managed-kms-keys)) and that the CMK key policy allows this role's `kms:Decrypt`.

## Security

See [CONTRIBUTING](./CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License.

## Code Style

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
