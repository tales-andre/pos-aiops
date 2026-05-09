output "bucket_id" {
  description = "ID do bucket S3 criado"
  value       = aws_s3_bucket.this.id
}

output "bucket_arn" {
  description = "ARN do bucket S3 criado"
  value       = aws_s3_bucket.this.arn
}

output "bucket_name" {
  description = "Nome completo do bucket S3 criado (com prefixo hvt-)"
  value       = aws_s3_bucket.this.bucket
}

output "bucket_domain_name" {
  description = "Domain name do bucket S3"
  value       = aws_s3_bucket.this.bucket_domain_name
}

output "bucket_regional_domain_name" {
  description = "Regional domain name do bucket S3"
  value       = aws_s3_bucket.this.bucket_regional_domain_name
}

output "logging_bucket_id" {
  description = "ID do bucket de logs"
  value       = aws_s3_bucket.logging.id
}

output "logging_bucket_arn" {
  description = "ARN do bucket de logs"
  value       = aws_s3_bucket.logging.arn
}

output "logging_bucket_name" {
  description = "Nome do bucket de logs"
  value       = aws_s3_bucket.logging.bucket
}
