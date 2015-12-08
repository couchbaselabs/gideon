
# Python script to generate the cloudformation template json file
# This is not strictly needed, but it takes the pain out of writing a
# cloudformation template by hand.  It also allows for DRY approaches
# to maintaining cloudformation templates.

from troposphere import Ref, Template, Parameter, Output, Join, GetAtt, Tags
import troposphere.ec2 as ec2
import troposphere.cloudformation as cloudformation
import configuration

t = Template()

t.add_description(
    'Toplevel Stack'
)

#
# Parameters
#
keyname_param = t.add_parameter(Parameter(
    'KeyName', Type='String',
    Description='Name of an existing EC2 KeyPair to enable SSH access'
))


instance = cloudformation.Stack("vpcStack")
instance.TemplateURL =  "https://s3.amazonaws.com/" + configuration.S3_BUCKET_NAME + "/scalability_vpc.json"
instance.TimeoutInMinutes = 60
t.add_resource(instance)



p = {"KeyNameParameter": Ref("KeyName"), "SecurityGroupIdParameter" : GetAtt("vpcStack", "Outputs.SecurityGroupId"),
     "SubnetId1Parameter" : GetAtt("vpcStack", "Outputs.SubnetId1"), "SubnetId2Parameter" : GetAtt("vpcStack", "Outputs.SubnetId2")}


instance = cloudformation.Stack("couchbaseStack")
instance.TemplateURL = "https://s3.amazonaws.com/" + configuration.S3_BUCKET_NAME + "/scalability_couchbase.json"
instance.TimeoutInMinutes = 60
instance.Parameters = p
t.add_resource(instance)

print(t.to_json())
