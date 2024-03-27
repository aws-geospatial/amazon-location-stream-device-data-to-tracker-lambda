AWS_REGION:
	@test "${$@}" || (echo "$@ environment variable is undefined" && false)

S3_BUCKET:
	@test "${$@}" || (echo "$@ environment variable is undefined" && false)

build: template.yaml
	sam build --template $< --cached

packaged.yaml: build src/data_consumer.py S3_BUCKET AWS_REGION
	sam package --output-template-file $@ --s3-bucket ${S3_BUCKET} --region ${AWS_REGION}

publish: packaged.yaml AWS_REGION
	sam publish --template $< --region ${AWS_REGION}

.PHONY: AWS_REGION S3_BUCKET publish
