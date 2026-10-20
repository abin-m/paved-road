resource "aws_instance" "web" {
  count         = 1
  ami           = var.ami
  instance_type = "t3.micro"
}

resource "aws_db_instance" "main" {
  engine   = "postgres"
  password = var.db_password
}
