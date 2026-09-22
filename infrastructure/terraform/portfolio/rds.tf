resource "aws_db_subnet_group" "this" {
  name       = local.name
  subnet_ids = aws_subnet.database[*].id

  tags = { Name = local.name }
}

resource "aws_db_instance" "postgres" {
  identifier = "${local.name}-postgres"

  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t4g.micro"

  db_name  = var.database_name
  username = var.database_username
  port     = 5432

  manage_master_user_password = true

  allocated_storage     = 20
  max_allocated_storage = 0
  storage_type          = "gp3"
  storage_encrypted     = true

  multi_az               = false
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.database.id]

  backup_retention_period    = 1
  backup_window              = "02:00-02:30"
  maintenance_window         = "sun:03:00-sun:03:30"
  auto_minor_version_upgrade = true
  apply_immediately          = true

  deletion_protection      = false
  skip_final_snapshot      = true
  delete_automated_backups = true
  copy_tags_to_snapshot    = true

  performance_insights_enabled = false
  monitoring_interval          = 0

  tags = { Name = "${local.name}-postgres" }
}
