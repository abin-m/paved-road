variable "ami" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}
