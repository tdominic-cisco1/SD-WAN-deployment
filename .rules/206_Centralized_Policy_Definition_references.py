class Rule:
    id = "206"
    description = "Verify Centralized Policy Definition references"
    severity = "HIGH"
    
    # # Verify Policy Definition Names referenced in the Centralized Policies


    policy_definition_type = [
        'control_policy', 'data_policy'
    ]
    policy_definition_sub_type = [
        'hub_and_spoke_topology', 'mesh_topology', 'vpn_membership', 'custom_control_topology', 'traffic_data', 'cflowd', 'application_aware_routing'
    ] 

    # Extract the Policy Name and Definition Names referenced in the Centralized Policies at ['sdwan']['centralized_policies']['feature_policies']
    @classmethod
    def feature_policies(cls, inventory):
        results = {}
        for fpds in inventory.get('sdwan', {}).get('centralized_policies', {}).get('feature_policies', {}):
            fpdsname = fpds['name']
            fpdsdict = {}
            for x in cls.policy_definition_sub_type:
                try:
                    if x in fpds:
                        fp_definitions = []
                        for pd in fpds[x]:
                            fp_definitions.append(pd['policy_definition'])
                        fpdsdict[x] = fp_definitions
                except KeyError:
                    continue
            results[fpdsname] = fpdsdict
        return results  

    # Extract the Policy Definition Names defined in the Centralized Policies at ['sdwan']['centralized_policies']['definitions'][.][.]
    @classmethod
    def definitions(cls, inventory):
        results = {}
        for w in cls.policy_definition_type:
            for x in cls.policy_definition_sub_type:
                try:
                    definitions = []
                    for ds in inventory['sdwan']['centralized_policies']['definitions'][w][x]:
                        definitions.append(ds['name'])
                        results[x] = definitions
                except KeyError:
                    continue
        return results

    @classmethod
    def expand_site_id_range(cls, range_dict):
        """Expand site_id range like {from: 200, to: 300} to individual site IDs."""
        return range(range_dict['from'], range_dict['to'] + 1)
    
    @classmethod
    def format_site_ids_as_ranges(cls, site_ids):
        """Convert a set of site IDs to readable range format like '200-205, 210, 300-305'."""
        if not site_ids:
            return ""
        
        sorted_ids = sorted(site_ids)
        ranges = []
        start = end = sorted_ids[0]
        
        for site_id in sorted_ids[1:]:
            if site_id == end + 1:
                end = site_id
            else:
                if start == end:
                    ranges.append(str(start))
                else:
                    ranges.append(f"{start}-{end}")
                start = end = site_id
        
        # Add the last range
        if start == end:
            ranges.append(str(start))
        else:
            ranges.append(f"{start}-{end}")
        
        return ", ".join(ranges)
    
    @classmethod
    def get_sites_from_site_lists(cls, inventory, site_lists):
        """Extract all site IDs from given site lists, expanding ranges."""
        if not site_lists:
            return set()
        
        site_lists_set = set(site_lists)
        sites = []
        site_list_objects = inventory.get('sdwan', {}).get('policy_objects', {}).get('site_lists', [])
        
        for site_list_obj in site_list_objects:
            if site_list_obj.get('name') in site_lists_set:
                # Add individual site IDs
                sites.extend(site_list_obj.get('site_ids', []))
                
                # Expand and add site ID ranges
                for site_range in site_list_obj.get('site_id_ranges', []):
                    sites.extend(cls.expand_site_id_range(site_range))
        
        return set(sites)

    @classmethod
    def verify_cflowd_references(cls, inventory):
        """Verify that sites with cflowd action also have cflowd policy applied."""
        dp_with_cflowd_action = {}  # Map: policy_name -> site_lists where it's applied
        cflowd_pushed_site_lists = []
        
        try:
            # Find traffic data policies with cflowd action
            traffic_data_policies = inventory.get('sdwan', {}).get('centralized_policies', {}).get('definitions', {}).get('data_policy', {}).get('traffic_data', [])
            policies_with_cflowd = set()
            for traffic_dp_def in traffic_data_policies:
                for sequence in traffic_dp_def.get('sequences', []):
                    if sequence.get('actions', {}).get('cflowd'):
                        policies_with_cflowd.add(traffic_dp_def.get('name'))
                        break
            
            # Early return if no cflowd actions defined
            if not policies_with_cflowd:
                return None
            
            centralized_policy = inventory.get('sdwan', {}).get('centralized_policies', {})
            activated_policy = centralized_policy.get('activated_policy')
            
            # Only check the activated policy
            if not activated_policy:
                return None
            
            for feature_policy in centralized_policy.get('feature_policies', []):
                if feature_policy.get('name') == activated_policy:
                    # Sites where traffic data policy with cflowd action is applied
                    for feature_traffic_dp in feature_policy.get('traffic_data', []):
                        policy_def = feature_traffic_dp.get('policy_definition')
                        if policy_def in policies_with_cflowd:
                            site_lists = []
                            for site_region in feature_traffic_dp.get('site_region_vpn', []):
                                site_lists.extend(site_region.get('site_lists', []))
                            dp_with_cflowd_action[policy_def] = site_lists
                    
                    # Sites where cflowd policy is explicitly pushed
                    for feature_traffic_cflowd in feature_policy.get('cflowd', []):
                        cflowd_pushed_site_lists.extend(feature_traffic_cflowd.get('site_lists', []))
                    break  # Found activated policy
            
            # Convert cflowd pushed site lists
            sites_with_cflowd_pushed = cls.get_sites_from_site_lists(inventory, cflowd_pushed_site_lists)
            
            # Check each data policy with cflowd action
            problematic_policies = {}
            for policy_name, site_lists in dp_with_cflowd_action.items():
                sites_for_policy = cls.get_sites_from_site_lists(inventory, site_lists)
                
                # Check if this policy has sites missing cflowd policy
                if sites_for_policy and not sites_for_policy.issubset(sites_with_cflowd_pushed):
                    missing_sites = sites_for_policy - sites_with_cflowd_pushed
                    problematic_policies[policy_name] = missing_sites
            
            # Generate error messages for problematic policies
            if problematic_policies:
                all_missing_sites = set()
                for missing in problematic_policies.values():
                    all_missing_sites.update(missing)
                
                formatted_sites = cls.format_site_ids_as_ranges(all_missing_sites)
                policies_list = ", ".join(f"'{p}'" for p in problematic_policies)
                return [f"Missing cflowd reference: site_ids {formatted_sites} are referenced under traffic data policies {policies_list} with cflowd action but do not have cflowd policy applied under feature policies in the activated policy '{activated_policy}'"]
        
        except KeyError:
            pass
        
        return None

    @classmethod
    def match(cls, inventory):
        # Compare the Policy Definition Names referenced in the Centralized Policies at ['sdwan']['centralized_policies']['feature_policies'] 
        # to the Policy Definition Names defined in the Centralized Policies at ['sdwan']['centralized_policies']['definitions'][.][.]
        # and find the missing definitions
        # Compare the activated policy name at ['sdwan']['centralized_policies']['activated_policy'] 
        # to the Policy Names defined in the Centralized Policies at ['sdwan']['centralized_policies']['feature_policies']
        # and find the missing policy name
        feature_policies = cls.feature_policies(inventory)
        definitions = cls.definitions(inventory)
        missing_definitions = []
        try:
            for z in feature_policies:
                for x in feature_policies[z]:
                    for y in feature_policies[z][x]:
                        if y not in definitions[x]:
                            missing_definitions.append(str("Missing " + x + " definition: '" + y + "' at ['sdwan']['centralized_policies']['definitions'][.]['"+ x + "'] referenced under ['sdwan']['centralized_policies']['feature_policies']['" + z +"']"))
        except KeyError:
            pass
        try:
            if inventory['sdwan']['centralized_policies']['activated_policy']:
                if inventory['sdwan']['centralized_policies']['activated_policy'] not in feature_policies:
                    missing_definitions.append(str("Missing feature policy: '" + inventory['sdwan']['centralized_policies']['activated_policy'] + "' at ['sdwan']['centralized_policies']['feature_policies'] referenced under ['sdwan']['centralized_policies']['activated_policy']" ))
        except KeyError:
            pass

        # Whenever traffic data policy action contains cflowd, verify that the sites where respective traffic data policy is pushed also has cflowd template / data policy applied
        missing_cflowd_ref = cls.verify_cflowd_references(inventory)
        if missing_cflowd_ref:
            missing_definitions.extend(missing_cflowd_ref)

        return missing_definitions
    