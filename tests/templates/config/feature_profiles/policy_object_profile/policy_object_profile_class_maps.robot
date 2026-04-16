*** Settings ***
Documentation   Verify Policy Object Feature Profile Configuration Class Maps
Name            Policy Object Profile Class Maps
Suite Setup     Login SDWAN Manager
Suite Teardown  Run On Last Process    Logout SDWAN Manager
Default Tags    sdwan    config    feature_profiles     policy_object_profile   class_maps
Resource        ../../../sdwan_common.resource


{% if sdwan.feature_profiles.policy_object_profile.class_maps is defined %}

*** Test Cases ***
Get Policy Object Profile
    ${r}=    GET On Session    sdwan_manager    /dataservice/v1/feature-profile/sdwan/policy-object
    Set Suite Variable    ${r}


Get Class Maps
    ${profile}=    Get Value From Json    ${r.json()}    $[?(@.profileName=='{{ sdwan.feature_profiles.policy_object_profile.name }}')]
    Run Keyword If    ${profile} == []    Fail    Feature Profile '{{ sdwan.feature_profiles.policy_object_profile.name }}' should be present on the Manager
    ${profile_id}=    Get Value From Json    ${profile}    $..profileId

    ${class_map_raw}=    GET On Session    sdwan_manager    /dataservice/v1/feature-profile/sdwan/policy-object/${profile_id[0]}/class
    Set Suite Variable    ${class_map_raw}


{% for class_map in sdwan.feature_profiles.policy_object_profile.class_maps | default([]) %}

Verify Feature Profiles Policy Object Profile {{ sdwan.feature_profiles.policy_object_profile.name }} Class Map Feature {{ class_map.name }}

    ${class_maps}=    Get Value From Json    ${class_map_raw.json()}    $..data[?(@..name=='{{ class_map.name }}')]..payload
    Run Keyword If    ${class_maps} == []    Fail    Feature '{{ class_map.name }}' expected to be configured within the policy object profile '{{ sdwan.feature_profiles.policy_object_profile.name }}' on the Manager

    Should Be Equal Value Json String    ${class_maps[0]}    $..name    {{ class_map.name }}    msg=name
    Should Be Equal Value Json Special_String     ${class_maps[0]}     $.description    {{ class_map.description | default('not_defined') | normalize_special_string }}    msg=description

    Should Be Equal Value Json Yaml    ${class_maps[0]}    $.data.entries[0].queue   {{ class_map.queue | default('not_defined') }}    not_defined     msg=queue    var_msg=not_defined

{% endfor %}

{% endif %}