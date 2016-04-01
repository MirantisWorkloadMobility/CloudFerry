Scenario
========

## Overview

By default CloudFerry tool is going to migrate resources and instances,
specified in the filter config file, from the source cloud to the destination
cloud.
Default location of filter config file is `configs/filter.yaml`, but it always
can be changed by modifying main configuration file (configuration.ini).

Example:
```
[migrate]
filter_path = <new_filter_path>
```

If one wants to migrate ALL resources and instances from the source cloud to
the destination cloud then need to modify main configuration file
(configuration.ini) with:

```
[migrate]
migrate_whole_cloud = True
```

Just use default file scenario(scenario/cold_migrate.yaml) and see README file for instructions to run migration.


## Resource migration

If one wants to migrate resources then need to prepare custom file scenario. The main part is under keyword "process".
The mandatory item is "act_identity_trans". Other items can be removed if not needed.
The example below:
- 1. Prepare CloudFerry workspace(see "README").
- 2. Use "scenario/migrate_resources.yaml" in the [migrate] block in configuration.ini
- 3. Run migration as usual(see "README").

Example:
```
[migrate]
scenario = scenario/migrate_resources.yaml
```


## Instance migration

If one wants to migrate instance(s) then need to prepare custom file scenario. The main part is under keyword "process".
The items can not be removed from this block.
The example below:
- 1. Prepare CloudFerry workspace(see "README").
- 2. Use "scenario/migrate_vms.yaml" in the [migrate] block in configuration.ini
- 3. Run migration as usual(see "README").

Example: 
```
[migrate]
scenario = scenario/migrate_vms.yaml
```