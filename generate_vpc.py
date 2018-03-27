from troposphere import Base64, FindInMap, GetAtt, Join, Output
from troposphere import Parameter, Ref, Tags, Template
from troposphere.cloudfront import Distribution, DistributionConfig
from troposphere.cloudfront import Origin, DefaultCacheBehavior
from troposphere.ec2 import PortRange
from troposphere.ec2 import Route
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ec2 import RouteTable
from troposphere.ec2 import EIP, EIPAssociation, NetworkInterface, NetworkInterfaceProperty
from troposphere.ec2 import SecurityGroup, SecurityGroupRule
from troposphere.ec2 import SubnetRouteTableAssociation
from troposphere.ec2 import VPCGatewayAttachment
from troposphere.ec2 import Subnet
from troposphere.ec2 import InternetGateway, NatGateway
from troposphere.ec2 import Instance
from troposphere.ec2 import VPC
import troposphere.autoscaling as autoscaling
import troposphere.elasticloadbalancingv2 as elb
import troposphere.route53 as route53
from troposphere.cloudwatch import Alarm, MetricDimension
from troposphere.rds import DBInstance, DBSubnetGroup

import json
import yaml

# Load input json

with open('spec-prod.json') as spec_file:    
    spec = json.load(spec_file)

t = Template()

t.add_description(spec["project"]["desc"])

# tag variables
resource_tag = spec["project"]["tag"]
project_name = spec["project"]["name"]
environment_name = spec["project"]["env"]
ticket = spec["project"]["ticket"]
availability_zone_1 = spec["project"]["az1"]
availability_zone_2 = spec["project"]["az2"]

# params

vpcCidr_param = t.add_parameter(Parameter(
    "VpcCidr",
    Description="VPC CIDR",
    Default="10.0.0.0/16",
    Type="String",
    ))

natGatewayCidr_param = t.add_parameter(Parameter(
    "NatGatewayCidr",
    Description="Nat Gateway CIDR",
    Default="0.0.0.0/0",
    Type="String",
    ))

igwCidr_param = t.add_parameter(Parameter(
    "InternetGatewayCidr",
    Description="Internet Gateway CIDR",
    Default="0.0.0.0/0",
    Type="String",
    ))

publicSubnet01Cidr_param = t.add_parameter(Parameter(
    "PublicSubnet01Cidr",
    Description="PublicSubnet01 CIDR",
    Default="10.0.0.0/24",
    Type="String",
    ))

publicSubnet02Cidr_param = t.add_parameter(Parameter(
    "PublicSubnet02Cidr",
    Description="PublicSubnet02 CIDR",
    Default="10.0.1.0/24",
    Type="String",
    ))

privateWebSubnet01Cidr_param = t.add_parameter(Parameter(
    "privateWebSubnet01Cidr",
    Description="PrivateWebSubnet01 CIDR",
    Default="10.0.2.0/24",
    Type="String",
    ))

privateWebSubnet02Cidr_param = t.add_parameter(Parameter(
    "privateWebSubnet02Cidr",
    Description="PrivateWebSubnet02 CIDR",
    Default="10.0.3.0/24",
    Type="String",
    ))

privateDbSubnet01Cidr_param = t.add_parameter(Parameter(
    "privateDbSubnet01Cidr",
    Description="PrivateDbSubnet01 CIDR",
    Default="10.0.4.0/24",
    Type="String",
    ))

privateDbSubnet02Cidr_param = t.add_parameter(Parameter(
    "privateDbSubnet02Cidr",
    Description="PrivateDbSubnet02 CIDR",
    Default="10.0.5.0/24",
    Type="String",
    ))

availabilityZone01_param = t.add_parameter(Parameter(
    "AvailabilityZone01",
    Description="VPC AvailabilityZone01",
    Default=availability_zone_1,
    Type="String",
    ))

availabilityZone02_param = t.add_parameter(Parameter(
    "AvailabilityZone02",
    Description="VPC AvailabilityZone02",
    Default=availability_zone_2,
    Type="String",
    ))

tomcatPort_param = t.add_parameter(Parameter(
        "tomcatPort",
        Type="String",
        Default="80",
        Description="TCP/IP port of the web server",
    ))

dbPort_param = t.add_parameter(Parameter(
        "dbPort",
        Type="String",
        Default="3306",
        Description="TCP/IP port of the web server",
    ))

# Auto scaling group parameters

# Web Layer

web_asg_capacity = t.add_parameter(Parameter(
        "webAsgCapacity",
        Default="2",
        Type="Number",
        Description="Desired capcacity of AutoScalingGroup"
    ))
web_asg_min_size = t.add_parameter(Parameter(
        "webAsgMinSize",
        Default="2",
        Type="Number",
        Description="Minimum size of AutoScalingGroup"
    ))
web_asg_max_size = t.add_parameter(Parameter(
        "webAsgMaxSize",
        Default="5",
        Type="Number",
        Description="Maximum size of AutoScalingGroup"
    ))
web_asg_cooldown = t.add_parameter(Parameter(
        "webAsgCooldown",
        Default="360",
        Type="Number",
        Description="Cooldown before starting/stopping another instance"
    ))
web_asg_health_grace = t.add_parameter(Parameter(
        "webAsgHealthGrace",
        Default="360",
        Type="Number",
        Description="Wait before starting/stopping another instance"
    ))

# API Layer
api_asg_capacity = t.add_parameter(Parameter(
        "apiAsgCapacity",
        Default="2",
        Type="Number",
        Description="Desired capcacity of AutoScalingGroup"
    ))
api_asg_min_size = t.add_parameter(Parameter(
        "apiAsgMinSize",
        Default="2",
        Type="Number",
        Description="Minimum size of AutoScalingGroup"
    ))
api_asg_max_size = t.add_parameter(Parameter(
        "apiAsgMaxSize",
        Default="5",
        Type="Number",
        Description="Maximum size of AutoScalingGroup"
    ))
api_asg_cooldown = t.add_parameter(Parameter(
        "apiAsgCooldown",
        Default="360",
        Type="Number",
        Description="Cooldown before starting/stopping another instance"
    ))
api_asg_health_grace = t.add_parameter(Parameter(
        "apiAsgHealthGrace",
        Default="360",
        Type="Number",
        Description="Wait before starting/stopping another instance"
    ))

# VPC
VPC = t.add_resource(
    VPC(
        "VPC",
        EnableDnsSupport="true",
        CidrBlock=Ref(vpcCidr_param),
        EnableDnsHostnames="true",
        Tags=Tags(
            Name=Join("",[resource_tag,"-",environment_name,"-VPC"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
        )
))

# Public Subnets
publicSubnet01 = t.add_resource(Subnet(
    "publicSubnet01",
    VpcId=Ref("VPC"),
    AvailabilityZone=Ref(availabilityZone01_param),
    CidrBlock=Ref(publicSubnet01Cidr_param),
    MapPublicIpOnLaunch=True,
    Tags=Tags(
        Name=Join("",[resource_tag,"-PublicSubnet-01"]),
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    )
))

publicSubnet02 = t.add_resource(Subnet(
    "publicSubnet02",
    VpcId=Ref("VPC"),
    AvailabilityZone=Ref(availabilityZone02_param),
    CidrBlock=Ref(publicSubnet02Cidr_param),
    MapPublicIpOnLaunch=True,
    Tags=Tags(
        Name=Join("",[resource_tag,"-PublicSubnet-02"]),
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    )
))

# Private Subnets
privateWebSubnet01 = t.add_resource(Subnet(
    "privateWebSubnet01",
    VpcId=Ref("VPC"),
    AvailabilityZone=Ref(availabilityZone01_param),
    CidrBlock=Ref(privateWebSubnet01Cidr_param),
    Tags=Tags(
        Name=Join("",[resource_tag,"-PrivateWebSubnet-01"]),
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    )
))

privateWebSubnet02 = t.add_resource(Subnet(
    "privateWebSubnet02",
    VpcId=Ref("VPC"),
    AvailabilityZone=Ref(availabilityZone02_param),
    CidrBlock=Ref(privateWebSubnet02Cidr_param),
    Tags=Tags(
        Name=Join("",[resource_tag,"-PrivateWebSubnet-02"]),
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    )
))

privateDbSubnet01 = t.add_resource(Subnet(
    "privateDbSubnet01",
    VpcId=Ref("VPC"),
    AvailabilityZone=Ref(availabilityZone01_param),
    CidrBlock=Ref(privateDbSubnet01Cidr_param),
    Tags=Tags(
        Name=Join("",[resource_tag,"-PrivateDbSubnet-01"]),
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    )
))

privateDbSubnet02 = t.add_resource(Subnet(
    "privateDbSubnet02",
    VpcId=Ref("VPC"),
    AvailabilityZone=Ref(availabilityZone02_param),
    CidrBlock=Ref(privateDbSubnet02Cidr_param),
    Tags=Tags(
        Name=Join("",[resource_tag,"-PrivateDbSubnet-02"]),
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    )
))

# Security Groups

# Generating Bastion security group rules
bas_security_group_rules = []
for ip in spec["ops_ips"]["ssh"]:
    rule=[SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='22',
                ToPort='22',
                CidrIp=ip)]
    bas_security_group_rules.extend(rule)

for ip in spec["customer_ips"]["ssh"]:
    rule=[SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='22',
                ToPort='22',
                CidrIp=ip)]
    bas_security_group_rules.extend(rule)


basSecurityGroup = t.add_resource(
    SecurityGroup(
        'basSecurityGroup',
        GroupDescription='Allow SSH connections from an approved list of IPs',
        SecurityGroupIngress=bas_security_group_rules,
        VpcId=Ref(VPC),
        Tags=Tags(
            Name=Join("",[resource_tag,"-basSecurityGroup"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
        )
    ))

# Generating Load Balancer security group rules
alb_security_group_ingress_rules = []

albSecurityGroup = t.add_resource(
    SecurityGroup(
        'albSecurityGroup',
        GroupDescription='Allow all necessary ports from the internet',
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='443',
                ToPort='443',
                CidrIp='0.0.0.0/0'),
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='80',
                ToPort='80',
                CidrIp='0.0.0.0/0')
        ],
        VpcId=Ref(VPC),
        Tags=Tags(
            Name=Join("",[resource_tag,"-albSecurityGroup"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
        )
    ))


feSecurityGroup = t.add_resource(
    SecurityGroup(
        'feSecurityGroup',
        GroupDescription='Allow connections from Bastion and LB',
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='22',
                ToPort='22',
                SourceSecurityGroupId=Ref(basSecurityGroup)),
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort=Ref(tomcatPort_param),
                ToPort=Ref(tomcatPort_param),
                SourceSecurityGroupId=Ref(albSecurityGroup))
        ],
        VpcId=Ref(VPC),
        Tags=Tags(
            Name=Join("",[resource_tag,"-feSecurityGroup"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
        )
    ))

rdsSecurityGroup = t.add_resource(
    SecurityGroup(
        'rdsSecurityGroup',
        GroupDescription='RDS security group',
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort=Ref(dbPort_param),
                ToPort=Ref(dbPort_param),
                SourceSecurityGroupId=Ref(basSecurityGroup)),
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort=Ref(dbPort_param),
                ToPort=Ref(dbPort_param),
                SourceSecurityGroupId=Ref(feSecurityGroup))
        ],
        VpcId=Ref(VPC),
        Tags=Tags(
            Name=Join("",[resource_tag,"-rdsSecurityGroup"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
        )

    ))

# Internet Gateway
internetGateway = t.add_resource(
    InternetGateway(
        "InternetGateway",
        Tags=Tags(
            Name=Join("",[resource_tag,"-IGW"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
    )
))

igwVpcAttachment = t.add_resource(
    VPCGatewayAttachment(
        'AttachInternetGatewayToVPC',
        VpcId=Ref(VPC),
        InternetGatewayId=Ref(internetGateway)
))

# Public Subnet Route Table
publicRouteTable = t.add_resource(
    RouteTable(
        "publicRouteTable",
        VpcId=Ref("VPC"),
        Tags=Tags(
            Name=Join("",[resource_tag,"-PublicRouteTable"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
        )
))

publicSubnet01Association = t.add_resource(SubnetRouteTableAssociation(
    "publicSubnet01Association",
    SubnetId=Ref("publicSubnet01"),
    RouteTableId=Ref(publicRouteTable),
))

publicSubnet02Association = t.add_resource(SubnetRouteTableAssociation(
    "publicSubnet02Association",
    SubnetId=Ref("publicSubnet02"),
    RouteTableId=Ref(publicRouteTable),
))

igwRouteAttachment = t.add_resource(
    Route(
        'AttachInternetGatewayToPublicRouteTable',
        DestinationCidrBlock=Ref(igwCidr_param),
        GatewayId=Ref(internetGateway),
        RouteTableId=Ref(publicRouteTable)
))

# Private Subnet Route Table
natRouteTable = t.add_resource(
    RouteTable(
        "natRouteTable",
        VpcId=Ref("VPC"),
        Tags=Tags(
            Name=Join("",[resource_tag,"-NatRouteTable"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
        )
))

natRouteWeb01Association = t.add_resource(
    SubnetRouteTableAssociation(
        "natRouteWeb01Association",
        SubnetId=Ref("privateWebSubnet01"),
        RouteTableId=Ref(natRouteTable),
))

natRouteWeb02Association = t.add_resource(
    SubnetRouteTableAssociation(
        "natRouteWeb02Association",
        SubnetId=Ref("privateWebSubnet02"),
        RouteTableId=Ref(natRouteTable),
))

natRouteDb01Association = t.add_resource(
    SubnetRouteTableAssociation(
        "natRouteDb01Association",
        SubnetId=Ref("privateDbSubnet01"),
        RouteTableId=Ref(natRouteTable),
))

natRouteDb02Association = t.add_resource(
    SubnetRouteTableAssociation(
        "natRouteDb02Association",
        SubnetId=Ref("privateDbSubnet02"),
        RouteTableId=Ref(natRouteTable),
))

natElasticIp = t.add_resource(
    EIP(
        "natElasticIp",
        Domain="vpc",
))

natGateway = t.add_resource(
    NatGateway(
        "natGateway",
        AllocationId=GetAtt(natElasticIp, 'AllocationId'),
        SubnetId=Ref("publicSubnet01")
    )
)

natRouteAttachment = t.add_resource(
    Route(
        'AttachNatGatewayToPrivateRouteTable',
        DestinationCidrBlock=Ref(natGatewayCidr_param),
        NatGatewayId=Ref(natGateway),
        RouteTableId=Ref(natRouteTable)
))

# Public Subnet Instances

# Bastion

if spec["bastion"]:

    bas_num_nodes = spec["bastion"]["num_nodes"]
    bas_name = spec["bastion"]["canonical_name"]
    bas_instance_type = spec["bastion"]["ec2_instance_type"]
    bas_ami_id = spec["bastion"]["ami_id"]

    for bas_node in xrange(1, int(bas_num_nodes)+1):
        t.add_resource(Instance(
            "bas"+str(bas_node).zfill(2) ,
            SourceDestCheck="false",
            ImageId=bas_ami_id,
            InstanceType=bas_instance_type,
            KeyName=spec["key_name"],
            Tags=Tags(
                Name=Join("",[resource_tag,"-",bas_name,"-",str(bas_node).zfill(2)]),
                Environment=environment_name,
                Project=project_name,
                Ticket=ticket
            )   
        ))


# Application ELB

application_load_balancer = t.add_resource(elb.LoadBalancer(
    "applicationLoadBalancer",
    Name=Join("",[resource_tag,"-ALB"]),
    Scheme="internet-facing",
    Subnets=[Ref(publicSubnet01),Ref(publicSubnet02)],
    SecurityGroups=[Ref(albSecurityGroup)],
    Tags=Tags(
        Name=Join("",[resource_tag,"-ALB"]),
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    )  
))

default_target_group = t.add_resource(elb.TargetGroup(
    "defaultTargetGroup",
    Name=resource_tag + "-default",
    HealthCheckPath="/",
    HealthCheckIntervalSeconds="20",
    HealthCheckProtocol="HTTP",
    HealthCheckTimeoutSeconds="10",
    HealthyThresholdCount="4",
    Matcher=elb.Matcher(
        HttpCode="301"),
    Port=80,
    Protocol="HTTP",
    UnhealthyThresholdCount="3",
    VpcId=Ref(VPC),
    Tags=Tags(
        Name=resource_tag + "default",
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    )   
))

http_listener = t.add_resource(elb.Listener(
    "albHttpListener",
    Port="80",
    Protocol="HTTP",
    LoadBalancerArn=Ref(application_load_balancer),
    DefaultActions=[elb.Action(
        Type="forward",
        TargetGroupArn=Ref(default_target_group)
    )]
))

https_listener = t.add_resource(elb.Listener(
    "albHttpsListener",
    Port="443",
    Protocol="HTTPS",
    Certificates=[elb.Certificate(
        CertificateArn=spec["ssl_cert"]
    )],
    LoadBalancerArn=Ref(application_load_balancer),
    DefaultActions=[elb.Action(
        Type="forward",
        TargetGroupArn=Ref(default_target_group)
    )]
))

customers = spec["customers"]
target_groups = {}
web_target_groups = []
web_target_groups.append(Ref("defaultTargetGroup"))

api_target_groups = []

listeners = {}
priority = 1

for cust in customers:

    port = spec["customers"][cust]["port"]
    canonical_name = spec["customers"][cust]["canonical_name"]
    
    target_groups[cust]={}

    target_groups[cust]["web"] = t.add_resource(elb.TargetGroup(
        canonical_name + "WebTargetGroup",
        HealthCheckPath="/",
        HealthCheckIntervalSeconds="20",
        HealthCheckProtocol="HTTP",
        HealthCheckTimeoutSeconds="10",
        HealthyThresholdCount="4",
        Matcher=elb.Matcher(
            HttpCode="200"),
        Name=Join("",[resource_tag,"-",str(cust),"-webLayer"]),
        Port=port,
        Protocol="HTTP",
        UnhealthyThresholdCount="3",
        VpcId=Ref(VPC),
        Tags=Tags(
            Name=Join("",[resource_tag,"-",str(cust),"-webLayer"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
        )   
    ))

    web_target_groups.append(Ref(target_groups[cust]["web"]))

    target_groups[cust]["api"] = t.add_resource(elb.TargetGroup(
        canonical_name + "ApiTargetGroup",
        HealthCheckPath="/api/1.0/robo/version",
        HealthCheckIntervalSeconds="20",
        HealthCheckProtocol="HTTP",
        HealthCheckTimeoutSeconds="10",
        HealthyThresholdCount="4",
        Matcher=elb.Matcher(
            HttpCode="200"),
        Name=Join("",[resource_tag,"-",str(cust),"-apiLayer"]),
        Port=port,
        Protocol="HTTP",
        UnhealthyThresholdCount="3",
        VpcId=Ref(VPC),
        Tags=Tags(
            Name=Join("",[resource_tag,"-",str(cust),"-apiLayer"]),
            Environment=environment_name,
            Project=project_name,
            Ticket=ticket
        )   
    ))

    api_target_groups.append(Ref(target_groups[cust]["api"]))

    t.add_resource(elb.ListenerRule(
        canonical_name + "apiListenerRule",
        ListenerArn=Ref(https_listener),
        Conditions=[elb.Condition(
            Field="host-header",
            Values=[Join("", [str(cust),".",spec["domain"]])]
            ),
            elb.Condition(
                Field="path-pattern",
                Values=["/api/*"]
            )
        ],
        Actions=[elb.Action(
            Type="forward",
            TargetGroupArn=Ref(target_groups[cust]["api"])
        )],
        Priority=priority
    ))

    priority += 1

    t.add_resource(elb.ListenerRule(
        canonical_name + "webListenerRule",
        ListenerArn=Ref(https_listener),
        Conditions=[elb.Condition(
            Field="host-header",
            Values=[Join("", [str(cust),".",spec["domain"]])]
            )
        ],
        Actions=[elb.Action(
            Type="forward",
            TargetGroupArn=Ref(target_groups[cust]["web"])
        )],
        Priority=priority
    ))

    priority += 1

# Auto Scaling Groups

# Web Layer
# Launchconfiguration
web_name = spec["web"]["canonical_name"]
web_instance_type = spec["web"]["ec2_instance_type"]
web_ami_id = spec["web"]["ami_id"]

webEC2LaunchConfiguration = t.add_resource(autoscaling.LaunchConfiguration(
    "webEC2LaunchConfiguration",
    ImageId=web_ami_id,
    InstanceType=web_instance_type,
    KeyName=spec["key_name"],
    AssociatePublicIpAddress=False,
    SecurityGroups=[Ref(feSecurityGroup)],
))


webASG = t.add_resource(autoscaling.AutoScalingGroup(
    "webAutoScalingGroup",
    DesiredCapacity=Ref(web_asg_capacity),
    TargetGroupARNs=web_target_groups,
    Tags=autoscaling.Tags(
        Name=Join("",[resource_tag,"-",web_name]),
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    ),
    MetricsCollection=[
        autoscaling.MetricsCollection(
            Granularity="1Minute"
        )
    ],
    VPCZoneIdentifier=[Ref(privateWebSubnet01),Ref(privateWebSubnet02)],
    MinSize=Ref(web_asg_min_size),
    MaxSize=Ref(web_asg_max_size),
    Cooldown=Ref(web_asg_cooldown),
    LaunchConfigurationName=Ref(webEC2LaunchConfiguration),
    HealthCheckGracePeriod=Ref(web_asg_health_grace),
    HealthCheckType="EC2",
))

webAsgScalingOut = t.add_resource(autoscaling.ScalingPolicy(
    "webAsgScalingOut",
    AdjustmentType="ChangeInCapacity",
    AutoScalingGroupName=Ref(webASG),
    Cooldown="360",
    ScalingAdjustment="1",
))

webAsgScalingIn = t.add_resource(autoscaling.ScalingPolicy(
    "webAsgScalingIn",
    AdjustmentType="ChangeInCapacity",
    AutoScalingGroupName=Ref(webASG),
    Cooldown="360",
    ScalingAdjustment="-1",
))

webHighHttpRequestsAlarm = t.add_resource(Alarm(
    "webHighHttpRequestsAlarm",
    AlarmDescription="Alarm if more than 1000 http requests",
    Namespace="AWS/SQS",
    Dimensions=[
            MetricDimension(
                Name="AutoScalingGroupName",
                Value=Ref(webASG)
            ),
        ],
    MetricName="RequestCount",
    Statistic="Average",
    Period="1800",
    EvaluationPeriods="1",
    Threshold="1000",
    ComparisonOperator="GreaterThanThreshold",
    AlarmActions=[Ref(webAsgScalingOut)]
))

webLowHttpRequestsAlarm = t.add_resource(Alarm(
    "webLowHttpRequestsAlarm",
    AlarmDescription="Alarm if less than 1000 http requests",
    Namespace="AWS/SQS",
    Dimensions=[
            MetricDimension(
                Name="AutoScalingGroupName",
                Value=Ref(webASG)
            ),
        ],
    MetricName="RequestCount",
    Statistic="Average",
    Period="1800",
    EvaluationPeriods="1",
    Threshold="1000",
    ComparisonOperator="LessThanThreshold",
    AlarmActions=[Ref(webAsgScalingIn)]
))

# API Layer
# Launchconfiguration

api_name = spec["api"]["canonical_name"]
api_instance_type = spec["api"]["ec2_instance_type"]
api_ami_id = spec["api"]["ami_id"]

apiEC2LaunchConfiguration = t.add_resource(autoscaling.LaunchConfiguration(
    "apiEC2LaunchConfiguration",
    ImageId=api_ami_id,
    #InstanceId=Ref(web01),
    InstanceType=api_instance_type,
    KeyName=spec["key_name"],
    AssociatePublicIpAddress=False,
    SecurityGroups=[Ref(feSecurityGroup)],
))

apiASG = t.add_resource(autoscaling.AutoScalingGroup(
    "apiAutoScalingGroup",
    DesiredCapacity=Ref(api_asg_capacity),
    TargetGroupARNs=api_target_groups,
    Tags=autoscaling.Tags(
        Name=Join("",[resource_tag,"-",api_name]),
        Environment=environment_name,
        Project=project_name,
        Ticket=ticket
    ),
    MetricsCollection=[
        autoscaling.MetricsCollection(
            Granularity="1Minute"
        )
    ],
    VPCZoneIdentifier=[Ref(privateWebSubnet01),Ref(privateWebSubnet02)],
    MinSize=Ref(api_asg_min_size),
    MaxSize=Ref(api_asg_max_size),
    Cooldown=Ref(api_asg_cooldown),
    LaunchConfigurationName=Ref(apiEC2LaunchConfiguration),
    HealthCheckGracePeriod=Ref(api_asg_health_grace),
    HealthCheckType="EC2",
))

apiAsgScalingOut = t.add_resource(autoscaling.ScalingPolicy(
    "apiAsgScalingOut",
    AdjustmentType="ChangeInCapacity",
    AutoScalingGroupName=Ref(apiASG),
    Cooldown="360",
    ScalingAdjustment="1",
))

apiAsgScalingIn = t.add_resource(autoscaling.ScalingPolicy(
    "apiAsgScalingIn",
    AdjustmentType="ChangeInCapacity",
    AutoScalingGroupName=Ref(apiASG),
    Cooldown="360",
    ScalingAdjustment="-1",
))

apiHighMemoryUsageAlarm = t.add_resource(Alarm(
    "apiHighMemoryUsageAlarm",
    AlarmDescription="Alarm if less than 512 MB of available memory",
    Namespace="System/Linux",
    Dimensions=[
            MetricDimension(
                Name="AutoScalingGroupName",
                Value=Ref(apiASG)
            ),
        ],
    MetricName="MemoryAvailable",
    Statistic="Average",
    Period="1800",
    EvaluationPeriods="1",
    Threshold="512",
    ComparisonOperator="LessThanThreshold",
    AlarmActions=[Ref(apiAsgScalingOut)]
))

apiLowMemoryUsageAlarm = t.add_resource(Alarm(
    "apiLowMemoryUsageAlarm",
    AlarmDescription="Alarm if more than 2048 MB of available memory",
    Namespace="System/Linux",
    Dimensions=[
            MetricDimension(
                Name="AutoScalingGroupName",
                Value=Ref(apiASG)
            ),
        ],
    MetricName="MemoryAvailable",
    Statistic="Average",
    Period="1800",
    EvaluationPeriods="1",
    Threshold="2048",
    ComparisonOperator="GreaterThanThreshold",
    AlarmActions=[Ref(apiAsgScalingIn)]
))

privateDbSubnetGroup = t.add_resource(DBSubnetGroup(
    "privateDbSubnetGroup",
    DBSubnetGroupDescription="Subnets available for the RDS DB Instances",
    SubnetIds=[Ref(privateDbSubnet01), Ref(privateDbSubnet02)]
))

if spec["rds"]:

    rds_num_nodes = spec["rds"]["num_nodes"]
    rds_name = spec["rds"]["canonical_name"]
    rds_master_key = spec["rds"]["master_key"]
    rds_master_password = spec["rds"]["master_password"]
    rds_instance_type = spec["rds"]["ec2_instance_type"]
    rds_allocation_size = spec["rds"]["allocation_size"]
    rds_parameter_group = spec["rds"]["parameter_group"]

    for rds_node in xrange(1, int(rds_num_nodes)+1):
        rds_node = t.add_resource(DBInstance(
            "rds"+str(rds_node).zfill(2),
            DBName="PlanPlus",
            DBInstanceIdentifier=Join("",[resource_tag,"-",rds_name,"-",str(rds_node).zfill(2)]),
            AllocatedStorage=rds_allocation_size[rds_node-1],
            DBInstanceClass=rds_instance_type,
            StorageType="gp2",
            Engine="MySQL",
            EngineVersion="5.7.19",
            AutoMinorVersionUpgrade="false",
            KmsKeyId=rds_master_key,
            MasterUsername=Join("",["rdsgroup",str(rds_node),"master"]),
            MasterUserPassword=rds_master_password,
            StorageEncrypted="true",
            DBParameterGroupName=rds_parameter_group,
            DBSubnetGroupName=Ref(privateDbSubnetGroup),
            VPCSecurityGroups=[Ref(rdsSecurityGroup)],
            PubliclyAccessible="false",
            MultiAZ="true",
            BackupRetentionPeriod="35",
            Tags=Tags(
                Name=Join("",[resource_tag,"-",rds_name,"-",str(rds_node).zfill(2)]),
                Environment=environment_name,
                Project=project_name,
                Ticket=ticket
                )   

        ))

print(t.to_json())