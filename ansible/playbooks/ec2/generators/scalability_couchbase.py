
# Python script to generate the cloudformation template json file
# This is not strictly needed, but it takes the pain out of writing a
# cloudformation template by hand.  It also allows for DRY approaches
# to maintaining cloudformation templates.

from troposphere import Ref, Template, Parameter, Output, Join, GetAtt, Tags
import troposphere.ec2 as ec2
import configuration

t = Template()

t.add_description(
    'Couchbase Servers'
)

keynameparameter = t.add_parameter(Parameter(
    'KeyNameParameter', Type='AWS::EC2::KeyPair::KeyName',
    Description='KeyName'
))

subnetid1parameter = t.add_parameter(Parameter(
    'SubnetId1Parameter', Type='AWS::EC2::Subnet::Id',
    Description='SubnetId'
))

subnetid2parameter = t.add_parameter(Parameter(
    'SubnetId2Parameter', Type='AWS::EC2::Subnet::Id',
    Description='SubnetId'
))

securitygroupidparameter = t.add_parameter(Parameter(
    'SecurityGroupIdParameter', Type='AWS::EC2::SecurityGroup::Id',
    Description='SecurityGroupId'
))

# Couchbase Server Instances
numNodesPerGroup = configuration.NUM_COUCHBASE_SERVERS_DATA_CLUSTER1 / configuration.CLUSTER1_NUM_SERVER_GROUPS
groupnum=1
nodesInGroup=0
for i in xrange(configuration.NUM_COUCHBASE_SERVERS_DATA_CLUSTER1):
    name = "qecouchbaseserverdatacluster1node{}".format(i)
    group = "Group {}".format(groupnum)
    instance = ec2.Instance(name)
    instance.ImageId = configuration.COUCHBASE_IMAGE
    instance.InstanceType = configuration.COUCHBASE_INSTANCE_TYPE
    instance.AvailabilityZone = configuration.CLUSTER1_AVAILABILITY_ZONE
    instance.SecurityGroupIds = [ Ref(securitygroupidparameter)]
    instance.SubnetId = Ref(subnetid1parameter)
    instance.KeyName = Ref(keynameparameter)
    instancePhase = "node_primary"
    if i > 15:
        instancePhase = "node_secondary"
    instance.Tags=Tags(Name=name, Type="couchbaseserver_data_cluster1", Group=group, Phase=instancePhase)
    t.add_resource(instance)
    nodesInGroup+=1
    if nodesInGroup == numNodesPerGroup and groupnum < configuration.CLUSTER1_NUM_SERVER_GROUPS:
        nodesInGroup = 0
        groupnum+=1

for i in xrange(configuration.NUM_COUCHBASE_SERVERS_DATA_CLUSTER2):
    name = "couchbaseserverdatacluster2node{}".format(i)
    instance = ec2.Instance(name)
    instance.ImageId = configuration.COUCHBASE_IMAGE
    instance.InstanceType = configuration.COUCHBASE_INSTANCE_TYPE
    instance.AvailabilityZone = configuration.CLUSTER2_AVAILABILITY_ZONE
    instance.SecurityGroupIds = [ Ref(securitygroupidparameter)]
    instance.SubnetId = Ref(subnetid2parameter)
    instance.KeyName = Ref(keynameparameter)
    instance.Tags=Tags(Name=name, Type="couchbaseserver_data_cluster2")
    t.add_resource(instance)

for i in xrange(configuration.NUM_COUCHBASE_SERVERS_DATA_CLUSTER1_NEW):
    name = "couchbaseserverdatacluster1newnode{}".format(i)
    instance = ec2.Instance(name)
    instance.ImageId = configuration.COUCHBASE_IMAGE
    instance.InstanceType = configuration.COUCHBASE_INSTANCE_TYPE
    instance.AvailabilityZone = configuration.CLUSTER1_AVAILABILITY_ZONE
    instance.SecurityGroupIds = [ Ref(securitygroupidparameter)]
    instance.SubnetId = Ref(subnetid1parameter)
    instance.KeyName = Ref(keynameparameter)
    instancePhase = "node_primary"
    if i > 15:
        instancePhase = "node_secondary"
    instance.Tags=Tags(Name=name, Type="couchbaseserver_data_cluster1", Group=group, Phase=instancePhase)

    instance.Tags=Tags(Name=name, Type="couchbaseserver_data_cluster1_new")
    t.add_resource(instance)

for i in xrange(configuration.NUM_COUCHBASE_SERVERS_DATA_CLUSTER2_NEW):
    name = "qecouchbaseserverdatacluster2newnode{}".format(i)
    instance = ec2.Instance(name)
    instance.ImageId = configuration.COUCHBASE_IMAGE
    instance.InstanceType = configuration.COUCHBASE_INSTANCE_TYPE
    instance.AvailabilityZone = configuration.CLUSTER2_AVAILABILITY_ZONE
    instance.SecurityGroupIds = [ Ref(securitygroupidparameter)]
    instance.SubnetId = Ref(subnetid2parameter)
    instance.KeyName = Ref(keynameparameter)
    instance.Tags=Tags(Name=name, Type="couchbaseserver_data_cluster2_new")
    t.add_resource(instance)


for i in xrange(configuration.NUM_COUCHBASE_SERVERS_INDEX):
    name = "couchbaseserverindex{}".format(i)
    instance = ec2.Instance(name)
    instance.ImageId = configuration.COUCHBASE_IMAGE
    instance.InstanceType = configuration.COUCHBASE_INSTANCE_TYPE
    instance.AvailabilityZone = configuration.CLUSTER1_AVAILABILITY_ZONE
    instance.SecurityGroupIds = [ Ref(securitygroupidparameter)]
    instance.SubnetId = Ref(subnetid1parameter)
    instance.KeyName = Ref(keynameparameter)
    instance.Tags=Tags(Name=name, Type="couchbaseserver_index")
    t.add_resource(instance)


for i in xrange(configuration.NUM_COUCHBASE_SERVERS_QUERY):
    name = "couchbaseserverquery{}".format(i)
    instance = ec2.Instance(name)
    instance.ImageId = configuration.COUCHBASE_IMAGE
    instance.InstanceType = configuration.COUCHBASE_INSTANCE_TYPE
    instance.AvailabilityZone = configuration.CLUSTER1_AVAILABILITY_ZONE
    instance.SecurityGroupIds = [ Ref(securitygroupidparameter)]
    instance.SubnetId = Ref(subnetid1parameter)
    instance.KeyName = Ref(keynameparameter)
    instance.Tags=Tags(Name=name, Type="couchbaseserver_query")
    t.add_resource(instance)

for i in xrange(configuration.NUM_CLIENTS):
    name = "qeclients{}".format(i)
    instance = ec2.Instance(name)
    instance.ImageId = configuration.CLIENT_IMAGE
    instance.InstanceType = configuration.CLIENT_INSTANCE_TYPE
    instance.AvailabilityZone = configuration.CLUSTER1_AVAILABILITY_ZONE
    instance.SecurityGroupIds = [ Ref(securitygroupidparameter)]
    instance.SubnetId = Ref(subnetid1parameter)
    instance.KeyName = Ref(keynameparameter)
    instance.Tags=Tags(Name=name, Type="clients")
    t.add_resource(instance)

for i in xrange(configuration.NUM_BACKUPS):
    name = "backups{}".format(i)
    instance = ec2.Instance(name)
    instance.ImageId = configuration.BACKUP_IMAGE
    instance.InstanceType = configuration.BACKUP_INSTANCE_TYPE
    instance.AvailabilityZone = configuration.CLUSTER1_AVAILABILITY_ZONE
    instance.BlockDeviceMappings = [{
      "DeviceName" : "/dev/sda1",
      "Ebs" : { "VolumeSize" : configuration.BACKUP_SPACE }}]
    instance.SecurityGroupIds = [ Ref(securitygroupidparameter)]
    instance.SubnetId = Ref(subnetid1parameter)
    instance.KeyName = Ref(keynameparameter)
    instance.Tags=Tags(Name=name, Type="backups")
    t.add_resource(instance)

print(t.to_json())
