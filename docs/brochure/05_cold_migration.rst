==============
Cold Migration
==============

Cold migration is a pretty accurate term but may give the impression that things
need to be dark. This is a mode where the tenant environment can be shut down
but does not need to. In cold migration the same VM instance will be booted on
the destination cloud that was on the source cloud. There will be downtime
during cold migration as ephemeral storage is copied over to the destination
cloud. When you use the cold migration scenario as it comes, CloudFerry will
pause each instance (virtual machine), take a snapshot of the instance, copy the
snapshot to the destination cloud along with taking care of provisioning and
copying any resources that the instance uses. It then brings the instance back
online. The automated verifications are currently relatively limited and a
manual verification should be completed before production traffic is allowed to
be directed back to the migrated tenant.
