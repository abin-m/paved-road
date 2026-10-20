resource "aws_s3_bucket" "logs" {
  bucket = "api-logs-${terraform.workspace}"
}
