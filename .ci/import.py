import json
import os
import subprocess
import re


CWD = "../"

IMPORT_TF_FILENAME = "import.tf"
IMPORT_TF_PATH = os.path.join(CWD, IMPORT_TF_FILENAME)
IMPORT_PLAN_FILENAME = "import_plan.tfplan"
IMPORT_PLAN_PATH = os.path.join(CWD, IMPORT_PLAN_FILENAME)
IMPORT_PLAN_JSON_FILENAME = "import_plan.json"
IMPORT_PLAN_JSON_PATH = os.path.join(CWD, IMPORT_PLAN_JSON_FILENAME)
SDWAN_JSON_FILENAME = "sdwan.json"
SDWAN_JSON_PATH = os.path.join(CWD, SDWAN_JSON_FILENAME)



def get_id_associated_profile_parcels(change_index, parent_index, id_path, parcels=[]):
    """
    Recursively searches for the parcel ID associated with the given change_index.

    This function traverses the provided parcels list to find a parcel whose index, type, or name matches
    the specified change_index. If a match is found, it returns a string containing the id (parcelId and profileId).
    If the change_index starts with a parcel index or type, the function will recursively search subparcels.
    Returns an empty string if no match is found.

    Args:
        change_index (str): The index (tf change resource index value) to match against parcels.
        parent_index (str): The parent index used to construct parcel indices. The profileName from sdwan.json
        id_path (str): The accumulated ID path for the parcel. Initially it will be a profileId and parcelId will be added later.
        parcels (list): List of parcel dictionaries to search.

    Returns:
        str: The associated parcel ID path if found, otherwise an empty string.
    """
    for parcel in parcels:
        parcel_index = '-'.join([parent_index, parcel.get("payload").get('name')])
        parcel_index_from_type = '-'.join([parent_index, re.sub(r'[-/]', '_', parcel.get("parcelType"))]) # For nested parcel type.
        if (
            (change_index == parcel_index) or # Check for all profile feature parcels.
            (change_index == parcel_index_from_type) or # Check for transport profile feature -> wan_vpn -> ethernet_interfaces -> (ipv4 and ipv6)tracker parcels.
            (change_index == parcel.get("payload").get('name')) # Check for policy object parcels, this won't have `subparcels`.
            ):
            # Compare if the change_index is exactly same as parcel_index or parcel_index_from_type or parcel name then return the `ID Path`.
            # Example-1: (change_index = transport1_test-transport_bgp_test), 
            #            (parcel_index = transport1_test-transport_bgp_test) and 
            #            (parcel_index_type = transport1_test-routing_bgp)
            # Example-2: (change_index = transport1_test-management_vpn), 
            #            (parcel_index = transport1_test-management_vpn_test) and 
            #            (parcel_index_type = transport1_test-management_vpn).
            return ','.join([parcel.get("parcelId"), id_path])
        elif change_index.startswith(parcel_index) or change_index.startswith(parcel_index_from_type):
            # When parcel_index, parcel_index_from_type is not same with change_index values need to go deeper in subparcels.
            # Example-1: (parcel_index = transport1_test-wan_vpn-inet_tloc_test), 
            #            (parcel_index_from_type = transport1_test-wan_vpn-wan_vpn_interface_ethernet) and 
            #            (change_index = transport1_test-wan_vpn-inet_tloc_test-trackergroup). Now taken `parcel_index`
            # Example-2: (parcel_index = transport1_test-management_vpn_test), 
            #            (parcel_index_from_type = transport1_test-management_vpn) and 
            #            (change_index = transport1_test-management_vpn-management_interface_test). Now taken `parcel_index_from_type`
            parcel_id = get_id_associated_profile_parcels(
                change_index, 
                parcel_index if change_index.startswith(parcel_index) else parcel_index_from_type, 
                ','.join([id_path, parcel.get("parcelId")]), 
                parcel.get("subparcels")
            )
            if parcel_id:
                return parcel_id
    return ''

def get_id_to_values(tf_file_resource, json_file_key, json_file_resource, to_dir_, child: bool = False, parent_id: str = '', parent_name: str = ''):
    changes = [
        item for item in tf_file_resource 
        if (json_file_key == 'feature_templates' and item.get("type").endswith('feature_template')) or
           (json_file_key != 'feature_templates' and item.get("type") == f'sdwan_{json_file_key}' and item.get('type').startswith('sdwan_')) or 
           (item.get("type") == 'sdwan_attach_feature_device_template') or 
           (item.get("type").startswith('sdwan_') and item.get("type").endswith(('_feature', '_policy', '_tag'))) or  # Check for all profile features, policy and tag.
           (item.get("type").startswith('sdwan_') and item.get("name").startswith('policy_object')) # Check for policy object.
    ]

    id_pattern = re.compile(r'"([^"]*Id)":\s*"([a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12})"')

    for change in changes:
        if change and change.get("module_address") == "module.sdwan" and change.get("type").startswith("sdwan"):
            to_ = '.'.join([change.get("module_address"), change.get("type"), change.get("name")])
            for element in json_file_resource:
                if change.get("name") == "attach_feature_device_template" and json_file_key == "feature_device_template":
                    name = element["data"].get("templateName")
                    if change.get("index") == name:
                        id_ = element["data"].get("templateId")
                        change_data = change.get("change") or {}
                        after_data = change_data.get("after") or {}
                        devices_data = after_data.get("devices") or []
                        chassis_ids = [device.get("id") for device in devices_data if device and device.get("id")]
                        if len(chassis_ids):
                            id_ = f'{id_, chassis_ids}'.translate(str.maketrans("", "", "'() "))
                            id_name_ = (id_, change.get("index"))
                            if id_name_ not in to_dir_:
                                to_dir_.setdefault(to_, []).append(id_name_)
                            break
                elif change.get("name").endswith(("feature_template", "device_template")) and not change.get("name").endswith(("attach_feature_device_template")):
                    name = f'{parent_name}/{element["data"].get("templateName")}' if child else element["data"].get("templateName")
                    id_ = element["data"].get("templateId")
                elif change.get("name") in {"localized_policy", "centralized_policy", "security_policy"}:
                    name = element["data"].get("policyName")
                    if change.get("index") == name:
                        endpoint = element['endpoint']
                        id_ = endpoint.split('/')[-1]
                        if element["data"].get("isPolicyActivated"):
                            id_name_ = (id_, "activated_policy")
                            to_centralizes = 'module.sdwan.sdwan_activate_centralized_policy.activate_centralized_policy'
                            to_dir_.setdefault(to_centralizes, []).append(id_name_)
                        id_name_ = (id_, change.get("index"))
                        if id_name_ not in to_dir_:
                            to_dir_.setdefault(to_, []).append(id_name_)
                        break
                elif (change.get("type").startswith('sdwan_') and
                    (change.get("name").endswith(('_feature_profile', '_feature', '_policy')) or # Check for all the profile, feature and policy.
                    change.get("name").startswith(('policy_object')))): # Check for policy object.
                    name = element["data"].get("profileName")
                    change_index = change.get("index")
                    if isinstance(change_index, int): # This will handle when the policy-object feature object index as integer number.
                        change_index = change.get("change", {}).get('after', {}).get('name', None)
                    associated_profile_parcels = element["data"].get("associatedProfileParcels")
                    id_ = ''
                    if change_index and name:
                        change_name = change.get("name")
                        profile_type = '_'.join(element["data"].get('profileType').split('-'))
                        if change_index == name:
                            id_ = element["data"].get("profileId")
                        elif change_index.startswith(name) and len(associated_profile_parcels): # Check for all feature profile.
                            id_ = get_id_associated_profile_parcels(change_index, name, element["data"].get("profileId"), associated_profile_parcels)
                        elif change_name.startswith(profile_type) and len(associated_profile_parcels): # Check for policy object.
                            id_ = get_id_associated_profile_parcels(change_index, name, element["data"].get("profileId"), associated_profile_parcels)
                        if id_:
                            id_name_ = (id_, change.get("index"))
                            if id_name_ not in to_dir_:
                                to_dir_.setdefault(to_, []).append(id_name_)
                            break
                elif (change.get("type").startswith('sdwan_') and change.get("name") in {"configuration_group", "policy_group", "tag"}):
                    change_index = change.get("index")
                    name = element["data"].get("name")
                    if (change_index and name) and (change_index == name):
                        id_name_ = (element["data"].get("id"), change_index)
                        if id_name_ not in to_dir_:
                            to_dir_.setdefault(to_, []).append(id_name_)
                        break
                else:
                    name = f'{parent_name}/{element["data"].get("name")}' if child else element["data"].get("name")

                if change.get("index") == name:
                    if not change.get("name").endswith(("feature_template", "device_template", "localized_policy")):
                        data_section = json.dumps(element["data"])
                        match = id_pattern.search(data_section)
                        id_ = match.group(2) if match else None
                    id_name_ = (id_, change.get("index"))
                    if id_name_ not in to_dir_:
                        to_dir_.setdefault(to_, []).append(id_name_)
                        

def tf_import():
    if os.path.exists(IMPORT_TF_PATH):
        os.remove(IMPORT_TF_PATH)

    # terraform init
    subprocess.run(["terraform", "init"], cwd=CWD)

    # terraform plan
    subprocess.run(
        ["terraform", "plan", "-out="+IMPORT_PLAN_FILENAME, "-input=false"], cwd=CWD
    )
    with open(IMPORT_PLAN_JSON_PATH, "w") as f:
        subprocess.run(
            ["terraform", "show", "-json", IMPORT_PLAN_FILENAME],
            stdout=f,
            cwd=CWD,
        )
    
    tf_plan = None
    with open(IMPORT_PLAN_JSON_PATH) as file:
        tf_plan = json.load(file)

    sdwan_json = None
    with open(SDWAN_JSON_PATH) as file:
        sdwan_json = json.load(file)

    to_dir_ = {}
    for json_file_key, json_file_resource in sdwan_json.items():
        tf_file_resource = tf_plan.get("resource_changes", [])
        if tf_file_resource:
            get_id_to_values(tf_file_resource, json_file_key, json_file_resource, to_dir_)

    terraform_imports = ""
    for k, v in to_dir_.items():
        for id, index in v:
            id_value = id if not "repository" in k else index
            if id != None or "repository" in k:
                terraform_imports += "import {\n"
                terraform_imports += f'  id = "{id_value}"\n'
                if isinstance(index, int):
                    terraform_imports += f'  to = {k}[{index}]\n'
                else:
                    terraform_imports += f'  to = {k}[\"{index}\"]\n'
                terraform_imports += "}\n"
    
    with open(IMPORT_TF_PATH, "w") as file:
        file.write(terraform_imports)


    # cleanup
    if os.path.exists(IMPORT_PLAN_PATH):
        os.remove(IMPORT_PLAN_PATH)
    if os.path.exists(IMPORT_PLAN_JSON_PATH):
        os.remove(IMPORT_PLAN_JSON_PATH)


if __name__ == "__main__":
    tf_import()
