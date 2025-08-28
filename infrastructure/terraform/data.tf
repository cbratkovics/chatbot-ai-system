# Data Layer - RDS Aurora, ElastiCache Redis, and data services

# ElastiCache Redis Cluster
module "elasticache" {
  source = "terraform-aws-modules/elasticache/aws"
  version = "~> 1.0"
  
  cluster_id               = "${local.name_prefix}-redis"
  description              = "Redis cluster for ${local.name_prefix}"
  node_type               = "cache.r7g.large"
  num_cache_nodes         = 3
  port                    = 6379
  parameter_group_name    = aws_elasticache_parameter_group.redis.name
  engine_version          = "7.0"
  
  subnet_group_name = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]
  
  # Multi-AZ and automatic failover
  automatic_failover_enabled = true
  multi_az_enabled          = true
  
  # Backup and maintenance
  snapshot_retention_limit = 7
  snapshot_window         = "03:00-05:00"
  maintenance_window      = "sun:05:00-sun:07:00"
  
  # Encryption
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                = random_password.redis_auth.result
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-redis"
  })
}

resource "random_password" "redis_auth" {
  length  = 32
  special = true
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = module.vpc_primary.private_subnets
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-redis-subnet-group"
  })
}

resource "aws_elasticache_parameter_group" "redis" {
  family = "redis7"
  name   = "${local.name_prefix}-redis-params"
  
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }
  
  parameter {
    name  = "timeout"
    value = "300"
  }
  
  parameter {
    name  = "tcp-keepalive"
    value = "60"
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-redis-params"
  })
}

# RDS Aurora PostgreSQL Cluster
module "rds" {
  source = "terraform-aws-modules/rds-aurora/aws"
  version = "~> 8.0"
  
  name              = "${local.name_prefix}-aurora"
  engine            = "aurora-postgresql"
  engine_version    = "15.3"
  engine_mode       = "provisioned"
  
  master_username = "chatbot_admin"
  master_password = random_password.db_password.result
  
  vpc_id                = module.vpc_primary.vpc_id
  subnets              = module.vpc_primary.database_subnets
  create_db_subnet_group = true
  db_subnet_group_name  = "${local.name_prefix}-db-subnet-group"
  
  security_group_rules = {
    postgres_ingress = {
      source_security_group_id = aws_security_group.ecs.id
    }
  }
  
  # Cluster configuration
  instances = {
    1 = {
      instance_class      = "db.r6g.large"
      publicly_accessible = false
    }
    2 = {
      instance_class      = "db.r6g.large"
      publicly_accessible = false
    }
  }
  
  # Read replicas for read-heavy workloads
  autoscaling_enabled      = true
  autoscaling_min_capacity = 2
  autoscaling_max_capacity = 10
  
  # Backup and maintenance
  backup_retention_period = 30
  preferred_backup_window = "03:00-04:00"
  preferred_maintenance_window = "sun:04:00-sun:05:00"
  
  # Performance monitoring
  enabled_cloudwatch_logs_exports = ["postgresql"]
  monitoring_interval            = 60
  monitoring_role_arn           = aws_iam_role.rds_monitoring.arn
  
  # Encryption
  storage_encrypted   = true
  kms_key_id         = aws_kms_key.main.arn
  
  # Deletion protection
  deletion_protection      = true
  skip_final_snapshot     = false
  final_snapshot_identifier = "${local.name_prefix}-aurora-final-snapshot"
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-aurora"
  })
}

resource "random_password" "db_password" {
  length  = 32
  special = true
}

# RDS Monitoring Role
resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name_prefix}-rds-monitoring-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rds-monitoring-role"
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Database secrets
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${local.name_prefix}-db-credentials"
  description            = "Database credentials for ${local.name_prefix}"
  kms_key_id             = aws_kms_key.main.id
  recovery_window_in_days = 7
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-db-credentials"
  })
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  
  secret_string = jsonencode({
    username = module.rds.cluster_master_username
    password = random_password.db_password.result
    engine   = "postgres"
    host     = module.rds.cluster_endpoint
    port     = module.rds.cluster_port
    dbname   = module.rds.cluster_database_name
  })
}

# Redis credentials
resource "aws_secretsmanager_secret" "redis_credentials" {
  name                    = "${local.name_prefix}-redis-credentials"
  description            = "Redis credentials for ${local.name_prefix}"
  kms_key_id             = aws_kms_key.main.id
  recovery_window_in_days = 7
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-redis-credentials"
  })
}

resource "aws_secretsmanager_secret_version" "redis_credentials" {
  secret_id = aws_secretsmanager_secret.redis_credentials.id
  
  secret_string = jsonencode({
    host     = module.elasticache.primary_endpoint_address
    port     = module.elasticache.port
    auth_token = random_password.redis_auth.result
  })
}

# DocumentDB for conversation history (alternative/additional storage)
resource "aws_docdb_cluster" "conversations" {
  cluster_identifier      = "${local.name_prefix}-docdb"
  engine                 = "docdb"
  master_username        = "docdb_admin"
  master_password        = random_password.docdb_password.result
  backup_retention_period = 7
  preferred_backup_window = "02:00-03:00"
  skip_final_snapshot    = false
  final_snapshot_identifier = "${local.name_prefix}-docdb-final-snapshot"
  
  db_subnet_group_name   = aws_docdb_subnet_group.conversations.name
  vpc_security_group_ids = [aws_security_group.docdb.id]
  
  # Encryption
  storage_encrypted = true
  kms_key_id       = aws_kms_key.main.arn
  
  # Enable logging
  enabled_cloudwatch_logs_exports = ["audit", "profiler"]
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-docdb"
  })
}

resource "aws_docdb_cluster_instance" "conversations" {
  count              = 2
  identifier         = "${local.name_prefix}-docdb-${count.index}"
  cluster_identifier = aws_docdb_cluster.conversations.id
  instance_class     = "db.t3.medium"
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-docdb-${count.index}"
  })
}

resource "aws_docdb_subnet_group" "conversations" {
  name       = "${local.name_prefix}-docdb-subnet-group"
  subnet_ids = module.vpc_primary.database_subnets
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-docdb-subnet-group"
  })
}

resource "aws_security_group" "docdb" {
  name_prefix = "${local.name_prefix}-docdb-"
  description = "Security group for DocumentDB cluster"
  vpc_id      = module.vpc_primary.vpc_id
  
  ingress {
    from_port       = 27017
    to_port         = 27017
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
    description     = "MongoDB from ECS"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-docdb-sg"
  })
}

resource "random_password" "docdb_password" {
  length  = 32
  special = true
}

# OpenSearch for analytics and search
resource "aws_opensearch_domain" "analytics" {
  domain_name    = "${local.name_prefix}-analytics"
  engine_version = "OpenSearch_2.3"
  
  cluster_config {
    instance_type            = "t3.small.search"
    instance_count          = 3
    dedicated_master_enabled = true
    master_instance_type    = "t3.small.search"
    master_instance_count   = 3
    zone_awareness_enabled  = true
    
    zone_awareness_config {
      availability_zone_count = 3
    }
  }
  
  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = 20
  }
  
  vpc_options {
    subnet_ids         = slice(module.vpc_primary.private_subnets, 0, 3)
    security_group_ids = [aws_security_group.opensearch.id]
  }
  
  # Encryption
  encrypt_at_rest {
    enabled    = true
    kms_key_id = aws_kms_key.main.id
  }
  
  node_to_node_encryption {
    enabled = true
  }
  
  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }
  
  # Access policy
  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task_role.arn
        }
        Action   = "es:*"
        Resource = "arn:aws:es:${var.primary_region}:${data.aws_caller_identity.current.account_id}:domain/${local.name_prefix}-analytics/*"
      }
    ]
  })
  
  log_publishing_options {
    enabled                  = true
    log_type                = "INDEX_SLOW_LOGS"
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch.arn
  }
  
  log_publishing_options {
    enabled                  = true
    log_type                = "SEARCH_SLOW_LOGS"
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch.arn
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-opensearch"
  })
}

resource "aws_security_group" "opensearch" {
  name_prefix = "${local.name_prefix}-opensearch-"
  description = "Security group for OpenSearch cluster"
  vpc_id      = module.vpc_primary.vpc_id
  
  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
    description     = "HTTPS from ECS"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-opensearch-sg"
  })
}

resource "aws_cloudwatch_log_group" "opensearch" {
  name              = "/aws/opensearch/domains/${local.name_prefix}-analytics"
  retention_in_days = 30
  kms_key_id       = aws_kms_key.main.arn
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-opensearch-logs"
  })
}

# S3 bucket for data lake and analytics
resource "aws_s3_bucket" "data_lake" {
  bucket = "${local.name_prefix}-data-lake-${data.aws_caller_identity.current.account_id}"
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-data-lake"
  })
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.main.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  
  rule {
    id     = "analytics_data_lifecycle"
    status = "Enabled"
    
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    
    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }
    
    expiration {
      days = 2555  # 7 years
    }
  }
}

# Outputs
output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = module.elasticache.primary_endpoint_address
  sensitive   = true
}

output "database_endpoint" {
  description = "RDS Aurora cluster endpoint"
  value       = module.rds.cluster_endpoint
  sensitive   = true
}

output "docdb_endpoint" {
  description = "DocumentDB cluster endpoint"
  value       = aws_docdb_cluster.conversations.endpoint
  sensitive   = true
}

output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  value       = aws_opensearch_domain.analytics.endpoint
  sensitive   = true
}