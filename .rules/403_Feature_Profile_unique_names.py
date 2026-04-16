class Rule:
    id = "403"
    description = "Verify Feature Profile unique names"
    severity = "HIGH"

    feature_profile_types = ["cli_profiles", "other_profiles", "service_profiles", "system_profiles", "transport_profiles"]

    @classmethod
    def match(cls, inventory):
        results = []
        profile_names = []
        if inventory.get('sdwan', {}).get('feature_profiles', {}).get("policy_object_profile", None):
            profile_names.append(inventory.get('sdwan', {}).get('feature_profiles', {}).get("policy_object_profile", {}).get("name", "Policy_Profile_Global"))
        for profile_type in cls.feature_profile_types:
            for profile in inventory.get('sdwan', {}).get('feature_profiles', {}).get(profile_type, []):
                profile_names.append(profile['name'])
        non_unique_names = [name for name in set(profile_names) if profile_names.count(name) > 1]
        for name in non_unique_names:
            results.append(f"Feature Profile name '{name}' is not unique")

        return results