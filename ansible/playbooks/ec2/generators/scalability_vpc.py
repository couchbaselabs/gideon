
# Python script to generate the cloudformation template json file
# This is not strictly needed, but it takes the pain out of writing a
# cloudformation template by hand.  It also allows for DRY approaches
# to maintaining cloudformation templates.

from troposphere import Ref, Template, Parameter, Output, Join, GetAtt, Tags
import troposphere.ec2 as ec2
import configuration

t = Template()

t.add_description(
    'VPC Script'
)

def createCouchbaseVPC(t):
    couchbaseVPC = t.add_resource(ec2.VPC(
        'VPC', CidrBlock='10.0.0.0/16',
        EnableDnsSupport='true',
        EnableDnsHostnames='true',
        Tags=Tags(Name=Join('', ['vpc-scalabilty-', Ref('AWS::Region')]))
    ))
    return couchbaseVPC

def createCouchbaseInternetGateway(t):
    couchbaseInternetGateway = t.add_resource(ec2.InternetGateway(
        'GATEWAY',
         Tags=Tags(Name=Join('', ['gateway-scalability-', Ref('AWS::Region')]))
    ))
    return couchbaseInternetGateway

def createCouchbaseVPCGatewayAttachment(t, gateway, vpc):
    couchbaseVPCGatewayAttachment =  t.add_resource(ec2.VPCGatewayAttachment(
        'VPCGATEWAYATTACHMENT',
        InternetGatewayId=Ref(gateway),
        VpcId=Ref(vpc)
    ))
    return couchbaseVPCGatewayAttachment

def createCouchbaseRouteTable(t, vpc):
    couchbaseRouteTable = t.add_resource(ec2.RouteTable(
        'ROUTETABLE',
        VpcId=Ref(vpc),
        Tags=Tags(Name=Join('', ['routetable-scalabilty-', Ref('AWS::Region')]))
    ))
    return couchbaseRouteTable

def createCouchbaseRoute(t, gateway, routetable):
    couchbaseRoute = t.add_resource(ec2.Route(
        'ROUTE',
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=Ref(gateway),
        RouteTableId=Ref(routetable)
    ))
    return couchbaseRoute

def createCouchbaseSubnet1(t, vpc):
    couchbaseSubnet = t.add_resource(ec2.Subnet(
       'SUBNET1',
        AvailabilityZone = configuration.CLUSTER1_AVAILABILITY_ZONE,
        CidrBlock='10.0.0.0/17',
        MapPublicIpOnLaunch='true',
        Tags=Tags(Name=Join('', ['subnet1-scalability-', Ref('AWS::Region')])),
        VpcId=Ref(vpc)
    ))
    return couchbaseSubnet

def createCouchbaseSubnet2(t, vpc):
    couchbaseSubnet = t.add_resource(ec2.Subnet(
       'SUBNET2',
        AvailabilityZone = configuration.CLUSTER2_AVAILABILITY_ZONE,
        CidrBlock='10.0.128.0/17',
        MapPublicIpOnLaunch='true',
        Tags=Tags(Name=Join('', ['subnet2-scalability-', Ref('AWS::Region')])),
        VpcId=Ref(vpc)
    ))
    return couchbaseSubnet



def createCouchbaseSubnetRouteTableAssociation(t, subnet, routetable):
    couchbaseSubnetRouteTableAssociation = t.add_resource(ec2.SubnetRouteTableAssociation(
        'SUBNETROUTETABLEASSOCATION1',
        RouteTableId=Ref(routetable),
        SubnetId=Ref(subnet)
    ))
    return couchbaseSubnetRouteTableAssociation


def createCouchbaseSubnetRouteTableAssociation2(t, subnet, routetable):
    couchbaseSubnetRouteTableAssociation = t.add_resource(ec2.SubnetRouteTableAssociation(
        'SUBNETROUTETABLEASSOCATION2',
        RouteTableId=Ref(routetable),
        SubnetId=Ref(subnet)
    ))
    return couchbaseSubnetRouteTableAssociation


def createCouchbaseSecurityGroups(t, vpc):

    # Couchbase security group
    secGrpCouchbase = ec2.SecurityGroup('CouchbaseSecurityGroup')
    secGrpCouchbase.GroupDescription = "Allow access to Couchbase Server"
    secGrpCouchbase.VpcId = Ref(vpc)
    secGrpCouchbase.SecurityGroupIngress = [
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="22",
            ToPort="22",
            CidrIp="0.0.0.0/0",
        ),
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="8091",
            ToPort="8091",
            CidrIp="0.0.0.0/0",
        ),
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="8092",
            ToPort="8092",
            CidrIp="0.0.0.0/0",
        ),
        ec2.SecurityGroupRule(   # sync gw user port
            IpProtocol="tcp",
            FromPort="4984",
            ToPort="4984",
            CidrIp="0.0.0.0/0",
        ),
        ec2.SecurityGroupRule(   # sync gw admin port
            IpProtocol="tcp",
            FromPort="4985",
            ToPort="4985",
            CidrIp="0.0.0.0/0",
        ),
        ec2.SecurityGroupRule(   # expvars
            IpProtocol="tcp",
            FromPort="9876",
            ToPort="9876",
            CidrIp="0.0.0.0/0",
        )
    ]

    # Add security group to template
    t.add_resource(secGrpCouchbase)

    cbIngressPorts = [
        {"FromPort": "4369", "ToPort": "4369" },    # couchbase server
        {"FromPort": "5984", "ToPort": "5984" },    # couchbase server
        {"FromPort": "11209", "ToPort": "11209" },  # couchbase server 
        {"FromPort": "11210", "ToPort": "11210" },  # couchbase server
        {"FromPort": "11211", "ToPort": "11211" },  # couchbase server
        {"FromPort": "21100", "ToPort": "21299" },  # couchbase server
    ]

    for cbIngressPort in cbIngressPorts:
        from_port = cbIngressPort["FromPort"]
        to_port = cbIngressPort["ToPort"]
        name = 'CouchbaseSecurityGroupIngress{}'.format(from_port)
        secGrpCbIngress = ec2.SecurityGroupIngress(name)
        secGrpCbIngress.GroupId = GetAtt(secGrpCouchbase, 'GroupId')
        secGrpCbIngress.IpProtocol = "tcp"
        secGrpCbIngress.FromPort = from_port
        secGrpCbIngress.ToPort = to_port
        secGrpCbIngress.SourceSecurityGroupId = GetAtt(secGrpCouchbase, 'GroupId')
        t.add_resource(secGrpCbIngress)

    return secGrpCouchbase


couchbaseVPC = createCouchbaseVPC(t)
couchbaseInternetGateway = createCouchbaseInternetGateway(t)
couchbaseVPCGatewayAttachment = createCouchbaseVPCGatewayAttachment(t, couchbaseInternetGateway, couchbaseVPC)
couchbaseRouteTable = createCouchbaseRouteTable(t, couchbaseVPC)
couchbaseRoute = createCouchbaseRoute(t, couchbaseInternetGateway, couchbaseRouteTable)
couchbaseSubnet = createCouchbaseSubnet1(t, couchbaseVPC)
couchbaseSubnetRouteTableAssociation = createCouchbaseSubnetRouteTableAssociation(t, couchbaseSubnet, couchbaseRouteTable)
secGrpCouchbase = createCouchbaseSecurityGroups(t, couchbaseVPC)


couchbaseSubnet2 = createCouchbaseSubnet2(t, couchbaseVPC)
couchbaseSubnetRouteTableAssociation2 = createCouchbaseSubnetRouteTableAssociation2(t, couchbaseSubnet2, couchbaseRouteTable)

output = Output(
    "SubnetId1",
    Description="Subnet ID1",
    Value= Ref("SUBNET1")
)
t.add_output(output)

output = Output(
    "SubnetId2",
    Description="Subnet ID2",
    Value= Ref("SUBNET2")
)
t.add_output(output)


output = Output(
    "SecurityGroupId",
    Description="Security Group ID",
    Value= Ref("CouchbaseSecurityGroup")
)

t.add_output(output)

print(t.to_json())
