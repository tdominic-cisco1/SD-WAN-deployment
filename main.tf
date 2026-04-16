module "sdwan" {
  source  = "netascode/nac-sdwan/sdwan"
  version = "1.4.0"

  yaml_directories = ["data/"]

  write_default_values_file = "defaults.yaml"
}
