import boto3
from datetime import datetime
from datetime import timedelta


def start_instance(region, iid, wait_until_running=True):
    ec2 = boto3.resource('ec2', region_name=region)
                
    # Start the EC2 instance
    instance = ec2.Instance(iid)
    instance.start()
    
    if wait_until_running:
        instance.wait_until_running()   
    
def get_public_ip(region, iid):
    ec2 = boto3.resource('ec2', region_name=region)
    instance = ec2.Instance(iid)
    
    # Return the public IP address
    return instance.public_ip_address

def stop_instance(region, iid, wait_until_stopped=True):
    ec2 = boto3.resource('ec2', region_name=region)
    
    # Get the EC2 instance
    instance = ec2.Instance(iid)
    instance.stop()
    
    # Wait for the instance to be in the 'stopped' state
    if wait_until_stopped:
        instance.wait_until_stopped()

def get_instance_status(region, iid):
    ec2 = boto3.resource('ec2', region_name=region)
    
    # Get the EC2 instance
    instance = ec2.Instance(iid)
    # Get the status
    status = instance.state['Name']
    
    # Return the instance status
    return status
    
def get_instance_usage(region, iid):
    cloudwatch = boto3.client("cloudwatch", region_name=region)
    
    # Get the CPU utilization for the past 5 minutes
    cpu_utilization = cloudwatch.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": iid}],
        StartTime= datetime.utcnow() - timedelta(seconds = 600),
        EndTime= datetime.utcnow(),
        Period=300,
        Statistics=["Maximum", "Average"],
        Unit="Percent"
    )

    return {
        "avg": cpu_utilization["Datapoints"][0]["Average"] if len(cpu_utilization["Datapoints"]) > 0 else None,
        "max": cpu_utilization["Datapoints"][0]["Maximum"] if len(cpu_utilization["Datapoints"]) > 0 else None,
    }